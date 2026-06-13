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

    transaction_date: str | None = Field(None, alias="transactionDate")
    billable_pages: int = Field(0, alias="billablePages")
    login_id: str | None = Field(None, alias="loginId")
    client_code: str | None = Field(None, alias="clientCode")
    firm_id: str | None = Field(None, alias="firmId")
    search: str | None = None
    description: str | None = None
    cso_id: int | None = Field(None, alias="csoId")
    report_id: str | None = Field(None, alias="reportId")
    search_fee: str | None = Field(None, alias="searchFee")

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

    court_id: str | None = Field(None, alias="courtId")
    case_id: int | None = Field(None, alias="caseId")
    case_year: int | None = Field(None, alias="caseYear")
    case_number: int | None = Field(None, alias="caseNumber")
    case_office: str | None = Field(None, alias="caseOffice")
    case_type: str | None = Field(None, alias="caseType")
    case_title: str | None = Field(None, alias="caseTitle")
    date_filed: str | None = Field(None, alias="dateFiled")
    date_termed: str | None = Field(None, alias="dateTermed")
    date_dismissed: str | None = Field(None, alias="dateDismissed")
    date_discharged: str | None = Field(None, alias="dateDischarged")
    effective_date_closed: str | None = Field(None, alias="effectiveDateClosed")
    nature_of_suit: str | None = Field(None, alias="natureOfSuit")
    bankruptcy_chapter: str | None = Field(None, alias="bankruptcyChapter")
    disposition_method: str | None = Field(None, alias="dispositionMethod")
    joint_bankruptcy_flag: str | None = Field(None, alias="jointBankruptcyFlag")
    jurisdiction_type: str | None = Field(None, alias="jurisdictionType")
    case_link: str | None = Field(None, alias="caseLink")
    case_number_full: str | None = Field(None, alias="caseNumberFull")
    jpml_number: int | None = Field(None, alias="jpmlNumber")

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

    court_id: str | None = Field(None, alias="courtId")
    case_id: int | None = Field(None, alias="caseId")
    case_year: int | None = Field(None, alias="caseYear")
    case_number: int | None = Field(None, alias="caseNumber")
    last_name: str | None = Field(None, alias="lastName")
    first_name: str | None = Field(None, alias="firstName")
    middle_name: str | None = Field(None, alias="middleName")
    generation: str | None = None
    party_type: str | None = Field(None, alias="partyType")
    party_role: str | None = Field(None, alias="partyRole")
    jurisdiction_type: str | None = Field(None, alias="jurisdictionType")
    court_case: CourtCase | None = Field(None, alias="courtCase")
    # Denormalized case fields (also present at party level)
    date_filed: str | None = Field(None, alias="dateFiled")
    effective_date_closed: str | None = Field(None, alias="effectiveDateClosed")
    date_dismissed: str | None = Field(None, alias="dateDismissed")
    date_discharged: str | None = Field(None, alias="dateDischarged")
    nature_of_suit: str | None = Field(None, alias="natureOfSuit")
    bankruptcy_chapter: str | None = Field(None, alias="bankruptcyChapter")
    case_office: str | None = Field(None, alias="caseOffice")
    case_type: str | None = Field(None, alias="caseType")
    case_title: str | None = Field(None, alias="caseTitle")
    case_number_full: str | None = Field(None, alias="caseNumberFull")
    disposition: str | None = None

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

    receipt: Receipt | None = None
    page_info: PageInfo | None = Field(None, alias="pageInfo")
    content: list[CaseResult] = []
    master_case: Any | None = Field(None, alias="masterCase")


class PartySearchResponse(BaseModel):
    """Response from party search API."""

    receipt: Receipt | None = None
    page_info: PageInfo | None = Field(None, alias="pageInfo")
    content: list[PartyResult] = []
    master_case: Any | None = Field(None, alias="masterCase")


# =============================================================================
# Request/Criteria Models
# =============================================================================


class CaseSearchCriteria(SearchCriteriaMixin, BaseModel):
    """Search criteria for case searches."""

    model_config = ConfigDict(populate_by_name=True)

    # All court types
    jurisdiction_type: str | None = Field(None, alias="jurisdictionType")
    case_id: int | None = Field(None, alias="caseId")
    case_number_full: str | None = Field(None, alias="caseNumberFull")
    case_title: str | None = Field(None, alias="caseTitle")
    case_office: str | None = Field(None, alias="caseOffice")
    case_number: str | None = Field(None, alias="caseNumber")
    case_type: list[str] | None = Field(None, alias="caseType")
    case_year: str | None = Field(None, alias="caseYear")
    court_id: list[str] | None = Field(None, alias="courtId")
    date_filed_from: str | None = Field(None, alias="dateFiledFrom")
    date_filed_to: str | None = Field(None, alias="dateFiledTo")
    effective_date_closed_from: str | None = Field(None, alias="effectiveDateClosedFrom")
    effective_date_closed_to: str | None = Field(None, alias="effectiveDateClosedTo")
    # Bankruptcy only
    federal_bankruptcy_chapter: list[str] | None = Field(None, alias="federalBankruptcyChapter")
    date_dismissed_from: str | None = Field(None, alias="dateDismissedFrom")
    date_dismissed_to: str | None = Field(None, alias="dateDismissedTo")
    date_discharged_from: str | None = Field(None, alias="dateDischargedFrom")
    date_discharged_to: str | None = Field(None, alias="dateDischargedTo")
    # Civil/Appellate only
    nature_of_suit: list[str] | None = Field(None, alias="natureOfSuit")
    # JPML only
    jpml_number: int | None = Field(None, alias="jpmlNumber")
    # Nested party search within case search
    party: Optional["PartyInCaseSearch"] = None


class PartyInCaseSearch(BaseModel):
    """Party criteria when nested in a case search."""

    last_name: str | None = Field(None, alias="lastName")
    first_name: str | None = Field(None, alias="firstName")
    middle_name: str | None = Field(None, alias="middleName")
    role: list[str] | None = None


class PartySearchCriteria(SearchCriteriaMixin, BaseModel):
    """Search criteria for party searches."""

    model_config = ConfigDict(populate_by_name=True)

    # Party fields
    last_name: str | None = Field(None, alias="lastName")
    first_name: str | None = Field(None, alias="firstName")
    middle_name: str | None = Field(None, alias="middleName")
    generation: str | None = None
    exact_name_match: bool | None = Field(None, alias="exactNameMatch")
    ssn: str | None = None  # Bankruptcy only
    party_type: str | None = Field(None, alias="partyType")
    role: list[str] | None = None
    # Case year range
    case_year_from: int | None = Field(None, alias="caseYearFrom")
    case_year_to: int | None = Field(None, alias="caseYearTo")
    # Nested case criteria
    court_case: CaseSearchCriteria | None = Field(None, alias="courtCase")


# =============================================================================
# Batch Job Models
# =============================================================================


class BatchJobInfo(BaseModel):
    """Batch job status information."""

    report_id: int = Field(..., alias="reportId")
    status: str  # WAITING, RUNNING, COMPLETED
    start_time: str | None = Field(None, alias="startTime")
    end_time: str | None = Field(None, alias="endTime")
    record_count: int | None = Field(None, alias="recordCount")
    unbilled_page_count: int | None = Field(None, alias="unbilledPageCount")
    download_fee: float | None = Field(None, alias="downloadFee")
    pages: int | None = None
    search_type: str | None = Field(None, alias="searchType")
    criteria: dict | None = None

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

    receipt: Receipt | None = None
    page_info: PageInfo | None = Field(None, alias="pageInfo")
    content: list[BatchJobInfo] = []
