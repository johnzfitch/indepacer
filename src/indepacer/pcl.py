"""PACER Case Locator (PCL) API client.

This module provides a client for searching the PCL API, which is the nationwide
index of federal court cases. Supports both immediate searches (paginated, max
5,400 results) and batch searches (async, max 108,000 results).

API Documentation: https://pacer.uscourts.gov/help/pacer/pacer-case-locator-api-user-guide
"""

from dataclasses import dataclass, field
from typing import Callable, Optional, TypeVar

import requests

T = TypeVar("T")

from .auth import authenticate
from .config import PacerConfig
from .security import create_secure_session
from .models import (
    BatchJobInfo,
    BatchJobListResponse,
    CaseSearchCriteria,
    CaseSearchResponse,
    PartySearchCriteria,
    PartySearchResponse,
)


class PCLError(Exception):
    """Base exception for PCL API errors."""

    pass


class PCLAuthError(PCLError):
    """Authentication error (401)."""

    pass


class PCLValidationError(PCLError):
    """Validation error (406) - invalid search parameters."""

    pass


class PCLNotFoundError(PCLError):
    """Resource not found (404)."""

    pass


@dataclass
class PCLClient:
    """Client for the PACER Case Locator API.

    Handles authentication, token refresh, and all API operations.

    Usage:
        config = get_config()
        client = PCLClient(config)
        results = client.search_cases(CaseSearchCriteria(case_title="Apple"))
    """

    config: PacerConfig
    _token: Optional[str] = field(default=None, repr=False)
    _session: requests.Session = field(default_factory=requests.Session, repr=False)

    def __post_init__(self):
        """Initialize session with TLS hardening and default headers."""
        self._session = create_secure_session(tls_level=self.config.tls_level)
        self._session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    @property
    def token(self) -> str:
        """Get current auth token, authenticating if needed."""
        if not self._token:
            self._authenticate()
        return self._token

    def _authenticate(self) -> None:
        """Authenticate with PACER and store token."""
        result = authenticate(self.config)
        if not result.success:
            raise PCLAuthError(f"Authentication failed: {result.error}")
        self._token = result.token

    def _make_request(
        self,
        method: str,
        endpoint: str,
        payload: Optional[dict] = None,
        retry_auth: bool = True,
    ) -> requests.Response:
        """Make an authenticated request to the PCL API.

        Args:
            method: HTTP method (GET, POST, DELETE)
            endpoint: API endpoint path (e.g., "/cases/find")
            payload: JSON payload for POST requests
            retry_auth: Whether to retry with fresh auth on 401

        Returns:
            Response object

        Raises:
            PCLAuthError: Authentication failed
            PCLValidationError: Invalid search parameters (406)
            PCLError: Other API errors
        """
        url = f"{self.config.pcl_url}{endpoint}"
        headers = {"X-NEXT-GEN-CSO": self.token}

        if self.config.client_code:
            headers["X-CLIENT-CODE"] = self.config.client_code

        try:
            if method.upper() == "GET":
                response = self._session.get(url, headers=headers, timeout=60)
            elif method.upper() == "POST":
                response = self._session.post(
                    url, headers=headers, json=payload, timeout=60
                )
            elif method.upper() == "DELETE":
                response = self._session.delete(url, headers=headers, timeout=60)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            # Check for token refresh in response headers
            if new_token := response.headers.get("X-NEXT-GEN-CSO"):
                self._token = new_token

            # Handle error responses
            if response.status_code == 401:
                if retry_auth:
                    self._token = None
                    self._authenticate()
                    return self._make_request(method, endpoint, payload, retry_auth=False)
                raise PCLAuthError("Authentication failed after retry")

            if response.status_code == 404:
                raise PCLNotFoundError(f"Resource not found: {endpoint}")

            if response.status_code == 406:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("message", response.text)
                except Exception:
                    error_msg = response.text
                raise PCLValidationError(f"Invalid search parameters: {error_msg}")

            response.raise_for_status()
            return response

        except requests.exceptions.RequestException as e:
            raise PCLError(f"Network error: {e}") from e

    # =========================================================================
    # Immediate Searches (paginated, max 5,400 results)
    # =========================================================================

    def search_cases(
        self,
        criteria: CaseSearchCriteria,
        page: int = 0,
    ) -> CaseSearchResponse:
        """Search for cases matching the given criteria.

        Args:
            criteria: Search criteria (case number, title, court, dates, etc.)
            page: Page number (0-indexed, 54 results per page, max 100 pages)

        Returns:
            CaseSearchResponse with results and pagination info
        """
        endpoint = f"/cases/find?page={page}"
        payload = criteria.to_api_dict()

        response = self._make_request("POST", endpoint, payload)
        return CaseSearchResponse.model_validate(response.json())

    def search_parties(
        self,
        criteria: PartySearchCriteria,
        page: int = 0,
    ) -> PartySearchResponse:
        """Search for parties matching the given criteria.

        Args:
            criteria: Search criteria (name, SSN, case filters, etc.)
            page: Page number (0-indexed, 54 results per page, max 100 pages)

        Returns:
            PartySearchResponse with results and pagination info
        """
        endpoint = f"/parties/find?page={page}"
        payload = criteria.to_api_dict()

        response = self._make_request("POST", endpoint, payload)
        return PartySearchResponse.model_validate(response.json())

    def _fetch_all_pages(
        self,
        search_fn: Callable,
        criteria,
        max_pages: int = 100,
    ) -> list[T]:
        """Fetch all pages using the given search function.

        Args:
            search_fn: Search method (search_cases or search_parties)
            criteria: Search criteria
            max_pages: Maximum pages to fetch (default 100, the API limit)

        Returns:
            List of response objects, one per page
        """
        results = []
        page = 0

        while page < max_pages:
            response = search_fn(criteria, page=page)
            results.append(response)

            if response.page_info and response.page_info.last:
                break
            page += 1

        return results

    def search_cases_all_pages(
        self,
        criteria: CaseSearchCriteria,
        max_pages: int = 100,
    ) -> list[CaseSearchResponse]:
        """Fetch all pages of case search results."""
        return self._fetch_all_pages(self.search_cases, criteria, max_pages)

    def search_parties_all_pages(
        self,
        criteria: PartySearchCriteria,
        max_pages: int = 100,
    ) -> list[PartySearchResponse]:
        """Fetch all pages of party search results."""
        return self._fetch_all_pages(self.search_parties, criteria, max_pages)

    # =========================================================================
    # Batch Searches (async, max 108,000 results)
    # =========================================================================

    def start_batch_case_search(self, criteria: CaseSearchCriteria) -> BatchJobInfo:
        """Start a batch case search job.

        Args:
            criteria: Search criteria

        Returns:
            BatchJobInfo with job ID and initial status
        """
        endpoint = "/cases/download"
        payload = criteria.to_api_dict()

        response = self._make_request("POST", endpoint, payload)
        return BatchJobInfo.model_validate(response.json())

    def start_batch_party_search(self, criteria: PartySearchCriteria) -> BatchJobInfo:
        """Start a batch party search job.

        Args:
            criteria: Search criteria

        Returns:
            BatchJobInfo with job ID and initial status
        """
        endpoint = "/parties/download"
        payload = criteria.to_api_dict()

        response = self._make_request("POST", endpoint, payload)
        return BatchJobInfo.model_validate(response.json())

    def get_batch_status(self, report_id: int, search_type: str = "cases") -> BatchJobInfo:
        """Get status of a batch search job.

        Args:
            report_id: Job ID from start_batch_*_search
            search_type: "cases" or "parties"

        Returns:
            BatchJobInfo with current status
        """
        endpoint = f"/{search_type}/download/status/{report_id}"
        response = self._make_request("GET", endpoint)
        return BatchJobInfo.model_validate(response.json())

    def list_batch_jobs(self, search_type: str = "cases") -> BatchJobListResponse:
        """List all batch jobs for the current user.

        Args:
            search_type: "cases" or "parties"

        Returns:
            BatchJobListResponse with list of jobs
        """
        endpoint = f"/{search_type}/reports"
        response = self._make_request("GET", endpoint)
        return BatchJobListResponse.model_validate(response.json())

    def download_batch_results(
        self,
        report_id: int,
        search_type: str = "cases",
    ) -> CaseSearchResponse | PartySearchResponse:
        """Download results from a completed batch job.

        Args:
            report_id: Job ID from start_batch_*_search
            search_type: "cases" or "parties"

        Returns:
            CaseSearchResponse or PartySearchResponse with all results
        """
        endpoint = f"/{search_type}/download/{report_id}"
        response = self._make_request("GET", endpoint)
        data = response.json()

        if search_type == "cases":
            return CaseSearchResponse.model_validate(data)
        return PartySearchResponse.model_validate(data)

    def delete_batch_job(self, report_id: int, search_type: str = "cases") -> bool:
        """Delete a batch job and its results.

        Args:
            report_id: Job ID to delete
            search_type: "cases" or "parties"

        Returns:
            True if deleted successfully
        """
        endpoint = f"/{search_type}/reports/{report_id}"
        response = self._make_request("DELETE", endpoint)
        return response.status_code == 204
