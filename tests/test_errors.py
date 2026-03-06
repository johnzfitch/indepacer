"""Tests for error handling and classification."""

from __future__ import annotations

import pytest

from indepacer.errors import (
    ERRORS,
    classify_download_error,
    classify_pcl_error,
    show_error,
)


class TestErrorCatalog:
    def test_all_keys_have_context(self):
        for key, ctx in ERRORS.items():
            assert ctx.title, f"Missing title for {key}"
            assert ctx.message, f"Missing message for {key}"
            assert ctx.suggestions, f"Missing suggestions for {key}"

    def test_known_keys_exist(self):
        expected = [
            "auth_missing", "auth_failed", "mfa_required",
            "case_not_found", "network_error", "context_not_set",
        ]
        for key in expected:
            assert key in ERRORS


class TestClassifyDownloadError:
    def test_not_found(self):
        key, _ = classify_download_error("Case not found in court")
        assert key == "case_not_found"

    def test_auth(self):
        key, _ = classify_download_error("Authentication failed")
        assert key == "auth_failed"

    def test_network(self):
        key, _ = classify_download_error("Network timeout occurred")
        assert key == "network_error"

    def test_generic(self):
        key, _ = classify_download_error("Something unexpected")
        assert key == "network_error"


class TestClassifyPclError:
    def test_auth_error(self):
        from indepacer.pcl import PCLAuthError
        key, _ = classify_pcl_error(PCLAuthError("bad token"))
        assert key == "auth_failed"

    def test_mfa_error(self):
        from indepacer.pcl import PCLAuthError
        key, _ = classify_pcl_error(PCLAuthError("MFA required"))
        assert key == "mfa_required"

    def test_validation_error(self):
        from indepacer.pcl import PCLValidationError
        key, _ = classify_pcl_error(PCLValidationError("bad params"))
        assert key == "pcl_validation"

    def test_not_found_error(self):
        from indepacer.pcl import PCLNotFoundError
        key, _ = classify_pcl_error(PCLNotFoundError("no case"))
        assert key == "case_not_found"


class TestShowError:
    def test_known_key(self, capsys):
        show_error("auth_missing")
        # Should not raise

    def test_unknown_key(self, capsys):
        show_error("nonexistent_key", detail="something went wrong")
        # Should not raise

    def test_with_extra_suggestions(self, capsys):
        show_error("auth_failed", extra_suggestions=["Try again later"])
        # Should not raise
