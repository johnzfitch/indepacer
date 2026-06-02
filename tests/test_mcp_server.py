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

    def test_policy_invalid_maps_to_failclosed(self):
        p = mcp.error_payload("search cases", ValueError("policy.csv row 2: 'x'"))
        assert p["error"] == "POLICY_INVALID"
        assert "row 2" in p["reason"]

    def test_garbage_policy_surfaces_as_policy_invalid(self):
        # End-to-end: a fat-fingered policy.csv refuses the billable tool.
        _write_policy("Setting,Value\nMax spend per search ($),fifty\n")
        with pytest.raises(ValueError) as e:
            mcp.search_cases(case_number="1:20-cv-1")
        assert mcp.error_payload("search cases", e.value)["error"] == "POLICY_INVALID"
