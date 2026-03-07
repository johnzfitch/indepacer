"""Pydantic models for PACER Case Locator (PCL) API responses."""

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class SearchCriteriaMixin:
    """Mixin providing to_api_dict() for search criteria models."""

    def to_api_dict(self) -> dict:
        """Convert to API request format, excluding empty values."""
        result = {}
        for k, v in self.model_dump(by_alias=True, exclude_none=True).items():
            if v == [] or v == "":
                continue
            if isinstance(v, dict):
                v = {kk: vv for kk, vv in v.items() if vv not in (None, [], "")}
                if not v:
                    continue
            result[k] = v
        return result


# =============================================================================
# Response Models
# =============================================================================


class Receipt(BaseModel):
    """Billing receipt from a PCL search."""

    transaction_date: Optional[str] = Field(None, alias="transactionDate")
    billable_pages: int = Field(0, alias="billablePages")
    login_id: Optional[str] = Field(None, alias="loginId")
    client_code: Optional[str] = Field(None, alias="clientCode")
    firm_id: Optional[str] = Field(None, alias="firmId")
    search: Optional[str] = None
    description: Optional[str] = None
    cso_id: Optional[int] = Field(None, alias="csoId")
    report_id: Optional[str] = Field(None, alias="reportId")
    search_fee: Optional[str] = Field(None, alias="searchFee")

    @property
    def fee_cents(self) -> int:
        """Get search fee in cents."""
        if self.search_fee:
            try:
                return int(float(self.search_fee) * 100)
            except ValueError:
                return 0
        return 0


class PageInfo(BaseModel):
    """Pagination information for search results."""

    number: int = 0  # Current page (0-indexed)
    size: int = 54  # Results per page
    total_pages: int = Field(0, alias="totalPages")
    total_elements: int = Field(0, alias="totalElements")
    number_of_elements: int = Field(0, alias="numberOfElements")
    first: bool = True
    last: bool = True


class CourtCase(BaseModel):
    """Court case information (nested in party results or standalone)."""

    court_id: Optional[str] = Field(None, alias="courtId")
    case_id: Optional[int] = Field(None, alias="caseId")
    case_year: Optional[int] = Field(None, alias="caseYear")
    case_number: Optional[int] = Field(None, alias="caseNumber")
    case_office: Optional[str] = Field(None, alias="caseOffice")
    case_type: Optional[str] = Field(None, alias="caseType")
    case_title: Optional[str] = Field(None, alias="caseTitle")
    date_filed: Optional[str] = Field(None, alias="dateFiled")
    date_termed: Optional[str] = Field(None, alias="dateTermed")
    date_dismissed: Optional[str] = Field(None, alias="dateDismissed")
    date_discharged: Optional[str] = Field(None, alias="dateDischarged")
    effective_date_closed: Optional[str] = Field(None, alias="effectiveDateClosed")
    nature_of_suit: Optional[str] = Field(None, alias="natureOfSuit")
    bankruptcy_chapter: Optional[str] = Field(None, alias="bankruptcyChapter")
    disposition_method: Optional[str] = Field(None, alias="dispositionMethod")
    joint_bankruptcy_flag: Optional[str] = Field(None, alias="jointBankruptcyFlag")
    jurisdiction_type: Optional[str] = Field(None, alias="jurisdictionType")
    case_link: Optional[str] = Field(None, alias="caseLink")
    case_number_full: Optional[str] = Field(None, alias="caseNumberFull")
    jpml_number: Optional[int] = Field(None, alias="jpmlNumber")

    @property
    def status(self) -> str:
        """Get case status (Open/Closed/Dismissed/Discharged)."""
        if self.date_discharged:
            return "Discharged"
        if self.date_dismissed:
            return "Dismissed"
        if self.effective_date_closed:
            return "Closed"
        return "Open"


class CaseResult(CourtCase):
    """Case search result (extends CourtCase with same fields)."""

    pass


class PartyResult(BaseModel):
    """Party search result."""

    court_id: Optional[str] = Field(None, alias="courtId")
    case_id: Optional[int] = Field(None, alias="caseId")
    case_year: Optional[int] = Field(None, alias="caseYear")
    case_number: Optional[int] = Field(None, alias="caseNumber")
    last_name: Optional[str] = Field(None, alias="lastName")
    first_name: Optional[str] = Field(None, alias="firstName")
    middle_name: Optional[str] = Field(None, alias="middleName")
    generation: Optional[str] = None
    party_type: Optional[str] = Field(None, alias="partyType")
    party_role: Optional[str] = Field(None, alias="partyRole")
    jurisdiction_type: Optional[str] = Field(None, alias="jurisdictionType")
    court_case: Optional[CourtCase] = Field(None, alias="courtCase")
    # Denormalized case fields (also present at party level)
    date_filed: Optional[str] = Field(None, alias="dateFiled")
    effective_date_closed: Optional[str] = Field(None, alias="effectiveDateClosed")
    date_dismissed: Optional[str] = Field(None, alias="dateDismissed")
    date_discharged: Optional[str] = Field(None, alias="dateDischarged")
    nature_of_suit: Optional[str] = Field(None, alias="natureOfSuit")
    bankruptcy_chapter: Optional[str] = Field(None, alias="bankruptcyChapter")
    case_office: Optional[str] = Field(None, alias="caseOffice")
    case_type: Optional[str] = Field(None, alias="caseType")
    case_title: Optional[str] = Field(None, alias="caseTitle")
    case_number_full: Optional[str] = Field(None, alias="caseNumberFull")
    disposition: Optional[str] = None

    @property
    def full_name(self) -> str:
        """Get formatted full name."""
        parts = []
        if self.first_name and self.first_name.strip():
            parts.append(self.first_name.strip())
        if self.middle_name and self.middle_name.strip():
            parts.append(self.middle_name.strip())
        if self.last_name and self.last_name.strip():
            parts.append(self.last_name.strip())
        if self.generation and self.generation.strip():
            parts.append(self.generation.strip())
        return " ".join(parts) if parts else "(Unknown)"


class CaseSearchResponse(BaseModel):
    """Response from case search API."""

    receipt: Optional[Receipt] = None
    page_info: Optional[PageInfo] = Field(None, alias="pageInfo")
    content: list[CaseResult] = []
    master_case: Optional[Any] = Field(None, alias="masterCase")


class PartySearchResponse(BaseModel):
    """Response from party search API."""

    receipt: Optional[Receipt] = None
    page_info: Optional[PageInfo] = Field(None, alias="pageInfo")
    content: list[PartyResult] = []
    master_case: Optional[Any] = Field(None, alias="masterCase")


# =============================================================================
# Request/Criteria Models
# =============================================================================


class CaseSearchCriteria(SearchCriteriaMixin, BaseModel):
    """Search criteria for case searches."""

    model_config = ConfigDict(populate_by_name=True)

    # All court types
    jurisdiction_type: Optional[str] = Field(None, alias="jurisdictionType")
    case_id: Optional[int] = Field(None, alias="caseId")
    case_number_full: Optional[str] = Field(None, alias="caseNumberFull")
    case_title: Optional[str] = Field(None, alias="caseTitle")
    case_office: Optional[str] = Field(None, alias="caseOffice")
    case_number: Optional[str] = Field(None, alias="caseNumber")
    case_type: Optional[list[str]] = Field(None, alias="caseType")
    case_year: Optional[str] = Field(None, alias="caseYear")
    court_id: Optional[list[str]] = Field(None, alias="courtId")
    date_filed_from: Optional[str] = Field(None, alias="dateFiledFrom")
    date_filed_to: Optional[str] = Field(None, alias="dateFiledTo")
    effective_date_closed_from: Optional[str] = Field(None, alias="effectiveDateClosedFrom")
    effective_date_closed_to: Optional[str] = Field(None, alias="effectiveDateClosedTo")
    # Bankruptcy only
    federal_bankruptcy_chapter: Optional[list[str]] = Field(None, alias="federalBankruptcyChapter")
    date_dismissed_from: Optional[str] = Field(None, alias="dateDismissedFrom")
    date_dismissed_to: Optional[str] = Field(None, alias="dateDismissedTo")
    date_discharged_from: Optional[str] = Field(None, alias="dateDischargedFrom")
    date_discharged_to: Optional[str] = Field(None, alias="dateDischargedTo")
    # Civil/Appellate only
    nature_of_suit: Optional[list[str]] = Field(None, alias="natureOfSuit")
    # JPML only
    jpml_number: Optional[int] = Field(None, alias="jpmlNumber")
    # Nested party search within case search
    party: Optional["PartyInCaseSearch"] = None


class PartyInCaseSearch(BaseModel):
    """Party criteria when nested in a case search."""

    last_name: Optional[str] = Field(None, alias="lastName")
    first_name: Optional[str] = Field(None, alias="firstName")
    middle_name: Optional[str] = Field(None, alias="middleName")
    role: Optional[list[str]] = None


class PartySearchCriteria(SearchCriteriaMixin, BaseModel):
    """Search criteria for party searches."""

    model_config = ConfigDict(populate_by_name=True)

    # Party fields
    last_name: Optional[str] = Field(None, alias="lastName")
    first_name: Optional[str] = Field(None, alias="firstName")
    middle_name: Optional[str] = Field(None, alias="middleName")
    generation: Optional[str] = None
    exact_name_match: Optional[bool] = Field(None, alias="exactNameMatch")
    ssn: Optional[str] = None  # Bankruptcy only
    party_type: Optional[str] = Field(None, alias="partyType")
    role: Optional[list[str]] = None
    # Case year range
    case_year_from: Optional[int] = Field(None, alias="caseYearFrom")
    case_year_to: Optional[int] = Field(None, alias="caseYearTo")
    # Nested case criteria
    court_case: Optional[CaseSearchCriteria] = Field(None, alias="courtCase")


# =============================================================================
# Batch Job Models
# =============================================================================


class BatchJobInfo(BaseModel):
    """Batch job status information."""

    report_id: int = Field(..., alias="reportId")
    status: str  # WAITING, RUNNING, COMPLETED
    start_time: Optional[str] = Field(None, alias="startTime")
    end_time: Optional[str] = Field(None, alias="endTime")
    record_count: Optional[int] = Field(None, alias="recordCount")
    unbilled_page_count: Optional[int] = Field(None, alias="unbilledPageCount")
    download_fee: Optional[float] = Field(None, alias="downloadFee")
    pages: Optional[int] = None
    search_type: Optional[str] = Field(None, alias="searchType")
    criteria: Optional[dict] = None

    @property
    def is_complete(self) -> bool:
        """Check if batch job is complete."""
        return self.status == "COMPLETED"

    @property
    def is_running(self) -> bool:
        """Check if batch job is still running."""
        return self.status in ("WAITING", "RUNNING")


class BatchJobListResponse(BaseModel):
    """Response from batch job list API."""

    receipt: Optional[Receipt] = None
    page_info: Optional[PageInfo] = Field(None, alias="pageInfo")
    content: list[BatchJobInfo] = []
