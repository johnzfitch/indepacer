"""Tests for the PACER Case Locator (PCL) API client.

All network access is mocked: the client's `_session` is replaced with a
MagicMock and `pacer_cli.pcl.authenticate` is patched so no real login occurs.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from pacer_cli.auth import AuthResult
from pacer_cli.config import PacerConfig
from pacer_cli.models import (
    CaseSearchCriteria,
    PartySearchCriteria,
)
from pacer_cli.pcl import (
    PCLAuthError,
    PCLClient,
    PCLError,
    PCLNotFoundError,
    PCLValidationError,
)


@pytest.fixture
def config() -> PacerConfig:
    return PacerConfig(username="user", password="pass")


@pytest.fixture
def client(config):
    """A PCLClient with a mocked session and patched authentication."""
    with patch("pacer_cli.pcl.authenticate") as mock_auth:
        mock_auth.return_value = AuthResult(success=True, token="tok-" + "x" * 124)
        c = PCLClient(config)
        c._session = MagicMock(spec=requests.Session)
        # default token so requests don't trigger auth unless we clear it
        c._token = "tok-" + "x" * 124
        c._mock_auth = mock_auth
        yield c


def _resp(status_code=200, json_data=None, text="", headers=None):
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data if json_data is not None else {}
    resp.text = text
    resp.headers = headers or {}
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(response=resp)
    else:
        resp.raise_for_status.return_value = None
    return resp


# Minimal realistic PCL payloads -------------------------------------------------

CASE_PAGE_LAST = {
    "receipt": {
        "transactionDate": "2026-06-10",
        "billablePages": 1,
        "loginId": "user",
        "search": "Case Search",
        "searchFee": "0.10",
    },
    "pageInfo": {
        "number": 0,
        "size": 54,
        "totalPages": 1,
        "totalElements": 1,
        "numberOfElements": 1,
        "first": True,
        "last": True,
    },
    "content": [
        {
            "courtId": "nysd",
            "caseId": 500997,
            "caseNumberFull": "1:18-cv-08434",
            "caseTitle": "Apple Inc. v. Samsung",
            "dateFiled": "2018-09-15",
            "caseLink": "https://ecf.nysd.uscourts.gov/cgi-bin/iqquerymenu.pl?500997",
        }
    ],
}

PARTY_PAGE_LAST = {
    "receipt": {"billablePages": 1, "searchFee": "0.10"},
    "pageInfo": {
        "number": 0,
        "size": 54,
        "totalPages": 1,
        "totalElements": 1,
        "numberOfElements": 1,
        "first": True,
        "last": True,
    },
    "content": [
        {
            "courtId": "nysd",
            "caseId": 1,
            "lastName": "Smith",
            "firstName": "John",
            "partyType": "Plaintiff",
        }
    ],
}


def _case_page(number, last):
    return {
        "pageInfo": {
            "number": number,
            "size": 54,
            "totalPages": 3,
            "totalElements": 150,
            "numberOfElements": 54,
            "first": number == 0,
            "last": last,
        },
        "content": [{"courtId": "nysd", "caseId": number}],
    }


# ---------------------------------------------------------------------------
# Exception classes
# ---------------------------------------------------------------------------


class TestExceptions:
    def test_hierarchy(self):
        assert issubclass(PCLAuthError, PCLError)
        assert issubclass(PCLValidationError, PCLError)
        assert issubclass(PCLNotFoundError, PCLError)
        assert issubclass(PCLError, Exception)


# ---------------------------------------------------------------------------
# Authentication / token property
# ---------------------------------------------------------------------------


class TestAuthentication:
    def test_token_property_authenticates_when_missing(self, config):
        with patch("pacer_cli.pcl.authenticate") as mock_auth:
            mock_auth.return_value = AuthResult(success=True, token="abc")
            c = PCLClient(config)
            c._session = MagicMock(spec=requests.Session)
            assert c.token == "abc"
            mock_auth.assert_called_once()

    def test_token_property_cached(self, client):
        # token already set in fixture; property returns it without re-auth
        assert client.token.startswith("tok-")
        client._mock_auth.assert_not_called()

    def test_authenticate_failure_raises(self, config):
        with patch("pacer_cli.pcl.authenticate") as mock_auth:
            mock_auth.return_value = AuthResult(success=False, error="bad creds")
            c = PCLClient(config)
            c._session = MagicMock(spec=requests.Session)
            with pytest.raises(PCLAuthError, match="bad creds"):
                _ = c.token

    def test_post_init_sets_json_headers(self, config):
        with patch("pacer_cli.pcl.authenticate"):
            c = PCLClient(config)
            assert c._session.headers["Accept"] == "application/json"
            assert c._session.headers["Content-Type"] == "application/json"


# ---------------------------------------------------------------------------
# _make_request behaviors
# ---------------------------------------------------------------------------


class TestMakeRequest:
    def test_get_request_success(self, client):
        client._session.get.return_value = _resp(json_data={"ok": True})
        resp = client._make_request("GET", "/cases/reports")
        assert resp.json() == {"ok": True}
        url = client._session.get.call_args[0][0]
        assert url.endswith("/cases/reports")

    def test_post_includes_payload(self, client):
        client._session.post.return_value = _resp(json_data={})
        client._make_request("POST", "/cases/find", payload={"a": 1})
        assert client._session.post.call_args.kwargs["json"] == {"a": 1}

    def test_delete_request(self, client):
        client._session.delete.return_value = _resp(status_code=204)
        resp = client._make_request("DELETE", "/cases/reports/5")
        assert resp.status_code == 204

    def test_unsupported_method_raises(self, client):
        with pytest.raises(ValueError, match="Unsupported HTTP method"):
            client._make_request("PATCH", "/x")

    def test_client_code_header(self, config):
        with patch("pacer_cli.pcl.authenticate"):
            c = PCLClient(config)
            c.config.client_code = "MATTER-1"
            c._session = MagicMock(spec=requests.Session)
            c._token = "tok"
            c._session.get.return_value = _resp(json_data={})
            c._make_request("GET", "/x")
            headers = c._session.get.call_args.kwargs["headers"]
            assert headers["X-CLIENT-CODE"] == "MATTER-1"

    def test_token_refresh_from_response_header(self, client):
        client._session.get.return_value = _resp(
            json_data={}, headers={"X-NEXT-GEN-CSO": "newtoken"}
        )
        client._make_request("GET", "/x")
        assert client._token == "newtoken"

    def test_404_raises_not_found(self, client):
        client._session.get.return_value = _resp(status_code=404)
        with pytest.raises(PCLNotFoundError):
            client._make_request("GET", "/cases/missing")

    def test_406_validation_error_with_json_message(self, client):
        client._session.post.return_value = _resp(
            status_code=406, json_data={"message": "bad field"}
        )
        with pytest.raises(PCLValidationError, match="bad field"):
            client._make_request("POST", "/cases/find", payload={})

    def test_406_validation_error_with_text_fallback(self, client):
        resp = _resp(status_code=406, text="plain text error")
        resp.json.side_effect = ValueError("not json")
        client._session.post.return_value = resp
        with pytest.raises(PCLValidationError, match="plain text error"):
            client._make_request("POST", "/cases/find", payload={})

    def test_500_raises_pclerror_via_raise_for_status(self, client):
        client._session.get.return_value = _resp(status_code=500)
        with pytest.raises(PCLError):
            client._make_request("GET", "/x")

    def test_network_exception_wrapped(self, client):
        client._session.get.side_effect = requests.ConnectionError("down")
        with pytest.raises(PCLError, match="Network error"):
            client._make_request("GET", "/x")

    def test_401_retries_with_fresh_auth_then_succeeds(self, client):
        first = _resp(status_code=401)
        second = _resp(json_data={"ok": True})
        client._session.get.side_effect = [first, second]
        client._mock_auth.return_value = AuthResult(success=True, token="fresh")
        resp = client._make_request("GET", "/x")
        assert resp.json() == {"ok": True}
        # token cleared then re-authenticated
        client._mock_auth.assert_called_once()

    def test_401_after_retry_raises(self, client):
        # retry_auth False path: a 401 with retry disabled
        client._session.get.return_value = _resp(status_code=401)
        with pytest.raises(PCLAuthError, match="after retry"):
            client._make_request("GET", "/x", retry_auth=False)


# ---------------------------------------------------------------------------
# Immediate searches
# ---------------------------------------------------------------------------


class TestImmediateSearches:
    def test_search_cases(self, client):
        client._session.post.return_value = _resp(json_data=CASE_PAGE_LAST)
        result = client.search_cases(CaseSearchCriteria(case_title="Apple"))
        assert len(result.content) == 1
        assert result.content[0].case_link.endswith("500997")
        assert result.receipt.fee_cents == 10
        # endpoint includes page param
        assert "page=0" in client._session.post.call_args[0][0]

    def test_search_cases_with_page(self, client):
        client._session.post.return_value = _resp(json_data=_case_page(2, True))
        client.search_cases(CaseSearchCriteria(case_title="Apple"), page=2)
        assert "page=2" in client._session.post.call_args[0][0]

    def test_search_parties(self, client):
        client._session.post.return_value = _resp(json_data=PARTY_PAGE_LAST)
        result = client.search_parties(PartySearchCriteria(last_name="Smith"))
        assert result.content[0].full_name == "John Smith"
        assert "/parties/find" in client._session.post.call_args[0][0]


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


class TestPagination:
    def test_fetch_all_pages_stops_on_last(self, client):
        pages = [
            _resp(json_data=_case_page(0, False)),
            _resp(json_data=_case_page(1, False)),
            _resp(json_data=_case_page(2, True)),
        ]
        client._session.post.side_effect = pages
        results = client.search_cases_all_pages(CaseSearchCriteria(case_title="x"))
        assert len(results) == 3
        assert results[-1].page_info.last is True

    def test_fetch_all_pages_respects_max_pages(self, client):
        # never-last responses; max_pages caps the loop
        client._session.post.return_value = _resp(json_data=_case_page(0, False))
        results = client.search_cases_all_pages(
            CaseSearchCriteria(case_title="x"), max_pages=2
        )
        assert len(results) == 2

    def test_search_parties_all_pages(self, client):
        client._session.post.return_value = _resp(json_data=PARTY_PAGE_LAST)
        results = client.search_parties_all_pages(PartySearchCriteria(last_name="Smith"))
        assert len(results) == 1


# ---------------------------------------------------------------------------
# Batch searches
# ---------------------------------------------------------------------------


class TestBatchSearches:
    def test_start_batch_case_search(self, client):
        client._session.post.return_value = _resp(
            json_data={"reportId": 42, "status": "WAITING"}
        )
        job = client.start_batch_case_search(CaseSearchCriteria(case_title="x"))
        assert job.report_id == 42
        assert job.is_running is True
        assert "/cases/download" in client._session.post.call_args[0][0]

    def test_start_batch_party_search(self, client):
        client._session.post.return_value = _resp(
            json_data={"reportId": 7, "status": "RUNNING"}
        )
        job = client.start_batch_party_search(PartySearchCriteria(last_name="x"))
        assert job.report_id == 7
        assert "/parties/download" in client._session.post.call_args[0][0]

    def test_get_batch_status(self, client):
        client._session.get.return_value = _resp(
            json_data={"reportId": 42, "status": "COMPLETED"}
        )
        job = client.get_batch_status(42, search_type="cases")
        assert job.is_complete is True
        assert "/cases/download/status/42" in client._session.get.call_args[0][0]

    def test_list_batch_jobs(self, client):
        client._session.get.return_value = _resp(
            json_data={"content": [{"reportId": 1, "status": "COMPLETED"}]}
        )
        resp = client.list_batch_jobs(search_type="parties")
        assert len(resp.content) == 1
        assert "/parties/reports" in client._session.get.call_args[0][0]

    def test_download_batch_results_cases(self, client):
        client._session.get.return_value = _resp(json_data=CASE_PAGE_LAST)
        resp = client.download_batch_results(42, search_type="cases")
        assert resp.content[0].court_id == "nysd"
        assert "/cases/download/42" in client._session.get.call_args[0][0]

    def test_download_batch_results_parties(self, client):
        client._session.get.return_value = _resp(json_data=PARTY_PAGE_LAST)
        resp = client.download_batch_results(7, search_type="parties")
        assert resp.content[0].last_name == "Smith"

    def test_delete_batch_job_success(self, client):
        client._session.delete.return_value = _resp(status_code=204)
        assert client.delete_batch_job(42) is True

    def test_delete_batch_job_not_deleted(self, client):
        client._session.delete.return_value = _resp(status_code=200)
        assert client.delete_batch_job(42) is False
