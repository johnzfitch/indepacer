"""Root conftest — prevent pytest from collecting test-like functions from source modules."""

import indepacer.auth


# Prevent pytest from collecting test_credentials from auth.py
# (it matches pytest's test function naming convention)
indepacer.auth.test_credentials.__test__ = False  # type: ignore[attr-defined]
