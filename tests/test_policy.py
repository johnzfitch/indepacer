"""Tests for the spend-governance policy CSV overlay (fail-closed)."""

from __future__ import annotations

import pytest

import pacer_cli.config as cfg_mod
from pacer_cli.config import PacerConfig, apply_policy_csv, get_config


def _write_policy(text: str) -> None:
    """Write policy.csv at the (monkeypatched) POLICY_CSV path."""
    cfg_mod.POLICY_CSV.parent.mkdir(parents=True, exist_ok=True)
    cfg_mod.POLICY_CSV.write_text(text, encoding="utf-8")


class TestDefaults:
    def test_conservative_builtin_defaults(self):
        c = PacerConfig()
        assert c.per_op_cap_usd == 1.00
        assert c.daily_cap_usd == 10.00
        assert c.require_client_code is False

    def test_missing_file_keeps_defaults(self):
        # No policy.csv written -> overlay is a no-op.
        c = apply_policy_csv(get_config())
        assert c.per_op_cap_usd == 1.00
        assert c.daily_cap_usd == 10.00

    def test_negative_cap_field_rejected(self):
        with pytest.raises(ValueError):
            PacerConfig(per_op_cap_usd=-1)


class TestOverlay:
    def test_valid_overlay_applies(self):
        _write_policy(
            "Setting,Value\n"
            "Max spend per search ($),5.00\n"
            "Max spend per day ($),50.00\n"
            "Require client/matter code,Yes\n"
        )
        c = apply_policy_csv(get_config())
        assert c.per_op_cap_usd == 5.00
        assert c.daily_cap_usd == 50.00
        assert c.require_client_code is True

    def test_dollar_sign_and_commas_stripped(self):
        _write_policy("Setting,Value\nMax spend per day ($),\"$1,250.00\"\n")
        c = apply_policy_csv(get_config())
        assert c.daily_cap_usd == 1250.00

    def test_unknown_rows_ignored(self):
        _write_policy("Setting,Value\nSomething Random,9\nMax spend per search ($),3\n")
        c = apply_policy_csv(get_config())
        assert c.per_op_cap_usd == 3.0


class TestFailClosed:
    def test_blank_dollar_cell_keeps_safe_default(self):
        # A blank cap must NOT become "unlimited".
        _write_policy("Setting,Value\nMax spend per search ($),\n")
        c = apply_policy_csv(get_config())
        assert c.per_op_cap_usd == 1.00  # built-in default, never inf

    def test_garbage_dollar_cell_raises_naming_row(self):
        _write_policy("Setting,Value\nMax spend per search ($),fifty\n")
        with pytest.raises(ValueError) as exc:
            apply_policy_csv(get_config())
        assert "row 2" in str(exc.value)
        assert "fifty" in str(exc.value)

    def test_negative_cap_in_csv_raises(self):
        _write_policy("Setting,Value\nMax spend per day ($),-5\n")
        with pytest.raises(ValueError):
            apply_policy_csv(get_config())

    def test_blank_toggle_treated_as_on(self):
        _write_policy("Setting,Value\nRequire client/matter code,\n")
        c = apply_policy_csv(get_config())
        assert c.require_client_code is True

    def test_garbage_toggle_treated_as_on(self):
        _write_policy("Setting,Value\nRequire client/matter code,maybe\n")
        c = apply_policy_csv(get_config())
        assert c.require_client_code is True

    def test_explicit_no_toggle(self):
        _write_policy("Setting,Value\nRequire client/matter code,No\n")
        c = apply_policy_csv(get_config())
        assert c.require_client_code is False
