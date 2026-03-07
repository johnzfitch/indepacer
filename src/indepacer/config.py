"""Configuration management for PACER credentials and settings."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

CONFIG_DIR = Path.home() / ".config" / "indepacer"
CONFIG_FILE = CONFIG_DIR / "config.env"

# New hierarchical archive structure
PACER_ROOT = Path.home() / ".pacer"
VAULT_FILE = PACER_ROOT / "vault.json"
ARCHIVE_ROOT = PACER_ROOT / "archives"
CONTEXT_FILE = PACER_ROOT / "config" / "context.json"

# PACER API endpoints
PACER_AUTH_URL = "https://pacer.login.uscourts.gov/services/cso-auth"
PACER_LOGOUT_URL = "https://pacer.login.uscourts.gov/services/cso-logout"
PACER_QA_AUTH_URL = "https://qa-login.uscourts.gov/services/cso-auth"

# PCL (PACER Case Locator) API endpoints
PCL_API_URL = "https://pcl.uscourts.gov/pcl-public-api/rest"
PCL_QA_API_URL = "https://qa-pcl.uscourts.gov/pcl-public-api/rest"


class PacerConfig(BaseSettings):
    """PACER configuration loaded from environment or config file."""

    model_config = SettingsConfigDict(
        env_prefix="PACER_",
        env_file=str(CONFIG_FILE) if CONFIG_FILE.exists() else None,
        env_file_encoding="utf-8",
    )

    username: Optional[str] = None
    password: Optional[SecretStr] = None
    totp_secret: Optional[SecretStr] = None  # Base32-encoded TOTP secret for MFA (production)
    qa_totp_secret: Optional[SecretStr] = None  # Base32-encoded TOTP secret for QA environment
    client_code: Optional[str] = None  # Optional client code for billing
    use_qa: bool = False  # Use QA environment instead of production

    # Legacy paths (deprecated, kept for backward compatibility)
    output_dir: Path = Path("./results")
    docket_archive: Path = Path("./results/local_docket_archive")
    document_archive: Path = Path("./results/local_document_archive")
    parsed_dockets: Path = Path("./results/parsed_dockets")

    # New hierarchical archive root
    archive_root: Path = ARCHIVE_ROOT

    # Security settings (from PR #1 + PR #2 fixes)
    rate_limit: bool = True
    rate_limit_rpm: int = 30
    peak_warning: bool = True
    audit_log: bool = True
    tls_level: Literal["standard", "strict", "paranoid"] = "standard"

    @field_validator("rate_limit_rpm")
    @classmethod
    def _validate_rpm(cls, v: int) -> int:
        if v < 1:
            raise ValueError("rate_limit_rpm must be >= 1 to avoid division by zero")
        return v

    @property
    def auth_url(self) -> str:
        """Get appropriate auth URL based on environment."""
        return PACER_QA_AUTH_URL if self.use_qa else PACER_AUTH_URL

    @property
    def pcl_url(self) -> str:
        """Get appropriate PCL API URL based on environment."""
        return PCL_QA_API_URL if self.use_qa else PCL_API_URL

    @property
    def has_mfa(self) -> bool:
        """Check if MFA is configured for the active environment."""
        return self.active_totp_secret is not None

    @property
    def active_totp_secret(self) -> Optional[SecretStr]:
        """Get TOTP secret for current environment (QA or production)."""
        if self.use_qa:
            return self.qa_totp_secret
        return self.totp_secret

    def get_case_dir(self, court: str, case_number: str) -> Path:
        """Get case directory path in hierarchical archive.

        Args:
            court: Court identifier (e.g., 'nysd', 'cacd')
            case_number: Case number (e.g., '1:18-cv-08434')

        Returns:
            Path to case directory: ~/.pacer/archives/{court}/{case}/
        """
        # Normalize: lowercase court, replace : with - for filesystem safety
        safe_court = court.lower().rstrip("e").rstrip("c")  # nysdce -> nysd
        safe_case = case_number.replace(":", "-").replace("/", "-")
        return self.archive_root / safe_court / safe_case

    def get_docket_path(self, court: str, case_number: str) -> Path:
        """Get docket HTML path for a case."""
        return self.get_case_dir(court, case_number) / "docket.html"

    def get_docs_manifest_path(self, court: str, case_number: str) -> Path:
        """Get docs.json manifest path for a case."""
        return self.get_case_dir(court, case_number) / "docs.json"

    def get_documents_dir(self, court: str, case_number: str) -> Path:
        """Get documents directory for a case."""
        return self.get_case_dir(court, case_number) / "documents"


class ContextConfig(BaseModel):
    """Active working context for CLI commands."""

    court: Optional[str] = None
    case_number: Optional[str] = None
    case_path: Optional[Path] = None
    updated_at: Optional[str] = None

    @classmethod
    def load(cls) -> "ContextConfig":
        """Load context from ~/.pacer/config/context.json."""
        if CONTEXT_FILE.exists():
            try:
                data = json.loads(CONTEXT_FILE.read_text(encoding="utf-8"))
                # Convert case_path string back to Path
                if data.get("case_path"):
                    data["case_path"] = Path(data["case_path"])
                return cls(**data)
            except (json.JSONDecodeError, TypeError):
                pass
        return cls()

    def save(self) -> Path:
        """Save context to ~/.pacer/config/context.json."""
        CONTEXT_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "court": self.court,
            "case_number": self.case_number,
            "case_path": str(self.case_path) if self.case_path else None,
            "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        CONTEXT_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return CONTEXT_FILE

    def clear(self) -> None:
        """Clear active context."""
        if CONTEXT_FILE.exists():
            CONTEXT_FILE.unlink()
        self.court = None
        self.case_number = None
        self.case_path = None
        self.updated_at = None

    @property
    def is_set(self) -> bool:
        """Check if context is set."""
        return self.court is not None and self.case_number is not None


def get_config() -> PacerConfig:
    """Load configuration from environment and config file."""
    return PacerConfig()


def save_credentials(
    username: str,
    password: str,
    totp_secret: Optional[str] = None,
    client_code: Optional[str] = None,
    vault_passphrase: Optional[str] = None,
) -> Path:
    """Save PACER credentials to encrypted vault (or legacy plaintext).

    Args:
        username: PACER username
        password: PACER password
        totp_secret: Base32-encoded TOTP secret from MFA setup (optional)
        client_code: Client billing code (optional)
        vault_passphrase: If provided, store in encrypted vault instead of plaintext

    Returns:
        Path to config file (vault or legacy)
    """
    if vault_passphrase:
        return _save_credentials_vault(username, password, totp_secret, client_code, vault_passphrase)
    return _save_credentials_legacy(username, password, totp_secret, client_code)


def _save_credentials_legacy(
    username: str,
    password: str,
    totp_secret: Optional[str] = None,
    client_code: Optional[str] = None,
) -> Path:
    """Save credentials to plaintext config.env (legacy mode)."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    with open(CONFIG_FILE, "w") as f:
        f.write(f"PACER_USERNAME={username}\n")
        f.write(f"PACER_PASSWORD={password}\n")
        if totp_secret:
            f.write(f"PACER_TOTP_SECRET={totp_secret}\n")
        if client_code:
            f.write(f"PACER_CLIENT_CODE={client_code}\n")

    os.chmod(CONFIG_FILE, 0o600)
    return CONFIG_FILE


def _save_credentials_vault(
    username: str,
    password: str,
    totp_secret: Optional[str] = None,
    client_code: Optional[str] = None,
    passphrase: str = "",
) -> Path:
    """Save credentials to encrypted vault."""
    from .vault import PacerVault

    vault = PacerVault(path=VAULT_FILE)

    if vault.exists:
        vault.unlock(passphrase)
    else:
        vault.init(passphrase)

    vault.set("PACER_USERNAME", username)
    vault.set("PACER_PASSWORD", password)
    if totp_secret:
        vault.set("PACER_TOTP_SECRET", totp_secret)
    if client_code:
        vault.set("PACER_CLIENT_CODE", client_code)

    vault.save()

    # Remove legacy plaintext file if it exists
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()

    return VAULT_FILE


def vault_exists() -> bool:
    """Check if encrypted vault exists."""
    return VAULT_FILE.exists()


def get_config_from_vault(passphrase: str) -> PacerConfig:
    """Load configuration from encrypted vault.

    Args:
        passphrase: Vault passphrase

    Returns:
        PacerConfig with credentials from vault
    """
    from .vault import PacerVault

    vault = PacerVault(path=VAULT_FILE)
    vault.unlock(passphrase)

    # Set env vars temporarily so PacerConfig picks them up
    env_backup = {}
    vault_keys = ["PACER_USERNAME", "PACER_PASSWORD", "PACER_TOTP_SECRET", "PACER_CLIENT_CODE"]

    for key in vault_keys:
        env_backup[key] = os.environ.get(key)
        value = vault.get(key)
        if value:
            os.environ[key] = value
        elif key in os.environ:
            del os.environ[key]

    try:
        config = PacerConfig()
    finally:
        # Restore original env
        for key, value in env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    return config


def clear_credentials() -> bool:
    """Remove stored credentials (both vault and legacy)."""
    cleared = False
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
        cleared = True
    if VAULT_FILE.exists():
        VAULT_FILE.unlink()
        cleared = True
    return cleared


def ensure_dirs(config: PacerConfig) -> None:
    """Create output directories if they don't exist."""
    config.output_dir.mkdir(parents=True, exist_ok=True)
    config.docket_archive.mkdir(parents=True, exist_ok=True)
    config.document_archive.mkdir(parents=True, exist_ok=True)
    config.parsed_dockets.mkdir(parents=True, exist_ok=True)


def check_legacy_archive() -> Optional[Path]:
    """Check for old-style flat archive that could be migrated.

    Returns:
        Path to legacy archive if found and contains HTML files, None otherwise.
    """
    legacy = Path("./results/local_docket_archive")
    if legacy.exists() and any(legacy.glob("*.html")):
        return legacy
    return None


def migration_marker_exists() -> bool:
    """Check if migration has already been completed."""
    return (PACER_ROOT / ".migrated").exists()


def mark_migration_complete() -> None:
    """Mark migration as complete to avoid re-prompting."""
    PACER_ROOT.mkdir(parents=True, exist_ok=True)
    (PACER_ROOT / ".migrated").write_text(
        datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), encoding="utf-8"
    )
