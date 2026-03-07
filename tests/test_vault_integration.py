"""Test vault and OTP integration."""

import tempfile
from pathlib import Path

import pytest
from pydantic import SecretStr


class TestOTP:
    """Test TOTP implementation."""

    def test_hotp_generates_6_digits(self):
        from pacer_cli.otp import hotp
        code = hotp("JBSWY3DPEHPK3PXP", counter=1)
        assert len(code) == 6
        assert code.isdigit()

    def test_totp_generates_6_digits(self):
        from pacer_cli.otp import totp
        code = totp("JBSWY3DPEHPK3PXP")
        assert len(code) == 6
        assert code.isdigit()

    def test_totp_rejects_zero_time_step(self):
        from pacer_cli.otp import totp
        with pytest.raises(ValueError, match="time_step must be a positive integer"):
            totp("JBSWY3DPEHPK3PXP", time_step=0)

    def test_totp_rejects_negative_time_step(self):
        from pacer_cli.otp import totp
        with pytest.raises(ValueError, match="time_step must be a positive integer"):
            totp("JBSWY3DPEHPK3PXP", time_step=-1)

    def test_empty_secret_raises(self):
        from pacer_cli.otp import hotp
        with pytest.raises(ValueError):
            hotp("", counter=1)

    def test_generate_totp_alias(self):
        from pacer_cli.otp import generate_totp
        code = generate_totp("JBSWY3DPEHPK3PXP")
        assert len(code) == 6


class TestVault:
    """Test encrypted vault."""

    def test_vault_init_and_unlock(self):
        from pacer_cli.vault import PacerVault

        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir) / "test_vault.json"
            vault = PacerVault(path=vault_path)

            # Init
            vault.init("test-passphrase")
            assert vault.exists

            # Set secrets
            vault.set("PACER_PASSWORD", "my-secret")
            vault.save()

            # Unlock in new instance
            vault2 = PacerVault(path=vault_path)
            vault2.unlock("test-passphrase")
            assert vault2.get("PACER_PASSWORD") == "my-secret"

    def test_wrong_passphrase_fails(self):
        from pacer_cli.vault import PacerVault, VaultError

        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir) / "test_vault.json"
            vault = PacerVault(path=vault_path)
            vault.init("correct-passphrase")
            vault.set("SECRET", "value")
            vault.save()

            vault2 = PacerVault(path=vault_path)
            with pytest.raises(VaultError):
                vault2.unlock("wrong-passphrase")


class TestConfigQATOTP:
    """Test QA TOTP secret handling."""

    def test_active_totp_secret_production(self):
        from pacer_cli.config import PacerConfig

        config = PacerConfig(
            totp_secret=SecretStr("PROD_SECRET"),
            qa_totp_secret=SecretStr("QA_SECRET"),
            use_qa=False,
            _env_file=None,
        )
        assert config.active_totp_secret.get_secret_value() == "PROD_SECRET"

    def test_active_totp_secret_qa(self):
        from pacer_cli.config import PacerConfig

        config = PacerConfig(
            totp_secret=SecretStr("PROD_SECRET"),
            qa_totp_secret=SecretStr("QA_SECRET"),
            use_qa=True,
            _env_file=None,
        )
        assert config.active_totp_secret.get_secret_value() == "QA_SECRET"

    def test_active_totp_secret_qa_fallback(self):
        """QA mode falls back to totp_secret when qa_totp_secret is not set."""
        from pacer_cli.config import PacerConfig

        config = PacerConfig(
            totp_secret=SecretStr("PROD_SECRET"),
            qa_totp_secret=None,
            use_qa=True,
            _env_file=None,
        )
        assert config.active_totp_secret.get_secret_value() == "PROD_SECRET"

    def test_has_mfa_true_when_active_secret_set(self):
        from pacer_cli.config import PacerConfig

        # QA mode with only QA secret
        config = PacerConfig(
            qa_totp_secret=SecretStr("QA_SECRET"),
            use_qa=True,
            _env_file=None,
        )
        assert config.has_mfa

    def test_has_mfa_false_when_no_active_secret(self):
        from pacer_cli.config import PacerConfig

        # Production mode with only QA secret (no prod secret)
        config = PacerConfig(
            qa_totp_secret=SecretStr("QA_SECRET"),
            totp_secret=None,
            use_qa=False,
            _env_file=None,
        )
        assert not config.has_mfa


class TestVaultPassphraseValidation:
    """Test vault passphrase requirements."""

    def test_empty_passphrase_rejected(self):
        from pacer_cli.config import _save_credentials_vault
        from pacer_cli.vault import VaultError

        with tempfile.TemporaryDirectory() as tmpdir:
            import pacer_cli.config as config_module
            original_vault_file = config_module.VAULT_FILE
            config_module.VAULT_FILE = Path(tmpdir) / "vault.json"
            try:
                with pytest.raises(VaultError, match="at least 8 characters"):
                    _save_credentials_vault("user", "pass", passphrase="")
            finally:
                config_module.VAULT_FILE = original_vault_file

    def test_short_passphrase_rejected(self):
        from pacer_cli.config import _save_credentials_vault
        from pacer_cli.vault import VaultError

        with tempfile.TemporaryDirectory() as tmpdir:
            import pacer_cli.config as config_module
            original_vault_file = config_module.VAULT_FILE
            config_module.VAULT_FILE = Path(tmpdir) / "vault.json"
            try:
                with pytest.raises(VaultError, match="at least 8 characters"):
                    _save_credentials_vault("user", "pass", passphrase="short")
            finally:
                config_module.VAULT_FILE = original_vault_file
