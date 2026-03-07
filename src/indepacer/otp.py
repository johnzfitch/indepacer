"""TOTP implementation using only Python stdlib.

Replaces pyotp dependency with ~20 lines of code.
Implements RFC 6238 (TOTP) and RFC 4226 (HOTP).
"""

from base64 import b32decode
from hmac import new as hmac_new
from struct import pack, unpack
from time import time


def hotp(secret: str, counter: int, digits: int = 6) -> str:
    """Generate HMAC-based One-Time Password (RFC 4226).

    Args:
        secret: Base32-encoded shared secret
        counter: 8-byte counter value
        digits: Number of digits in OTP (default 6)

    Returns:
        OTP as zero-padded string

    Raises:
        ValueError: If secret is empty or digits < 1
    """
    if not secret:
        raise ValueError("Secret cannot be empty")
    if digits < 1:
        raise ValueError("Digits must be at least 1")

    # Decode base32 secret (add padding if needed)
    key = b32decode(secret.upper() + "=" * ((8 - len(secret)) % 8))

    # HMAC-SHA1 of counter
    counter_bytes = pack(">Q", counter)
    mac = hmac_new(key, counter_bytes, "sha1").digest()

    # Dynamic truncation
    offset = mac[-1] & 0x0F
    binary = unpack(">L", mac[offset : offset + 4])[0] & 0x7FFFFFFF

    # Extract digits
    return str(binary)[-digits:].zfill(digits)


def totp(secret: str, time_step: int = 30, digits: int = 6) -> str:
    """Generate Time-based One-Time Password (RFC 6238).

    Args:
        secret: Base32-encoded shared secret (from PACER MFA setup)
        time_step: Time step in seconds (default 30)
        digits: Number of digits in OTP (default 6)

    Returns:
        Current OTP as zero-padded string

    Raises:
        ValueError: If secret is empty or time_step is 0
        ZeroDivisionError: If time_step is 0
    """
    counter = int(time() // time_step)
    return hotp(secret, counter, digits)


# Alias for compatibility with existing code
def generate_totp(secret: str) -> str:
    """Generate current TOTP code from secret.

    This is the main entry point, matching the pyotp interface.

    Args:
        secret: Base32-encoded TOTP secret from PACER MFA setup

    Returns:
        6-digit TOTP code as string
    """
    return totp(secret, time_step=30, digits=6)
