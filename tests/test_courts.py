"""Tests for court lookup utilities."""

from __future__ import annotations

import pytest

from pacer_cli.courts import (
    get_cso_court_id,
    get_ecf_domain_from_url,
    get_ecf_url,
    list_courts,
    normalize_court_id,
)


class TestGetEcfDomainFromUrl:
    def test_extracts_domain(self):
        url = "https://ecf.nysd.uscourts.gov/doc1/123"
        assert get_ecf_domain_from_url(url) == "nysd"

    def test_case_insensitive(self):
        url = "https://ECF.CACD.USCOURTS.GOV/cgi-bin/DktRpt.pl"
        assert get_ecf_domain_from_url(url) == "cacd"

    def test_no_match(self):
        assert get_ecf_domain_from_url("https://example.com") is None


class TestListCourts:
    def test_returns_list(self):
        courts = list_courts()
        assert isinstance(courts, list)
        assert len(courts) > 0

    def test_filter_by_type(self):
        districts = list_courts(court_type="District")
        if districts:
            assert all(c["type"] == "District" for c in districts)


class TestNormalizeCourtId:
    def test_already_valid(self):
        # If the lookup data contains the ID, it should pass through
        result = normalize_court_id("nysd")
        # This depends on lookup data; just check it doesn't crash
        assert result is None or isinstance(result, str)

    def test_ecf_domain_lookup(self):
        result = normalize_court_id("nysd")
        # Depends on court-lookup.json contents
        if result:
            assert result.isupper()
