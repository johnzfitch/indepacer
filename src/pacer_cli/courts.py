"""Court lookup utilities using PACER court data.

Provides mappings between ECF domains, court IDs, and CSO court IDs
using the official PACER court lookup data.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional


@lru_cache(maxsize=1)
def _load_court_data() -> list[dict[str, Any]]:
    """Load and cache court lookup data from JSON file."""
    data_path = Path(__file__).parent / "data" / "court-lookup.json"
    with open(data_path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("data", [])


@lru_cache(maxsize=256)
def get_court_by_ecf_domain(ecf_domain: str) -> Optional[dict[str, Any]]:
    """Look up court info by ECF domain name.

    Args:
        ecf_domain: ECF domain like 'nysd', 'cacd', 'ca1'
                    (extracted from ecf.{domain}.uscourts.gov)

    Returns:
        Court data dict or None if not found
    """
    ecf_domain = ecf_domain.lower()

    for court in _load_court_data():
        login_url = court.get("login_url", "")
        # Extract domain from login_url like https://ecf.nysd.uscourts.gov
        match = re.search(r"ecf\.([a-z0-9]+)\.uscourts\.gov", login_url.lower())
        if match and match.group(1) == ecf_domain:
            return court

    return None


@lru_cache(maxsize=256)
def get_court_by_id(court_id: str) -> Optional[dict[str, Any]]:
    """Look up court info by court ID.

    Args:
        court_id: Court ID like 'NYSDC', 'CACDC', '01CA'

    Returns:
        Court data dict or None if not found
    """
    court_id_upper = court_id.upper()

    for court in _load_court_data():
        if court.get("court_id", "").upper() == court_id_upper:
            return court

    return None


def get_cso_court_id(ecf_domain: str) -> Optional[str]:
    """Get CSO court ID from ECF domain.

    Args:
        ecf_domain: ECF domain like 'nysd', 'cacd', 'ca1'

    Returns:
        CSO court ID like 'NYSDC', 'CACDC', '01CA' or None

    Example:
        >>> get_cso_court_id('nysd')
        'NYSDC'
        >>> get_cso_court_id('cacd')
        'CACDC'
    """
    court = get_court_by_ecf_domain(ecf_domain)
    return court.get("court_id") if court else None


def get_ecf_url(court_id: str) -> Optional[str]:
    """Get ECF login URL from court ID.

    Args:
        court_id: Court ID like 'NYSDC', 'CACDC'

    Returns:
        ECF URL like 'https://ecf.nysd.uscourts.gov' or None

    Example:
        >>> get_ecf_url('NYSDC')
        'https://ecf.nysd.uscourts.gov'
    """
    court = get_court_by_id(court_id)
    return court.get("login_url") if court else None


def get_ecf_domain_from_url(url: str) -> Optional[str]:
    """Extract ECF domain from a URL.

    Args:
        url: Any URL containing ecf.{domain}.uscourts.gov

    Returns:
        Domain like 'nysd', 'cacd' or None

    Example:
        >>> get_ecf_domain_from_url('https://ecf.nysd.uscourts.gov/doc1/123')
        'nysd'
    """
    match = re.search(r"ecf\.([a-z0-9]+)\.uscourts\.gov", url.lower())
    return match.group(1) if match else None


def get_court_name(court_id: str) -> Optional[str]:
    """Get human-readable court name.

    Args:
        court_id: Court ID like 'NYSDC'

    Returns:
        Court name like 'Southern District of New York' or None
    """
    court = get_court_by_id(court_id)
    return court.get("court_name") or court.get("title") if court else None


def get_court_type(court_id: str) -> Optional[str]:
    """Get court type (District, Bankruptcy, Appeals).

    Args:
        court_id: Court ID like 'NYSDC'

    Returns:
        Court type string or None
    """
    court = get_court_by_id(court_id)
    return court.get("type") if court else None


def list_courts(court_type: Optional[str] = None) -> list[dict[str, str]]:
    """List all courts, optionally filtered by type.

    Args:
        court_type: Optional filter: 'District', 'Bankruptcy', 'Appeals'

    Returns:
        List of dicts with 'court_id', 'name', 'login_url', 'type'
    """
    result = []
    for court in _load_court_data():
        if court_type and court.get("type") != court_type:
            continue

        result.append({
            "court_id": court.get("court_id", ""),
            "name": court.get("court_name") or court.get("title", ""),
            "login_url": court.get("login_url", ""),
            "type": court.get("type", ""),
        })

    return result


def normalize_court_id(court_id: str) -> Optional[str]:
    """Normalize various court ID formats to CSO format.

    Handles:
    - 'nysdce' -> 'NYSDC' (PCL format with 'e' suffix)
    - 'nysd' -> 'NYSDC' (ECF domain)
    - 'NYSDC' -> 'NYSDC' (already correct)

    Args:
        court_id: Court ID in any format

    Returns:
        Normalized CSO court ID or None
    """
    court_id = court_id.upper()

    # Already a valid CSO ID?
    if get_court_by_id(court_id):
        return court_id

    # Try stripping common suffixes (PCL format: 'nysdce' -> 'nysdc')
    for suffix in ("E", "CE", "KE"):
        if court_id.endswith(suffix):
            stripped = court_id[:-len(suffix)]
            # Try adding 'C' back (for district courts)
            candidate = stripped + "C"
            if get_court_by_id(candidate):
                return candidate

    # Try as ECF domain
    cso_id = get_cso_court_id(court_id.lower())
    if cso_id:
        return cso_id

    return None


# ---------------------------------------------------------------------------
# Court search scoping (~/.pacer/config/courts.csv)
# ---------------------------------------------------------------------------
#
# A firm that practices in a few districts shouldn't pay for nationwide PCL
# hits. court is a real PCL filter (CaseSearchCriteria.court_id), so a simple
# human-edited enable/disable list scopes searches. The CSV is human-edited and
# agent-read-only — same invariant as policy.csv (an agent can't widen its own
# reach).


def _courts_csv_path() -> "Path":
    # Imported lazily to avoid a courts <-> config import cycle at module load.
    from .config import PACER_ROOT

    return PACER_ROOT / "config" / "courts.csv"


@lru_cache(maxsize=1)
def all_search_court_ids() -> list[str]:
    """All PCL/ECF-style court IDs (e.g. 'nysd') derived from login URLs.

    These are the IDs CaseSearchCriteria.court_id expects, parsed from each
    court's ecf.{domain}.uscourts.gov login URL. Courts without an ECF login
    URL (e.g. the PCL portal itself) are omitted.
    """
    ids = set()
    for court in _load_court_data():
        m = re.search(r"ecf\.([a-z0-9]+)\.uscourts\.gov", court.get("login_url", "").lower())
        if m:
            ids.add(m.group(1))
    return sorted(ids)


def read_courts_scope() -> dict[str, bool]:
    """Read courts.csv -> {court_id: enabled}. Empty dict if the file is absent."""
    path = _courts_csv_path()
    if not path.exists():
        return {}
    import csv as _csv

    scope: dict[str, bool] = {}
    with path.open(encoding="utf-8") as fh:
        for row in _csv.reader(fh):
            if not row or row[0].strip().lower() in ("court_id", ""):
                continue
            enabled = row[1].strip() if len(row) > 1 else "1"
            scope[row[0].strip().lower()] = enabled not in ("0", "", "no", "false")
    return scope


def write_courts_scope(scope: dict[str, bool]) -> "Path":
    """Write {court_id: enabled} to courts.csv (sorted), creating dirs as needed."""
    path = _courts_csv_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    import csv as _csv

    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = _csv.writer(fh)
        writer.writerow(["court_id", "enabled"])
        for cid in sorted(scope):
            writer.writerow([cid, "1" if scope[cid] else "0"])
    return path


def enabled_court_ids() -> Optional[list[str]]:
    """Enabled court IDs for scoping a search, or None for no scope (nationwide).

    Raw view used by ``pacer courts status``: None when courts.csv is absent or
    every known court is enabled; an empty list when the file disables
    everything. The search path uses :func:`resolve_court_scope`, which turns
    that empty list into a refusal rather than a silent nationwide search.
    """
    scope = read_courts_scope()
    if not scope:
        return None
    enabled = sorted(cid for cid, on in scope.items() if on)
    universe = set(all_search_court_ids())
    if not enabled:
        return enabled  # explicit empty -> resolve_court_scope() refuses
    # If everything known is enabled and nothing is disabled, treat as nationwide.
    if set(enabled) >= universe and all(scope.values()):
        return None
    return enabled


def resolve_court_scope(explicit_courts) -> Optional[list[str]]:
    """The single open/off switch for scoping a billable search.

    One source of truth so callers never re-implement the rule (which is how an
    empty scope leaked through as a nationwide search). Returns:
      * a non-empty list — explicit ``--court`` wins, else the enabled subset;
      * ``None`` — search everywhere (no scope file, or every court enabled);
    and **raises** ``ScopeError`` when courts.csv disables every court, so an
    empty scope fails closed instead of silently widening to nationwide.
    """
    from .security import ScopeError  # local import: courts is lower-level than security

    if explicit_courts:
        return list(explicit_courts)
    ids = enabled_court_ids()
    if ids == []:
        raise ScopeError("courts.csv disables every court; no courts in scope")
    return ids
