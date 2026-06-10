"""Configuration management for PACER credentials and settings."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

CONFIG_DIR = Path.home() / ".config" / "pacer-cli"
CONFIG_FILE = CONFIG_DIR / "config.env"

# New hierarchical archive structure
PACER_ROOT = Path.home() / ".pacer"
VAULT_FILE = PACER_ROOT / "vault.json"
ARCHIVE_ROOT = PACER_ROOT / "archives"
CONTEXT_FILE = PACER_ROOT / "config" / "context.json"
POLICY_CSV = PACER_ROOT / "config" / "policy.csv"

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

    username: str | None = None
    password: SecretStr | None = None
    totp_secret: SecretStr | None = None  # Base32-encoded TOTP secret for MFA (production)
    qa_totp_secret: SecretStr | None = None  # Base32-encoded TOTP secret for QA environment
    client_code: str | None = None  # Optional client code for billing
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

    # Spend governance - conservative defaults so the cap works with zero config.
    # Lawyers raise these via the human-edited policy.csv (see apply_policy_csv);
    # nothing in the agent path writes them.
    per_op_cap_usd: float = 1.00  # hard stop per billable call
    daily_cap_usd: float = 10.00  # hard stop, UTC calendar day
    require_client_code: bool = False  # block billable ops with no matter code

    @field_validator("rate_limit_rpm")
    @classmethod
    def _validate_rpm(cls, v: int) -> int:
        if v < 1:
            raise ValueError("rate_limit_rpm must be >= 1 to avoid division by zero")
        return v

    @field_validator("per_op_cap_usd", "daily_cap_usd")
    @classmethod
    def _validate_caps(cls, v: float) -> float:
        if v < 0:
            raise ValueError("spend caps cannot be negative")
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
    def active_totp_secret(self) -> SecretStr | None:
        """Get TOTP secret for current environment (QA or production).

        Falls back to totp_secret if qa_totp_secret is not set in QA mode.
        """
        if self.use_qa:
            return self.qa_totp_secret or self.totp_secret
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

    court: str | None = None
    case_number: str | None = None
    case_path: Path | None = None
    updated_at: str | None = None

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
                pass  # corrupt context.json -> fall back to an empty context
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
    """Load configuration from environment and config file.

    Returns the base config with conservative built-in caps. The policy.csv
    overlay is applied lazily by the billable-op gate (apply_policy_csv) so a
    fat-fingered CSV refuses billable ops without breaking read-only commands.
    """
    return PacerConfig()


# Lawyer-facing CSV labels -> PacerConfig cap fields.
_POLICY_LABELS = {
    "max spend per search ($)": "per_op_cap_usd",
    "max spend per day ($)": "daily_cap_usd",
    "require client/matter code": "require_client_code",
}
_POLICY_FALSY = {"no", "n", "false", "off", "0"}


class PolicyError(ValueError):
    """policy.csv has an unparseable value. Blocks billable ops (fail-closed).

    A ValueError subclass so existing ``except ValueError`` callers still catch
    it, while letting callers distinguish a policy-parse failure from an
    ordinary invalid-argument ValueError.
    """


def apply_policy_csv(cfg: PacerConfig) -> PacerConfig:
    """Overlay spend caps from the human-edited ~/.pacer/config/policy.csv.

    The CSV is the *human* surface for raising/lowering caps; nothing in the
    agent path writes it. Fail-closed: a missing file keeps the conservative
    built-in defaults, a blank cell keeps the safe default (never "unlimited"),
    and an unparseable dollar cell raises ValueError (naming the row) so billable
    ops refuse while read-only commands still run.
    """
    import csv

    if not POLICY_CSV.exists():
        return cfg

    with POLICY_CSV.open(encoding="utf-8") as fh:
        for i, row in enumerate(csv.reader(fh), start=1):
            if not row or row[0].strip().lower() in ("setting", ""):
                continue
            field_name = _POLICY_LABELS.get(row[0].strip().lower())
            if field_name is None:
                continue  # unknown row: ignore, never fail
            raw = row[1].strip() if len(row) > 1 else ""
            if field_name == "require_client_code":
                # Garbage means tighter: on unless explicitly a falsy value.
                setattr(cfg, field_name, raw.lower() not in _POLICY_FALSY)
            elif raw == "":
                continue  # blank dollar cell keeps the conservative default
            else:
                try:
                    value = float(raw.lstrip("$").replace(",", ""))
                except ValueError:
                    raise PolicyError(
                        f"policy.csv row {i}: '{raw}' is not a dollar amount"
                    )
                if value < 0:
                    raise PolicyError(
                        f"policy.csv row {i}: spend caps cannot be negative"
                    )
                setattr(cfg, field_name, value)
    return cfg


def save_credentials(
    username: str,
    password: str,
    totp_secret: str | None = None,
    client_code: str | None = None,
    vault_passphrase: str | None = None,
) -> Path:
    """Save PACER credentials to encrypted vault.

    Args:
        username: PACER username
        password: PACER password
        totp_secret: Base32-encoded TOTP secret from MFA setup (optional)
        client_code: Client billing code (optional)
        vault_passphrase: Passphrase for vault encryption

    Returns:
        Path to vault file
    """
    if vault_passphrase:
        return _save_credentials_vault(username, password, totp_secret, client_code, vault_passphrase)
    return _save_credentials_legacy(username, password, totp_secret, client_code)


def _save_credentials_legacy(
    username: str,
    password: str,
    totp_secret: str | None = None,
    client_code: str | None = None,
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
    totp_secret: str | None = None,
    client_code: str | None = None,
    passphrase: str = "",
) -> Path:
    """Save credentials to encrypted vault."""
    from .vault import PacerVault, VaultError

    if not passphrase or len(passphrase) < 8:
        raise VaultError("Vault passphrase must be at least 8 characters")

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

    # Read values directly from vault and construct PacerConfig
    # (avoid setting os.environ which leaks credentials and is not thread-safe)
    config_kwargs = {}

    username = vault.get("PACER_USERNAME")
    if username:
        config_kwargs["username"] = username

    password = vault.get("PACER_PASSWORD")
    if password:
        config_kwargs["password"] = SecretStr(password)

    totp_secret = vault.get("PACER_TOTP_SECRET")
    if totp_secret:
        config_kwargs["totp_secret"] = SecretStr(totp_secret)

    qa_totp_secret = vault.get("PACER_QA_TOTP_SECRET")
    if qa_totp_secret:
        config_kwargs["qa_totp_secret"] = SecretStr(qa_totp_secret)

    client_code = vault.get("PACER_CLIENT_CODE")
    if client_code:
        config_kwargs["client_code"] = client_code

    return PacerConfig(**config_kwargs, _env_file=None)


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


def check_legacy_archive() -> Path | None:
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
