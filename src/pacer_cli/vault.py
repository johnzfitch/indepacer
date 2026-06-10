"""Minimal encrypted credential vault for PACER.

Stores credentials encrypted with AES-256-GCM, key derived via Scrypt.
Depends on the `cryptography` package.

Usage:
    vault = PacerVault()
    vault.unlock("passphrase")
    vault.set("PACER_PASSWORD", "secret")
    password = vault.get("PACER_PASSWORD")
    vault.save()
"""

import json
import os
import secrets
from base64 import b64decode, b64encode
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

VAULT_PATH = Path.home() / ".pacer" / "vault.json"


def _get_int_env(name: str, default: int) -> int:
    """Return a positive int from environment or the given default on error."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    if value <= 0:
        return default
    return value


# Default Scrypt parameters: moderate memory usage but still memory-hard.
# Users can override via environment variables, e.g.:
#   PACER_VAULT_SCRYPT_N, PACER_VAULT_SCRYPT_R, PACER_VAULT_SCRYPT_P
DEFAULT_SCRYPT_N = 2**14  # ~16MB memory, suitable for most systems
DEFAULT_SCRYPT_R = 8
DEFAULT_SCRYPT_P = 1

SCRYPT_N = _get_int_env("PACER_VAULT_SCRYPT_N", DEFAULT_SCRYPT_N)
SCRYPT_R = _get_int_env("PACER_VAULT_SCRYPT_R", DEFAULT_SCRYPT_R)
SCRYPT_P = _get_int_env("PACER_VAULT_SCRYPT_P", DEFAULT_SCRYPT_P)
SALT_SIZE = 32
NONCE_SIZE = 12
KEY_SIZE = 32


class VaultError(Exception):
    """Vault operation failed."""
    pass


class VaultLocked(VaultError):  # noqa: N818
    """Vault is locked, call unlock() first."""
    pass


class PacerVault:
    """Encrypted credential storage for PACER.

    Credentials are encrypted with AES-256-GCM using a key derived
    from a passphrase via Scrypt (memory-hard KDF).
    """

    def __init__(self, path: Path = VAULT_PATH):
        self.path = path
        self._key: bytes | None = None
        self._data: dict = {}
        self._salt: bytes | None = None

    @property
    def is_locked(self) -> bool:
        return self._key is None

    @property
    def exists(self) -> bool:
        return self.path.exists()

    def _derive_key(self, passphrase: str, salt: bytes) -> bytes:
        """Derive 256-bit key from passphrase using Scrypt."""
        kdf = Scrypt(salt=salt, length=KEY_SIZE, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
        return kdf.derive(passphrase.encode("utf-8"))

    def _encrypt(self, plaintext: str) -> dict:
        """Encrypt plaintext with AES-256-GCM."""
        if self._key is None:
            raise VaultLocked("Vault is locked")
        nonce = secrets.token_bytes(NONCE_SIZE)
        aesgcm = AESGCM(self._key)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        return {
            "nonce": b64encode(nonce).decode(),
            "ciphertext": b64encode(ciphertext).decode(),
        }

    def _decrypt(self, encrypted: dict) -> str:
        """Decrypt AES-256-GCM ciphertext."""
        if self._key is None:
            raise VaultLocked("Vault is locked")
        nonce = b64decode(encrypted["nonce"])
        ciphertext = b64decode(encrypted["ciphertext"])
        aesgcm = AESGCM(self._key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")

    def init(self, passphrase: str) -> None:
        """Initialize a new vault with the given passphrase."""
        if self.exists:
            raise VaultError(f"Vault already exists at {self.path}")
        self._salt = secrets.token_bytes(SALT_SIZE)
        self._key = self._derive_key(passphrase, self._salt)
        self._data = {}
        self.save()

    def unlock(self, passphrase: str) -> None:
        """Unlock existing vault with passphrase."""
        if not self.exists:
            raise VaultError(f"No vault at {self.path}, run init() first")

        with open(self.path) as f:
            vault_data = json.load(f)

        self._salt = b64decode(vault_data["salt"])
        self._key = self._derive_key(passphrase, self._salt)

        # Verify passphrase by decrypting check value
        try:
            check = vault_data.get("check")
            if check:
                self._decrypt(check)
        except Exception:
            self._key = None
            raise VaultError("Invalid passphrase")

        # Load encrypted secrets
        self._data = vault_data.get("secrets", {})

    def lock(self) -> None:
        """Lock the vault, clearing the key from memory."""
        if self._key:
            # Overwrite key bytes before clearing reference
            key_len = len(self._key)
            # Note: Python doesn't guarantee secure erasure, but we try
            self._key = b'\x00' * key_len
        self._key = None
        self._data = {}

    def get(self, name: str) -> str | None:
        """Get a decrypted secret by name."""
        if self.is_locked:
            raise VaultLocked("Vault is locked")
        encrypted = self._data.get(name)
        if encrypted is None:
            return None
        return self._decrypt(encrypted)

    def set(self, name: str, value: str) -> None:
        """Set an encrypted secret."""
        if self.is_locked:
            raise VaultLocked("Vault is locked")
        self._data[name] = self._encrypt(value)

    def delete(self, name: str) -> bool:
        """Delete a secret. Returns True if it existed."""
        if self.is_locked:
            raise VaultLocked("Vault is locked")
        if name in self._data:
            del self._data[name]
            return True
        return False

    def list_secrets(self) -> list[str]:
        """List all secret names (not values)."""
        if self.is_locked:
            raise VaultLocked("Vault is locked")
        return list(self._data.keys())

    def save(self) -> None:
        """Save vault to disk."""
        if self.is_locked:
            raise VaultLocked("Vault is locked")

        self.path.parent.mkdir(parents=True, exist_ok=True)

        # Create check value to verify passphrase on unlock
        check = self._encrypt("pacer-vault-check")

        vault_data = {
            "version": 1,
            "salt": b64encode(self._salt).decode(),
            "check": check,
            "secrets": self._data,
            "kdf": {
                "algorithm": "scrypt",
                "n": SCRYPT_N,
                "r": SCRYPT_R,
                "p": SCRYPT_P,
                "key_size": KEY_SIZE,
            },
        }

        # Write atomically (os.replace works cross-platform)
        tmp_path = self.path.with_suffix(".tmp")
        with open(tmp_path, "w") as f:
            json.dump(vault_data, f, indent=2)
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, self.path)

    def change_passphrase(self, old_passphrase: str, new_passphrase: str) -> None:
        """Change vault passphrase, re-encrypting all secrets."""
        # Unlock with old passphrase
        self.unlock(old_passphrase)

        # Decrypt all secrets
        decrypted = {name: self.get(name) for name in self.list_secrets()}

        # Generate new salt and derive new key
        self._salt = secrets.token_bytes(SALT_SIZE)
        self._key = self._derive_key(new_passphrase, self._salt)

        # Re-encrypt all secrets
        self._data = {}
        for name, value in decrypted.items():
            self.set(name, value)

        self.save()
