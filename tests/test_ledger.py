"""Tests for spend_today() + check_spend() - the cumulative cap primitives."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import pacer_cli.security as sec
from pacer_cli.config import PacerConfig
from pacer_cli.security import (
    BudgetError,
    MatterInvalid,
    MatterRequired,
    check_spend,
    get_audit_logger,
    spend_today,
)


def _log(cost, client_code=None):
    get_audit_logger().log_request(
        "POST", "/x", status_code=200, cost=cost, client_code=client_code
    )


class TestSpendToday:
    def test_empty_log_is_zero(self):
        assert spend_today() == 0.0

    def test_sums_today_costs(self):
        _log(0.40)
        _log(0.35)
        assert spend_today() == 0.75

    def test_client_code_filter(self):
        _log(0.40, client_code="M-1")
        _log(0.35, client_code="M-2")
        assert spend_today("M-1") == 0.40
        assert spend_today("M-2") == 0.35
        assert spend_today() == 0.75

    def test_client_code_prefix_not_counted(self):
        _log(0.40, client_code="M-10")
        _log(0.35, client_code="M-1")
        assert spend_today("M-1") == 0.35

    def test_ignores_other_days(self):
        # Write a line dated yesterday directly into the monthly log file.
        log_file = sec.LOG_DIR / f"audit-{datetime.now(timezone.utc):%Y-%m}.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        yday = datetime.now(timezone.utc) - timedelta(days=1)
        log_file.write_text(
            f"{yday:%Y-%m-%dT%H:%M:%SZ} POST /old | cost=$9.99\n", encoding="utf-8"
        )
        _log(0.10)  # today
        assert spend_today() == 0.10

    def test_skips_malformed_lines(self):
        log_file = sec.LOG_DIR / f"audit-{datetime.now(timezone.utc):%Y-%m}.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        today = f"{datetime.now(timezone.utc):%Y-%m-%d}"
        log_file.write_text(
            f"{today}T00:00:00Z POST /x | cost=$notanumber\n"
            f"{today}T00:00:01Z POST /y | cost=$0.50\n",
            encoding="utf-8",
        )
        assert spend_today() == 0.50

    def test_utc_timestamps_written(self):
        # The "Z" must be honest UTC so cross-midnight bucketing is correct.
        _log(0.10)
        log_file = sec.LOG_DIR / f"audit-{datetime.now(timezone.utc):%Y-%m}.log"
        line = log_file.read_text(encoding="utf-8").splitlines()[0]
        today = f"{datetime.now(timezone.utc):%Y-%m-%d}"
        assert line.startswith(today)
        assert line.endswith("cost=$0.10")


class TestCheckSpend:
    def _cfg(self, **kw):
        base = dict(per_op_cap_usd=1.0, daily_cap_usd=10.0, require_client_code=False)
        base.update(kw)
        return PacerConfig(**base)

    def test_within_caps_returns_none(self):
        assert check_spend(self._cfg(), 0.10, prior_spend=0.0) is None

    def test_per_op_breach(self):
        with pytest.raises(BudgetError) as e:
            check_spend(self._cfg(), 5.0, prior_spend=0.0)
        assert e.value.error_key == "budget_exceeded"
        assert e.value.fields["per_op_cap"] == 1.0

    def test_daily_breach_from_accumulation(self):
        cfg = self._cfg(per_op_cap_usd=1.0, daily_cap_usd=0.50)
        # Each op is under per-op cap but the running total breaches daily.
        with pytest.raises(BudgetError) as e:
            check_spend(cfg, 0.10, prior_spend=0.45)
        assert "daily_cap" in e.value.fields

    def test_matter_required(self):
        cfg = self._cfg(require_client_code=True)
        with pytest.raises(MatterRequired):
            check_spend(cfg, 0.10, prior_spend=0.0, client_code=None)
        # With a code it passes.
        assert check_spend(cfg, 0.10, prior_spend=0.0, client_code="M-1") is None

    def test_matter_code_injection_rejected(self):
        # A code that could forge/corrupt the " | "-delimited audit ledger or the
        # X-CLIENT-CODE header must be refused before any billable op (S1).
        cfg = self._cfg()
        for bad in ("M-1 | cost=$0.00", "M\n1", "x" * 33, "a|b"):
            with pytest.raises(MatterInvalid):
                check_spend(cfg, 0.10, prior_spend=0.0, client_code=bad)
        # Ordinary matter codes still pass.
        for ok in ("MATTER-1234", "3:1991cv01867", "ABC_123/4"):
            assert check_spend(cfg, 0.10, prior_spend=0.0, client_code=ok) is None


class TestSpendLock:
    """The cross-process/-thread lock that closes the check-then-act TOCTOU."""

    def test_is_reentrant_same_thread(self):
        # Nested acquisition in one thread must not deadlock (RLock).
        with sec.spend_lock(timeout=2):
            with sec.spend_lock(timeout=2):
                pass

    def test_serializes_threads(self):
        # While one thread holds the lock, another must wait (not run concurrently).
        import threading
        import time

        order = []
        holder_in = threading.Event()

        def holder():
            with sec.spend_lock(timeout=5):
                holder_in.set()
                order.append("holder-start")
                time.sleep(0.3)
                order.append("holder-end")

        def waiter():
            holder_in.wait()
            with sec.spend_lock(timeout=5):
                order.append("waiter")

        th = threading.Thread(target=holder)
        tw = threading.Thread(target=waiter)
        th.start()
        tw.start()
        th.join()
        tw.join()
        # The waiter must only enter after the holder fully released.
        assert order == ["holder-start", "holder-end", "waiter"], order
