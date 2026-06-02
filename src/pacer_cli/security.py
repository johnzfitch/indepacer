"""Security hardening for PACER CLI.

Provides rate limiting, TLS enforcement, peak hours detection,
audit logging, and streaming downloads to protect federal court
system resources and prevent account issues.

Addresses all issues from PR #1 and PR #2:
- Timezone DST handling via zoneinfo (not hardcoded UTC-6)
- StreamingDownload as context manager (no resource leaks)
- ECDHE-only cipher suites (no deprecated DHE)
- Rate limit validation (no division-by-zero)
- Specific exception handling (no bare excepts)
- Response consumption detection
- Global state reset for test isolation
"""

from __future__ import annotations

import logging
import ssl
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Iterator, Literal, Optional

if TYPE_CHECKING:
    from .config import PacerConfig

import requests
from requests.adapters import HTTPAdapter

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo  # type: ignore[no-redef]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_RATE_LIMIT_RPM = 30
MAX_CONNECTIONS = 10
MAX_MEMORY_RESPONSE_SIZE = 50 * 1024 * 1024  # 50 MB
STREAMING_CHUNK_SIZE = 8192
PEAK_HOURS_START = 6  # 6 AM CST/CDT
PEAK_HOURS_END = 18  # 6 PM CST/CDT
BULK_DOWNLOAD_THRESHOLD = 100  # entries before considered "bulk"

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_RETRIES = 3
BACKOFF_FACTOR = 2.0

# ECDHE-only ciphers - no deprecated DHE
SECURE_CIPHERS = "ECDHE+AESGCM:ECDHE+CHACHA20"

LOG_DIR = Path.home() / ".pacer" / "logs"

# ---------------------------------------------------------------------------
# TLS Adapter
# ---------------------------------------------------------------------------


class TLSAdapter(HTTPAdapter):
    """HTTPS adapter enforcing TLS 1.2+ with secure cipher suites."""

    def __init__(
        self,
        tls_level: Literal["standard", "strict", "paranoid"] = "standard",
        **kwargs,
    ):
        self.tls_level = tls_level
        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2

        if self.tls_level == "paranoid":
            ctx.minimum_version = ssl.TLSVersion.TLSv1_3
        elif self.tls_level == "strict":
            ctx.set_ciphers(SECURE_CIPHERS)
        else:
            # Standard: enforce TLS 1.2+ with safe defaults
            try:
                ctx.set_ciphers(SECURE_CIPHERS)
            except ssl.SSLError:
                pass  # Fall back to OpenSSL defaults

        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------


class RateLimiter:
    """Thread-safe token-bucket rate limiter."""

    def __init__(self, rpm: int = DEFAULT_RATE_LIMIT_RPM):
        if rpm < 1:
            raise ValueError(f"Rate limit RPM must be >= 1, got {rpm}")
        self.rpm = rpm
        self._interval = 60.0 / rpm
        self._lock = threading.Lock()
        self._last_request: float = 0.0
        self._request_count: int = 0

    def wait(self) -> None:
        """Block until the next request is allowed."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request
            if elapsed < self._interval:
                time.sleep(self._interval - elapsed)
            self._last_request = time.monotonic()
            self._request_count += 1

    @property
    def request_count(self) -> int:
        return self._request_count

    def reset(self) -> None:
        with self._lock:
            self._last_request = 0.0
            self._request_count = 0


# Module-level rate limiter (resettable for tests)
_rate_limiter: Optional[RateLimiter] = None
_rate_limiter_lock = threading.Lock()


def get_rate_limiter(rpm: int = DEFAULT_RATE_LIMIT_RPM) -> RateLimiter:
    """Get or create the module-level rate limiter."""
    global _rate_limiter
    with _rate_limiter_lock:
        if _rate_limiter is None:
            _rate_limiter = RateLimiter(rpm)
        return _rate_limiter


def reset_rate_limiter() -> None:
    """Reset the global rate limiter (for test isolation)."""
    global _rate_limiter
    with _rate_limiter_lock:
        _rate_limiter = None


# ---------------------------------------------------------------------------
# Peak Hours Detection
# ---------------------------------------------------------------------------


def _now_cst() -> datetime:
    """Current time in US Central (handles DST automatically)."""
    return datetime.now(ZoneInfo("America/Chicago"))


def is_peak_hours() -> bool:
    """Check if current time is during PACER peak hours (6AM-6PM Central)."""
    now = _now_cst()
    return PEAK_HOURS_START <= now.hour < PEAK_HOURS_END


def is_bulk_download(entry_count: int) -> bool:
    """Check if a download qualifies as 'bulk'."""
    return entry_count >= BULK_DOWNLOAD_THRESHOLD


def show_peak_hours_warning(entry_count: int = 0) -> None:
    """Print a peak-hours warning if applicable.

    Does not return a value - callers should not depend on a return.
    """
    if not is_peak_hours():
        return

    now = _now_cst()
    tz_abbr = now.strftime("%Z")  # CST or CDT automatically

    try:
        from rich.console import Console
        from rich.panel import Panel

        console = Console(stderr=True)
        msg = (
            f"[yellow]PACER peak hours ({PEAK_HOURS_START}AM-"
            f"{PEAK_HOURS_END - 12}PM {tz_abbr})[/]\n"
            "Court systems experience heavy load during business hours."
        )
        if entry_count >= BULK_DOWNLOAD_THRESHOLD:
            msg += (
                f"\n[bold]Bulk download ({entry_count} entries) may be "
                "throttled or rejected.[/]"
            )
        console.print(Panel(msg, title="[yellow]Peak Hours[/]", border_style="yellow"))
    except ImportError:
        pass  # rich not installed -> skip the cosmetic peak-hours panel


# ---------------------------------------------------------------------------
# Audit Logger
# ---------------------------------------------------------------------------


class AuditLogger:
    """Append-only audit log for PACER operations."""

    def __init__(self, log_dir: Optional[Path] = None):
        # Resolve LOG_DIR at call time (not import) so tests can redirect it.
        self.log_dir = log_dir if log_dir is not None else LOG_DIR
        self._logger: Optional[logging.Logger] = None

    def _ensure_logger(self) -> logging.Logger:
        if self._logger is None:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            log_file = self.log_dir / f"audit-{datetime.now(timezone.utc):%Y-%m}.log"
            self._logger = logging.getLogger("pacer.audit")
            self._logger.setLevel(logging.INFO)
            if not self._logger.handlers:
                handler = logging.FileHandler(log_file, encoding="utf-8")
                formatter = logging.Formatter(
                    "%(asctime)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%SZ"
                )
                # Emit timestamps in true UTC so the trailing "Z" is honest and
                # spend_today() can bucket lines by UTC calendar day.
                formatter.converter = time.gmtime
                handler.setFormatter(formatter)
                self._logger.addHandler(handler)
        return self._logger

    def log_request(
        self,
        method: str,
        url: str,
        status_code: Optional[int] = None,
        cost: float = 0.0,
        error: Optional[str] = None,
        client_code: Optional[str] = None,
    ) -> None:
        logger = self._ensure_logger()
        parts = [f"{method} {url}"]
        if status_code is not None:
            parts.append(f"status={status_code}")
        if cost > 0:
            parts.append(f"cost=${cost:.2f}")
        if client_code:
            parts.append(f"client={client_code}")
        if error:
            parts.append(f"error={error}")
        logger.info(" | ".join(parts))

    def log_download(
        self,
        url: str,
        filepath: Path,
        size_bytes: int,
        pages: int = 0,
        cost: float = 0.0,
        client_code: Optional[str] = None,
    ) -> None:
        logger = self._ensure_logger()
        line = (
            f"DOWNLOAD {url} -> {filepath} | "
            f"size={size_bytes} pages={pages} cost=${cost:.2f}"
        )
        if client_code:
            line += f" | client={client_code}"
        logger.info(line)


_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def reset_audit_logger() -> None:
    """Reset global audit logger (for test isolation).

    Also detaches handlers from the shared ``pacer.audit`` logging.Logger so a
    redirected LOG_DIR (e.g. a fresh temp dir per test) takes effect instead of
    a stale FileHandler pointing at a previous directory.
    """
    global _audit_logger
    _audit_logger = None
    logger = logging.getLogger("pacer.audit")
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)


# ---------------------------------------------------------------------------
# Spend governance - preventive cap, summed from the audit log
# ---------------------------------------------------------------------------


class GovernanceError(Exception):
    """Base for preventive spend-cap refusals (CLI exits 3 on these)."""

    error_key: str = "budget_exceeded"

    def __init__(self, message: str, **fields: object) -> None:
        super().__init__(message)
        self.fields = fields


class BudgetError(GovernanceError):
    """A per-op or daily spend cap would be exceeded."""

    error_key = "budget_exceeded"


class MatterRequired(GovernanceError):
    """policy.csv requires a client/matter code for billable operations."""

    error_key = "matter_required"


class ScopeError(GovernanceError):
    """courts.csv is present but disables every court - refuse rather than
    silently search nationwide (fail-closed)."""

    error_key = "scope_empty"


def spend_today(client_code: Optional[str] = None) -> float:
    """Sum today's billed cost (UTC calendar day) from the current audit log.

    Reads the same append-only log AuditLogger writes - no separate store. Uses
    the ``cost=$N`` token each billable call records. When ``client_code`` is
    given, only lines tagged ``client=<code>`` are counted.
    """
    log_file = LOG_DIR / f"audit-{datetime.now(timezone.utc):%Y-%m}.log"
    if not log_file.exists():
        return 0.0
    today = f"{datetime.now(timezone.utc):%Y-%m-%d}"
    total = 0.0
    for line in log_file.read_text(encoding="utf-8").splitlines():
        if not line.startswith(today) or "cost=$" not in line:
            continue
        if client_code is not None:
            # Exact field match on the " | "-delimited log so one client code
            # can't match another it's a prefix of (e.g. M-1 vs M-10).
            tokens = [t.strip() for t in line.split("|")]
            if f"client={client_code}" not in tokens:
                continue
        try:
            total += float(line.split("cost=$")[1].split()[0])
        except (IndexError, ValueError):
            continue
    return round(total, 2)


def check_spend(
    config: "PacerConfig",
    estimated_cost: float,
    *,
    prior_spend: float,
    client_code: Optional[str] = None,
) -> None:
    """Pure, side-effect-free preventive cap check.

    Raises a :class:`GovernanceError` subclass when ``estimated_cost`` would
    breach a cap; returns ``None`` when the operation is within policy. Ctx-free
    so both the CLI gate and the MCP server share one enforcement path.

    ``config`` is duck-typed (reads ``require_client_code``/``per_op_cap_usd``/
    ``daily_cap_usd``) to avoid a ``config <-> security`` import cycle.
    """
    if config.require_client_code and not client_code:
        raise MatterRequired(
            "a client/matter code is required for billable operations",
            client_code=client_code,
        )
    if estimated_cost > config.per_op_cap_usd:
        raise BudgetError(
            "operation exceeds the per-operation spend cap",
            estimated=round(estimated_cost, 2),
            per_op_cap=config.per_op_cap_usd,
        )
    if prior_spend + estimated_cost > config.daily_cap_usd:
        raise BudgetError(
            "operation would exceed the daily spend cap",
            estimated=round(estimated_cost, 2),
            spent_today=round(prior_spend, 2),
            daily_cap=config.daily_cap_usd,
        )


# ---------------------------------------------------------------------------
# Streaming Download
# ---------------------------------------------------------------------------


@dataclass
class StreamingDownload:
    """Context-manager for streaming large responses safely.

    Usage::

        with streaming_download(session, url) as dl:
            for chunk in dl.iter_chunks():
                f.write(chunk)
    """

    response: requests.Response
    max_size: int = MAX_MEMORY_RESPONSE_SIZE
    _bytes_read: int = 0
    _closed: bool = False

    def iter_chunks(self, chunk_size: int = STREAMING_CHUNK_SIZE) -> Iterator[bytes]:
        for chunk in self.response.iter_content(chunk_size=chunk_size):
            self._bytes_read += len(chunk)
            if self._bytes_read > self.max_size:
                self.close()
                raise MemoryError(
                    f"Response exceeded {self.max_size} bytes, aborting download"
                )
            yield chunk

    @property
    def bytes_read(self) -> int:
        return self._bytes_read

    def close(self) -> None:
        if not self._closed:
            try:
                self.response.close()
            except OSError:
                pass  # best-effort cleanup; socket already broken is harmless
            self._closed = True

    def __enter__(self) -> "StreamingDownload":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


@contextmanager
def streaming_download(
    session: requests.Session,
    url: str,
    headers: Optional[dict] = None,
    timeout: int = 120,
    max_size: int = MAX_MEMORY_RESPONSE_SIZE,
) -> Iterator[StreamingDownload]:
    """Open a streaming download as a context manager."""
    resp = session.get(url, headers=headers or {}, stream=True, timeout=timeout)
    resp.raise_for_status()
    dl = StreamingDownload(response=resp, max_size=max_size)
    try:
        yield dl
    finally:
        dl.close()


# ---------------------------------------------------------------------------
# Memory-safe response reading
# ---------------------------------------------------------------------------


def safe_response_content(response: requests.Response, max_size: int = MAX_MEMORY_RESPONSE_SIZE) -> bytes:
    """Read response content with a size guard.

    Checks Content-Length header before reading. Falls back to
    chunked reading if header is absent.
    """
    content_length = response.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > max_size:
                raise MemoryError(
                    f"Response Content-Length {content_length} exceeds limit {max_size}"
                )
        except ValueError:
            pass  # non-integer Content-Length -> fall through to chunked reads

    # Use chunked read to enforce limit
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_content(chunk_size=STREAMING_CHUNK_SIZE):
        total += len(chunk)
        if total > max_size:
            raise MemoryError(f"Response exceeded {max_size} bytes while reading")
        chunks.append(chunk)

    return b"".join(chunks)


# ---------------------------------------------------------------------------
# Secure Session Factory
# ---------------------------------------------------------------------------


def create_secure_session(
    tls_level: Literal["standard", "strict", "paranoid"] = "standard",
    max_connections: int = MAX_CONNECTIONS,
) -> requests.Session:
    """Create a requests Session with TLS hardening and connection pooling."""
    session = requests.Session()
    adapter = TLSAdapter(
        tls_level=tls_level,
        pool_connections=max_connections,
        pool_maxsize=max_connections,
    )
    session.mount("https://", adapter)
    return session


# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------


def request_with_retry(
    session: requests.Session,
    method: str,
    url: str,
    max_retries: int = MAX_RETRIES,
    backoff_factor: float = BACKOFF_FACTOR,
    **kwargs,
) -> requests.Response:
    """Make an HTTP request with exponential backoff on retryable errors."""
    last_exc: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        try:
            resp = session.request(method, url, **kwargs)
            if resp.status_code not in RETRYABLE_STATUS_CODES:
                return resp
            if attempt < max_retries:
                wait = backoff_factor * (2 ** attempt)
                time.sleep(wait)
            last_exc = requests.HTTPError(response=resp)
        except requests.ConnectionError as exc:
            last_exc = exc
            if attempt < max_retries:
                wait = backoff_factor * (2 ** attempt)
                time.sleep(wait)

    raise last_exc  # type: ignore[misc]
