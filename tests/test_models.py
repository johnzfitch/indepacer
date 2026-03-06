"""Tests for Pydantic models and search criteria."""

from __future__ import annotations

import pytest

from indepacer.models import (
    BatchJobInfo,
    CaseResult,
    CaseSearchCriteria,
    CaseSearchResponse,
    PageInfo,
    PartyResult,
    PartySearchCriteria,
    PartySearchResponse,
    Receipt,
)


class TestReceipt:
    def test_fee_cents(self):
        r = Receipt(searchFee="0.30")
        assert r.fee_cents == 30

    def test_fee_cents_none(self):
        r = Receipt()
        assert r.fee_cents == 0

    def test_fee_cents_invalid(self):
        r = Receipt(searchFee="N/A")
        assert r.fee_cents == 0


class TestPageInfo:
    def test_defaults(self):
        p = PageInfo()
        assert p.first is True
        assert p.last is True
        assert p.size == 54


class TestCaseResult:
    def test_status_open(self):
        c = CaseResult()
        assert c.status == "Open"

    def test_status_closed(self):
        c = CaseResult(effectiveDateClosed="2020-01-01")
        assert c.status == "Closed"

    def test_status_dismissed(self):
        c = CaseResult(dateDismissed="2020-06-01")
        assert c.status == "Dismissed"

    def test_status_discharged(self):
        c = CaseResult(dateDischarged="2020-03-01")
        assert c.status == "Discharged"

    def test_status_priority(self):
        # Discharged takes priority over dismissed/closed
        c = CaseResult(dateDischarged="2020-03-01", dateDismissed="2020-06-01")
        assert c.status == "Discharged"


class TestPartyResult:
    def test_full_name(self):
        p = PartyResult(firstName="John", lastName="Doe")
        assert p.full_name == "John Doe"

    def test_full_name_unknown(self):
        p = PartyResult()
        assert p.full_name == "(Unknown)"

    def test_full_name_with_middle_and_generation(self):
        p = PartyResult(firstName="John", middleName="Q", lastName="Doe", generation="Jr.")
        assert p.full_name == "John Q Doe Jr."


class TestCaseSearchCriteria:
    def test_to_api_dict_excludes_none(self):
        criteria = CaseSearchCriteria(case_title="Apple")
        d = criteria.to_api_dict()
        assert "caseTitle" in d
        assert "courtId" not in d

    def test_to_api_dict_excludes_empty_list(self):
        criteria = CaseSearchCriteria(court_id=[])
        d = criteria.to_api_dict()
        assert "courtId" not in d

    def test_to_api_dict_includes_list(self):
        criteria = CaseSearchCriteria(court_id=["nysdce"])
        d = criteria.to_api_dict()
        assert d["courtId"] == ["nysdce"]


class TestPartySearchCriteria:
    def test_to_api_dict(self):
        criteria = PartySearchCriteria(last_name="Smith")
        d = criteria.to_api_dict()
        assert d["lastName"] == "Smith"


class TestCaseSearchResponse:
    def test_parse_empty(self):
        resp = CaseSearchResponse.model_validate({"content": []})
        assert resp.content == []
        assert resp.receipt is None

    def test_parse_with_results(self):
        data = {
            "content": [{"caseTitle": "Test v. Case", "courtId": "nysdce"}],
            "pageInfo": {"number": 0, "totalPages": 1, "last": True},
        }
        resp = CaseSearchResponse.model_validate(data)
        assert len(resp.content) == 1
        assert resp.content[0].case_title == "Test v. Case"
        assert resp.page_info.last is True


class TestBatchJobInfo:
    def test_is_complete(self):
        j = BatchJobInfo(reportId=1, status="COMPLETED")
        assert j.is_complete is True
        assert j.is_running is False

    def test_is_running(self):
        j = BatchJobInfo(reportId=1, status="RUNNING")
        assert j.is_complete is False
        assert j.is_running is True

    def test_waiting(self):
        j = BatchJobInfo(reportId=1, status="WAITING")
        assert j.is_running is True
