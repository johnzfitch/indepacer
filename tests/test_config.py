"""Tests for configuration management."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from pacer_cli.config import (
    ContextConfig,
    PacerConfig,
    save_credentials,
    clear_credentials,
)


class TestPacerConfig:
    def test_defaults(self):
        cfg = PacerConfig(_env_file=None)
        assert cfg.username is None
        assert cfg.rate_limit is True
        assert cfg.rate_limit_rpm == 30
        assert cfg.tls_level == "standard"

    def test_has_mfa_false_by_default(self):
        cfg = PacerConfig(_env_file=None)
        assert cfg.has_mfa is False

    def test_has_mfa_true_with_secret(self):
        cfg = PacerConfig(totp_secret="SECRET")
        assert cfg.has_mfa is True

    def test_auth_url_production(self):
        cfg = PacerConfig(use_qa=False)
        assert "pacer.login.uscourts.gov" in cfg.auth_url

    def test_auth_url_qa(self):
        cfg = PacerConfig(use_qa=True)
        assert "qa-login" in cfg.auth_url

    def test_pcl_url_production(self):
        cfg = PacerConfig(use_qa=False)
        assert "pcl.uscourts.gov" in cfg.pcl_url

    def test_pcl_url_qa(self):
        cfg = PacerConfig(use_qa=True)
        assert "qa-pcl" in cfg.pcl_url

    def test_case_dir_normalization(self, tmp_path):
        cfg = PacerConfig(archive_root=tmp_path)
        d = cfg.get_case_dir("nysdce", "1:18-cv-08434")
        assert "nysd" in str(d)
        assert "1-18-cv-08434" in str(d)

    def test_rate_limit_rpm_zero_rejected(self):
        with pytest.raises(ValidationError, match="rate_limit_rpm"):
            PacerConfig(rate_limit_rpm=0)

    def test_rate_limit_rpm_negative_rejected(self):
        with pytest.raises(ValidationError, match="rate_limit_rpm"):
            PacerConfig(rate_limit_rpm=-5)

    def test_tls_level_invalid_rejected(self):
        with pytest.raises(ValidationError):
            PacerConfig(tls_level="ultra")  # type: ignore[arg-type]

    def test_tls_level_valid_values(self):
        for level in ("standard", "strict", "paranoid"):
            cfg = PacerConfig(tls_level=level)
            assert cfg.tls_level == level


class TestContextConfig:
    def test_load_empty(self, tmp_path):
        ctx = ContextConfig.load()
        assert ctx.is_set is False

    def test_save_and_load_roundtrip(self, tmp_path, monkeypatch):
        from pacer_cli.config import CONTEXT_FILE

        ctx = ContextConfig(court="nysd", case_number="1:18-cv-08434")
        path = ctx.save()
        assert path.exists()

        data = json.loads(path.read_text())
        assert data["court"] == "nysd"
        assert "Z" in data["updated_at"]

    def test_clear(self, tmp_path):
        ctx = ContextConfig(court="nysd", case_number="test")
        ctx.save()
        ctx.clear()
        assert ctx.is_set is False


class TestCredentials:
    def test_save_and_clear(self, tmp_path, monkeypatch):
        from pacer_cli.config import CONFIG_DIR, CONFIG_FILE

        # Patch CONFIG_DIR/CONFIG_FILE so they point to tmp
        config_dir = tmp_path / ".config" / "pacer-cli"
        config_file = config_dir / "config.env"
        monkeypatch.setattr("pacer_cli.config.CONFIG_DIR", config_dir)
        monkeypatch.setattr("pacer_cli.config.CONFIG_FILE", config_file)

        path = save_credentials("user", "pass", totp_secret="SECRET")
        assert path.exists()
        content = path.read_text()
        assert "PACER_USERNAME=user" in content
        assert "PACER_PASSWORD=pass" in content
        assert "PACER_TOTP_SECRET=SECRET" in content

        assert clear_credentials() is True
        assert not config_file.exists()

    def test_clear_when_no_file(self, tmp_path, monkeypatch):
        config_file = tmp_path / "nonexistent"
        monkeypatch.setattr("pacer_cli.config.CONFIG_FILE", config_file)
        assert clear_credentials() is False
