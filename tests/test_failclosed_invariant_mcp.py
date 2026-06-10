"""Fail-closed *invariant* tests for the MCP surface.

Mirrors tests/test_failclosed_invariant.py (the CLI surface) for the MCP tools:
a "network tripwire" makes constructing any PACER client/downloader raise, then
every billable MCP tool is driven under every refusal condition and asserted to
never reach the network. A positive control proves the tripwire isn't vacuously
green.
"""

from __future__ import annotations

import pytest

import pacer_cli.config as cfg_mod
from pacer_cli import mcp_server as mcp


class NetworkReached(Exception):
    """Raised if a billable client/downloader is constructed - the tripwire."""


@pytest.fixture
def tripwire(monkeypatch):
    import pacer_cli.downloader as dl_mod
    import pacer_cli.pcl as pcl_mod

    def trip(*_a, **_k):
        raise NetworkReached("a billable network client was constructed")

    monkeypatch.setattr(pcl_mod, "PCLClient", trip)
    monkeypatch.setattr(dl_mod, "DocketDownloader", trip)
    monkeypatch.setattr(dl_mod, "DocumentDownloader", trip)


def _policy(text: str) -> None:
    cfg_mod.POLICY_CSV.parent.mkdir(parents=True, exist_ok=True)
    cfg_mod.POLICY_CSV.write_text("Setting,Value\n" + text + "\n", encoding="utf-8")


def _disable_all_courts() -> None:
    from pacer_cli.courts import all_search_court_ids, write_courts_scope

    write_courts_scope({cid: False for cid in all_search_court_ids()})


# (policy.csv body, disable_all_courts?) -> a refusal condition.
REFUSALS = {
    "over_daily_cap": ("Max spend per day ($),0.01", False),
    "garbage_policy": ("Max spend per search ($),fifty", False),
    "matter_required": ("Require client/matter code,Yes", False),
    "empty_scope": ("", True),
}

# Billable MCP tools and the kwargs to invoke them; "scopeable" honor courts.csv.
MCP_BILLABLE = {
    "search_cases": (mcp.search_cases, {"case_number": "1:20-cv-1"}, True),
    "search_parties": (mcp.search_parties, {"last_name": "Smith"}, True),
    "get_docket": (mcp.get_docket, {"case_number": "1:20-cv-1", "court_id": "nysd"}, False),
    "get_document": (mcp.get_document, {"doc_link": "https://ecf.x/doc1/1"}, False),
}


@pytest.mark.parametrize("tool_name", list(MCP_BILLABLE))
@pytest.mark.parametrize("refusal", list(REFUSALS))
def test_mcp_refusal_never_reaches_network(tripwire, tool_name, refusal):
    fn, kwargs, scopeable = MCP_BILLABLE[tool_name]
    if refusal == "empty_scope" and not scopeable:
        pytest.skip("download tool has no court scope")
    body, disable_courts = REFUSALS[refusal]
    _policy(body)
    if disable_courts:
        _disable_all_courts()

    with pytest.raises(Exception) as exc_info:
        fn(**kwargs)

    assert not isinstance(exc_info.value, NetworkReached), (
        f"{tool_name}/{refusal} reached the network despite a refusal"
    )
    payload = mcp.error_payload(tool_name, exc_info.value)
    assert payload["error"] in {
        "BUDGET_EXCEEDED", "POLICY_INVALID", "MATTER_REQUIRED", "SCOPE_EMPTY",
        "MATTER_INVALID", "INVALID_ARGUMENT",
    }


def test_positive_control_mcp_reaches_network_when_allowed(tripwire):
    _policy("Max spend per day ($),100.00")
    with pytest.raises(NetworkReached):
        mcp.search_cases(case_number="1:20-cv-1")


def test_matter_supplied_clears_gate_then_reaches_network(tripwire):
    # Supplying a valid --matter clears the matter gate (not a no-op); without
    # one it still refuses.
    from pacer_cli.security import GovernanceError

    _policy("Require client/matter code,Yes")
    with pytest.raises(NetworkReached):
        mcp.search_cases(case_number="1:20-cv-1", client_code="M-1")
    with pytest.raises(GovernanceError):
        mcp.search_cases(case_number="1:20-cv-1")
