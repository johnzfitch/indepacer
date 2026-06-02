"""User-friendly error handling with actionable next steps."""

from dataclasses import dataclass
from typing import List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel

err_console = Console(stderr=True)


@dataclass
class ErrorContext:
    """Rich error context with suggestions."""

    title: str
    message: str
    suggestions: List[str]
    docs_link: Optional[str] = None


# Error catalog
ERRORS = {
    "budget_exceeded": ErrorContext(
        title="Budget Cap Reached",
        message="This operation would exceed a spend cap in policy.csv.",
        suggestions=[
            "Raise the cap in [cyan]~/.pacer/config/policy.csv[/]",
            "Check today's spend in [cyan]~/.pacer/logs/[/]",
        ],
    ),
    "matter_required": ErrorContext(
        title="Client/Matter Code Required",
        message="policy.csv requires a client/matter code for billable operations.",
        suggestions=[
            "Add: [cyan]--matter MATTER-1234[/]",
            "Or set a default via [cyan]pacer auth login --client-code …[/]",
        ],
    ),
    "policy_invalid": ErrorContext(
        title="Policy File Unparseable",
        message="A value in policy.csv could not be parsed; billable ops are blocked (fail-closed).",
        suggestions=[
            "Fix the offending row in [cyan]~/.pacer/config/policy.csv[/]",
            "Dollar caps must be plain numbers, e.g. [cyan]5.00[/]",
        ],
    ),
    "auth_missing": ErrorContext(
        title="Credentials Not Configured",
        message="PACER credentials are required for this operation.",
        suggestions=[
            "Run: [cyan]pacer auth login[/]",
            "Or set environment variables: PACER_USERNAME, PACER_PASSWORD",
        ],
    ),
    "auth_failed": ErrorContext(
        title="Authentication Failed",
        message="Could not authenticate with PACER servers.",
        suggestions=[
            "Verify credentials: [cyan]pacer auth status[/]",
            "Test connection: [cyan]pacer auth test[/]",
            "Re-enter credentials: [cyan]pacer auth login[/]",
        ],
    ),
    "mfa_required": ErrorContext(
        title="MFA Required",
        message="Your PACER account requires multi-factor authentication.",
        suggestions=[
            "Configure MFA: [cyan]pacer auth setup-mfa[/]",
            "Get TOTP secret from PACER 'Manage My Account' page",
        ],
    ),
    "mfa_invalid": ErrorContext(
        title="Invalid MFA Code",
        message="The TOTP code was rejected.",
        suggestions=[
            "Check your device clock is synchronized",
            "Verify TOTP secret: [cyan]pacer auth setup-mfa[/]",
            "Try with manual OTP: [cyan]pacer auth test --otp CODE[/]",
        ],
    ),
    "case_not_found": ErrorContext(
        title="Case Not Found",
        message="No matching case was found in PACER.",
        suggestions=[
            "Search by title: [cyan]pacer pcl cases -t 'PARTY NAME'[/]",
            "Try different court: [cyan]pacer pcl cases -c COURT_ID[/]",
            "Check case number format (e.g., 1:20-cv-12345)",
            "View court list: [cyan]pacer courts[/]",
        ],
    ),
    "case_not_downloaded": ErrorContext(
        title="Docket Not Downloaded",
        message="This case is not in the local archive.",
        suggestions=[
            "Download docket: [cyan]pacer download docket CASE_NUM COURT[/]",
            "Or with case link: [cyan]pacer download docket -l URL[/]",
        ],
    ),
    "network_error": ErrorContext(
        title="Network Error",
        message="Could not connect to PACER servers.",
        suggestions=[
            "Check internet connection",
            "Retry the command",
            "PACER status: https://pacer.uscourts.gov",
        ],
    ),
    "pcl_validation": ErrorContext(
        title="Invalid Search Parameters",
        message="PCL API rejected the search criteria.",
        suggestions=[
            "Check date format (YYYY-MM-DD)",
            "Verify court ID: [cyan]pacer courts[/]",
            "View search options: [cyan]pacer pcl cases --help[/]",
        ],
    ),
    "context_not_set": ErrorContext(
        title="No Context Set",
        message="No active case context is set.",
        suggestions=[
            "Set context: [cyan]pacer use case COURT CASE_NUMBER[/]",
            "Or provide arguments explicitly",
            "View current context: [cyan]pacer use status[/]",
        ],
    ),
    "docs_not_found": ErrorContext(
        title="Document Manifest Not Found",
        message="No docs.json file found for this case.",
        suggestions=[
            "Re-download the docket to generate it",
            "Download docket: [cyan]pacer download docket CASE_NUM COURT[/]",
        ],
    ),
    "parse_error": ErrorContext(
        title="Parse Error",
        message="Could not parse the docket file.",
        suggestions=[
            "The docket HTML may be invalid or corrupted",
            "Try re-downloading the docket",
            "Check if the file exists and is readable",
        ],
    ),
}


def show_error(
    error_key: str,
    detail: Optional[str] = None,
    extra_suggestions: Optional[List[str]] = None,
):
    """Display a rich error panel with suggestions.

    Args:
        error_key: Key from ERRORS catalog
        detail: Additional detail message
        extra_suggestions: Additional suggestions to append
    """
    ctx = ERRORS.get(error_key)
    if not ctx:
        err_console.print(f"[red]Error:[/] {detail or error_key}")
        return

    message = ctx.message
    if detail:
        message += f"\n[dim]{detail}[/]"

    suggestions = ctx.suggestions.copy()
    if extra_suggestions:
        suggestions.extend(extra_suggestions)

    suggestion_text = "\n".join(f"  {s}" for s in suggestions)

    panel_content = f"{message}\n\n[bold]Next steps:[/]\n{suggestion_text}"

    err_console.print(
        Panel(
            panel_content,
            title=f"[red]{ctx.title}[/]",
            border_style="red",
        )
    )


def classify_pcl_error(error: Exception) -> Tuple[str, str]:
    """Classify PCL exceptions to error keys.

    Args:
        error: Exception from PCL operations

    Returns:
        Tuple of (error_key, detail_message)
    """
    # Import here to avoid circular imports
    from .pcl import PCLAuthError, PCLError, PCLNotFoundError, PCLValidationError

    error_str = str(error)

    if isinstance(error, PCLAuthError):
        if "MFA" in error_str or "OTP" in error_str:
            return "mfa_required", error_str
        return "auth_failed", error_str
    elif isinstance(error, PCLValidationError):
        return "pcl_validation", error_str
    elif isinstance(error, PCLNotFoundError):
        return "case_not_found", error_str
    elif "Network" in error_str or "timeout" in error_str.lower():
        return "network_error", error_str
    elif isinstance(error, PCLError):
        return "auth_failed", error_str
    else:
        return "network_error", error_str


def classify_download_error(error_message: str) -> Tuple[str, str]:
    """Classify download error messages to error keys.

    Args:
        error_message: Error message from download result

    Returns:
        Tuple of (error_key, detail_message)
    """
    error_lower = error_message.lower()

    if "not found" in error_lower:
        return "case_not_found", error_message
    elif "auth" in error_lower or "login" in error_lower:
        return "auth_failed", error_message
    elif "network" in error_lower or "timeout" in error_lower:
        return "network_error", error_message
    else:
        return "network_error", error_message
