"""Shared fixtures for indepacer tests."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from indepacer.config import PacerConfig
from indepacer.docket_types import DocketEntry, DocketMeta, ParsedDocket, Party


# ---------------------------------------------------------------------------
# Environment isolation
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch, tmp_path):
    """Ensure tests don't touch real PACER config or home directory."""
    monkeypatch.setenv("HOME", str(tmp_path))
    # Clear any PACER_ env vars that could leak into PacerConfig
    for key in list(os.environ):
        if key.startswith("PACER_"):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture(autouse=True)
def _reset_security_globals():
    """Reset module-level singletons between tests."""
    from indepacer.security import reset_audit_logger, reset_rate_limiter

    reset_rate_limiter()
    reset_audit_logger()
    yield
    reset_rate_limiter()
    reset_audit_logger()


# ---------------------------------------------------------------------------
# Config fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def pacer_config(tmp_path: Path) -> PacerConfig:
    """Minimal PacerConfig with temp dirs (no real credentials)."""
    return PacerConfig(
        username="testuser",
        password="testpass",
        archive_root=tmp_path / "archives",
        output_dir=tmp_path / "output",
    )


@pytest.fixture
def pacer_config_mfa(pacer_config: PacerConfig) -> PacerConfig:
    """PacerConfig with MFA enabled."""
    return PacerConfig(
        username=pacer_config.username,
        password=pacer_config.password,
        totp_secret="JBSWY3DPEHPK3PXP",  # well-known test secret
        archive_root=pacer_config.archive_root,
    )


# ---------------------------------------------------------------------------
# Docket fixtures
# ---------------------------------------------------------------------------

SAMPLE_DOCKET_HTML = """
<html>
<head><title>CM/ECF - nysd</title></head>
<body>
<h3>CASE #: 1:18-cv-08434-VEC-SLC</h3>
<table width='100%' border=0 CELLSPACING=5>
<tr><td width='60%'>
Apple Inc. v. Samsung Electronics Co.<br>
Assigned to: Judge Vernon S. Broderick<br>
Cause: 28:1332 Diversity
</td>
<td width='40%'>
Date Filed: 09/15/2018<br>
Nature of Suit: 442 Civil Rights: Jobs<br>
Jurisdiction: Federal Question
</td></tr>
</table>
<table rules='all'>
<tr><td>09/15/2018</td><td><a href='/doc1/123'>1</a></td><td><!--SB-->COMPLAINT filed</td></tr>
<tr><td>09/20/2018</td><td><a href='/doc1/124'>2</a></td><td><!--SB-->MOTION to dismiss</td></tr>
<tr><td>10/01/2018</td><td>3</td><td><!--SB-->ORDER denying motion</td></tr>
</table>
</body></html>
"""


@pytest.fixture
def sample_docket_html() -> str:
    return SAMPLE_DOCKET_HTML


@pytest.fixture
def sample_docket() -> ParsedDocket:
    """Pre-built ParsedDocket for tests that don't need parsing."""
    meta = DocketMeta(
        court_id="nysd",
        case_number="1:18-cv-08434-VEC-SLC",
        case_title="Apple Inc. v. Samsung Electronics Co.",
        date_filed="2018-09-15",
        judge="Judge Vernon S. Broderick",
        nature_of_suit="442",
        nos_description="Civil Rights: Jobs",
    )
    entries = [
        DocketEntry(seq=0, date="2018-09-15", doc_num="1", doc_url="/doc1/123", text="COMPLAINT filed"),
        DocketEntry(seq=1, date="2018-09-20", doc_num="2", doc_url="/doc1/124", text="MOTION to dismiss"),
        DocketEntry(seq=2, date="2018-10-01", doc_num="3", text="ORDER denying motion"),
    ]
    return ParsedDocket(meta=meta, entries=entries, parties=[])


@pytest.fixture
def sample_docket_file(tmp_path: Path, sample_docket_html: str) -> Path:
    """Write sample HTML to a temp file and return the path."""
    p = tmp_path / "docket.html"
    p.write_text(sample_docket_html, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Network fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session():
    """A mock requests.Session that never hits the network."""
    with patch("requests.Session") as cls:
        session = MagicMock(spec=requests.Session)
        cls.return_value = session
        yield session


@pytest.fixture
def mock_response():
    """Factory for mock HTTP responses."""

    def _make(
        status_code: int = 200,
        json_data: dict | None = None,
        text: str = "",
        content: bytes = b"",
        headers: dict | None = None,
        url: str = "https://example.com",
    ) -> MagicMock:
        resp = MagicMock(spec=requests.Response)
        resp.status_code = status_code
        resp.text = text or json.dumps(json_data or {})
        resp.content = content or resp.text.encode()
        resp.headers = headers or {"content-type": "application/json"}
        resp.url = url
        resp.json.return_value = json_data or {}
        resp.ok = 200 <= status_code < 400
        resp.raise_for_status.side_effect = (
            None if resp.ok else requests.HTTPError(response=resp)
        )
        return resp

    return _make
