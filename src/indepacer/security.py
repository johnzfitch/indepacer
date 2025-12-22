"""Security hardening module for PACER CLI.

This module provides:
- Rate limiting with configurable delays
- Peak hour detection (PACER requests bulk downloads 6PM-6AM CST only)
- Streaming downloads to prevent memory exhaustion
- Connection pooling limits
- Request logging for audit trails
- TLS/SSL certificate validation
- Memory-safe download handling

PACER Usage Policy Reminder:
Large bulk downloads are expected to be done from 6PM-6AM CST.
Excessive usage during peak hours (6AM-6PM CST) may risk account closure.
"""

import logging
import ssl
import time
import threading
import weakref
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from functools import wraps
from pathlib import Path
from typing import Callable, Iterator, Optional, TypeVar
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib3.util.ssl_ import create_urllib3_context

# Configure module logger
logger = logging.getLogger("indepacer.security")


# =============================================================================
# CONSTANTS
# =============================================================================

# CST timezone offset (UTC-6)
CST_OFFSET_HOURS = -6

# Peak hours: 6AM-6PM CST (bulk downloads should be avoided)
PEAK_HOUR_START = 6   # 6 AM CST
PEAK_HOUR_END = 18    # 6 PM CST

# Default rate limits (requests per minute)
DEFAULT_RATE_LIMIT = 30  # 30 requests per minute = 1 every 2 seconds
BULK_RATE_LIMIT = 10     # 10 requests per minute during bulk operations

# Connection pool limits
MAX_POOL_CONNECTIONS = 10
MAX_POOL_BLOCK = True

# Streaming chunk size (8KB - balanced for memory/performance)
STREAM_CHUNK_SIZE = 8192

# Maximum response size to load into memory (50MB)
MAX_MEMORY_RESPONSE_SIZE = 50 * 1024 * 1024

# Retry configuration
MAX_RETRIES = 3
RETRY_BACKOFF_FACTOR = 0.5
RETRY_STATUS_CODES = [429, 500, 502, 503, 504]

# Audit log location
AUDIT_LOG_DIR = Path.home() / ".pacer" / "logs"


# =============================================================================
# PEAK HOURS DETECTION
# =============================================================================

class DownloadPeriod(Enum):
    """Classification of current time for PACER downloads."""
    PEAK = "peak"          # 6AM-6PM CST - avoid bulk downloads
    OFF_PEAK = "off_peak"  # 6PM-6AM CST - bulk downloads recommended


@dataclass
class PeakHoursInfo:
    """Information about current download period."""
    period: DownloadPeriod
    current_hour_cst: int
    hours_until_off_peak: int
    message: str
    should_warn: bool = False


def get_current_cst_hour() -> int:
    """Get current hour in CST (Central Standard Time).

    Note: This uses a fixed CST offset. For proper CDT handling,
    you would need to check if DST is active.
    """
    utc_now = datetime.now(timezone.utc)
    cst_hour = (utc_now.hour + CST_OFFSET_HOURS) % 24
    return cst_hour


def check_peak_hours() -> PeakHoursInfo:
    """Check if current time is during PACER peak hours.

    PACER requests that large bulk downloads be performed from 6PM-6AM CST.
    This function checks the current time and provides appropriate warnings.

    Returns:
        PeakHoursInfo with period classification and user messaging
    """
    current_hour = get_current_cst_hour()

    if PEAK_HOUR_START <= current_hour < PEAK_HOUR_END:
        # During peak hours (6AM-6PM CST)
        hours_until_off_peak = PEAK_HOUR_END - current_hour
        return PeakHoursInfo(
            period=DownloadPeriod.PEAK,
            current_hour_cst=current_hour,
            hours_until_off_peak=hours_until_off_peak,
            message=(
                f"PACER Peak Hours Active ({current_hour}:00 CST)\n"
                f"Large bulk downloads should be performed 6PM-6AM CST.\n"
                f"Off-peak period begins in {hours_until_off_peak} hour(s).\n"
                "Excessive downloads during peak hours may risk account closure."
            ),
            should_warn=True,
        )
    else:
        # During off-peak hours (6PM-6AM CST) - bulk downloads OK
        if current_hour >= PEAK_HOUR_END:
            hours_until_peak = 24 - current_hour + PEAK_HOUR_START
        else:
            hours_until_peak = PEAK_HOUR_START - current_hour

        return PeakHoursInfo(
            period=DownloadPeriod.OFF_PEAK,
            current_hour_cst=current_hour,
            hours_until_off_peak=0,
            message=(
                f"Off-Peak Period ({current_hour}:00 CST)\n"
                f"Bulk downloads are appropriate during this time.\n"
                f"Peak hours begin in {hours_until_peak} hour(s)."
            ),
            should_warn=False,
        )


def is_bulk_download(document_count: int = 1, page_count: int = 0) -> bool:
    """Determine if an operation constitutes a bulk download.

    Args:
        document_count: Number of documents to download
        page_count: Estimated page count

    Returns:
        True if this should be considered a bulk download
    """
    # Consider bulk if: >10 documents OR >100 pages
    return document_count > 10 or page_count > 100


# =============================================================================
# RATE LIMITING
# =============================================================================

@dataclass
class RateLimiter:
    """Thread-safe rate limiter using token bucket algorithm.

    Implements configurable rate limiting to prevent overwhelming
    PACER servers and to comply with usage policies.
    """

    requests_per_minute: float = DEFAULT_RATE_LIMIT
    _last_request_time: float = field(default_factory=time.time)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _request_count: int = 0
    _window_start: float = field(default_factory=time.time)

    @property
    def min_interval(self) -> float:
        """Minimum seconds between requests."""
        return 60.0 / self.requests_per_minute

    def wait(self) -> float:
        """Wait if necessary to comply with rate limit.

        Returns:
            Seconds waited (0 if no wait needed)
        """
        with self._lock:
            now = time.time()
            elapsed = now - self._last_request_time

            if elapsed < self.min_interval:
                wait_time = self.min_interval - elapsed
                time.sleep(wait_time)
                self._last_request_time = time.time()
                return wait_time
            else:
                self._last_request_time = now
                return 0.0

    def get_stats(self) -> dict:
        """Get current rate limiter statistics."""
        with self._lock:
            now = time.time()
            window_elapsed = now - self._window_start

            # Reset window every minute
            if window_elapsed >= 60:
                rate = self._request_count / (window_elapsed / 60)
                self._request_count = 0
                self._window_start = now
            else:
                rate = self._request_count / max(window_elapsed / 60, 0.001)

            return {
                "requests_per_minute_limit": self.requests_per_minute,
                "current_rate": rate,
                "min_interval_seconds": self.min_interval,
            }

    def record_request(self) -> None:
        """Record that a request was made."""
        with self._lock:
            self._request_count += 1


# Global rate limiter instance
_global_rate_limiter: Optional[RateLimiter] = None
_rate_limiter_lock = threading.Lock()


def get_rate_limiter(requests_per_minute: Optional[float] = None) -> RateLimiter:
    """Get or create the global rate limiter.

    Args:
        requests_per_minute: Override default rate limit

    Returns:
        Global RateLimiter instance
    """
    global _global_rate_limiter

    with _rate_limiter_lock:
        if _global_rate_limiter is None:
            rpm = requests_per_minute or DEFAULT_RATE_LIMIT
            _global_rate_limiter = RateLimiter(requests_per_minute=rpm)
        elif requests_per_minute is not None:
            _global_rate_limiter.requests_per_minute = requests_per_minute

        return _global_rate_limiter


def rate_limited(func: Callable) -> Callable:
    """Decorator to apply rate limiting to a function.

    Usage:
        @rate_limited
        def download_document(url: str) -> bytes:
            ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        limiter = get_rate_limiter()
        limiter.wait()
        limiter.record_request()
        return func(*args, **kwargs)
    return wrapper


# =============================================================================
# TLS/SSL SECURITY
# =============================================================================

class TLSSecurityLevel(Enum):
    """TLS security enforcement levels."""
    STANDARD = "standard"       # Default requests behavior
    STRICT = "strict"           # TLS 1.2+ only, verify certificates
    PARANOID = "paranoid"       # TLS 1.3 only (where supported)


def create_secure_ssl_context(level: TLSSecurityLevel = TLSSecurityLevel.STRICT) -> ssl.SSLContext:
    """Create an SSL context with appropriate security settings.

    Args:
        level: Security level to apply

    Returns:
        Configured SSLContext
    """
    ctx = create_urllib3_context()

    if level in (TLSSecurityLevel.STRICT, TLSSecurityLevel.PARANOID):
        # Require TLS 1.2 minimum
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2

        # Verify certificates and hostname
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED

        # Disable weak ciphers
        ctx.set_ciphers("ECDHE+AESGCM:DHE+AESGCM:ECDHE+CHACHA20:DHE+CHACHA20")

    if level == TLSSecurityLevel.PARANOID:
        # TLS 1.3 only (if supported by OpenSSL version)
        try:
            ctx.minimum_version = ssl.TLSVersion.TLSv1_3
        except AttributeError:
            # TLS 1.3 not available, stick with 1.2
            pass

    return ctx


class SecureHTTPAdapter(HTTPAdapter):
    """HTTP adapter with enhanced security settings."""

    def __init__(
        self,
        security_level: TLSSecurityLevel = TLSSecurityLevel.STRICT,
        **kwargs
    ):
        self.security_level = security_level

        # Set connection pooling limits
        kwargs.setdefault("pool_connections", MAX_POOL_CONNECTIONS)
        kwargs.setdefault("pool_maxsize", MAX_POOL_CONNECTIONS)
        kwargs.setdefault("pool_block", MAX_POOL_BLOCK)

        # Configure retry policy
        retry = Retry(
            total=MAX_RETRIES,
            backoff_factor=RETRY_BACKOFF_FACTOR,
            status_forcelist=RETRY_STATUS_CODES,
            allowed_methods=["GET", "POST", "DELETE"],
            raise_on_status=False,
        )
        kwargs.setdefault("max_retries", retry)

        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        """Initialize pool manager with secure SSL context."""
        if self.security_level != TLSSecurityLevel.STANDARD:
            kwargs["ssl_context"] = create_secure_ssl_context(self.security_level)
        return super().init_poolmanager(*args, **kwargs)


def create_secure_session(
    security_level: TLSSecurityLevel = TLSSecurityLevel.STRICT
) -> requests.Session:
    """Create a requests session with security hardening.

    Features:
    - TLS 1.2+ enforcement
    - Connection pooling limits
    - Automatic retries with backoff
    - Secure default headers

    Args:
        security_level: TLS security level

    Returns:
        Configured requests.Session
    """
    session = requests.Session()

    # Mount secure adapter for HTTPS
    adapter = SecureHTTPAdapter(security_level=security_level)
    session.mount("https://", adapter)

    # Set secure default headers
    session.headers.update({
        "User-Agent": "PACER-CLI/1.0 (Security-Hardened)",
        "Accept-Encoding": "gzip, deflate",
    })

    return session


# =============================================================================
# STREAMING DOWNLOADS (MEMORY SAFETY)
# =============================================================================

@dataclass
class StreamingDownload:
    """Memory-safe streaming download handler.

    Prevents memory exhaustion by streaming large files to disk
    instead of loading them entirely into memory.
    """

    response: requests.Response
    chunk_size: int = STREAM_CHUNK_SIZE
    _bytes_downloaded: int = 0

    def iter_content(self) -> Iterator[bytes]:
        """Iterate over response content in chunks.

        Yields:
            Chunks of response data
        """
        for chunk in self.response.iter_content(chunk_size=self.chunk_size):
            if chunk:
                self._bytes_downloaded += len(chunk)
                yield chunk

    def save_to_file(self, filepath: Path) -> int:
        """Stream response directly to file.

        Args:
            filepath: Destination file path

        Returns:
            Total bytes written
        """
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "wb") as f:
            for chunk in self.iter_content():
                f.write(chunk)

        return self._bytes_downloaded

    @property
    def bytes_downloaded(self) -> int:
        """Get total bytes downloaded so far."""
        return self._bytes_downloaded

    @property
    def content_length(self) -> Optional[int]:
        """Get expected content length from headers."""
        length = self.response.headers.get("Content-Length")
        return int(length) if length else None


def streaming_download(
    session: requests.Session,
    url: str,
    filepath: Path,
    headers: Optional[dict] = None,
    timeout: int = 120,
) -> int:
    """Download a file using streaming to prevent memory exhaustion.

    Args:
        session: Requests session
        url: URL to download
        filepath: Destination file path
        headers: Optional request headers
        timeout: Request timeout in seconds

    Returns:
        Total bytes downloaded

    Raises:
        requests.RequestException: On network errors
        IOError: On file write errors
    """
    # Apply rate limiting
    limiter = get_rate_limiter()
    limiter.wait()
    limiter.record_request()

    response = session.get(
        url,
        headers=headers,
        stream=True,
        timeout=timeout,
    )
    response.raise_for_status()

    downloader = StreamingDownload(response)
    return downloader.save_to_file(filepath)


def safe_response_content(
    response: requests.Response,
    max_size: int = MAX_MEMORY_RESPONSE_SIZE,
) -> bytes:
    """Safely get response content with size limit.

    Args:
        response: Requests response object
        max_size: Maximum bytes to load into memory

    Returns:
        Response content

    Raises:
        ValueError: If response exceeds max_size
    """
    content_length = response.headers.get("Content-Length")

    if content_length and int(content_length) > max_size:
        raise ValueError(
            f"Response too large ({int(content_length)} bytes). "
            f"Maximum allowed: {max_size} bytes. "
            "Use streaming_download() for large files."
        )

    # Stream and check size
    chunks = []
    total_size = 0

    for chunk in response.iter_content(chunk_size=STREAM_CHUNK_SIZE):
        total_size += len(chunk)
        if total_size > max_size:
            raise ValueError(
                f"Response exceeded maximum size ({max_size} bytes). "
                "Use streaming_download() for large files."
            )
        chunks.append(chunk)

    return b"".join(chunks)


# =============================================================================
# AUDIT LOGGING
# =============================================================================

@dataclass
class AuditEntry:
    """Entry in the security audit log."""
    timestamp: str
    operation: str
    url: str
    method: str
    status_code: Optional[int] = None
    bytes_transferred: int = 0
    duration_ms: int = 0
    error: Optional[str] = None
    user_agent: str = ""


class AuditLogger:
    """Security audit logger for tracking all PACER operations.

    Logs all network requests for compliance and debugging.
    """

    def __init__(self, log_dir: Path = AUDIT_LOG_DIR):
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._setup_logger()

    def _setup_logger(self) -> None:
        """Configure the audit file logger."""
        self._logger = logging.getLogger("indepacer.audit")
        self._logger.setLevel(logging.INFO)

        # Rotate logs daily
        log_file = self.log_dir / f"audit_{datetime.now().strftime('%Y%m%d')}.log"

        handler = logging.FileHandler(log_file, encoding="utf-8")
        handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))

        # Avoid duplicate handlers
        if not self._logger.handlers:
            self._logger.addHandler(handler)

    def log_request(
        self,
        operation: str,
        url: str,
        method: str = "GET",
        status_code: Optional[int] = None,
        bytes_transferred: int = 0,
        duration_ms: int = 0,
        error: Optional[str] = None,
    ) -> None:
        """Log a network request to the audit trail.

        Args:
            operation: Type of operation (e.g., "docket_download")
            url: Request URL (sensitive params redacted)
            method: HTTP method
            status_code: Response status code
            bytes_transferred: Bytes sent/received
            duration_ms: Request duration in milliseconds
            error: Error message if failed
        """
        # Redact sensitive URL parameters
        parsed = urlparse(url)
        redacted_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if parsed.query:
            redacted_url += "?[params_redacted]"

        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            operation=operation,
            url=redacted_url,
            method=method,
            status_code=status_code,
            bytes_transferred=bytes_transferred,
            duration_ms=duration_ms,
            error=error,
        )

        if error:
            self._logger.warning(
                f"{entry.operation} | {entry.method} {entry.url} | "
                f"ERROR: {entry.error}"
            )
        else:
            self._logger.info(
                f"{entry.operation} | {entry.method} {entry.url} | "
                f"{entry.status_code} | {entry.bytes_transferred}B | "
                f"{entry.duration_ms}ms"
            )


# Global audit logger
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def audit_request(operation: str) -> Callable:
    """Decorator to automatically audit a function's network requests.

    Usage:
        @audit_request("docket_download")
        def download_docket(url: str) -> bytes:
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            error = None
            status_code = None
            bytes_transferred = 0

            try:
                result = func(*args, **kwargs)

                # Try to extract info from result
                if hasattr(result, "status_code"):
                    status_code = result.status_code
                if hasattr(result, "content"):
                    bytes_transferred = len(result.content)

                return result

            except Exception as e:
                error = str(e)
                raise

            finally:
                duration_ms = int((time.time() - start_time) * 1000)
                url = kwargs.get("url", args[0] if args else "unknown")

                get_audit_logger().log_request(
                    operation=operation,
                    url=str(url),
                    method=kwargs.get("method", "GET"),
                    status_code=status_code,
                    bytes_transferred=bytes_transferred,
                    duration_ms=duration_ms,
                    error=error,
                )

        return wrapper
    return decorator


# =============================================================================
# RESOURCE CLEANUP
# =============================================================================

# Track active sessions for cleanup
_active_sessions: weakref.WeakSet = weakref.WeakSet()


def register_session(session: requests.Session) -> None:
    """Register a session for cleanup tracking."""
    _active_sessions.add(session)


def cleanup_sessions() -> int:
    """Close all tracked sessions.

    Returns:
        Number of sessions closed
    """
    count = 0
    for session in list(_active_sessions):
        try:
            session.close()
            count += 1
        except Exception:
            pass
    return count


# =============================================================================
# SECURITY CONFIGURATION
# =============================================================================

@dataclass
class SecurityConfig:
    """Security configuration settings."""

    # Rate limiting
    rate_limit_enabled: bool = True
    requests_per_minute: float = DEFAULT_RATE_LIMIT
    bulk_requests_per_minute: float = BULK_RATE_LIMIT

    # Peak hours enforcement
    peak_hours_warning: bool = True
    block_bulk_during_peak: bool = False  # Warning only by default

    # TLS settings
    tls_security_level: TLSSecurityLevel = TLSSecurityLevel.STRICT

    # Memory safety
    max_memory_response_size: int = MAX_MEMORY_RESPONSE_SIZE
    enable_streaming: bool = True
    stream_chunk_size: int = STREAM_CHUNK_SIZE

    # Audit logging
    audit_logging_enabled: bool = True
    audit_log_dir: Path = AUDIT_LOG_DIR

    # Timeouts
    default_timeout: int = 60
    download_timeout: int = 120

    @classmethod
    def from_env(cls) -> "SecurityConfig":
        """Load security config from environment variables."""
        import os

        return cls(
            rate_limit_enabled=os.environ.get("PACER_RATE_LIMIT", "true").lower() == "true",
            requests_per_minute=float(os.environ.get("PACER_RATE_LIMIT_RPM", str(DEFAULT_RATE_LIMIT))),
            peak_hours_warning=os.environ.get("PACER_PEAK_WARNING", "true").lower() == "true",
            audit_logging_enabled=os.environ.get("PACER_AUDIT_LOG", "true").lower() == "true",
        )


# Global security config
_security_config: Optional[SecurityConfig] = None


def get_security_config() -> SecurityConfig:
    """Get the global security configuration."""
    global _security_config
    if _security_config is None:
        _security_config = SecurityConfig.from_env()
    return _security_config


def configure_security(config: SecurityConfig) -> None:
    """Set the global security configuration."""
    global _security_config
    _security_config = config

    # Apply rate limiter settings
    if config.rate_limit_enabled:
        get_rate_limiter(config.requests_per_minute)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def check_download_safety(
    document_count: int = 1,
    page_count: int = 0,
) -> tuple[bool, str]:
    """Check if a download operation is safe to proceed.

    Args:
        document_count: Number of documents to download
        page_count: Estimated page count

    Returns:
        Tuple of (is_safe, warning_message)
    """
    messages = []
    is_safe = True

    # Check peak hours
    peak_info = check_peak_hours()
    is_bulk = is_bulk_download(document_count, page_count)

    if peak_info.should_warn and is_bulk:
        messages.append(peak_info.message)

        config = get_security_config()
        if config.block_bulk_during_peak:
            is_safe = False
            messages.append(
                "Bulk downloads are blocked during peak hours. "
                "Override with --force or wait until 6PM CST."
            )

    return is_safe, "\n".join(messages)


def format_peak_hours_banner() -> str:
    """Get a formatted banner about PACER usage policy."""
    peak_info = check_peak_hours()

    if peak_info.period == DownloadPeriod.PEAK:
        return (
            "=" * 60 + "\n"
            "PACER USAGE REMINDER\n"
            "=" * 60 + "\n"
            f"Current time: {peak_info.current_hour_cst}:00 CST (Peak Hours)\n"
            "\n"
            "Large bulk downloads should be performed 6PM-6AM CST.\n"
            "Excessive usage during peak hours may risk account closure.\n"
            f"Off-peak begins in: {peak_info.hours_until_off_peak} hour(s)\n"
            "=" * 60
        )
    else:
        return (
            f"Off-Peak Period ({peak_info.current_hour_cst}:00 CST) - "
            "Bulk downloads OK"
        )
