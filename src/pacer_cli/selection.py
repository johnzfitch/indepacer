"""Interactive selection utilities for CLI."""

from typing import List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from .models import CaseResult

console = Console()


class CaseSelector:
    """Interactive case selection from search results."""

    def __init__(self, results: List[CaseResult], page_size: int = 20):
        self.results = results
        self.page_size = page_size
        self.current_page = 0

    @property
    def total_pages(self) -> int:
        return (len(self.results) + self.page_size - 1) // self.page_size

    def display_page(self) -> None:
        """Display current page of results with selection numbers."""
        start = self.current_page * self.page_size
        end = min(start + self.page_size, len(self.results))
        page_results = self.results[start:end]

        table = Table(title=f"Search Results (Page {self.current_page + 1}/{self.total_pages})")
        table.add_column("#", style="bold cyan", width=3)
        table.add_column("Court", style="cyan", no_wrap=True, width=6)
        table.add_column("Case #", style="green", width=18)
        table.add_column("Title", max_width=40)
        table.add_column("Filed", width=12)
        table.add_column("Status", width=8)

        for i, case in enumerate(page_results, start=1):
            table.add_row(
                str(i),
                case.court_id or "",
                case.case_number_full or "",
                (case.case_title or "")[:40],
                case.date_filed or "",
                case.status,
            )

        console.print(table)
        console.print(f"[dim]{len(self.results)} total results[/]")

    def prompt_selection(self) -> Optional[CaseResult]:
        """Prompt user for single case selection."""
        self.display_page()

        page_size = min(self.page_size, len(self.results) - self.current_page * self.page_size)

        while True:
            try:
                hint = f"[1-{page_size}]"
                if self.total_pages > 1:
                    hint += ", [cyan]n[/]=next, [cyan]p[/]=prev"
                hint += ", [cyan]q[/]=quit"

                response = Prompt.ask(f"Select {hint}")

                if response.lower() == "q":
                    return None
                elif response.lower() == "n" and self.current_page < self.total_pages - 1:
                    self.current_page += 1
                    self.display_page()
                elif response.lower() == "p" and self.current_page > 0:
                    self.current_page -= 1
                    self.display_page()
                else:
                    idx = int(response)
                    abs_idx = self.current_page * self.page_size + idx - 1
                    if 0 <= abs_idx < len(self.results):
                        return self.results[abs_idx]
                    console.print("[yellow]Invalid selection[/]")
            except ValueError:
                console.print("[yellow]Enter a number or n/p/q[/]")

    def prompt_multi_selection(self) -> List[CaseResult]:
        """Select multiple cases with '1,3,5-10' syntax."""
        self.display_page()

        console.print("[dim]Enter numbers separated by commas, or ranges (1-5)[/]")
        console.print("[dim]Example: 1,3,5-10[/]")

        response = Prompt.ask("Select cases")
        if response.lower() == "q":
            return []

        selected = []
        try:
            for part in response.split(","):
                part = part.strip()
                if "-" in part:
                    start, end = map(int, part.split("-"))
                    for i in range(start, end + 1):
                        abs_idx = self.current_page * self.page_size + i - 1
                        if 0 <= abs_idx < len(self.results):
                            selected.append(self.results[abs_idx])
                else:
                    abs_idx = self.current_page * self.page_size + int(part) - 1
                    if 0 <= abs_idx < len(self.results):
                        selected.append(self.results[abs_idx])
        except ValueError:
            console.print("[yellow]Invalid selection format[/]")
            return []

        return selected

    def prompt_action(self, case: CaseResult) -> Optional[str]:
        """Prompt for action on selected case."""
        console.print(
            Panel(
                f"[bold]{case.case_title}[/]\n"
                f"Court: {case.court_id} | Case: {case.case_number_full}\n"
                f"Filed: {case.date_filed} | Status: {case.status}",
                title="Selected Case",
            )
        )

        console.print(
            "  [cyan]d[/] Download docket\n"
            "  [cyan]v[/] View (if downloaded)\n"
            "  [cyan]s[/] Set as context\n"
            "  [cyan]c[/] Copy case info\n"
            "  [cyan]b[/] Back to results\n"
            "  [cyan]q[/] Quit"
        )

        action = Prompt.ask("Action", choices=["d", "v", "s", "c", "b", "q"], default="b")
        return action


def interactive_case_select(results: List[CaseResult]) -> Optional[Tuple[CaseResult, str]]:
    """Run interactive selection loop.

    Returns:
        Tuple of (CaseResult, action) or None if cancelled
    """
    if not results:
        console.print("[yellow]No results to select from.[/]")
        return None

    selector = CaseSelector(results)

    while True:
        case = selector.prompt_selection()
        if case is None:
            return None

        action = selector.prompt_action(case)
        if action == "b":
            continue  # Back to results
        elif action == "q":
            return None
        else:
            return (case, action)


def interactive_multi_select(results: List[CaseResult]) -> List[CaseResult]:
    """Run interactive multi-selection.

    Returns:
        List of selected CaseResult objects
    """
    if not results:
        console.print("[yellow]No results to select from.[/]")
        return []

    selector = CaseSelector(results)
    return selector.prompt_multi_selection()
