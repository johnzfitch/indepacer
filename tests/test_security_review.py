"""Security review tests — static checks for common vulnerabilities.

These tests scan the codebase for security anti-patterns covering:
- Credential handling (no hardcoded secrets, proper file permissions)
- Input validation (no SQL injection vectors, no shell injection)
- TLS configuration (no disabled verification, no weak protocols)
- Dependency safety (no known-bad patterns)
- OWASP Top 10 relevant checks
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).parent.parent / "src" / "indepacer"
PY_FILES = list(SRC_DIR.glob("*.py"))


def _read_all_source() -> list[tuple[Path, str]]:
    """Read all Python source files."""
    return [(p, p.read_text(encoding="utf-8")) for p in PY_FILES]


# =========================================================================
# Credential Safety
# =========================================================================

class TestCredentialSafety:
    """Ensure credentials are never hardcoded or logged."""

    def test_no_hardcoded_passwords(self):
        patterns = [
            r'password\s*=\s*["\'][^"\']+["\']',
            r'secret\s*=\s*["\'][A-Za-z0-9+/=]{8,}["\']',
            r'token\s*=\s*["\'][A-Za-z0-9]{20,}["\']',
        ]
        for filepath, content in _read_all_source():
            for pattern in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    # Allow default/placeholder values and type hints
                    if any(ok in match.lower() for ok in [
                        'none', '""', "''", "password.get_secret",
                        "testpass", "testuser", 'example',
                    ]):
                        continue
                    assert False, (
                        f"Potential hardcoded credential in {filepath.name}: {match}"
                    )

    def test_config_file_permissions_set(self):
        """save_credentials should set restrictive permissions (0o600)."""
        config_src = (SRC_DIR / "config.py").read_text()
        assert "0o600" in config_src or "0600" in config_src, (
            "Credential file should be written with mode 600"
        )

    def test_password_uses_secret_str(self):
        """Password field should use Pydantic SecretStr to prevent accidental logging."""
        config_src = (SRC_DIR / "config.py").read_text()
        assert "SecretStr" in config_src
        # Check password field uses SecretStr
        assert re.search(r"password.*SecretStr", config_src), (
            "password field should use SecretStr type"
        )

    def test_totp_secret_uses_secret_str(self):
        config_src = (SRC_DIR / "config.py").read_text()
        assert re.search(r"totp_secret.*SecretStr", config_src), (
            "totp_secret field should use SecretStr type"
        )


# =========================================================================
# TLS / Network Security
# =========================================================================

class TestTLSSecurity:
    """Ensure proper TLS configuration."""

    def test_no_verify_false(self):
        """Never disable TLS certificate verification."""
        for filepath, content in _read_all_source():
            assert "verify=False" not in content, (
                f"TLS verification disabled in {filepath.name}"
            )
            assert "verify = False" not in content, (
                f"TLS verification disabled in {filepath.name}"
            )

    def test_no_ssl_no_check(self):
        """No environment-based SSL bypass."""
        for filepath, content in _read_all_source():
            assert "CURL_CA_BUNDLE" not in content
            assert "REQUESTS_CA_BUNDLE" not in content

    def test_minimum_tls_version(self):
        """Security module enforces TLS 1.2+."""
        sec_src = (SRC_DIR / "security.py").read_text()
        assert "TLSv1_2" in sec_src or "TLSv1.2" in sec_src, (
            "Security module should enforce minimum TLS 1.2"
        )

    def test_no_deprecated_protocols(self):
        """No SSLv2, SSLv3, or TLS 1.0/1.1 usage."""
        for filepath, content in _read_all_source():
            for proto in ["SSLv2", "SSLv3", "PROTOCOL_SSLv2", "PROTOCOL_SSLv3"]:
                assert proto not in content, (
                    f"Deprecated protocol {proto} in {filepath.name}"
                )

    def test_secure_cipher_suites(self):
        """Only ECDHE ciphers (no deprecated DHE)."""
        sec_src = (SRC_DIR / "security.py").read_text()
        cipher_match = re.search(r'SECURE_CIPHERS\s*=\s*"([^"]+)"', sec_src)
        assert cipher_match, "SECURE_CIPHERS constant not found"
        ciphers = cipher_match.group(1)
        for suite in ciphers.split(":"):
            if "DHE" in suite:
                assert suite.startswith("ECDHE"), (
                    f"Non-ECDHE cipher suite found: {suite}"
                )


# =========================================================================
# Input Validation
# =========================================================================

class TestInputValidation:
    """Check for injection vulnerabilities."""

    def test_no_shell_injection(self):
        """No os.system(), subprocess with shell=True, or eval()."""
        for filepath, content in _read_all_source():
            assert "os.system(" not in content, (
                f"os.system() in {filepath.name} — use subprocess instead"
            )
            assert "shell=True" not in content, (
                f"shell=True in {filepath.name} — command injection risk"
            )
            # eval is sometimes in comments; check actual calls
            if "eval(" in content:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name) and node.func.id == "eval":
                            assert False, f"eval() call in {filepath.name}"

    def test_no_format_string_sql(self):
        """No f-string or format SQL queries (not applicable but defensive check)."""
        sql_patterns = [
            r'f["\'].*SELECT.*FROM.*{',
            r'f["\'].*INSERT.*INTO.*{',
            r'f["\'].*DELETE.*FROM.*{',
            r'\.format\(.*SELECT',
        ]
        for filepath, content in _read_all_source():
            for pattern in sql_patterns:
                assert not re.search(pattern, content, re.IGNORECASE), (
                    f"Potential SQL injection in {filepath.name}"
                )

    def test_url_construction_uses_urljoin(self):
        """Verify URL construction uses urljoin or similar safe methods."""
        # downloader.py should import urljoin
        dl_src = (SRC_DIR / "downloader.py").read_text()
        assert "urljoin" in dl_src, "downloader.py should use urljoin for URL construction"


# =========================================================================
# Error Handling
# =========================================================================

class TestErrorHandling:
    """Check for proper error handling patterns."""

    def test_no_bare_except_in_security(self):
        """Security module should use specific exception types."""
        sec_src = (SRC_DIR / "security.py").read_text()
        tree = ast.parse(sec_src)
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    # Bare except: — check context
                    assert False, (
                        f"Bare except in security.py at line {node.lineno}"
                    )

    def test_auth_returns_errors_not_raises(self):
        """Auth module should return AuthResult, not raise on auth failure."""
        auth_src = (SRC_DIR / "auth.py").read_text()
        # The authenticate function should catch exceptions and return AuthResult
        assert "AuthResult(" in auth_src
        assert "except" in auth_src

    def test_network_timeouts_set(self):
        """All HTTP requests should have explicit timeouts."""
        for filepath, content in _read_all_source():
            if filepath.name in ("security.py", "auth.py", "downloader.py", "pcl.py"):
                # These files make HTTP requests — they should set timeout
                if "requests." in content or "session." in content:
                    if ".get(" in content or ".post(" in content:
                        assert "timeout" in content, (
                            f"HTTP requests without timeout in {filepath.name}"
                        )


# =========================================================================
# Rate Limiting
# =========================================================================

class TestRateLimitingReview:
    """Verify rate limiting protects PACER resources."""

    def test_rate_limiter_exists(self):
        sec_src = (SRC_DIR / "security.py").read_text()
        assert "RateLimiter" in sec_src

    def test_default_rpm_reasonable(self):
        """Default rate should be <= 60 RPM to be respectful of PACER."""
        from indepacer.security import DEFAULT_RATE_LIMIT_RPM
        assert DEFAULT_RATE_LIMIT_RPM <= 60

    def test_rate_limit_configurable(self):
        """Rate limit should be configurable via config."""
        config_src = (SRC_DIR / "config.py").read_text()
        assert "rate_limit_rpm" in config_src


# =========================================================================
# Audit Logging
# =========================================================================

class TestAuditLoggingReview:
    def test_audit_logger_exists(self):
        sec_src = (SRC_DIR / "security.py").read_text()
        assert "AuditLogger" in sec_src

    def test_audit_log_configurable(self):
        config_src = (SRC_DIR / "config.py").read_text()
        assert "audit_log" in config_src


# =========================================================================
# Dependency Review
# =========================================================================

class TestDependencyReview:
    """Check pyproject.toml for dependency safety."""

    def test_pinned_minimum_versions(self):
        """All dependencies should have minimum version pins."""
        pyproject = (Path(__file__).parent.parent / "pyproject.toml").read_text()
        # All deps should use >= not ==
        deps_section = re.search(r'dependencies\s*=\s*\[(.*?)\]', pyproject, re.DOTALL)
        assert deps_section, "dependencies section not found"
        deps = deps_section.group(1)
        for line in deps.strip().split("\n"):
            line = line.strip().strip('"').strip("',")
            if line:
                assert ">=" in line, f"Dependency missing minimum version: {line}"

    def test_no_wildcard_versions(self):
        pyproject = (Path(__file__).parent.parent / "pyproject.toml").read_text()
        assert '"*"' not in pyproject, "Wildcard dependency versions are unsafe"

    def test_dev_deps_separate(self):
        """Dev dependencies should be in optional-dependencies, not main."""
        pyproject = (Path(__file__).parent.parent / "pyproject.toml").read_text()
        assert "[project.optional-dependencies]" in pyproject
        # pytest should not be in main dependencies
        main_deps = re.search(r'^dependencies\s*=\s*\[(.*?)\]', pyproject, re.DOTALL | re.MULTILINE)
        if main_deps:
            assert "pytest" not in main_deps.group(1)
