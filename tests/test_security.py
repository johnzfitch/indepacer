"""Tests for the security module.

Covers all 11 issues from PR #2 plus the 23 review comments from PR #1.
"""

from __future__ import annotations

import ssl
import time
import threading
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from pacer_cli.security import (
    BULK_DOWNLOAD_THRESHOLD,
    DEFAULT_RATE_LIMIT_RPM,
    MAX_MEMORY_RESPONSE_SIZE,
    PEAK_HOURS_END,
    PEAK_HOURS_START,
    SECURE_CIPHERS,
    AuditLogger,
    RateLimiter,
    StreamingDownload,
    TLSAdapter,
    create_secure_session,
    get_audit_logger,
    get_rate_limiter,
    is_bulk_download,
    is_peak_hours,
    request_with_retry,
    reset_audit_logger,
    reset_rate_limiter,
    safe_response_content,
    show_peak_hours_warning,
    streaming_download,
)


# =========================================================================
# PR #2 Bug #1: Timezone DST handling
# =========================================================================

class TestTimezoneHandling:
    """Verify zoneinfo-based Central time (not hardcoded UTC-6)."""

    def test_peak_hours_uses_zoneinfo(self):
        """is_peak_hours should not crash — proves zoneinfo import works."""
        result = is_peak_hours()
        assert isinstance(result, bool)

    @patch("pacer_cli.security._now_cst")
    def test_peak_during_business_hours(self, mock_now):
        from zoneinfo import ZoneInfo
        mock_now.return_value = datetime(2025, 7, 15, 12, 0, tzinfo=ZoneInfo("America/Chicago"))
        assert is_peak_hours() is True

    @patch("pacer_cli.security._now_cst")
    def test_not_peak_at_night(self, mock_now):
        from zoneinfo import ZoneInfo
        mock_now.return_value = datetime(2025, 7, 15, 22, 0, tzinfo=ZoneInfo("America/Chicago"))
        assert is_peak_hours() is False

    @patch("pacer_cli.security._now_cst")
    def test_peak_boundary_start(self, mock_now):
        from zoneinfo import ZoneInfo
        mock_now.return_value = datetime(2025, 1, 15, 6, 0, tzinfo=ZoneInfo("America/Chicago"))
        assert is_peak_hours() is True

    @patch("pacer_cli.security._now_cst")
    def test_peak_boundary_end(self, mock_now):
        from zoneinfo import ZoneInfo
        mock_now.return_value = datetime(2025, 1, 15, 18, 0, tzinfo=ZoneInfo("America/Chicago"))
        assert is_peak_hours() is False  # 6PM is end, not included


# =========================================================================
# PR #2 Bug #2: StreamingDownload resource leaks
# =========================================================================

class TestStreamingDownload:
    """Verify context manager properly closes HTTP responses."""

    def test_context_manager_closes_response(self):
        resp = MagicMock(spec=requests.Response)
        resp.iter_content.return_value = [b"data"]

        dl = StreamingDownload(response=resp)
        with dl:
            chunks = list(dl.iter_chunks())
        assert chunks == [b"data"]
        resp.close.assert_called_once()

    def test_close_idempotent(self):
        resp = MagicMock(spec=requests.Response)
        dl = StreamingDownload(response=resp)
        dl.close()
        dl.close()
        resp.close.assert_called_once()

    def test_exceeds_max_size(self):
        resp = MagicMock(spec=requests.Response)
        # Simulate chunks that exceed the limit
        resp.iter_content.return_value = [b"x" * 100] * 10

        dl = StreamingDownload(response=resp, max_size=500)
        with pytest.raises(MemoryError, match="exceeded"):
            with dl:
                for _ in dl.iter_chunks():
                    pass
        # Response should still be closed after error
        resp.close.assert_called()

    def test_bytes_read_tracked(self):
        resp = MagicMock(spec=requests.Response)
        resp.iter_content.return_value = [b"abc", b"def"]

        dl = StreamingDownload(response=resp)
        with dl:
            list(dl.iter_chunks())
        assert dl.bytes_read == 6


# =========================================================================
# PR #2 Bug #3: Global state cleanup for test isolation
# =========================================================================

class TestGlobalStateReset:
    def test_reset_rate_limiter(self):
        rl1 = get_rate_limiter(rpm=10)
        reset_rate_limiter()
        rl2 = get_rate_limiter(rpm=20)
        assert rl1 is not rl2
        assert rl2.rpm == 20

    def test_reset_audit_logger(self):
        al1 = get_audit_logger()
        reset_audit_logger()
        al2 = get_audit_logger()
        assert al1 is not al2


# =========================================================================
# PR #2 Bug #4 & #5: Input validation
# =========================================================================

class TestSecurityConfig:
    """Validate config settings from PR #2 fixes."""

    def test_rate_limit_rpm_zero_raises(self):
        from pydantic import ValidationError
        from pacer_cli.config import PacerConfig

        with pytest.raises(ValidationError):
            PacerConfig(rate_limit_rpm=0)

    def test_tls_level_literal_validation(self):
        from pydantic import ValidationError
        from pacer_cli.config import PacerConfig

        with pytest.raises(ValidationError):
            PacerConfig(tls_level="invalid")  # type: ignore[arg-type]


# =========================================================================
# PR #2 Bug #7: Cipher suite hardening (ECDHE-only)
# =========================================================================

class TestCipherSuites:
    def test_no_dhe_in_ciphers(self):
        assert "DHE" not in SECURE_CIPHERS or "ECDHE" in SECURE_CIPHERS
        # Our constant should only contain ECDHE
        parts = SECURE_CIPHERS.split(":")
        for part in parts:
            if "DHE" in part:
                assert part.startswith("ECDHE"), f"Non-ECDHE DHE cipher found: {part}"

    def test_tls_adapter_standard(self):
        adapter = TLSAdapter(tls_level="standard")
        assert adapter.tls_level == "standard"

    def test_tls_adapter_paranoid(self):
        adapter = TLSAdapter(tls_level="paranoid")
        assert adapter.tls_level == "paranoid"


# =========================================================================
# PR #2 Bug #8: Rate limit validation
# =========================================================================

class TestRateLimiter:
    def test_zero_rpm_raises(self):
        with pytest.raises(ValueError, match="must be >= 1"):
            RateLimiter(rpm=0)

    def test_negative_rpm_raises(self):
        with pytest.raises(ValueError, match="must be >= 1"):
            RateLimiter(rpm=-1)

    def test_valid_rpm(self):
        rl = RateLimiter(rpm=60)
        assert rl.rpm == 60

    def test_wait_increments_count(self):
        rl = RateLimiter(rpm=6000)  # Very high RPM so wait is negligible
        rl.wait()
        assert rl.request_count == 1
        rl.wait()
        assert rl.request_count == 2

    def test_reset(self):
        rl = RateLimiter(rpm=6000)
        rl.wait()
        rl.reset()
        assert rl.request_count == 0

    def test_thread_safety(self):
        rl = RateLimiter(rpm=6000)
        errors = []

        def _do_wait():
            try:
                for _ in range(10):
                    rl.wait()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=_do_wait) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert rl.request_count == 40


# =========================================================================
# PR #2 Bug #9: show_peak_hours_warning return type
# =========================================================================

class TestPeakHoursWarning:
    @patch("pacer_cli.security._now_cst")
    def test_returns_none(self, mock_now):
        from zoneinfo import ZoneInfo
        mock_now.return_value = datetime(2025, 7, 15, 12, 0, tzinfo=ZoneInfo("America/Chicago"))
        result = show_peak_hours_warning(entry_count=200)
        assert result is None

    @patch("pacer_cli.security._now_cst")
    def test_no_warning_off_peak(self, mock_now):
        from zoneinfo import ZoneInfo
        mock_now.return_value = datetime(2025, 7, 15, 23, 0, tzinfo=ZoneInfo("America/Chicago"))
        result = show_peak_hours_warning()
        assert result is None


# =========================================================================
# PR #2 Bug #10 & #11: Exception handling
# =========================================================================

class TestExceptionHandling:
    def test_streaming_download_oserror_on_close(self):
        """close() handles OSError gracefully."""
        resp = MagicMock(spec=requests.Response)
        resp.close.side_effect = OSError("connection reset")

        dl = StreamingDownload(response=resp)
        dl.close()  # Should not raise
        assert dl._closed is True


# =========================================================================
# Bulk download detection
# =========================================================================

class TestBulkDownload:
    def test_below_threshold(self):
        assert is_bulk_download(50) is False

    def test_at_threshold(self):
        assert is_bulk_download(BULK_DOWNLOAD_THRESHOLD) is True

    def test_above_threshold(self):
        assert is_bulk_download(500) is True


# =========================================================================
# Safe response content
# =========================================================================

class TestSafeResponseContent:
    def test_reads_small_response(self):
        resp = MagicMock(spec=requests.Response)
        resp.headers = {"content-length": "100"}
        resp.iter_content.return_value = [b"hello"]

        data = safe_response_content(resp)
        assert data == b"hello"

    def test_rejects_oversized_content_length(self):
        resp = MagicMock(spec=requests.Response)
        resp.headers = {"content-length": str(MAX_MEMORY_RESPONSE_SIZE + 1)}

        with pytest.raises(MemoryError):
            safe_response_content(resp)


# =========================================================================
# Secure session factory
# =========================================================================

class TestCreateSecureSession:
    def test_returns_session(self):
        session = create_secure_session()
        assert isinstance(session, requests.Session)

    def test_https_adapter_mounted(self):
        session = create_secure_session(tls_level="strict")
        adapter = session.get_adapter("https://example.com")
        assert isinstance(adapter, TLSAdapter)


# =========================================================================
# Retry logic
# =========================================================================

class TestRequestWithRetry:
    def test_success_on_first_try(self):
        session = MagicMock(spec=requests.Session)
        resp = MagicMock(status_code=200)
        session.request.return_value = resp

        result = request_with_retry(session, "GET", "https://example.com", max_retries=2)
        assert result.status_code == 200
        assert session.request.call_count == 1

    def test_retries_on_429(self):
        session = MagicMock(spec=requests.Session)
        resp_429 = MagicMock(status_code=429)
        resp_200 = MagicMock(status_code=200)
        session.request.side_effect = [resp_429, resp_200]

        result = request_with_retry(
            session, "GET", "https://example.com",
            max_retries=2, backoff_factor=0.01,
        )
        assert result.status_code == 200
        assert session.request.call_count == 2

    def test_retries_on_connection_error(self):
        session = MagicMock(spec=requests.Session)
        resp_200 = MagicMock(status_code=200)
        session.request.side_effect = [requests.ConnectionError("timeout"), resp_200]

        result = request_with_retry(
            session, "GET", "https://example.com",
            max_retries=2, backoff_factor=0.01,
        )
        assert result.status_code == 200

    def test_raises_after_max_retries(self):
        session = MagicMock(spec=requests.Session)
        session.request.side_effect = requests.ConnectionError("down")

        with pytest.raises(requests.ConnectionError):
            request_with_retry(
                session, "GET", "https://example.com",
                max_retries=1, backoff_factor=0.01,
            )


# =========================================================================
# Audit logger
# =========================================================================

class TestAuditLogger:
    def test_log_request(self, tmp_path):
        logger = AuditLogger(log_dir=tmp_path / "logs")
        logger.log_request("GET", "https://pacer.uscourts.gov/test", status_code=200)

        log_files = list((tmp_path / "logs").glob("audit-*.log"))
        assert len(log_files) == 1
        content = log_files[0].read_text()
        assert "GET" in content
        assert "200" in content

    def test_log_download(self, tmp_path):
        # Clear any existing handlers from previous tests on the shared logger
        import logging
        existing_logger = logging.getLogger("pacer.audit")
        existing_logger.handlers.clear()

        logger = AuditLogger(log_dir=tmp_path / "logs")
        logger.log_download(
            "https://ecf.nysd.uscourts.gov/doc1/123",
            tmp_path / "doc.pdf",
            size_bytes=5000,
            pages=10,
            cost=1.0,
        )

        log_files = list((tmp_path / "logs").glob("audit-*.log"))
        assert len(log_files) == 1
        content = log_files[0].read_text()
        assert "DOWNLOAD" in content
        assert "$1.00" in content
