"""Tests for docket HTML parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from indepacer.docket_types import DocketEntry, ParsedDocket
from indepacer.parser import (
    parse_docket,
    parse_docket_file,
    parse_docket_regex,
    clean_text,
)


class TestParseDocket:
    def test_extracts_case_number(self, sample_docket_html):
        docket = parse_docket(sample_docket_html)
        assert docket.meta.case_number == "1:18-cv-08434-VEC-SLC"

    def test_extracts_court_id(self, sample_docket_html):
        docket = parse_docket(sample_docket_html)
        assert docket.meta.court_id == "nysd"

    def test_extracts_entries(self, sample_docket_html):
        docket = parse_docket(sample_docket_html)
        assert len(docket.entries) >= 2

    def test_entry_dates_iso_format(self, sample_docket_html):
        docket = parse_docket(sample_docket_html)
        for entry in docket.entries:
            assert len(entry.date) == 10
            assert entry.date[4] == "-"

    def test_entry_doc_nums(self, sample_docket_html):
        docket = parse_docket(sample_docket_html)
        doc_nums = [e.doc_num for e in docket.entries if e.doc_num]
        assert "1" in doc_nums

    def test_entry_text_not_empty(self, sample_docket_html):
        docket = parse_docket(sample_docket_html)
        for entry in docket.entries:
            assert len(entry.text) > 0


class TestParseDocketRegex:
    def test_basic_extraction(self, sample_docket_html):
        docket = parse_docket_regex(sample_docket_html)
        assert docket.meta.court_id == "nysd"


class TestParseDocketFile:
    def test_compact_format(self, sample_docket_file):
        output = parse_docket_file(sample_docket_file, output_format="compact")
        assert "PACER Docket" in output

    def test_json_format(self, sample_docket_file):
        import json
        output = parse_docket_file(sample_docket_file, output_format="json")
        data = json.loads(output)
        assert "meta" in data
        assert "entries" in data

    def test_markdown_format(self, sample_docket_file):
        output = parse_docket_file(sample_docket_file, output_format="markdown")
        assert "#" in output


class TestDocketTypes:
    def test_entry_is_key_filing(self):
        e = DocketEntry(seq=0, date="2020-01-01", text="COMPLAINT filed by plaintiff")
        assert e.is_key_filing is True

    def test_entry_not_key_filing(self):
        e = DocketEntry(seq=0, date="2020-01-01", text="Clerk entry of reassignment")
        assert e.is_key_filing is False

    def test_parsed_docket_key_entries(self, sample_docket):
        key = sample_docket.key_entries()
        # COMPLAINT, MOTION, ORDER are all key terms
        assert len(key) >= 2

    def test_to_compact(self, sample_docket):
        text = sample_docket.to_compact()
        assert "nysd" in text.lower() or "NYSD" in text

    def test_to_json(self, sample_docket):
        import json
        data = json.loads(sample_docket.to_json())
        assert data["meta"]["court_id"] == "nysd"

    def test_to_markdown(self, sample_docket):
        md = sample_docket.to_markdown()
        assert "Apple" in md


class TestCleanText:
    def test_strips_tags(self):
        assert "hello" in clean_text("<b>hello</b>")

    def test_collapses_whitespace(self):
        result = clean_text("hello    world")
        assert "  " not in result
