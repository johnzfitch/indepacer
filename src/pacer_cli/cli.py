"""PACER CLI - Command-line interface for legal document research."""

import csv
import re
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

from .config import (
    ContextConfig,
    PacerConfig,
    check_legacy_archive,
    clear_credentials,
    ensure_dirs,
    get_config,
    get_config_from_vault,
    mark_migration_complete,
    migration_marker_exists,
    save_credentials,
    vault_exists,
)
from .security import BULK_DOWNLOAD_THRESHOLD, show_peak_hours_warning

console = Console()
err_console = Console(stderr=True)


# ============================================================================
# COMMAND ALIAS SUPPORT
# ============================================================================

# Maps short aliases to full command paths
COMMAND_ALIASES = {
    # Top-level shortcuts
    "docket": ["download", "docket"],
    "doc": ["download", "document"],
    "grep": ["search"],
    "find": ["search"],
    
    # Alternative PCL shortcuts
    "cases": ["pcl", "cases"],
    "parties": ["pcl", "parties"],
}


class AliasGroup(click.Group):
    """Click Group that supports command aliases.
    
    Allows users to use shorter command names that map to full paths.
    Example: 'pacer docket' -> 'pacer download docket'
    """
    
    def get_command(self, ctx: click.Context, cmd_name: str) -> Optional[click.Command]:
        # Try exact match first
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv
        
        # Check if it's an alias
        if cmd_name in COMMAND_ALIASES:
            alias_path = COMMAND_ALIASES[cmd_name]
            
            # For single-element paths, just look up directly
            if len(alias_path) == 1:
                return click.Group.get_command(self, ctx, alias_path[0])
            
            # For multi-part paths (e.g., ["download", "docket"]),
            # navigate through subgroups
            current_group = self
            for i, part in enumerate(alias_path[:-1]):
                sub_cmd = click.Group.get_command(current_group, ctx, part)
                if sub_cmd is None or not isinstance(sub_cmd, click.Group):
                    return None
                current_group = sub_cmd
            
            return click.Group.get_command(current_group, ctx, alias_path[-1])
        
        return None
    
    def resolve_command(self, ctx: click.Context, args: list) -> tuple:
        """Resolve command, handling multi-part aliases."""
        cmd_name = args[0] if args else None
        
        if cmd_name and cmd_name in COMMAND_ALIASES:
            alias_path = COMMAND_ALIASES[cmd_name]
            
            # Get the actual command
            cmd = self.get_command(ctx, cmd_name)
            if cmd:
                return cmd_name, cmd, args[1:]
        
        return super().resolve_command(ctx, args)
    
    def format_commands(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        """Add aliases section to help output."""
        super().format_commands(ctx, formatter)
        
        # Show aliases in help
        with formatter.section("Aliases"):
            alias_rows = []
            for alias, path in sorted(COMMAND_ALIASES.items()):
                full_cmd = " ".join(path)
                alias_rows.append((alias, f"→ {full_cmd}"))
            formatter.write_dl(alias_rows)


# ============================================================================
# COST CONFIRMATION HELPERS
# ============================================================================


def confirm_cost(
    ctx: click.Context,
    operation: str,
    estimated_cost: float,
    details: Optional[str] = None,
) -> bool:
    """Prompt user to confirm a billable operation.

    Args:
        ctx: Click context (checks ctx.obj["auto_confirm"])
        operation: Description of operation (e.g., "Download docket")
        estimated_cost: Estimated cost in dollars
        details: Additional details to show

    Returns:
        True if user confirms or auto_confirm is set, False otherwise
    """
    if ctx.obj.get("auto_confirm"):
        return True

    console.print()
    content = f"[bold]{operation}[/bold]\nEstimated cost: [yellow]${estimated_cost:.2f}[/yellow]"
    if details:
        content += f"\n\n{details}"

    console.print(Panel(content, title="Billable Operation", border_style="yellow"))

    return click.confirm("Proceed?", default=True)


def confirm_cost_pages(
    ctx: click.Context,
    operation: str,
    pages: int,
    cost_per_page: float = 0.10,
    details: Optional[str] = None,
) -> bool:
    """Prompt for page-based cost confirmation.

    Args:
        ctx: Click context
        operation: Description of operation
        pages: Estimated number of pages
        cost_per_page: Cost per page (default $0.10)
        details: Additional details

    Returns:
        True if user confirms or auto_confirm is set
    """
    estimated_cost = pages * cost_per_page
    page_info = f"~{pages} page(s) @ ${cost_per_page:.2f}/page"
    full_details = f"{page_info}\n{details}" if details else page_info
    return confirm_cost(ctx, operation, estimated_cost, full_details)


@click.group(cls=AliasGroup)
@click.version_option()
@click.option("--yes", "-y", is_flag=True, help="Skip cost confirmation prompts")
@click.pass_context
def cli(ctx, yes: bool):
    """PACER CLI - Download, parse, and search federal court documents.

    A command-line interface for the PACER (Public Access to Court Electronic
    Records) system. Streamlines legal research by automating docket downloads,
    document retrieval, and data extraction.

    \b
    Quick start:
      pacer auth login               Configure PACER credentials
      pacer docket nysd 1:18-cv-08434   Download a docket
      pacer view                     View the downloaded docket
      pacer doc 31                   Download document #31

    \b
    Short aliases:
      pacer docket   →  pacer download docket
      pacer doc      →  pacer download document  
      pacer grep     →  pacer search
      pacer cases    →  pacer pcl cases
      pacer parties  →  pacer pcl parties

    \b
    Cost confirmation:
      By default, prompts before billable operations.
      Use --yes / -y to skip confirmation (for scripting).
    """
    ctx.ensure_object(dict)

    # Load config - check vault first
    if vault_exists():
        from rich.prompt import Prompt
        try:
            passphrase = Prompt.ask("[dim]Vault passphrase[/]", password=True)
            ctx.obj["config"] = get_config_from_vault(passphrase)
        except Exception as e:
            err_console.print(f"[red]Failed to unlock vault:[/] {e}")
            err_console.print("[dim]Using config file fallback...[/]")
            ctx.obj["config"] = get_config()
    else:
        ctx.obj["config"] = get_config()

    ctx.obj["auto_confirm"] = yes
    
    # Check for legacy archive on first run (unless migrated)
    if not migration_marker_exists():
        legacy_path = check_legacy_archive()
        if legacy_path:
            legacy_count = len(list(legacy_path.glob("*.html")))
            if legacy_count > 0:
                console.print()
                console.print(Panel(
                    f"[yellow]Found {legacy_count} files in legacy archive format.[/]\n\n"
                    f"Run [cyan]pacer migrate[/] to reorganize into the new structure:\n"
                    f"  ~/.pacer/<court>/<case>/docket.html\n\n"
                    f"[dim]This enables context-aware commands and doc link caching.[/]",
                    title="Migration Available",
                    border_style="yellow",
                ))


# ============================================================================
# MIGRATE COMMAND
# ============================================================================


@cli.command("migrate")
@click.option("--dry-run", is_flag=True, help="Show what would be moved without moving")
@click.option("--legacy-dir", type=click.Path(exists=True, path_type=Path), help="Legacy archive directory")
@click.pass_context
def migrate_archive(ctx, dry_run: bool, legacy_dir: Optional[Path]):
    """Migrate from legacy flat archive to new hierarchical structure.

    \b
    Moves files from:
      ./results/local_docket_archive/nysdce_1+2018cv08434.html

    \b
    To:
      ~/.pacer/nysd/1-2018cv08434/docket.html

    Also generates docs.json for each docket (enables auto-resolution of doc links).

    \b
    Examples:
      pacer migrate --dry-run          # Preview changes
      pacer migrate                    # Perform migration
      pacer migrate --legacy-dir ./old # Migrate from custom location
    """
    from .parser import parse_docket
    from .downloader import extract_document_metadata
    
    config: PacerConfig = ctx.obj["config"]
    
    # Find legacy files
    source_dir = legacy_dir or config.docket_archive
    if not source_dir.exists():
        console.print(f"[yellow]No legacy archive found at:[/] {source_dir}")
        return
    
    # Pattern: {court}_{case}.html where case has + for :
    legacy_pattern = re.compile(r"^([a-z]{2,5}dce)_(.+)\.html$")
    
    files_to_migrate = []
    for html_file in source_dir.glob("*.html"):
        match = legacy_pattern.match(html_file.name)
        if match:
            court_id = match.group(1)
            case_raw = match.group(2)
            # Normalize: nysdce -> nysd, 1+2018cv08434 -> 1-2018cv08434
            court_normalized = court_id.rstrip("e").rstrip("c")
            case_normalized = case_raw.replace("+", "-").replace(":", "-")
            files_to_migrate.append({
                "source": html_file,
                "court": court_normalized,
                "case": case_normalized,
                "target_dir": config.archive_root / court_normalized / case_normalized,
            })
    
    if not files_to_migrate:
        console.print("[yellow]No legacy docket files found to migrate.[/]")
        if not dry_run:
            mark_migration_complete()
        return
    
    console.print(f"[cyan]Found {len(files_to_migrate)} dockets to migrate[/]\n")
    
    if dry_run:
        table = Table(title="Migration Preview")
        table.add_column("Source", style="dim")
        table.add_column("Target", style="green")
        
        for item in files_to_migrate[:20]:
            table.add_row(
                item["source"].name,
                str(item["target_dir"] / "docket.html"),
            )
        
        console.print(table)
        if len(files_to_migrate) > 20:
            console.print(f"[dim]... and {len(files_to_migrate) - 20} more[/]")
        
        console.print(f"\n[dim]Run without --dry-run to perform migration.[/]")
        return
    
    # Perform migration
    migrated = 0
    skipped = 0
    errors = 0
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Migrating dockets...", total=len(files_to_migrate))
        
        for item in files_to_migrate:
            try:
                target_dir = item["target_dir"]
                target_html = target_dir / "docket.html"
                
                # Skip if already migrated
                if target_html.exists():
                    skipped += 1
                    progress.advance(task)
                    continue
                
                # Create target directory
                target_dir.mkdir(parents=True, exist_ok=True)
                
                # Copy docket file
                source_html = item["source"]
                html_content = source_html.read_text(encoding="utf-8", errors="ignore")
                target_html.write_text(html_content, encoding="utf-8")
                
                # Generate docs.json from the docket
                try:
                    import json
                    # Construct base URL from court ID (e.g., nysd -> https://ecf.nysd.uscourts.gov)
                    base_url = f"https://ecf.{item['court']}.uscourts.gov"

                    docs_data = extract_document_metadata(
                        html_content,
                        base_url,
                        case_number=item["case"],
                        court_id=item["court"],
                    )

                    if docs_data.get("documents"):
                        docs_json = target_dir / "docs.json"
                        docs_json.write_text(json.dumps(docs_data, indent=2))
                except Exception:
                    # docs.json generation failed, but docket copy still succeeds
                    pass
                
                migrated += 1
                
            except Exception as e:
                err_console.print(f"[red]Error migrating {item['source'].name}:[/] {e}")
                errors += 1
            
            progress.advance(task)
    
    console.print()
    console.print(f"[green]Migrated:[/] {migrated} dockets")
    if skipped:
        console.print(f"[dim]Skipped:[/] {skipped} (already exist)")
    if errors:
        console.print(f"[red]Errors:[/] {errors}")
    
    console.print(f"\n[dim]New archive location:[/] {config.archive_root}")
    
    # Mark migration complete
    mark_migration_complete()
    
    console.print()
    console.print(Panel(
        "[green]Migration complete![/]\n\n"
        "You can now use context-aware commands:\n"
        "  [cyan]pacer use case nysd 1-2018cv08434[/]\n"
        "  [cyan]pacer view[/]\n"
        "  [cyan]pacer doc 31[/]  (auto-resolves link)\n\n"
        "[dim]Legacy files were copied (not moved). Delete manually if desired.[/]",
        title="Next Steps",
        border_style="green",
    ))


# ============================================================================
# AUTH COMMANDS
# ============================================================================


@cli.group()
def auth():
    """Manage PACER authentication credentials."""
    pass


@auth.command("init")
@click.option("--qa", is_flag=True, help="Configure for QA environment instead of production")
@click.option("--no-vault", is_flag=True, help="Skip encrypted vault (use plain config file)")
@click.pass_context
def auth_init(ctx, qa: bool, no_vault: bool):
    """Interactive setup wizard for PACER credentials.

    \b
    Guides you through:
      1. Username and password
      2. MFA setup (if enabled on your PACER account)
      3. Encrypted vault setup (recommended)
      4. Credential verification against PACER servers

    \b
    Example:
      pacer auth init              # Production setup (encrypted by default)
      pacer auth init --qa         # QA environment setup
      pacer auth init --no-vault   # Skip encryption (not recommended)
    """
    from rich.prompt import Confirm, Prompt

    from .auth import authenticate, generate_totp, logout

    env_name = "QA" if qa else "Production"
    console.print(Panel(
        f"[bold]PACER Credential Setup[/] - {env_name} Environment\n\n"
        "This wizard will configure your PACER credentials and verify they work.",
        title="Setup Wizard",
        border_style="blue",
    ))

    # Step 1: Username and password
    console.print("\n[bold cyan]Step 1:[/] Enter your PACER credentials\n")
    username = Prompt.ask("  PACER Username")
    password = Prompt.ask("  PACER Password", password=True)

    # Step 2: MFA
    console.print("\n[bold cyan]Step 2:[/] Multi-Factor Authentication\n")
    console.print("  [dim]If MFA is enabled on your PACER account, you'll need the Base32[/]")
    console.print("  [dim]secret from PACER's 'Manage My Account' → MFA setup page.[/]")
    console.print("  [dim]This is the text shown below the QR code (not the QR code itself).[/]\n")

    has_mfa = Confirm.ask("  Is MFA enabled on your PACER account?", default=False)
    totp_secret = None

    if has_mfa:
        while True:
            totp_secret = Prompt.ask("  TOTP Secret (Base32 string)").strip().upper()
            if not totp_secret:
                console.print("  [yellow]Skipping MFA setup.[/]")
                totp_secret = None
                break

            # Validate by generating a code
            try:
                code = generate_totp(totp_secret)
                console.print(f"  [green]Valid![/] Current code: [bold]{code}[/]")
                console.print("  [dim]This code should match what you'd see in Authy/Google Authenticator.[/]")
                if Confirm.ask("  Does this code look correct?", default=True):
                    break
                else:
                    console.print("  [yellow]Let's try again.[/]")
            except Exception as e:
                console.print(f"  [red]Invalid secret:[/] {e}")
                console.print("  [dim]The secret should be a Base32 string (letters A-Z and digits 2-7).[/]")
                if not Confirm.ask("  Try again?", default=True):
                    totp_secret = None
                    break

    # Step 3: Vault encryption (default: enabled)
    passphrase = None
    if no_vault:
        console.print("\n[bold cyan]Step 3:[/] Storage\n")
        console.print("  [yellow]Skipping encryption (--no-vault specified)[/]")
        console.print("  [dim]Credentials will be stored in plain text at ~/.config/pacer-cli/config.env[/]")
    else:
        console.print("\n[bold cyan]Step 3:[/] Encrypted Storage (Recommended)\n")
        console.print("  [dim]Your credentials will be encrypted with AES-256-GCM.[/]")
        console.print("  [dim]You'll need this passphrase when using pacer.[/]\n")

        use_vault = Confirm.ask("  Enable encrypted vault?", default=True)
        if use_vault:
            while True:
                passphrase = Prompt.ask("  Vault passphrase (min 8 chars)", password=True)
                if len(passphrase) < 8:
                    console.print("  [red]Passphrase must be at least 8 characters.[/]")
                    continue
                confirm = Prompt.ask("  Confirm passphrase", password=True)
                if passphrase != confirm:
                    console.print("  [red]Passphrases don't match.[/]")
                    continue
                break
        else:
            console.print("  [yellow]Credentials will be stored in plain text.[/]")

    # Step 4: Test connection
    console.print("\n[bold cyan]Step 4:[/] Verifying credentials with PACER...\n")

    # Build test config
    test_config = PacerConfig(
        username=username,
        password=password,
        totp_secret=totp_secret,
        use_qa=qa,
        _env_file=None,
    )

    with console.status("  Authenticating...", spinner="dots"):
        result = authenticate(test_config)

    if result.success:
        console.print("  [green]Authentication successful![/]")
        # Logout cleanly
        logout(test_config, result.token)
    else:
        console.print(f"  [red]Authentication failed:[/] {result.error}")
        if not Confirm.ask("\n  Save credentials anyway?", default=False):
            console.print("[yellow]Setup cancelled.[/]")
            return

    # Step 5: Save credentials
    console.print("\n[bold cyan]Step 5:[/] Saving credentials...\n")
    try:
        config_path = save_credentials(
            username=username,
            password=password,
            totp_secret=totp_secret,
            client_code=None,
            vault_passphrase=passphrase,
        )
        storage_type = "encrypted vault" if passphrase else "config file"
        console.print(f"  [green]Saved to {storage_type}:[/] {config_path}")
        console.print("  [dim]File permissions: 600 (owner read/write only)[/]")
    except Exception as e:
        console.print(f"  [red]Failed to save:[/] {e}")
        return

    # Summary
    console.print(Panel(
        f"[green]Setup complete![/]\n\n"
        f"  Environment: {env_name}\n"
        f"  Username: {username}\n"
        f"  MFA: {'Configured' if totp_secret else 'Not configured'}\n"
        f"  Storage: {'Encrypted vault' if passphrase else 'Plain config file'}\n\n"
        f"[dim]Try: pacer pcl cases -t \"test\" to search cases[/]",
        title="Success",
        border_style="green",
    ))


@auth.command("login")
@click.option("--username", "-u", default=None, help="Your PACER username")
@click.option("--password", "-p", default=None, help="Your PACER password")
@click.option(
    "--totp-secret",
    "-t",
    default=None,
    help="TOTP secret for MFA (Base32 string from PACER setup)",
)
@click.option(
    "--client-code",
    "-c",
    default=None,
    help="Client billing code (optional)",
)
@click.pass_context
def auth_login(ctx, username: Optional[str], password: Optional[str], totp_secret: Optional[str], client_code: Optional[str]):
    """Store PACER credentials securely.

    \b
    If no credentials exist, runs the full setup wizard (pacer auth init).
    Otherwise, updates existing credentials.

    \b
    Example:
      pacer auth login                    # Interactive (wizard if first time)
      pacer auth login -u myuser -p pass  # Quick update
    """
    from .config import CONFIG_FILE

    # If no credentials exist and no args provided, run the full wizard
    if not CONFIG_FILE.exists() and not vault_exists() and username is None:
        console.print("[dim]No credentials found. Starting setup wizard...[/]\n")
        ctx.invoke(auth_init)
        return

    # Prompt for missing credentials
    from rich.prompt import Prompt
    if username is None:
        username = Prompt.ask("PACER Username")
    if password is None:
        password = Prompt.ask("PACER Password", password=True)

    config_path = save_credentials(username, password, totp_secret, client_code)
    console.print(f"[green]Credentials saved to:[/] {config_path}")
    console.print("[dim]File permissions set to 600 (owner read/write only)[/]")

    if totp_secret:
        console.print("[green]MFA:[/] TOTP secret configured for automatic code generation")
    else:
        console.print("[yellow]MFA:[/] No TOTP secret provided.")
        console.print("[dim]If your account has MFA enabled, use --totp-secret or pacer auth setup-mfa[/]")


@auth.command("code")
@click.option("--watch", "-w", is_flag=True, help="Continuously display codes (updates every 30s)")
@click.pass_context
def auth_code(ctx, watch: bool):
    """Generate current TOTP code from stored secret.

    \b
    Useful for:
      - Logging into PACER web interface manually
      - Removing/resetting MFA on your PACER account
      - Verifying your TOTP secret is correct
    """
    config: PacerConfig = ctx.obj["config"]

    if not config.totp_secret:
        err_console.print("[red]No TOTP secret configured.[/]")
        err_console.print("Run [cyan]pacer auth setup-mfa[/] to configure MFA.")
        sys.exit(1)

    from .auth import generate_totp
    import time

    secret = config.totp_secret.get_secret_value()

    if watch:
        console.print("[dim]Press Ctrl+C to stop[/]\n")
        try:
            while True:
                code = generate_totp(secret)
                # Calculate seconds until next code
                remaining = 30 - (int(time.time()) % 30)
                console.print(f"\r[bold green]{code}[/]  [dim]expires in {remaining:2d}s[/]", end="")
                time.sleep(1)
        except KeyboardInterrupt:
            console.print("\n")
    else:
        code = generate_totp(secret)
        remaining = 30 - (int(time.time()) % 30)
        console.print(f"[bold green]{code}[/]  [dim]expires in {remaining}s[/]")


@auth.command("setup-mfa")
@click.option(
    "--totp-secret",
    "-t",
    prompt="TOTP Secret (Base32 from PACER MFA setup)",
    help="The Base32 secret string shown during PACER MFA enrollment",
)
@click.pass_context
def auth_setup_mfa(ctx, totp_secret: str):
    """Configure MFA for an existing account.

    \b
    Get the TOTP secret from PACER's "Manage My Account" page during
    MFA enrollment. It's the Base32 string shown below the QR code.

    \b
    Example secret format: JBSWY3DPEHPK3PXP
    """
    config: PacerConfig = ctx.obj["config"]

    if not config.username or not config.password:
        err_console.print("[red]Error:[/] No credentials configured.")
        err_console.print("Run [cyan]pacer auth login[/] first.")
        sys.exit(1)

    # Validate the secret by trying to generate a code
    try:
        from .auth import generate_totp
        code = generate_totp(totp_secret.strip().upper())
        console.print(f"[green]TOTP secret valid.[/] Current code: {code}")
    except Exception as e:
        err_console.print(f"[red]Invalid TOTP secret:[/] {e}")
        sys.exit(1)

    # Save with existing credentials
    config_path = save_credentials(
        config.username,
        config.password.get_secret_value(),
        totp_secret.strip().upper(),
        config.client_code,
    )
    console.print(f"[green]MFA configured.[/] Updated: {config_path}")


@auth.command("test")
@click.option("--otp", "-o", default=None, help="Manual OTP code (if not using stored TOTP)")
@click.pass_context
def auth_test(ctx, otp: Optional[str]):
    """Test authentication with PACER servers.

    Verifies credentials work and immediately logs out.
    """
    config: PacerConfig = ctx.obj["config"]

    from .auth import test_credentials

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Testing PACER authentication...", total=None)
        result = test_credentials(config, otp)

    if result.success:
        console.print("[green]Authentication successful![/]")
        if result.error:  # Warnings
            console.print(f"[yellow]Note:[/] {result.error}")
    else:
        err_console.print(f"[red]Authentication failed:[/] {result.error}")
        sys.exit(1)


@auth.command("logout")
def auth_logout():
    """Remove stored PACER credentials."""
    if clear_credentials():
        console.print("[green]Credentials removed.[/]")
    else:
        console.print("[yellow]No credentials found.[/]")


@auth.command("status")
@click.pass_context
def auth_status(ctx):
    """Check authentication status."""
    config: PacerConfig = ctx.obj["config"]

    table = Table(title="Authentication Status", show_header=False)
    table.add_column("Key", style="cyan")
    table.add_column("Value")

    if config.username:
        table.add_row("Username", config.username)
        table.add_row("Password", "[green]configured[/]" if config.password else "[red]missing[/]")
        table.add_row("MFA (TOTP)", "[green]configured[/]" if config.has_mfa else "[dim]not set[/]")
        table.add_row("Client Code", config.client_code or "[dim]not set[/]")
        table.add_row("Environment", "QA" if config.use_qa else "Production")

        if config.has_mfa:
            table.add_row("Status", "[green]Ready (with MFA)[/]")
        else:
            table.add_row("Status", "[green]Ready[/] [dim](no MFA)[/]")
    else:
        table.add_row("Status", "[red]Not configured[/]")
        table.add_row("Action", "Run [cyan]pacer auth login[/]")

    console.print(table)

    if not config.has_mfa and config.username:
        console.print()
        console.print(Panel(
            "[yellow]MFA Note:[/] PACER requires MFA for CM/ECF filing accounts by Dec 2025.\n"
            "PACER-only (search) accounts can optionally enable MFA.\n\n"
            "To configure: [cyan]pacer auth setup-mfa[/]",
            title="Multi-Factor Authentication",
            border_style="dim",
        ))


# ============================================================================
# USE (CONTEXT) COMMANDS
# ============================================================================


@cli.group()
def use():
    """Set working context for subsequent commands.

    The context system lets you set a default court and case for commands,
    reducing repetitive typing.

    \b
    Examples:
      pacer use case nysd "1:18-cv-08434"  # Set active case
      pacer download docket                 # Uses active context
      pacer view                            # Uses active context
      pacer use status                      # Show current context
      pacer use clear                       # Clear context
    """
    pass


@use.command("case")
@click.argument("court")
@click.argument("case_number")
@click.option("--create", is_flag=True, help="Create case directory if missing")
@click.pass_context
def use_case(ctx, court: str, case_number: str, create: bool):
    """Set active court and case for subsequent commands.

    \b
    Examples:
      pacer use case nysd "1:18-cv-08434"
      pacer use case cacd "2:20-cv-01234" --create
    """
    config: PacerConfig = ctx.obj["config"]

    # Normalize court ID
    court_normalized = court.lower().rstrip("e").rstrip("c")
    case_path = config.get_case_dir(court_normalized, case_number)

    if not case_path.exists():
        if create:
            case_path.mkdir(parents=True, exist_ok=True)
            console.print(f"[green]Created:[/] {case_path}")
        else:
            console.print(f"[yellow]Warning:[/] Case directory does not exist: {case_path}")
            console.print("[dim]Use --create to create it, or download a docket first[/]")

    context = ContextConfig.load()
    context.court = court_normalized
    context.case_number = case_number
    context.case_path = case_path
    context.save()

    console.print(f"[green]Context set:[/] {court_normalized.upper()} / {case_number}")


@use.command("clear")
def use_clear():
    """Clear active context."""
    context = ContextConfig.load()
    context.clear()
    console.print("[dim]Context cleared[/]")


@use.command("status")
@click.pass_context
def use_status(ctx):
    """Show current working context."""
    config: PacerConfig = ctx.obj["config"]
    context = ContextConfig.load()

    if context.is_set:
        table = Table(title="Active Context", show_header=False)
        table.add_column("Key", style="cyan")
        table.add_column("Value")
        table.add_row("Court", context.court.upper() if context.court else "(none)")
        table.add_row("Case", context.case_number or "(none)")
        table.add_row("Path", str(context.case_path) if context.case_path else "(none)")

        # Show case status
        if context.case_path and context.case_path.exists():
            docket = context.case_path / "docket.html"
            docs = context.case_path / "docs.json"
            documents_dir = context.case_path / "documents"
            doc_count = len(list(documents_dir.glob("*.pdf"))) if documents_dir.exists() else 0

            table.add_row("Docket", "[green]downloaded[/]" if docket.exists() else "[dim]not downloaded[/]")
            table.add_row("Doc manifest", "[green]cached[/]" if docs.exists() else "[dim]none[/]")
            if doc_count > 0:
                table.add_row("Documents", f"[green]{doc_count} PDF(s)[/]")
        else:
            table.add_row("Status", "[yellow]Directory not found[/]")

        console.print(table)

        if context.updated_at:
            console.print(f"\n[dim]Last updated: {context.updated_at}[/]")
    else:
        console.print("[dim]No active context.[/]")
        console.print("Set context with: [cyan]pacer use case <court> <case_number>[/]")


# ============================================================================
# DOWNLOAD COMMANDS
# ============================================================================


@cli.group()
def download():
    """Download dockets and documents from PACER."""
    pass


@download.command("docket")
@click.argument("case_number", required=False)
@click.argument("court_id", required=False)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose/trace logging")
@click.option("--case-link", "-l", default=None, help="Direct CM/ECF case link URL (bypasses PCL search)")
@click.option("--legacy", is_flag=True, help="Use legacy flat archive structure")
@click.pass_context
def download_docket_cmd(
    ctx,
    case_number: Optional[str],
    court_id: Optional[str],
    verbose: bool,
    case_link: str,
    legacy: bool,
):
    """Download a single case docket.

    \b
    With context set (via 'pacer use case'):
      pacer download docket

    \b
    With explicit arguments:
      pacer download docket "1:2018cv08434" nysdce

    \b
    With direct case link:
      pacer download docket "1:2018cv08434" nysdce -l "https://ecf.nysd.uscourts.gov/..."
    """
    from .downloader import DocketDownloader

    config: PacerConfig = ctx.obj["config"]

    # Resolve from context if not provided
    if not case_number or not court_id:
        context = ContextConfig.load()
        if not context.is_set:
            err_console.print("[red]Error:[/] No case specified and no context set.")
            err_console.print("[dim]Either provide arguments or use:[/] pacer use case <court> <case>")
            sys.exit(1)
        case_number = case_number or context.case_number
        court_id = court_id or context.court
        console.print(f"[dim]Using context: {court_id.upper()} / {case_number}[/]")

    # Normalize court ID
    court_normalized = court_id.lower().rstrip("e").rstrip("c")

    # Determine output path
    if legacy:
        # Legacy flat structure
        ensure_dirs(config)
        output_dir = config.docket_archive.resolve()
        filename = f"{court_id}_{case_number.replace(':', '+')}.html"
    else:
        # New hierarchical structure
        case_dir = config.get_case_dir(court_normalized, case_number)
        case_dir.mkdir(parents=True, exist_ok=True)
        output_dir = case_dir
        filename = "docket.html"

    if verbose:
        console.print(f"[cyan]TRACE:[/] Output directory: {output_dir}")
        console.print(f"[cyan]TRACE:[/] Case number: {case_number}")
        console.print(f"[cyan]TRACE:[/] Court ID: {court_id} (normalized: {court_normalized})")
        if case_link:
            console.print(f"[cyan]TRACE:[/] Case link: {case_link}")

    # Cost confirmation
    if not confirm_cost_pages(
        ctx,
        "Download docket",
        pages=5,  # Conservative estimate
        details=f"Case: {case_number}\nCourt: {court_normalized.upper()}",
    ):
        console.print("[dim]Cancelled.[/]")
        return

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task(f"Downloading docket {case_number} from {court_normalized}...", total=None)

        downloader = DocketDownloader(config, verbose=verbose)

        if case_link:
            # Direct download using provided case link
            result = downloader.download_docket_by_link(case_link, output_dir, filename)
        else:
            # Search PCL first to find case link
            result = downloader.download_docket_by_case_number(
                case_number, court_id, output_dir, filename=filename
            )

    if result.success:
        console.print(f"[green]Downloaded:[/] {result.filepath.name}")
        console.print(f"[dim]Saved to:[/] {result.filepath}")
        console.print(f"[dim]Pages:[/] ~{result.pages} ([yellow]${result.cost:.2f}[/])")

        # Auto-update context after successful download
        if not legacy:
            context = ContextConfig.load()
            context.court = court_normalized
            context.case_number = case_number
            context.case_path = output_dir
            context.save()
            console.print(f"[dim]Context updated: {court_normalized.upper()} / {case_number}[/]")
    else:
        from .errors import classify_download_error, show_error
        error_key, detail = classify_download_error(result.error or "Unknown error")
        show_error(error_key, detail)


@download.command("document")
@click.argument("doc_number")
@click.argument("doc_link", required=False)
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose/trace logging")
@click.pass_context
def download_document(ctx, doc_number: str, doc_link: Optional[str], verbose: bool):
    """Download a single document from a case.

    \b
    With context set (auto-resolves link from docs.json):
      pacer download document 31

    \b
    With explicit link:
      pacer download document 31 "https://ecf.almd.uscourts.gov/doc1/017149132"

    The document link is resolved automatically from the cached docs.json
    if you've previously downloaded the docket.
    """
    from .downloader import DocumentDownloader, load_cached_documents, get_document_by_number

    config: PacerConfig = ctx.obj["config"]

    # Resolve from context if no explicit link
    context = ContextConfig.load()
    case_dir = None
    case_label = ""

    if not doc_link:
        # Need context to resolve the link
        if not context.is_set or not context.case_path:
            err_console.print("[red]Error:[/] No document link provided and no context set.")
            err_console.print("[dim]Either provide a link or set context:[/] pacer use case <court> <case>")
            sys.exit(1)

        case_dir = context.case_path
        case_label = f"{context.court}/{context.case_number}"

        # Look up the document link from docs.json
        doc_info = get_document_by_number(case_dir, doc_number)
        if not doc_info:
            err_console.print(f"[red]Error:[/] Document #{doc_number} not found in docs.json")
            err_console.print(f"[dim]Available docs:[/] pacer docs")
            err_console.print(f"[dim]Re-download docket to refresh:[/] pacer download docket")
            sys.exit(1)

        doc_link = doc_info.get("url")
        if not doc_link:
            err_console.print(f"[red]Error:[/] Document #{doc_number} has no URL in docs.json")
            sys.exit(1)

        console.print(f"[dim]Using context: {case_label}[/]")
        console.print(f"[dim]Resolved link: {doc_link}[/]")
    else:
        case_label = "explicit"

    # Determine output directory
    if case_dir:
        # Save to case's documents/ subdirectory
        output_dir = case_dir / "documents"
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{doc_number.zfill(3)}.pdf"
    else:
        # Legacy: save to flat document archive
        ensure_dirs(config)
        output_dir = config.document_archive.resolve()
        filename = f"doc{doc_number}.pdf"

    # Cost confirmation
    if not confirm_cost_pages(
        ctx,
        "Download document",
        pages=10,  # Conservative estimate
        details=f"Document #{doc_number}\nCase: {case_label}",
    ):
        console.print("[dim]Cancelled.[/]")
        return

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task(f"Downloading document #{doc_number}...", total=None)

        downloader = DocumentDownloader(config, verbose=verbose)
        result = downloader.download_document(doc_link, output_dir, filename)

    if result.success:
        console.print(f"[green]Downloaded:[/] {result.filepath.name}")
        console.print(f"[dim]Saved to:[/] {result.filepath}")
        if result.pages:
            console.print(f"[dim]Pages:[/] ~{result.pages} ([yellow]${result.cost:.2f}[/])")
    else:
        err_console.print(f"[red]Error:[/] {result.error}")


@cli.command("docs")
@click.argument("case", required=False)
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.pass_context
def list_documents(ctx, case: Optional[str], output_json: bool):
    """List documents from a downloaded docket's cache.

    Uses the docs.json file created during docket download.

    \b
    Examples:
      pacer docs                           # Use current context
      pacer docs nysd/1-18-cv-08434        # Explicit case path
      pacer docs --json                    # Output as JSON
    """
    import json

    from .downloader import load_cached_documents

    config: PacerConfig = ctx.obj["config"]

    # Resolve case directory
    if case:
        # Check if it looks like a path (court/case format)
        if "/" in case:
            parts = case.split("/", 1)
            case_dir = config.archive_root / parts[0] / parts[1]
        else:
            # Assume it's just a case identifier, try to find it
            case_dir = config.archive_root / case
    else:
        # Use context
        context = ContextConfig.load()
        if not context.is_set:
            err_console.print("[red]Error:[/] No case specified and no context set.")
            err_console.print("[dim]Set context with:[/] pacer use case <court> <case>")
            sys.exit(1)
        case_dir = context.case_path

    if not case_dir or not case_dir.exists():
        err_console.print(f"[red]Error:[/] Case directory not found: {case_dir}")
        err_console.print("[dim]Download a docket first:[/] pacer download docket <case> <court>")
        sys.exit(1)

    docs = load_cached_documents(case_dir)

    if not docs:
        err_console.print(f"[yellow]No docs.json found in:[/] {case_dir}")
        err_console.print("[dim]Re-download the docket to generate it.[/]")
        sys.exit(1)

    if output_json:
        console.print_json(json.dumps(docs, indent=2))
    else:
        table = Table(title=f"Documents in {docs.get('case_number', 'Unknown')}")
        table.add_column("#", style="cyan", width=5)
        table.add_column("Date", width=12)
        table.add_column("Description", max_width=50)
        table.add_column("Attach", width=6)

        for doc in docs.get("documents", []):
            attach = f"+{doc['attachment_count']}" if doc.get("has_attachments") else ""
            table.add_row(
                doc.get("doc_num", ""),
                doc.get("date", ""),
                (doc.get("description", ""))[:50],
                attach,
            )

        console.print(table)
        console.print(f"\n[dim]Total: {docs.get('document_count', len(docs.get('documents', [])))} documents with links[/]")
        console.print(f"[dim]Case: {docs.get('case_title', '')}[/]")


@cli.command("view")
@click.argument("case", required=False)
@click.option(
    "--format", "-f", "output_format",
    type=click.Choice(["compact", "markdown", "json"]),
    default="compact",
    help="Output format",
)
@click.option("--verbose", "-v", is_flag=True, help="Show all entries")
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Save to file")
@click.pass_context
def view_case(
    ctx,
    case: Optional[str],
    output_format: str,
    verbose: bool,
    output: Optional[Path],
):
    """View a parsed docket from the local archive.

    \b
    CASE can be:
      - A court/case path: nysd/1-18-cv-08434
      - A file path: ./docket.html
      - Omitted: Uses current context case (if set)

    \b
    Examples:
      pacer view                           # Use current context
      pacer view nysd/1-18-cv-08434        # Explicit case
      pacer view --format markdown         # Markdown output
      pacer view -f json -o case.json      # Save as JSON
    """
    from .parser import parse_docket

    config: PacerConfig = ctx.obj["config"]

    # Resolve case to docket file path
    docket_path = None

    if case:
        # Check if it's a direct file path
        if case.endswith(".html") and Path(case).exists():
            docket_path = Path(case)
        elif "/" in case:
            # court/case format
            parts = case.split("/", 1)
            case_dir = config.archive_root / parts[0] / parts[1]
            docket_path = case_dir / "docket.html"
        else:
            # Try as case identifier under archive
            case_dir = config.archive_root / case
            docket_path = case_dir / "docket.html"
    else:
        # Use context
        context = ContextConfig.load()
        if not context.is_set:
            err_console.print("[red]Error:[/] No case specified and no context set.")
            err_console.print("[dim]Set context with:[/] pacer use case <court> <case>")
            sys.exit(1)
        if context.case_path:
            docket_path = context.case_path / "docket.html"

    if not docket_path or not docket_path.exists():
        err_console.print(f"[red]Error:[/] Docket not found: {docket_path}")
        err_console.print("[dim]Download it first:[/] pacer download docket <case> <court>")
        sys.exit(1)

    # Read and parse the docket
    try:
        html = docket_path.read_text(encoding="utf-8", errors="ignore")
        docket = parse_docket(html)
    except Exception as e:
        err_console.print(f"[red]Error parsing docket:[/] {e}")
        sys.exit(1)

    # Format output
    if output_format == "json":
        result = docket.to_json()
    elif output_format == "markdown":
        result = docket.to_markdown(verbose=verbose)
    else:  # compact
        result = docket.to_compact()

    # Output
    if output:
        output.write_text(result, encoding="utf-8")
        console.print(f"[green]Saved to:[/] {output}")
    else:
        console.print(result)


@download.command("batch")
@click.argument("csv_file", type=click.Path(exists=True, path_type=Path))
@click.option("--column-court", "-c", default="court_id", help="Column name for court ID")
@click.option("--column-case", "-n", default="case_number", help="Column name for case number")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose/trace logging")
@click.pass_context
def download_batch(ctx, csv_file: Path, column_court: str, column_case: str, verbose: bool):
    """Download multiple dockets from a CSV file.

    The CSV should have columns for court ID and case number.

    \b
    Example CSV format:
      court_id,case_number
      almdce,2:00-cv-00084
      azdce,2:98-cv-00020
    """
    from .downloader import DocketDownloader

    config: PacerConfig = ctx.obj["config"]
    ensure_dirs(config)

    cases = []
    with open(csv_file) as f:
        reader = csv.DictReader(f)
        for row in reader:
            cases.append((row[column_court], row[column_case]))

    console.print(f"[cyan]Found {len(cases)} cases to download[/]")

    # Cost confirmation for batch
    if not confirm_cost_pages(
        ctx,
        "Batch download",
        pages=len(cases) * 5,  # ~5 pages per docket estimate
        details=f"{len(cases)} dockets from {csv_file.name}",
    ):
        console.print("[dim]Cancelled.[/]")
        return

    downloader = DocketDownloader(config, verbose=verbose)
    output_dir = config.docket_archive.resolve()
    success = 0
    failed = 0

    with Progress(console=console) as progress:
        task = progress.add_task("Downloading dockets...", total=len(cases))

        for court_id, case_number in cases:
            try:
                result = downloader.download_docket_by_case_number(
                    case_number, court_id, output_dir
                )
                if result.success:
                    success += 1
                else:
                    err_console.print(f"[red]Failed:[/] {court_id}/{case_number}: {result.error}")
                    failed += 1
            except Exception as e:
                err_console.print(f"[red]Failed:[/] {court_id}/{case_number}: {e}")
                failed += 1
            progress.advance(task)

    console.print(f"\n[green]Success:[/] {success} | [red]Failed:[/] {failed}")


# ============================================================================
# PARSE COMMANDS
# ============================================================================


@cli.group()
def parse():
    """Parse downloaded docket HTML files."""
    pass


@parse.command("all")
@click.option(
    "--input-dir",
    "-i",
    type=click.Path(exists=True, path_type=Path),
    help="Input directory (default: local_docket_archive)",
)
@click.pass_context
def parse_all(ctx, input_dir: Optional[Path]):
    """Parse all dockets in the archive directory."""
    config: PacerConfig = ctx.obj["config"]
    ensure_dirs(config)

    from .reader import DocketParser

    source = input_dir or config.docket_archive

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task(f"Parsing dockets in {source}...", total=None)

        parser = DocketParser(str(source))
        parser.parse_dir()

    console.print(f"[green]Parsed dockets saved to:[/] {config.parsed_dockets}")


@parse.command("file")
@click.argument("docket_file", type=click.Path(exists=True, path_type=Path))
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.pass_context
def parse_file(ctx, docket_file: Path, output_json: bool):
    """Parse a single docket file.

    \b
    Example:
      pacer parse file ./results/local_docket_archive/almdce_2+00-cv-00084.html
    """
    from .reader import DocketParser

    parser = DocketParser()

    with open(docket_file) as f:
        content = f.read()

    data = parser.parse_data(content)
    meta = parser.extract_all_meta(content)

    if output_json:
        import json

        console.print_json(json.dumps({"data": data, "meta": meta}))
    else:
        console.print(Panel(f"[bold]Case Metadata[/]", subtitle=str(docket_file)))

        if meta:
            table = Table(show_header=False)
            table.add_column("Field", style="cyan")
            table.add_column("Value")
            for key, value in meta.items():
                table.add_row(str(key), str(value))
            console.print(table)

        console.print(f"\n[dim]Docket entries: {len(data) if data else 0}[/]")


@parse.command("text")
@click.argument("docket_file", type=click.Path(exists=True, path_type=Path))
@click.option("--verbose", "-v", is_flag=True, help="Show all entries (default: key entries only)")
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Save to file")
def parse_text(docket_file: Path, verbose: bool, output: Optional[Path]):
    """Extract plain text from docket HTML.

    Outputs clean, token-efficient text for analysis.
    By default shows only key entries (complaints, motions, orders, etc.)

    \b
    Examples:
      pacer parse text ./docket.html
      pacer parse text ./docket.html -v          # all entries
      pacer parse text ./docket.html -o out.txt  # save to file
    """
    from .parser import parse_docket_file

    text = parse_docket_file(docket_file, verbose=verbose)

    if output:
        output.write_text(text)
        console.print(f"[green]Saved to:[/] {output}")
    else:
        print(text)


# ============================================================================
# SEARCH COMMANDS
# ============================================================================


@cli.command("search")
@click.option("--require", "-r", multiple=True, help="Required terms (can specify multiple)")
@click.option("--exclude", "-e", multiple=True, help="Excluded terms (can specify multiple)")
@click.option("--within", "-w", type=int, help="Terms must appear within N entries of each other")
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output filename prefix")
@click.option("--individual", is_flag=True, help="Write individual match files per case")
@click.pass_context
def search_dockets(
    ctx,
    require: tuple,
    exclude: tuple,
    within: Optional[int],
    output: Optional[Path],
    individual: bool,
):
    """Search parsed docket entries.

    \b
    Examples:
      pacer search -r judge -r dismiss
      pacer search -r motion -w 10 -o motion_results
      pacer search -r settlement -e denied --individual
    """
    config: PacerConfig = ctx.obj["config"]

    if not require:
        err_console.print("[red]Error:[/] At least one --require term is needed.")
        sys.exit(1)

    from .reader import DocketProcessor

    processor = DocketProcessor()

    search_kwargs = {"require_term": list(require)}
    if exclude:
        search_kwargs["exclude_term"] = list(exclude)
    if within:
        search_kwargs["within"] = str(within)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Searching parsed dockets...", total=None)
        processor.search_dir(**search_kwargs)

    matches = getattr(processor, "hit_list", [])
    console.print(f"\n[green]Found {len(matches)} matches[/]")

    if output:
        if individual:
            processor.write_individual_matches(str(output))
            console.print(f"[dim]Individual results written with prefix:[/] {output}")
        else:
            processor.write_all_matches(str(output))
            console.print(f"[dim]Results written to:[/] {output}")

    if matches and not output:
        table = Table(title="Search Results (first 20)")
        table.add_column("Case", style="cyan")
        table.add_column("Entry")
        table.add_column("Text", max_width=60)

        for match in matches[:20]:
            if isinstance(match, dict):
                table.add_row(
                    match.get("case", ""),
                    str(match.get("entry", "")),
                    match.get("text", "")[:60],
                )
            else:
                table.add_row(str(match), "", "")

        console.print(table)

        if len(matches) > 20:
            console.print(f"[dim]... and {len(matches) - 20} more. Use -o to save all.[/]")


# ============================================================================
# INFO COMMANDS
# ============================================================================


@cli.command("courts")
def list_courts():
    """List common federal court identifiers."""
    courts = [
        ("almdce", "Alabama Middle District"),
        ("alndce", "Alabama Northern District"),
        ("alsdce", "Alabama Southern District"),
        ("akdce", "Alaska District"),
        ("azdce", "Arizona District"),
        ("aredce", "Arkansas Eastern District"),
        ("arwdce", "Arkansas Western District"),
        ("cacdce", "California Central District"),
        ("caedce", "California Eastern District"),
        ("candce", "California Northern District"),
        ("casdce", "California Southern District"),
        ("codce", "Colorado District"),
        ("ctdce", "Connecticut District"),
        ("dedce", "Delaware District"),
        ("dcdce", "District of Columbia"),
        ("flmdce", "Florida Middle District"),
        ("flndce", "Florida Northern District"),
        ("flsdce", "Florida Southern District"),
        ("gamdce", "Georgia Middle District"),
        ("gandce", "Georgia Northern District"),
        ("gasdce", "Georgia Southern District"),
        ("hidce", "Hawaii District"),
        ("iddce", "Idaho District"),
        ("ilcdce", "Illinois Central District"),
        ("ilndce", "Illinois Northern District"),
        ("ilsdce", "Illinois Southern District"),
        ("inndce", "Indiana Northern District"),
        ("insdce", "Indiana Southern District"),
        ("iandce", "Iowa Northern District"),
        ("iasdce", "Iowa Southern District"),
        ("ksdce", "Kansas District"),
        ("kyedce", "Kentucky Eastern District"),
        ("kywdce", "Kentucky Western District"),
        ("laedce", "Louisiana Eastern District"),
        ("lamdce", "Louisiana Middle District"),
        ("lawdce", "Louisiana Western District"),
        ("medce", "Maine District"),
        ("mddce", "Maryland District"),
        ("madce", "Massachusetts District"),
        ("miedce", "Michigan Eastern District"),
        ("miwdce", "Michigan Western District"),
        ("mndce", "Minnesota District"),
        ("msndce", "Mississippi Northern District"),
        ("mssdce", "Mississippi Southern District"),
        ("moedce", "Missouri Eastern District"),
        ("mowdce", "Missouri Western District"),
        ("mtdce", "Montana District"),
        ("nedce", "Nebraska District"),
        ("nvdce", "Nevada District"),
        ("nhdce", "New Hampshire District"),
        ("njdce", "New Jersey District"),
        ("nmdce", "New Mexico District"),
        ("nyedce", "New York Eastern District"),
        ("nyndce", "New York Northern District"),
        ("nysdce", "New York Southern District"),
        ("nywdce", "New York Western District"),
        ("ncedce", "North Carolina Eastern District"),
        ("ncmdce", "North Carolina Middle District"),
        ("ncwdce", "North Carolina Western District"),
        ("nddce", "North Dakota District"),
        ("ohndce", "Ohio Northern District"),
        ("ohsdce", "Ohio Southern District"),
        ("okedce", "Oklahoma Eastern District"),
        ("okndce", "Oklahoma Northern District"),
        ("okwdce", "Oklahoma Western District"),
        ("ordce", "Oregon District"),
        ("paedce", "Pennsylvania Eastern District"),
        ("pamdce", "Pennsylvania Middle District"),
        ("pawdce", "Pennsylvania Western District"),
        ("ridce", "Rhode Island District"),
        ("scdce", "South Carolina District"),
        ("sddce", "South Dakota District"),
        ("tnedce", "Tennessee Eastern District"),
        ("tnmdce", "Tennessee Middle District"),
        ("tnwdce", "Tennessee Western District"),
        ("txedce", "Texas Eastern District"),
        ("txndce", "Texas Northern District"),
        ("txsdce", "Texas Southern District"),
        ("txwdce", "Texas Western District"),
        ("utdce", "Utah District"),
        ("vtdce", "Vermont District"),
        ("vaedce", "Virginia Eastern District"),
        ("vawdce", "Virginia Western District"),
        ("waedce", "Washington Eastern District"),
        ("wawdce", "Washington Western District"),
        ("wvndce", "West Virginia Northern District"),
        ("wvsdce", "West Virginia Southern District"),
        ("wiedce", "Wisconsin Eastern District"),
        ("wiwdce", "Wisconsin Western District"),
        ("wydce", "Wyoming District"),
    ]

    table = Table(title="Federal District Court Identifiers")
    table.add_column("ID", style="cyan")
    table.add_column("Court Name")

    for court_id, name in courts:
        table.add_row(court_id, name)

    console.print(table)
    console.print("\n[dim]Use these IDs with download commands.[/]")


@cli.command("config")
@click.pass_context
def show_config(ctx):
    """Show current configuration."""
    config: PacerConfig = ctx.obj["config"]

    table = Table(title="Current Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value")

    table.add_row("Username", config.username or "[dim]not set[/]")
    table.add_row("Password", "[green]set[/]" if config.password else "[red]not set[/]")
    table.add_row("Output Directory", str(config.output_dir))
    table.add_row("Docket Archive", str(config.docket_archive))
    table.add_row("Document Archive", str(config.document_archive))
    table.add_row("Parsed Dockets", str(config.parsed_dockets))

    console.print(table)


# ============================================================================
# PCL (PACER CASE LOCATOR) COMMANDS
# ============================================================================


@cli.group()
def pcl():
    """Search the PACER Case Locator (nationwide case index).

    \b
    The PCL API provides access to the nationwide index of federal court cases.
    Searches are billable at $0.10 per page (54 results per page).

    \b
    Quick examples:
      pacer pcl cases -t "Apple v. Samsung"
      pacer pcl cases -c nysdce --filed-after 2023-01-01
      pacer pcl parties -l "Smith" -f "John" --jurisdiction cv
    """
    pass


@pcl.command("cases")
@click.option("--case-number", "-n", help="Full case number (e.g., 1:2020cv12345)")
@click.option("--title", "-t", help="Case title (starts-with match)")
@click.option("--court", "-c", multiple=True, help="Court ID or region (can repeat)")
@click.option(
    "--jurisdiction", "-j",
    type=click.Choice(["ap", "bk", "cr", "cv", "mdl"], case_sensitive=False),
    help="Jurisdiction type",
)
@click.option("--case-type", multiple=True, help="Case type code (can repeat)")
@click.option("--filed-after", help="Date filed from (YYYY-MM-DD)")
@click.option("--filed-before", help="Date filed to (YYYY-MM-DD)")
@click.option("--closed-after", help="Date closed from (YYYY-MM-DD)")
@click.option("--closed-before", help="Date closed to (YYYY-MM-DD)")
@click.option("--nature-of-suit", "--nos", multiple=True, help="Nature of suit code (can repeat)")
@click.option("--chapter", multiple=True, help="Bankruptcy chapter (7, 11, 13, etc.)")
@click.option("--page", default=0, type=int, help="Page number (0-indexed, 54 results/page)")
@click.option("--all-pages", is_flag=True, help="Fetch all pages (may incur costs)")
@click.option("--dry-run", is_flag=True, help="Show search parameters without executing (no cost)")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.option("--csv", "output_csv", is_flag=True, help="Output as CSV")
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output file")
@click.option("--interactive", "-i", is_flag=True, help="Enable interactive case selection")
@click.pass_context
def pcl_cases(
    ctx,
    case_number,
    title,
    court,
    jurisdiction,
    case_type,
    filed_after,
    filed_before,
    closed_after,
    closed_before,
    nature_of_suit,
    chapter,
    page,
    all_pages,
    dry_run,
    output_json,
    output_csv,
    output,
    interactive,
):
    """Search for federal court cases.

    \b
    Examples:
      pacer pcl cases -t "Apple"
      pacer pcl cases -c nysdce --filed-after 2023-01-01
      pacer pcl cases --jurisdiction bk --chapter 11 -c CA
      pacer pcl cases --nos 830 --all-pages --csv -o patent_cases.csv
    """
    from .models import CaseSearchCriteria
    from .pcl import PCLClient, PCLError

    config: PacerConfig = ctx.obj["config"]

    # Build search criteria
    criteria = CaseSearchCriteria(
        caseNumberFull=case_number,
        caseTitle=title,
        courtId=list(court) if court else None,
        jurisdictionType=jurisdiction,
        caseType=list(case_type) if case_type else None,
        dateFiledFrom=filed_after,
        dateFiledTo=filed_before,
        effectiveDateClosedFrom=closed_after,
        effectiveDateClosedTo=closed_before,
        natureOfSuit=list(nature_of_suit) if nature_of_suit else None,
        federalBankruptcyChapter=list(chapter) if chapter else None,
    )

    # Validate we have at least one search criterion
    api_dict = criteria.to_api_dict()
    if not api_dict:
        err_console.print("[red]Error:[/] At least one search criterion is required.")
        err_console.print("[dim]Try: pacer pcl cases --help[/]")
        sys.exit(1)

    # Dry run - show parameters without executing
    if dry_run:
        import json
        console.print("[cyan]Dry run - search parameters:[/]")
        console.print_json(json.dumps(api_dict, indent=2))
        console.print(f"\n[dim]Endpoint: POST /cases/find?page={page}[/]")
        console.print("[dim]Estimated cost: $0.10 per page (54 results/page)[/]")
        console.print("[dim]Remove --dry-run to execute search[/]")
        return

    try:
        client = PCLClient(config)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            if all_pages:
                show_peak_hours_warning(entry_count=BULK_DOWNLOAD_THRESHOLD)
                progress.add_task("Fetching all pages...", total=None)
                responses = client.search_cases_all_pages(criteria)
                # Flatten results
                all_results = []
                total_fee = 0.0
                for resp in responses:
                    all_results.extend(resp.content)
                    if resp.receipt and resp.receipt.search_fee:
                        total_fee += float(resp.receipt.search_fee)
                page_info = responses[-1].page_info if responses else None
            else:
                progress.add_task(f"Searching cases (page {page})...", total=None)
                response = client.search_cases(criteria, page=page)
                all_results = response.content
                page_info = response.page_info
                total_fee = float(response.receipt.search_fee) if response.receipt and response.receipt.search_fee else 0.0

        # Display cost
        if total_fee > 0:
            console.print(f"[yellow]Cost:[/] ${total_fee:.2f}")

        # Display results
        if not all_results:
            console.print("[yellow]No results found.[/]")
            if page_info:
                console.print(f"[dim]Total: {page_info.total_elements} cases[/]")
            return

        # Output formatting
        if output_json:
            import json
            data = [r.model_dump(by_alias=True, exclude_none=True) for r in all_results]
            json_str = json.dumps(data, indent=2, default=str)
            if output:
                output.write_text(json_str)
                console.print(f"[green]Saved {len(all_results)} cases to:[/] {output}")
            else:
                console.print_json(json_str)
        elif output_csv:
            import csv as csv_module
            import io
            fieldnames = ["court_id", "case_number_full", "case_type", "case_title", "date_filed", "effective_date_closed", "jurisdiction_type", "nature_of_suit", "case_link"]

            if output:
                with open(output, "w", newline="") as f:
                    writer = csv_module.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                    writer.writeheader()
                    for r in all_results:
                        writer.writerow(r.model_dump(exclude_none=True))
                console.print(f"[green]Saved {len(all_results)} cases to:[/] {output}")
            else:
                buffer = io.StringIO()
                writer = csv_module.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                for r in all_results:
                    writer.writerow(r.model_dump(exclude_none=True))
                console.print(buffer.getvalue())
        else:
            # Rich table output
            table = Table(title=f"Case Search Results ({len(all_results)} cases)")
            table.add_column("Court", style="cyan", no_wrap=True)
            table.add_column("Case #", style="green")
            table.add_column("Type", no_wrap=True)
            table.add_column("Title", max_width=40)
            table.add_column("Filed")
            table.add_column("Status")

            for case in all_results[:50]:  # Limit display to 50
                table.add_row(
                    case.court_id or "",
                    case.case_number_full or "",
                    case.case_type or "",
                    (case.case_title or "")[:40],
                    case.date_filed or "",
                    case.status,
                )

            console.print(table)

            if page_info:
                console.print(
                    f"\n[dim]Page {page_info.number + 1} of {page_info.total_pages} "
                    f"({page_info.total_elements} total cases)[/]"
                )
            if len(all_results) > 50:
                console.print(f"[dim]Showing first 50 of {len(all_results)}. Use --json or --csv for full output.[/]")

            # Interactive selection
            if interactive and all_results:
                from .selection import interactive_case_select
                selection = interactive_case_select(all_results)
                if selection:
                    case, action = selection
                    _handle_case_action(ctx, config, case, action)

    except PCLError as e:
        from .errors import classify_pcl_error, show_error
        error_key, detail = classify_pcl_error(e)
        show_error(error_key, detail)
        sys.exit(1)


def _handle_case_action(ctx, config: PacerConfig, case, action: str):
    """Execute action on selected case from interactive selection."""
    from .downloader import DocketDownloader

    if action == "d":
        # Download docket
        court = case.court_id.lower().rstrip("e").rstrip("c") if case.court_id else ""
        case_number = case.case_number_full or ""

        if not case.case_link:
            err_console.print("[red]Error:[/] Case has no download link.")
            return

        case_dir = config.get_case_dir(court, case_number)
        case_dir.mkdir(parents=True, exist_ok=True)

        console.print(f"[cyan]Downloading docket...[/]")
        downloader = DocketDownloader(config)
        result = downloader.download_docket_by_link(case.case_link, case_dir, "docket.html")

        if result.success:
            console.print(f"[green]Downloaded:[/] {result.filepath}")
            # Update context
            context = ContextConfig.load()
            context.court = court
            context.case_number = case_number
            context.case_path = case_dir
            context.save()
            console.print(f"[dim]Context set: {court.upper()} / {case_number}[/]")
        else:
            err_console.print(f"[red]Error:[/] {result.error}")

    elif action == "v":
        # View if downloaded
        court = case.court_id.lower().rstrip("e").rstrip("c") if case.court_id else ""
        case_number = case.case_number_full or ""
        case_dir = config.get_case_dir(court, case_number)
        docket_path = case_dir / "docket.html"

        if docket_path.exists():
            ctx.invoke(view_case, case=str(docket_path))
        else:
            err_console.print("[yellow]Docket not downloaded yet.[/]")
            err_console.print(f"[dim]Download with:[/] pacer download docket \"{case_number}\" {court}")

    elif action == "s":
        # Set as context
        court = case.court_id.lower().rstrip("e").rstrip("c") if case.court_id else ""
        case_number = case.case_number_full or ""
        case_dir = config.get_case_dir(court, case_number)

        context = ContextConfig.load()
        context.court = court
        context.case_number = case_number
        context.case_path = case_dir
        context.save()
        console.print(f"[green]Context set:[/] {court.upper()} / {case_number}")

    elif action == "c":
        # Copy case info
        info = f"{case.court_id} {case.case_number_full}"
        console.print(f"[cyan]Case info:[/] {info}")
        console.print(f"[dim]Title:[/] {case.case_title}")
        if case.case_link:
            console.print(f"[dim]Link:[/] {case.case_link}")


@pcl.command("parties")
@click.option("--last-name", "-l", help="Last name or company name (required unless SSN)")
@click.option("--first-name", "-f", help="First name")
@click.option("--middle-name", help="Middle name")
@click.option("--exact-match", is_flag=True, help="Require exact name match")
@click.option("--ssn", help="SSN (bankruptcy debtors only)")
@click.option("--role", multiple=True, help="Party role code (can repeat)")
@click.option("--court", "-c", multiple=True, help="Court ID or region (can repeat)")
@click.option(
    "--jurisdiction", "-j",
    type=click.Choice(["ap", "bk", "cr", "cv", "mdl"], case_sensitive=False),
    help="Jurisdiction type",
)
@click.option("--filed-after", help="Date filed from (YYYY-MM-DD)")
@click.option("--filed-before", help="Date filed to (YYYY-MM-DD)")
@click.option("--closed-after", help="Date closed from (YYYY-MM-DD)")
@click.option("--closed-before", help="Date closed to (YYYY-MM-DD)")
@click.option("--nature-of-suit", "--nos", multiple=True, help="Nature of suit code (can repeat)")
@click.option("--chapter", multiple=True, help="Bankruptcy chapter (7, 11, 13, etc.)")
@click.option("--page", default=0, type=int, help="Page number (0-indexed)")
@click.option("--all-pages", is_flag=True, help="Fetch all pages (may incur costs)")
@click.option("--dry-run", is_flag=True, help="Show search parameters without executing (no cost)")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.option("--csv", "output_csv", is_flag=True, help="Output as CSV")
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output file")
@click.pass_context
def pcl_parties(
    ctx,
    last_name,
    first_name,
    middle_name,
    exact_match,
    ssn,
    role,
    court,
    jurisdiction,
    filed_after,
    filed_before,
    closed_after,
    closed_before,
    nature_of_suit,
    chapter,
    page,
    all_pages,
    dry_run,
    output_json,
    output_csv,
    output,
):
    """Search for parties in federal court cases.

    \b
    Examples:
      pacer pcl parties -l "Smith" -f "John"
      pacer pcl parties -l "Apple Inc" --jurisdiction cv
      pacer pcl parties --ssn 123456789  # Bankruptcy only
      pacer pcl parties -l "Musk" --filed-after 2020-01-01 --json
    """
    from .models import CaseSearchCriteria, PartySearchCriteria
    from .pcl import PCLClient, PCLError

    config: PacerConfig = ctx.obj["config"]

    # Validate SSN usage
    if ssn and jurisdiction and jurisdiction != "bk":
        err_console.print("[yellow]Warning:[/] SSN search only works for bankruptcy cases.")

    # Build case filter criteria
    case_criteria = None
    if any([court, jurisdiction, filed_after, filed_before, closed_after, closed_before, nature_of_suit, chapter]):
        case_criteria = CaseSearchCriteria(
            courtId=list(court) if court else None,
            jurisdictionType=jurisdiction,
            dateFiledFrom=filed_after,
            dateFiledTo=filed_before,
            effectiveDateClosedFrom=closed_after,
            effectiveDateClosedTo=closed_before,
            natureOfSuit=list(nature_of_suit) if nature_of_suit else None,
            federalBankruptcyChapter=list(chapter) if chapter else None,
        )

    # Build party search criteria
    criteria = PartySearchCriteria(
        lastName=last_name,
        firstName=first_name,
        middleName=middle_name,
        exactNameMatch=exact_match if exact_match else None,
        ssn=ssn,
        role=list(role) if role else None,
        courtCase=case_criteria,
    )

    # Validate we have at least one search criterion
    api_dict = criteria.to_api_dict()
    if not api_dict:
        err_console.print("[red]Error:[/] At least one search criterion is required.")
        err_console.print("[dim]Provide --last-name, --ssn, or date filters.[/]")
        sys.exit(1)

    # Dry run - show parameters without executing
    if dry_run:
        import json
        console.print("[cyan]Dry run - search parameters:[/]")
        console.print_json(json.dumps(api_dict, indent=2))
        console.print(f"\n[dim]Endpoint: POST /parties/find?page={page}[/]")
        console.print("[dim]Estimated cost: $0.10 per page (54 results/page)[/]")
        console.print("[dim]Remove --dry-run to execute search[/]")
        return

    try:
        client = PCLClient(config)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            if all_pages:
                show_peak_hours_warning(entry_count=BULK_DOWNLOAD_THRESHOLD)
                progress.add_task("Fetching all pages...", total=None)
                responses = client.search_parties_all_pages(criteria)
                all_results = []
                total_fee = 0.0
                for resp in responses:
                    all_results.extend(resp.content)
                    if resp.receipt and resp.receipt.search_fee:
                        total_fee += float(resp.receipt.search_fee)
                page_info = responses[-1].page_info if responses else None
            else:
                progress.add_task(f"Searching parties (page {page})...", total=None)
                response = client.search_parties(criteria, page=page)
                all_results = response.content
                page_info = response.page_info
                total_fee = float(response.receipt.search_fee) if response.receipt and response.receipt.search_fee else 0.0

        # Display cost
        if total_fee > 0:
            console.print(f"[yellow]Cost:[/] ${total_fee:.2f}")

        # Display results
        if not all_results:
            console.print("[yellow]No results found.[/]")
            return

        # Output formatting
        if output_json:
            import json
            data = [r.model_dump(by_alias=True, exclude_none=True) for r in all_results]
            json_str = json.dumps(data, indent=2, default=str)
            if output:
                output.write_text(json_str)
                console.print(f"[green]Saved {len(all_results)} parties to:[/] {output}")
            else:
                console.print_json(json_str)
        elif output_csv:
            import csv as csv_module
            import io
            fieldnames = ["last_name", "first_name", "middle_name", "party_role", "court_id", "case_number_full", "case_title", "date_filed"]

            if output:
                with open(output, "w", newline="") as f:
                    writer = csv_module.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                    writer.writeheader()
                    for r in all_results:
                        writer.writerow(r.model_dump(exclude_none=True))
                console.print(f"[green]Saved {len(all_results)} parties to:[/] {output}")
            else:
                buffer = io.StringIO()
                writer = csv_module.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                for r in all_results:
                    writer.writerow(r.model_dump(exclude_none=True))
                console.print(buffer.getvalue())
        else:
            # Rich table output
            table = Table(title=f"Party Search Results ({len(all_results)} parties)")
            table.add_column("Name", style="cyan")
            table.add_column("Role")
            table.add_column("Court")
            table.add_column("Case #", style="green")
            table.add_column("Title", max_width=35)
            table.add_column("Filed")

            for party in all_results[:50]:
                table.add_row(
                    party.full_name,
                    party.party_role or "",
                    party.court_id or "",
                    party.case_number_full or "",
                    (party.case_title or "")[:35],
                    party.date_filed or "",
                )

            console.print(table)

            if page_info:
                console.print(
                    f"\n[dim]Page {page_info.number + 1} of {page_info.total_pages} "
                    f"({page_info.total_elements} total parties)[/]"
                )
            if len(all_results) > 50:
                console.print(f"[dim]Showing first 50 of {len(all_results)}. Use --json or --csv for full output.[/]")

    except PCLError as e:
        err_console.print(f"[red]Error:[/] {e}")
        sys.exit(1)


# ============================================================================
# PCL BATCH COMMANDS
# ============================================================================


@pcl.group("batch")
def pcl_batch():
    """Manage batch searches (for large result sets > 5,400).

    \b
    Batch searches run asynchronously and support up to 108,000 results.
    Start a job, check status, then download when complete.

    \b
    Workflow:
      pacer pcl batch start-cases -t "Smith" --jurisdiction bk
      pacer pcl batch status 1078
      pacer pcl batch download 1078 -o results.json
      pacer pcl batch delete 1078
    """
    pass


@pcl_batch.command("list")
@click.option("--type", "search_type", type=click.Choice(["cases", "parties"]), default="cases", help="Search type")
@click.pass_context
def batch_list(ctx, search_type):
    """List all batch jobs."""
    from .pcl import PCLClient, PCLError

    config: PacerConfig = ctx.obj["config"]

    try:
        client = PCLClient(config)
        response = client.list_batch_jobs(search_type)

        if not response.content:
            console.print("[yellow]No batch jobs found.[/]")
            return

        table = Table(title=f"Batch Jobs ({search_type})")
        table.add_column("ID", style="cyan")
        table.add_column("Status")
        table.add_column("Records")
        table.add_column("Pages")
        table.add_column("Fee")
        table.add_column("Started")

        for job in response.content:
            status_style = "green" if job.is_complete else "yellow" if job.is_running else "dim"
            table.add_row(
                str(job.report_id),
                f"[{status_style}]{job.status}[/{status_style}]",
                str(job.record_count or "-"),
                str(job.pages or "-"),
                f"${job.download_fee:.2f}" if job.download_fee else "-",
                job.start_time or "-",
            )

        console.print(table)

    except PCLError as e:
        err_console.print(f"[red]Error:[/] {e}")
        sys.exit(1)


@pcl_batch.command("status")
@click.argument("report_id", type=int)
@click.option("--type", "search_type", type=click.Choice(["cases", "parties"]), default="cases", help="Search type")
@click.pass_context
def batch_status(ctx, report_id, search_type):
    """Check status of a batch job."""
    from .pcl import PCLClient, PCLError

    config: PacerConfig = ctx.obj["config"]

    try:
        client = PCLClient(config)
        job = client.get_batch_status(report_id, search_type)

        table = Table(title=f"Batch Job {report_id}")
        table.add_column("Field", style="cyan")
        table.add_column("Value")

        status_style = "green" if job.is_complete else "yellow"
        table.add_row("Status", f"[{status_style}]{job.status}[/{status_style}]")
        table.add_row("Records", str(job.record_count or "-"))
        table.add_row("Pages", str(job.pages or "-"))
        table.add_row("Download Fee", f"${job.download_fee:.2f}" if job.download_fee else "-")
        table.add_row("Started", job.start_time or "-")
        table.add_row("Completed", job.end_time or "-")

        console.print(table)

        if job.is_complete:
            console.print(f"\n[green]Ready to download:[/] pacer pcl batch download {report_id}")

    except PCLError as e:
        err_console.print(f"[red]Error:[/] {e}")
        sys.exit(1)


@pcl_batch.command("download")
@click.argument("report_id", type=int)
@click.option("--type", "search_type", type=click.Choice(["cases", "parties"]), default="cases", help="Search type")
@click.option("--output", "-o", type=click.Path(path_type=Path), required=True, help="Output file (JSON)")
@click.pass_context
def batch_download(ctx, report_id, search_type, output):
    """Download results from a completed batch job."""
    import json

    from .pcl import PCLClient, PCLError

    config: PacerConfig = ctx.obj["config"]

    try:
        client = PCLClient(config)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(f"Downloading batch job {report_id}...", total=None)
            response = client.download_batch_results(report_id, search_type)

        data = [r.model_dump(by_alias=True, exclude_none=True) for r in response.content]
        output.write_text(json.dumps(data, indent=2, default=str))

        console.print(f"[green]Downloaded {len(data)} results to:[/] {output}")

        if response.receipt and response.receipt.search_fee:
            console.print(f"[yellow]Cost:[/] ${float(response.receipt.search_fee):.2f}")

    except PCLError as e:
        err_console.print(f"[red]Error:[/] {e}")
        sys.exit(1)


@pcl_batch.command("delete")
@click.argument("report_id", type=int)
@click.option("--type", "search_type", type=click.Choice(["cases", "parties"]), default="cases", help="Search type")
@click.pass_context
def batch_delete(ctx, report_id, search_type):
    """Delete a batch job and its results."""
    from .pcl import PCLClient, PCLError

    config: PacerConfig = ctx.obj["config"]

    try:
        client = PCLClient(config)
        if client.delete_batch_job(report_id, search_type):
            console.print(f"[green]Deleted batch job {report_id}[/]")
        else:
            console.print(f"[yellow]Could not delete batch job {report_id}[/]")

    except PCLError as e:
        err_console.print(f"[red]Error:[/] {e}")
        sys.exit(1)


if __name__ == "__main__":
    cli()
