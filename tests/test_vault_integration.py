"""Test vault and OTP integration."""

import tempfile
from pathlib import Path
from unittest import TestCase, main


class TestOTP(TestCase):
    """Test TOTP implementation."""

    def test_hotp_generates_6_digits(self):
        from indepacer.otp import hotp
        code = hotp("JBSWY3DPEHPK3PXP", counter=1)
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())

    def test_totp_generates_6_digits(self):
        from indepacer.otp import totp
        code = totp("JBSWY3DPEHPK3PXP")
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())

    def test_empty_secret_raises(self):
        from indepacer.otp import hotp
        with self.assertRaises(ValueError):
            hotp("", counter=1)

    def test_generate_totp_alias(self):
        from indepacer.otp import generate_totp
        code = generate_totp("JBSWY3DPEHPK3PXP")
        self.assertEqual(len(code), 6)


class TestVault(TestCase):
    """Test encrypted vault."""

    def test_vault_init_and_unlock(self):
        from indepacer.vault import PacerVault

        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir) / "test_vault.json"
            vault = PacerVault(path=vault_path)

            # Init
            vault.init("test-passphrase")
            self.assertTrue(vault.exists)

            # Set secrets
            vault.set("PACER_PASSWORD", "my-secret")
            vault.save()

            # Unlock in new instance
            vault2 = PacerVault(path=vault_path)
            vault2.unlock("test-passphrase")
            self.assertEqual(vault2.get("PACER_PASSWORD"), "my-secret")

    def test_wrong_passphrase_fails(self):
        from indepacer.vault import PacerVault, VaultError

        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir) / "test_vault.json"
            vault = PacerVault(path=vault_path)
            vault.init("correct-passphrase")
            vault.set("SECRET", "value")
            vault.save()

            vault2 = PacerVault(path=vault_path)
            with self.assertRaises(VaultError):
                vault2.unlock("wrong-passphrase")


class TestConfigQATOTP(TestCase):
    """Test QA TOTP secret handling."""

    def test_active_totp_secret_production(self):
        from indepacer.config import PacerConfig
        from pydantic import SecretStr

        config = PacerConfig(
            totp_secret=SecretStr("PROD_SECRET"),
            qa_totp_secret=SecretStr("QA_SECRET"),
            use_qa=False,
            _env_file=None,  # Don't load from env file
        )
        self.assertEqual(config.active_totp_secret.get_secret_value(), "PROD_SECRET")

    def test_active_totp_secret_qa(self):
        from indepacer.config import PacerConfig
        from pydantic import SecretStr

        config = PacerConfig(
            totp_secret=SecretStr("PROD_SECRET"),
            qa_totp_secret=SecretStr("QA_SECRET"),
            use_qa=True,
            _env_file=None,
        )
        self.assertEqual(config.active_totp_secret.get_secret_value(), "QA_SECRET")

    def test_has_mfa_true_when_active_secret_set(self):
        from indepacer.config import PacerConfig
        from pydantic import SecretStr

        # QA mode with only QA secret
        config = PacerConfig(
            qa_totp_secret=SecretStr("QA_SECRET"),
            use_qa=True,
            _env_file=None,
        )
        self.assertTrue(config.has_mfa)

    def test_has_mfa_false_when_no_active_secret(self):
        from indepacer.config import PacerConfig
        from pydantic import SecretStr

        # Production mode with only QA secret (no prod secret)
        config = PacerConfig(
            qa_totp_secret=SecretStr("QA_SECRET"),
            totp_secret=None,
            use_qa=False,
            _env_file=None,
        )
        self.assertFalse(config.has_mfa)


if __name__ == "__main__":
    main()
