"""PACER Authentication using the official API with MFA support.

This module implements authentication against the PACER API as documented in
the PACER Authentication API User Guide (May 2025).

For MFA-enabled accounts, you can either:
1. Store the TOTP secret for automatic code generation
2. Provide a one-time code manually at login time
"""

from dataclasses import dataclass
from typing import Optional

import requests

from .config import PacerConfig


@dataclass
class AuthResult:
    """Result of PACER authentication attempt."""

    success: bool
    token: Optional[str] = None  # nextGenCSO 128-byte token
    error: Optional[str] = None
    login_result: str = ""


def generate_totp(secret: str) -> str:
    """Generate current TOTP code from secret.

    Args:
        secret: Base32-encoded TOTP secret from PACER MFA setup

    Returns:
        6-digit TOTP code as string
    """
    from .otp import totp
    return totp(secret)


def authenticate(
    config: PacerConfig,
    otp_code: Optional[str] = None,
) -> AuthResult:
    """Authenticate with PACER and get session token.

    Args:
        config: PACER configuration with credentials
        otp_code: Manual OTP code (if not using stored TOTP secret)

    Returns:
        AuthResult with token on success, error message on failure
    """
    if not config.username or not config.password:
        return AuthResult(
            success=False,
            error="PACER credentials not configured. Run: pacer auth login",
        )

    # Build request payload
    payload = {
        "loginId": config.username,
        "password": config.password.get_secret_value(),
    }

    # Add OTP code if MFA is configured or provided
    if otp_code:
        payload["otpCode"] = otp_code
    elif config.has_mfa and config.active_totp_secret:
        payload["otpCode"] = generate_totp(config.active_totp_secret.get_secret_value())

    # Add optional client code
    if config.client_code:
        payload["clientCode"] = config.client_code

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        response = requests.post(
            config.auth_url,
            json=payload,
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        token = data.get("nextGenCSO", "")
        login_result = data.get("loginResult", "")
        error_desc = data.get("errorDescription", "")

        # loginResult "0" = success
        if login_result == "0" and token:
            return AuthResult(
                success=True,
                token=token,
                login_result=login_result,
                error=error_desc if error_desc else None,  # May have warnings
            )
        else:
            return AuthResult(
                success=False,
                login_result=login_result,
                error=error_desc or f"Authentication failed (code: {login_result})",
            )

    except requests.exceptions.RequestException as e:
        return AuthResult(
            success=False,
            error=f"Network error during authentication: {e}",
        )
    except Exception as e:
        return AuthResult(
            success=False,
            error=f"Authentication error: {e}",
        )


def logout(config: PacerConfig, token: str) -> bool:
    """Invalidate a PACER session token.

    Args:
        config: PACER configuration
        token: The nextGenCSO token to invalidate

    Returns:
        True if logout successful
    """
    from .config import PACER_LOGOUT_URL

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    payload = {"nextGenCSO": token}

    try:
        response = requests.post(
            PACER_LOGOUT_URL,
            json=payload,
            headers=headers,
            timeout=30,
        )
        data = response.json()
        return data.get("loginResult") == "0"
    except Exception:
        return False


def test_credentials(config: PacerConfig, otp_code: Optional[str] = None) -> AuthResult:
    """Test PACER credentials without keeping the session.

    Authenticates and immediately logs out to verify credentials work.

    Args:
        config: PACER configuration
        otp_code: Manual OTP code if needed

    Returns:
        AuthResult indicating if credentials are valid
    """
    result = authenticate(config, otp_code)

    if result.success and result.token:
        logout(config, result.token)

    return result
