# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.2.x   | :white_check_mark: |
| < 0.2   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in pacer-cli, please report it responsibly:

1. **Do not** open a public issue
2. Use [GitHub's private vulnerability reporting](https://github.com/johnzfitch/pacer-cli/security/advisories/new)
3. Or email the maintainer directly

We will respond within 48 hours and aim to publish a fix within 7 days for critical issues.

## Security Measures

This project implements the following security measures:

- **TLS 1.2+ enforcement** — All connections to PACER use TLS 1.2 or higher with ECDHE-only cipher suites
- **Credential protection** — Passwords stored using Pydantic `SecretStr`, config files created with `0600` permissions
- **Rate limiting** — Configurable request throttling (default 30 RPM) to protect federal court systems
- **Input validation** — Pydantic models with field validators; no shell injection or eval
- **Audit logging** — All PACER operations logged for billing reconciliation
- **Automated security tests** — `test_security_review.py` scans for common vulnerability patterns on every CI run
