# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-03-07

### Added

- **Auth init wizard** (`pacer auth init`) - Interactive setup with MFA validation, encrypted vault, and credential testing
- **TOTP code generator** (`pacer auth code`) - Generate codes for manual PACER login or MFA removal
- **Encrypted credential vault** - AES-256-GCM encryption with Scrypt KDF for secure credential storage
- **Inline TOTP implementation** - Replaced `pyotp` dependency with stdlib-only RFC 6238 implementation
- **Security module** - TLS hardening, rate limiting, audit logging
- **QA environment support** - `--qa` flag for testing against PACER QA servers

### Changed

- `pacer auth login` now redirects to init wizard if no credentials exist
- Vault passphrase prompted automatically when vault exists
- Encrypted storage enabled by default in setup wizard
- Scrypt parameters lowered (2^14) for broader compatibility, configurable via env vars

### Fixed

- QA TOTP fallback to production secret when QA secret not set
- `get_config_from_vault` no longer leaks credentials to environment variables
- `time_step <= 0` validation in TOTP generation
- Empty vault passphrase rejection (minimum 8 characters)
- Cross-platform atomic file writes with `os.replace()`
- Deprecated `datetime.utcnow()` calls replaced with timezone-aware versions
- Test isolation with `_env_file=None`

### Security

- Removed leaked TOTP secrets from documentation
- Added `*secret*.txt`, `*key*.txt` to gitignore
- KDF parameters now stored in vault for future migration compatibility

## [0.1.0] - 2024-12-01

### Added

- Initial release
- PCL case and party search
- Docket and document downloads
- Local archive with hierarchical structure
- Context-aware commands
- Rich CLI with aliases
