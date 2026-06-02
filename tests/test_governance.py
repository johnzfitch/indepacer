"""Tests for the cli.py spend gate: agent JSON refusals, exit 3, cap accumulation."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

import pacer_cli.cli as cli_mod
import pacer_cli.config as cfg_mod
from pacer_cli.cli import cli, enforce_spend
from pacer_cli.config import PacerConfig
from pacer_cli.security import get_audit_logger


def _write_policy(text: str) -> None:
    cfg_mod.POLICY_CSV.parent.mkdir(parents=True, exist_ok=True)
    cfg_mod.POLICY_CSV.write_text(text, encoding="utf-8")


def _fake_ctx(config=None, agent=False, auto_confirm=False):
    return SimpleNamespace(
        obj={"config": config or PacerConfig(), "agent": agent, "auto_confirm": auto_confirm}
    )


# ---------------------------------------------------------------------------
# enforce_spend unit behaviour
# ---------------------------------------------------------------------------


class TestEnforceSpend:
    def test_agent_within_caps_proceeds_silently(self):
        assert enforce_spend(_fake_ctx(agent=True), "op", 0.10) is True

    def test_auto_confirm_within_caps_proceeds(self):
        assert enforce_spend(_fake_ctx(auto_confirm=True), "op", 0.10) is True

    def test_human_within_caps_prompts(self, monkeypatch):
        # Interactive (non-agent, non -y) still routes through confirm_cost.
        calls = {}

        def fake_confirm(ctx, operation, cost, details=None):
            calls["hit"] = True
            return False  # human declines

        monkeypatch.setattr(cli_mod, "confirm_cost", fake_confirm)
        result = enforce_spend(_fake_ctx(), "op", 0.10)
        assert calls.get("hit") is True
        assert result is False

    def test_per_op_breach_exits_3(self):
        ctx = _fake_ctx(config=PacerConfig(per_op_cap_usd=1.0), agent=True)
        with pytest.raises(SystemExit) as e:
            enforce_spend(ctx, "op", 5.0)
        assert e.value.code == 3


# ---------------------------------------------------------------------------
# Full CLI agent-mode refusals (exit 3 + JSON on stderr)
# ---------------------------------------------------------------------------


class TestAgentRefusals:
    runner = CliRunner()

    def _invoke(self, *args):
        # CliRunner has no TTY -> agent mode auto-detects; pass --agent explicitly too.
        return self.runner.invoke(cli, ["--agent", *args])

    def test_budget_exceeded_json(self):
        _write_policy("Setting,Value\nMax spend per day ($),0.05\n")
        r = self._invoke("pcl", "cases", "-n", "1:20-cv-1")
        assert r.exit_code == 3
        payload = json.loads(r.output.strip().splitlines()[-1])
        assert payload["error"] == "BUDGET_EXCEEDED"
        assert payload["daily_cap"] == 0.05

    def test_matter_required_json(self):
        _write_policy("Setting,Value\nRequire client/matter code,Yes\n")
        r = self._invoke("pcl", "cases", "-n", "1:20-cv-1")
        assert r.exit_code == 3
        payload = json.loads(r.output.strip().splitlines()[-1])
        assert payload["error"] == "MATTER_REQUIRED"

    def test_matter_supplied_passes_gate(self):
        # With --matter, the matter requirement is satisfied; failure (if any)
        # must NOT be MATTER_REQUIRED. (Network call may fail later — fine.)
        _write_policy("Setting,Value\nRequire client/matter code,Yes\n")
        r = self._invoke("--matter", "M-1", "pcl", "cases", "-n", "1:20-cv-1")
        if r.exit_code == 3:
            payload = json.loads(r.output.strip().splitlines()[-1])
            assert payload["error"] != "MATTER_REQUIRED"

    def test_policy_invalid_blocks_billable(self):
        _write_policy("Setting,Value\nMax spend per search ($),fifty\n")
        r = self._invoke("pcl", "cases", "-n", "1:20-cv-1")
        assert r.exit_code == 3
        payload = json.loads(r.output.strip().splitlines()[-1])
        assert payload["error"] == "POLICY_INVALID"
        assert "row 2" in payload["reason"]

    def test_cumulative_breach(self):
        # Several sub-cap ops logged, then the next one tips over the daily cap.
        _write_policy("Setting,Value\nMax spend per search ($),1.00\nMax spend per day ($),0.25\n")
        logger = get_audit_logger()
        logger.log_request("POST", "/a", status_code=200, cost=0.10)
        logger.log_request("POST", "/b", status_code=200, cost=0.10)
        r = self._invoke("pcl", "cases", "-n", "1:20-cv-1")
        assert r.exit_code == 3
        payload = json.loads(r.output.strip().splitlines()[-1])
        assert payload["error"] == "BUDGET_EXCEEDED"
        assert payload["spent_today"] == 0.20


class TestReadOnlyStillRuns:
    def test_courts_runs_under_garbage_policy(self):
        _write_policy("Setting,Value\nMax spend per search ($),fifty\n")
        r = CliRunner().invoke(cli, ["courts"])
        assert r.exit_code == 0
        assert "Court" in r.output
