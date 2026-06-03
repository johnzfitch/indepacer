"""PACER-native MCP server - the governed client, exposed over Model Context Protocol.

This is a thin adapter, not new business logic. Every billable tool routes through
the SAME preventive cap as the CLI (``security.check_spend`` summed from the audit
log) and writes the same audit line, so an MCP-driven agent obeys one cap and leaves
one trail.

Invariants (identical to the CLI):
  * Caps change only via the human-edited ``policy.csv`` / ``courts.csv``. Nothing here
    writes them - an agent cannot widen its own reach.
  * Login stays human-in-the-loop: credentials come from env / ``config.env`` (or a
    pre-unlocked vault). This server never prompts, never auto-unlocks the vault.
  * A cap breach returns a structured MCP error mirroring the CLI's ``_deny`` JSON.

The ``mcp`` SDK is an optional dependency (``pip install -e '.[mcp]'``); importing this
module does not require it - only :func:`main` / :func:`build_server` do.
"""

from __future__ import annotations

from typing import Any, Optional

from .config import PacerConfig, PolicyError, apply_policy_csv, get_config
from .courts import resolve_court_scope
from .security import (
    GovernanceError,
    check_spend,
    get_audit_logger,
    spend_today,
)

# Cost model, mirrored from cli.py (kept local to avoid importing the click layer).
COST_PER_PAGE = 0.10
PCL_SEARCH_MAX = 3.00  # PACER caps a single search/report fee at $3.00


# ---------------------------------------------------------------------------
# Shared governance plumbing (pure, testable without the mcp SDK or a network)
# ---------------------------------------------------------------------------


def _load_config(client_code: Optional[str] = None) -> PacerConfig:
    """Config with the policy.csv overlay applied (human-provisioned creds only)."""
    cfg = get_config()  # env / config.env; never prompts, never unlocks the vault
    cfg = apply_policy_csv(cfg)  # may raise ValueError on a fat-fingered CSV (fail-closed)
    if client_code:
        cfg.client_code = client_code
    return cfg


def _guard(cfg: PacerConfig, operation: str, estimated_cost: float) -> None:
    """Run the preventive cap. Raises GovernanceError on a breach."""
    check_spend(
        cfg,
        estimated_cost,
        prior_spend=spend_today(),
        client_code=cfg.client_code,
    )


def _audit(cfg: PacerConfig, url: str, cost: float) -> None:
    if cost > 0:
        get_audit_logger().log_request(
            "POST", url, status_code=200, cost=cost, client_code=cfg.client_code
        )


def error_payload(operation: str, exc: Exception) -> dict[str, Any]:
    """Map a refusal to the same JSON shape the CLI's ``_deny`` emits."""
    if isinstance(exc, GovernanceError):  # budget / matter / scope refusals
        return {"error": exc.error_key.upper(), "operation": operation, **exc.fields}
    if isinstance(exc, PolicyError):  # unparseable policy.csv -> fail-closed
        return {"error": "POLICY_INVALID", "operation": operation, "reason": str(exc)}
    if isinstance(exc, ValueError):  # bad tool arguments (e.g. missing criteria)
        return {"error": "INVALID_ARGUMENT", "operation": operation, "reason": str(exc)}
    return {"error": "INTERNAL", "operation": operation, "reason": str(exc)}


# ---------------------------------------------------------------------------
# Tool implementations (return JSON-able dicts; raise on refusal)
# ---------------------------------------------------------------------------


def spend_status() -> dict[str, Any]:
    """Today's spend vs. the active caps - a read-only budget view (no billing)."""
    cfg = _load_config()
    spent = spend_today()
    return {
        "spent_today": spent,
        "per_op_cap": cfg.per_op_cap_usd,
        "daily_cap": cfg.daily_cap_usd,
        "remaining_today": round(max(0.0, cfg.daily_cap_usd - spent), 2),
        "require_client_code": cfg.require_client_code,
    }


def search_cases(
    case_number: Optional[str] = None,
    title: Optional[str] = None,
    court: Optional[list[str]] = None,
    client_code: Optional[str] = None,
) -> dict[str, Any]:
    """Search the PACER Case Locator for cases (billable; gated by the spend cap)."""
    from .models import CaseSearchCriteria
    from .pcl import PCLClient

    cfg = _load_config(client_code)
    scoped = resolve_court_scope(court)  # open / scoped / raises on empty scope
    criteria = CaseSearchCriteria(caseNumberFull=case_number, caseTitle=title, courtId=scoped)
    if not criteria.to_api_dict():
        raise ValueError("at least one search criterion is required")

    _guard(cfg, "search cases", COST_PER_PAGE)
    response = PCLClient(cfg).search_cases(criteria)
    fee = float(response.receipt.search_fee) if response.receipt and response.receipt.search_fee else 0.0
    _audit(cfg, "POST /cases/find", fee)
    return {
        "cost": fee,
        "count": len(response.content),
        "results": [r.model_dump(by_alias=True, exclude_none=True) for r in response.content],
    }


def search_parties(
    last_name: Optional[str] = None,
    first_name: Optional[str] = None,
    court: Optional[list[str]] = None,
    client_code: Optional[str] = None,
) -> dict[str, Any]:
    """Search the PACER Case Locator for parties (billable; gated by the spend cap)."""
    from .models import CaseSearchCriteria, PartySearchCriteria
    from .pcl import PCLClient

    cfg = _load_config(client_code)
    scoped = resolve_court_scope(court)  # open / scoped / raises on empty scope
    case_criteria = CaseSearchCriteria(courtId=scoped) if scoped else None
    criteria = PartySearchCriteria(
        lastName=last_name, firstName=first_name, courtCase=case_criteria
    )
    if not criteria.to_api_dict():
        raise ValueError("at least one search criterion is required")

    _guard(cfg, "search parties", COST_PER_PAGE)
    response = PCLClient(cfg).search_parties(criteria)
    fee = float(response.receipt.search_fee) if response.receipt and response.receipt.search_fee else 0.0
    _audit(cfg, "POST /parties/find", fee)
    return {
        "cost": fee,
        "count": len(response.content),
        "results": [r.model_dump(by_alias=True, exclude_none=True) for r in response.content],
    }


def get_docket(
    case_number: str,
    court_id: str,
    client_code: Optional[str] = None,
) -> dict[str, Any]:
    """Download a case docket (billable; gated). Returns the saved path + page count."""
    from .downloader import DocketDownloader

    cfg = _load_config(client_code)
    court_normalized = court_id.lower().rstrip("e").rstrip("c")
    case_dir = cfg.get_case_dir(court_normalized, case_number)
    case_dir.mkdir(parents=True, exist_ok=True)

    _guard(cfg, "download docket", 5 * COST_PER_PAGE)
    result = DocketDownloader(cfg).download_docket_by_case_number(
        case_number, court_id, case_dir, filename="docket.html"
    )
    if not result.success:
        raise RuntimeError(result.error or "docket download failed")
    cost = float(result.cost or 0.0)
    _audit(cfg, f"docket {court_normalized}/{case_number}", cost)
    return {"path": str(result.filepath), "pages": int(result.pages or 0), "cost": cost}


def get_document(
    doc_link: str,
    doc_number: str = "0",
    client_code: Optional[str] = None,
) -> dict[str, Any]:
    """Download a single document by CM/ECF link (billable; gated)."""
    from .downloader import DocumentDownloader

    cfg = _load_config(client_code)
    out_dir = cfg.document_archive.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    _guard(cfg, "download document", 10 * COST_PER_PAGE)
    result = DocumentDownloader(cfg).download_document(
        doc_link, out_dir, f"doc{doc_number}.pdf"
    )
    if not result.success:
        raise RuntimeError(result.error or "document download failed")
    cost = float(result.cost or 0.0)
    _audit(cfg, f"document {doc_number}", cost)
    return {"path": str(result.filepath), "pages": int(result.pages or 0), "cost": cost}


# ---------------------------------------------------------------------------
# MCP wiring (requires the optional `mcp` SDK)
# ---------------------------------------------------------------------------

# Tool name -> (callable, "operation" label for error payloads).
_BILLABLE_TOOLS = {
    "search_cases": (search_cases, "search cases"),
    "search_parties": (search_parties, "search parties"),
    "get_docket": (get_docket, "download docket"),
    "get_document": (get_document, "download document"),
}


def build_server():
    """Construct the FastMCP server. Imports the optional `mcp` SDK lazily."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise SystemExit(
            "The MCP server needs the optional 'mcp' extra: pip install -e '.[mcp]'"
        ) from exc

    server = FastMCP("pacer")

    def _wrap(fn, operation):
        def tool(**kwargs):
            try:
                return fn(**kwargs)
            except Exception as exc:  # convert refusals to a structured MCP error
                payload = error_payload(operation, exc)
                from mcp.server.fastmcp.exceptions import ToolError

                raise ToolError(__import__("json").dumps(payload)) from exc

        tool.__name__ = fn.__name__
        tool.__doc__ = fn.__doc__
        return tool

    for name, (fn, operation) in _BILLABLE_TOOLS.items():
        server.tool(name=name)(_wrap(fn, operation))

    # spend_status is read-only (no billing) -> exposed as a resource and a tool.
    server.tool(name="spend_status")(spend_status)
    server.resource("pacer://spend")(spend_status)

    return server


def main() -> None:
    """Console entry point: run the stdio MCP server."""
    build_server().run()


if __name__ == "__main__":
    main()
