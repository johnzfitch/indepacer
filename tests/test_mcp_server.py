"""Tests for the MCP server's governed adapter (no `mcp` SDK / network needed)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import pacer_cli.config as cfg_mod
from pacer_cli import mcp_server as mcp
from pacer_cli.security import GovernanceError, get_audit_logger, spend_today


def _write_policy(text: str) -> None:
    cfg_mod.POLICY_CSV.parent.mkdir(parents=True, exist_ok=True)
    cfg_mod.POLICY_CSV.write_text(text, encoding="utf-8")


class _FakeResult:
    def __init__(self, fee):
        self.content = [SimpleNamespace(model_dump=lambda **k: {"case": "1:20-cv-1"})]
        self.receipt = SimpleNamespace(search_fee=str(fee)) if fee is not None else None
        self.page_info = None


def _patch_pcl(monkeypatch, fee=0.10):
    """Replace PCLClient so searches return a canned receipt without a network call."""
    import pacer_cli.pcl as pcl_mod

    fake = SimpleNamespace(
        search_cases=lambda criteria, **k: _FakeResult(fee),
        search_parties=lambda criteria, **k: _FakeResult(fee),
    )
    monkeypatch.setattr(pcl_mod, "PCLClient", lambda cfg: fake)


class TestSpendStatus:
    def test_reports_caps_and_remaining(self):
        _write_policy("Setting,Value\nMax spend per day ($),2.00\n")
        get_audit_logger().log_request("POST", "/x", status_code=200, cost=0.50)
        s = mcp.spend_status()
        assert s["daily_cap"] == 2.00
        assert s["spent_today"] == 0.50
        assert s["remaining_today"] == 1.50
        assert "policy_error" not in s

    def test_readonly_survives_bad_policy(self):
        # A fat-fingered policy.csv must NOT take down the read-only status view;
        # only billable ops fail closed. Report conservative defaults + the error.
        _write_policy("Setting,Value\nMax spend per search ($),fifty\n")
        s = mcp.spend_status()
        assert s["per_op_cap"] == 1.00  # conservative built-in default
        assert s["daily_cap"] == 10.00
        assert "fifty" in s["policy_error"]


class TestSearchGovernance:
    def test_within_cap_records_and_returns(self, monkeypatch):
        _patch_pcl(monkeypatch, fee=0.10)
        out = mcp.search_cases(case_number="1:20-cv-1")
        assert out["count"] == 1
        assert out["cost"] == 0.10
        # The actual fee was written to the ledger.
        assert spend_today() == 0.10

    def test_daily_cap_breach_raises_before_network(self, monkeypatch):
        _write_policy("Setting,Value\nMax spend per day ($),0.05\n")
        # PCLClient must never be constructed if the gate refuses first.
        import pacer_cli.pcl as pcl_mod

        monkeypatch.setattr(
            pcl_mod, "PCLClient",
            lambda cfg: (_ for _ in ()).throw(AssertionError("network must not run")),
        )
        with pytest.raises(GovernanceError) as e:
            mcp.search_cases(case_number="1:20-cv-1")
        assert e.value.error_key == "budget_exceeded"

    def test_matter_required_raises(self):
        _write_policy("Setting,Value\nRequire client/matter code,Yes\n")
        with pytest.raises(GovernanceError) as e:
            mcp.search_cases(case_number="1:20-cv-1")
        assert e.value.error_key == "matter_required"

    def test_matter_supplied_passes_gate(self, monkeypatch):
        _patch_pcl(monkeypatch, fee=0.10)
        _write_policy("Setting,Value\nRequire client/matter code,Yes\n")
        out = mcp.search_cases(case_number="1:20-cv-1", client_code="M-1")
        assert out["cost"] == 0.10


class TestErrorPayload:
    def test_governance_error_shape(self):
        exc = GovernanceError("boom", estimated=5.0)
        exc.error_key = "budget_exceeded"
        p = mcp.error_payload("search cases", exc)
        assert p == {"error": "BUDGET_EXCEEDED", "operation": "search cases", "estimated": 5.0}

    def test_policy_error_maps_to_failclosed(self):
        from pacer_cli.config import PolicyError

        p = mcp.error_payload("search cases", PolicyError("policy.csv row 2: 'x'"))
        assert p["error"] == "POLICY_INVALID"
        assert "row 2" in p["reason"]

    def test_plain_valueerror_is_invalid_argument(self):
        # A bad tool argument must NOT be mislabeled as a policy parse failure.
        p = mcp.error_payload("search cases", ValueError("at least one criterion"))
        assert p["error"] == "INVALID_ARGUMENT"

    def test_garbage_policy_surfaces_as_policy_invalid(self):
        # End-to-end: a fat-fingered policy.csv refuses the billable tool.
        _write_policy("Setting,Value\nMax spend per search ($),fifty\n")
        with pytest.raises(ValueError) as e:
            mcp.search_cases(case_number="1:20-cv-1")
        assert mcp.error_payload("search cases", e.value)["error"] == "POLICY_INVALID"


class TestConcurrency:
    """Race-condition tests for the MCP server's governance layer.

    The MCP stdio server is single-threaded per connection, but the underlying
    security primitives must also be safe when called from multiple threads
    (e.g. two concurrent MCP connections, or a test harness using threads).
    """

    def test_get_audit_logger_singleton_is_thread_safe(self):
        """get_audit_logger() must return the same instance from many threads."""
        import threading

        from pacer_cli.security import get_audit_logger, reset_audit_logger

        reset_audit_logger()
        results: list = []

        def _grab():
            results.append(id(get_audit_logger()))

        threads = [threading.Thread(target=_grab) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads must see the same singleton instance.
        assert len(set(results)) == 1, "get_audit_logger() returned multiple instances"

    def test_audit_logger_no_duplicate_handlers_under_concurrency(self):
        """Concurrent _ensure_logger() calls must not add duplicate handlers."""
        import threading

        from pacer_cli.security import AuditLogger, reset_audit_logger

        reset_audit_logger()
        logger_obj = AuditLogger()
        barrier = threading.Barrier(10)

        def _init():
            barrier.wait()  # all threads start at the same instant
            logger_obj._ensure_logger()

        threads = [threading.Thread(target=_init) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        import logging

        inner = logging.getLogger("pacer.audit")
        assert len(inner.handlers) == 1, (
            f"Expected 1 handler, got {len(inner.handlers)} — duplicate handler race"
        )

    def test_check_then_act_gap_closed_by_spend_lock(self):
        """The check-then-act gap is closed by holding spend_lock across the
        critical section; concurrent threads must not both pass the cap."""
        import threading

        from pacer_cli.security import GovernanceError

        # _guard documents that it must run inside spend_lock().
        assert "spend_lock" in mcp._guard.__doc__

        # Daily cap of $0.10 allows exactly one $0.10 search. Two threads race;
        # the lock must serialize them so the second sees the first's spend.
        _write_policy("Setting,Value\nMax spend per search ($),1.00\nMax spend per day ($),0.10\n")
        import pacer_cli.pcl as pcl_mod

        def _fake(cfg):
            return SimpleNamespace(
                search_cases=lambda criteria, **k: _FakeResult(0.10),
            )

        # Use the real spend_lock + ledger; only the network is faked.
        import pacer_cli.security as sec
        orig = pcl_mod.PCLClient
        pcl_mod.PCLClient = _fake
        try:
            outcomes: list = []

            def _run():
                try:
                    mcp.search_cases(case_number="1:20-cv-1")
                    outcomes.append("ok")
                except GovernanceError:
                    outcomes.append("refused")
                except Exception as exc:  # pragma: no cover - defensive
                    outcomes.append(f"err:{exc}")

            threads = [threading.Thread(target=_run) for _ in range(2)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        finally:
            pcl_mod.PCLClient = orig

        # Exactly one billed; the other was refused by the cap (never both).
        assert sorted(outcomes) == ["ok", "refused"], outcomes
        assert sec.spend_today() == 0.10

