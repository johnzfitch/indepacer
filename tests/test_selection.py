"""Tests for the interactive case selector (selection.py).

The selector is a Rich TUI; we drive it by replacing ``Prompt.ask`` with a
queue of canned responses, so the pagination / selection / action logic is
exercised without a terminal.
"""

from __future__ import annotations

import pytest

from pacer_cli import selection as sel
from pacer_cli.models import CaseResult


def _cases(n: int) -> list[CaseResult]:
    return [
        CaseResult(
            courtId="nysd",
            caseNumberFull=f"1:20-cv-{i:04d}",
            caseTitle=f"Case number {i}",
            dateFiled="2020-01-01",
        )
        for i in range(n)
    ]


@pytest.fixture
def answers(monkeypatch):
    """Replace Prompt.ask with a FIFO queue of responses."""
    queue: list[str] = []

    def fake_ask(*_args, **_kwargs):
        return queue.pop(0)

    monkeypatch.setattr(sel.Prompt, "ask", fake_ask)
    return queue


class TestCaseSelectorBasics:
    def test_total_pages_rounds_up(self):
        assert sel.CaseSelector(_cases(0)).total_pages == 0
        assert sel.CaseSelector(_cases(1), page_size=20).total_pages == 1
        assert sel.CaseSelector(_cases(21), page_size=20).total_pages == 2
        assert sel.CaseSelector(_cases(40), page_size=20).total_pages == 2

    def test_display_page_runs(self):
        # Should render without raising for a partial last page.
        sel.CaseSelector(_cases(3), page_size=2).display_page()


class TestPromptSelection:
    def test_select_valid_number_returns_case(self, answers):
        answers.append("2")
        sel_obj = sel.CaseSelector(_cases(3))
        chosen = sel_obj.prompt_selection()
        assert chosen is sel_obj.results[1]

    def test_quit_returns_none(self, answers):
        answers.append("q")
        assert sel.CaseSelector(_cases(3)).prompt_selection() is None

    def test_non_numeric_then_valid_reprompts(self, answers):
        answers.extend(["abc", "1"])
        sel_obj = sel.CaseSelector(_cases(3))
        assert sel_obj.prompt_selection() is sel_obj.results[0]

    def test_out_of_range_then_valid(self, answers):
        answers.extend(["99", "1"])
        sel_obj = sel.CaseSelector(_cases(3))
        assert sel_obj.prompt_selection() is sel_obj.results[0]

    def test_next_page_then_select(self, answers):
        # 3 cases, page_size 2 -> 2 pages. 'n' then '1' picks the 3rd case.
        answers.extend(["n", "1"])
        sel_obj = sel.CaseSelector(_cases(3), page_size=2)
        assert sel_obj.prompt_selection() is sel_obj.results[2]

    def test_prev_page_then_select(self, answers):
        answers.extend(["n", "p", "1"])
        sel_obj = sel.CaseSelector(_cases(3), page_size=2)
        assert sel_obj.prompt_selection() is sel_obj.results[0]


class TestPromptMultiSelection:
    def test_comma_list(self, answers):
        answers.append("1,3")
        sel_obj = sel.CaseSelector(_cases(5))
        chosen = sel_obj.prompt_multi_selection()
        assert chosen == [sel_obj.results[0], sel_obj.results[2]]

    def test_range(self, answers):
        answers.append("1-3")
        sel_obj = sel.CaseSelector(_cases(5))
        chosen = sel_obj.prompt_multi_selection()
        assert chosen == sel_obj.results[0:3]

    def test_quit_returns_empty(self, answers):
        answers.append("q")
        assert sel.CaseSelector(_cases(5)).prompt_multi_selection() == []

    def test_invalid_format_returns_empty(self, answers):
        answers.append("1,x-y")
        assert sel.CaseSelector(_cases(5)).prompt_multi_selection() == []


class TestPromptAction:
    def test_returns_chosen_action(self, answers):
        answers.append("d")
        action = sel.CaseSelector(_cases(1)).prompt_action(_cases(1)[0])
        assert action == "d"


class TestInteractiveWrappers:
    def test_case_select_empty_returns_none(self):
        assert sel.interactive_case_select([]) is None

    def test_case_select_pick_then_action(self, answers):
        answers.extend(["1", "d"])  # select case 1, action download
        cases = _cases(3)
        result = sel.interactive_case_select(cases)
        assert result == (cases[0], "d")

    def test_case_select_back_then_pick(self, answers):
        answers.extend(["1", "b", "2", "s"])  # pick, back, pick again, set-context
        cases = _cases(3)
        result = sel.interactive_case_select(cases)
        assert result == (cases[1], "s")

    def test_case_select_quit_action_returns_none(self, answers):
        answers.extend(["1", "q"])
        assert sel.interactive_case_select(_cases(3)) is None

    def test_case_select_quit_selection_returns_none(self, answers):
        answers.append("q")
        assert sel.interactive_case_select(_cases(3)) is None

    def test_multi_select_empty_returns_empty(self):
        assert sel.interactive_multi_select([]) == []

    def test_multi_select_returns_selection(self, answers):
        answers.append("1,2")
        cases = _cases(4)
        assert sel.interactive_multi_select(cases) == cases[0:2]
