"""Tests for PACER authentication."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from indepacer.auth import AuthResult, authenticate, generate_totp, logout, test_credentials
from indepacer.config import PacerConfig


class TestGenerateTotp:
    def test_returns_6_digit_string(self):
        # Standard test secret
        code = generate_totp("JBSWY3DPEHPK3PXP")
        assert len(code) == 6
        assert code.isdigit()


class TestAuthenticate:
    def test_missing_credentials(self):
        cfg = PacerConfig(_env_file=None)
        result = authenticate(cfg)
        assert result.success is False
        assert "not configured" in result.error

    @patch("indepacer.auth.requests.post")
    def test_successful_auth(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "loginResult": "0",
            "nextGenCSO": "token123" * 16,
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        cfg = PacerConfig(username="user", password="pass")
        result = authenticate(cfg)
        assert result.success is True
        assert result.token is not None

    @patch("indepacer.auth.requests.post")
    def test_failed_auth(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "loginResult": "1",
            "errorDescription": "Invalid credentials",
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        cfg = PacerConfig(username="user", password="wrongpass")
        result = authenticate(cfg)
        assert result.success is False

    @patch("indepacer.auth.requests.post")
    def test_network_error(self, mock_post):
        mock_post.side_effect = requests.ConnectionError("timeout")

        cfg = PacerConfig(username="user", password="pass")
        result = authenticate(cfg)
        assert result.success is False
        assert "Network error" in result.error


class TestLogout:
    @patch("indepacer.auth.requests.post")
    def test_successful_logout(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"loginResult": "0"}
        mock_post.return_value = mock_resp

        cfg = PacerConfig()
        assert logout(cfg, "sometoken") is True

    @patch("indepacer.auth.requests.post")
    def test_failed_logout(self, mock_post):
        mock_post.side_effect = Exception("network error")

        cfg = PacerConfig()
        assert logout(cfg, "sometoken") is False


class TestTestCredentials:
    @patch("indepacer.auth.logout")
    @patch("indepacer.auth.authenticate")
    def test_authenticates_and_logs_out(self, mock_auth, mock_logout):
        mock_auth.return_value = AuthResult(success=True, token="token123")
        mock_logout.return_value = True

        cfg = PacerConfig(username="user", password="pass")
        result = test_credentials(cfg)
        assert result.success is True
        mock_logout.assert_called_once()
