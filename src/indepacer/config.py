"""Configuration management for PACER credentials and settings.

Security Configuration:
- Rate limiting: PACER_RATE_LIMIT, PACER_RATE_LIMIT_RPM
- Peak hours warning: PACER_PEAK_WARNING
- Audit logging: PACER_AUDIT_LOG
- TLS security level: PACER_TLS_LEVEL (standard, strict, paranoid)

All settings can be configured via environment variables or config file.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

CONFIG_DIR = Path.home() / ".config" / "indepacer"
CONFIG_FILE = CONFIG_DIR / "config.env"

# New hierarchical archive structure
PACER_ROOT = Path.home() / ".pacer"
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
    totp_secret: Optional[SecretStr] = None  # Base32-encoded TOTP secret for MFA
    client_code: Optional[str] = None  # Optional client code for billing
    use_qa: bool = False  # Use QA environment instead of production

    # Security settings
    rate_limit: bool = True  # Enable rate limiting (recommended)
    rate_limit_rpm: float = 30.0  # Requests per minute (default: 30)
    peak_warning: bool = True  # Show peak hours warnings (6AM-6PM CST)
    audit_log: bool = True  # Enable audit logging
    tls_level: str = "strict"  # TLS security level: standard, strict, paranoid

    # Legacy paths (deprecated, kept for backward compatibility)
    output_dir: Path = Path("./results")
    docket_archive: Path = Path("./results/local_docket_archive")
    document_archive: Path = Path("./results/local_document_archive")
    parsed_dockets: Path = Path("./results/parsed_dockets")

    # New hierarchical archive root
    archive_root: Path = ARCHIVE_ROOT

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
        """Check if MFA is configured."""
        return self.totp_secret is not None

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
            "updated_at": datetime.utcnow().isoformat() + "Z",
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
) -> Path:
    """Save PACER credentials to config file.

    Args:
        username: PACER username
        password: PACER password
        totp_secret: Base32-encoded TOTP secret from MFA setup (optional)
        client_code: Client billing code (optional)
    """
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


def clear_credentials() -> bool:
    """Remove stored credentials."""
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
        return True
    return False


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
        datetime.utcnow().isoformat() + "Z", encoding="utf-8"
    )
