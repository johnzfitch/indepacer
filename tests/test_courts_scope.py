"""Tests for courts.csv search scoping (human-edited, agent-read-only)."""

from __future__ import annotations

from click.testing import CliRunner

from pacer_cli import courts
from pacer_cli.cli import cli


def test_universe_is_ecf_domains():
    ids = courts.all_search_court_ids()
    assert "cand" in ids and "nysd" in ids
    assert all(i == i.lower() for i in ids)


def test_no_csv_means_nationwide():
    assert courts.enabled_court_ids() is None


def test_disable_all_then_enable_subset():
    runner = CliRunner()
    assert runner.invoke(cli, ["courts", "disable-all"]).exit_code == 0
    assert runner.invoke(cli, ["courts", "enable", "cand", "nysd"]).exit_code == 0
    assert courts.enabled_court_ids() == ["cand", "nysd"]


def test_disable_subset_from_nationwide():
    runner = CliRunner()
    # No CSV yet -> 'disable' seeds from the full universe minus the listed ones.
    runner.invoke(cli, ["courts", "disable", "txnd"])
    enabled = courts.enabled_court_ids()
    assert enabled is not None
    assert "txnd" not in enabled
    assert "cand" in enabled


def test_invert_flips_flags():
    runner = CliRunner()
    runner.invoke(cli, ["courts", "disable-all"])
    runner.invoke(cli, ["courts", "enable", "cand"])
    runner.invoke(cli, ["courts", "invert"])
    enabled = courts.enabled_court_ids()
    assert "cand" not in enabled
    assert "nysd" in enabled


def test_all_enabled_is_treated_as_nationwide():
    runner = CliRunner()
    runner.invoke(cli, ["courts", "enable-all"])
    assert courts.enabled_court_ids() is None


def test_status_reports_scope():
    runner = CliRunner()
    runner.invoke(cli, ["courts", "disable-all"])
    runner.invoke(cli, ["courts", "enable", "cand"])
    out = runner.invoke(cli, ["courts", "status"]).output
    assert "cand" in out
