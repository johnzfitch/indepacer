"""Fail-closed *invariant* tests.

Single-purpose tests only check the cases we thought to enumerate. This module
instead asserts the safety property that the whole governance layer exists to
guarantee:

    No billable PACER request is ever issued when policy or scope says no.

It does that with a "network tripwire" — constructing any PACER client or
downloader raises — then drives EVERY billable surface (CLI commands + MCP
tools) under EVERY refusal condition and asserts the tripwire never fires. This
is what would have caught the empty-courts.csv fail-open: the request slipping
through despite a restrictive scope file trips the wire regardless of which
code path leaked.

A positive control proves the tripwire isn't vacuously green: under a permissive
policy the billable path DOES reach the client (the wire fires).
"""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

import pacer_cli.config as cfg_mod
from pacer_cli import mcp_server as mcp
from pacer_cli.cli import cli
from pacer_cli.security import GovernanceError


class NetworkReached(Exception):
    """Raised if a billable client/downloader is constructed — the tripwire."""


@pytest.fixture
def tripwire(monkeypatch):
    """Make every billable network entry point explode if reached."""
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


# (label, policy.csv body, disable_all_courts?) -> a refusal condition.
REFUSALS = {
    "over_daily_cap": ("Max spend per day ($),0.01", False),
    "garbage_policy": ("Max spend per search ($),fifty", False),
    "matter_required": ("Require client/matter code,Yes", False),
    "empty_scope": ("", True),  # courts.csv with every court disabled
}

# Billable CLI invocations. "scopeable" ones honor courts.csv (searches).
CLI_BILLABLE = {
    "pcl_cases": (["pcl", "cases", "-n", "1:20-cv-1"], True),
    "pcl_parties": (["pcl", "parties", "-l", "Smith"], True),
    "download_docket": (["download", "docket", "1:20-cv-1", "nysd"], False),
}


def _setup(refusal: str) -> None:
    body, disable_courts = REFUSALS[refusal]
    _policy(body)
    if disable_courts:
        CliRunner().invoke(cli, ["courts", "disable-all"])


@pytest.mark.parametrize("cmd_name", list(CLI_BILLABLE))
@pytest.mark.parametrize("refusal", list(REFUSALS))
def test_cli_refusal_never_reaches_network(tripwire, cmd_name, refusal):
    args, scopeable = CLI_BILLABLE[cmd_name]
    # empty_scope only applies to commands that consult courts.csv.
    if refusal == "empty_scope" and not scopeable:
        pytest.skip("download has no court scope")
    _setup(refusal)

    result = CliRunner().invoke(cli, ["--agent", *args])

    # The invariant: refused with exit 3, and the tripwire never fired.
    assert not isinstance(result.exception, NetworkReached), (
        f"{cmd_name}/{refusal} reached the network despite a refusal"
    )
    assert result.exit_code == 3, f"{cmd_name}/{refusal} did not refuse (exit {result.exit_code})"
    # And it emitted a structured governance error, not a stack trace.
    payload = json.loads(result.output.strip().splitlines()[-1])
    assert payload["error"] in {
        "BUDGET_EXCEEDED", "POLICY_INVALID", "MATTER_REQUIRED", "SCOPE_EMPTY",
    }


# Billable MCP tools and the kwargs to invoke them.
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
    _setup(refusal)

    with pytest.raises(Exception) as exc_info:
        fn(**kwargs)

    # Must refuse (governance/policy/value error), never reach the network.
    assert not isinstance(exc_info.value, NetworkReached), (
        f"{tool_name}/{refusal} reached the network despite a refusal"
    )
    # error_payload turns it into a structured refusal, not INTERNAL.
    payload = mcp.error_payload(tool_name, exc_info.value)
    assert payload["error"] in {
        "BUDGET_EXCEEDED", "POLICY_INVALID", "MATTER_REQUIRED", "SCOPE_EMPTY", "INVALID_ARGUMENT",
    }


# --- Positive controls: prove the tripwire is not vacuously green ------------


def test_positive_control_cli_reaches_network_when_allowed(tripwire):
    # Permissive policy, no scope file, valid criteria -> the gate must pass and
    # the billable path must actually try to construct the client.
    _policy("Max spend per day ($),100.00")
    result = CliRunner().invoke(cli, ["--agent", "pcl", "cases", "-n", "1:20-cv-1"])
    assert isinstance(result.exception, NetworkReached)


def test_positive_control_mcp_reaches_network_when_allowed(tripwire):
    _policy("Max spend per day ($),100.00")
    with pytest.raises(NetworkReached):
        mcp.search_cases(case_number="1:20-cv-1")


def test_matter_required_is_satisfied_by_code_then_reaches_network(tripwire):
    # Specifically guards that supplying --matter clears the matter gate (and
    # only then proceeds), rather than the gate being a no-op.
    _policy("Require client/matter code,Yes")
    with pytest.raises(NetworkReached):
        mcp.search_cases(case_number="1:20-cv-1", client_code="M-1")
    with pytest.raises(GovernanceError):  # without a code it still refuses
        mcp.search_cases(case_number="1:20-cv-1")
