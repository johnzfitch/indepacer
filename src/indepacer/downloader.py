"""Modern PACER docket downloader using CM/ECF direct access.

Downloads dockets from CM/ECF court systems using authenticated requests.
The PCL API only provides case search - actual docket content must be
fetched from individual court CM/ECF systems.
"""

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests

from .auth import authenticate, AuthResult
from .config import PacerConfig
from .courts import get_cso_court_id, get_ecf_domain_from_url
from .models import CaseSearchCriteria


@dataclass
class DownloadResult:
    """Result of a docket download attempt."""
    success: bool
    filepath: Optional[Path] = None
    docs_filepath: Optional[Path] = None  # Path to docs.json manifest
    error: Optional[str] = None
    pages: int = 0
    cost: float = 0.0


def extract_document_metadata(
    html: str,
    base_url: str,
    case_number: str = "",
    court_id: str = "",
) -> dict:
    """Extract document metadata from docket HTML for caching.

    Args:
        html: Raw docket HTML
        base_url: ECF base URL (e.g., "https://ecf.nysd.uscourts.gov")
        case_number: Case number for metadata
        court_id: Court identifier for metadata

    Returns:
        Dictionary with document metadata suitable for docs.json
    """
    import json
    from datetime import datetime, timezone
    from urllib.parse import urljoin

    from .parser import parse_docket

    try:
        docket = parse_docket(html)
    except Exception:
        # If parsing fails, return empty manifest
        return {
            "case_number": case_number,
            "court_id": court_id,
            "base_url": base_url,
            "downloaded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "documents": [],
            "parse_error": True,
        }

    documents = []
    for entry in docket.entries:
        if entry.doc_num and entry.doc_url:
            documents.append({
                "seq": entry.seq,
                "doc_num": entry.doc_num,
                "date": entry.date,
                "description": entry.text[:200] if entry.text else "",
                "url": urljoin(base_url + "/", entry.doc_url),
                "has_attachments": entry.has_attachments,
                "attachment_count": entry.attachment_count,
            })

    return {
        "case_number": case_number or docket.meta.case_number or "",
        "court_id": court_id or docket.meta.court_id or "",
        "case_title": docket.meta.case_title or "",
        "base_url": base_url,
        "downloaded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "document_count": len(documents),
        "documents": documents,
    }


def load_cached_documents(case_dir: Path) -> Optional[dict]:
    """Load cached document metadata for a case.

    Args:
        case_dir: Path to case directory containing docs.json

    Returns:
        Dict from docs.json or None if not found
    """
    import json

    docs_path = case_dir / "docs.json"
    if docs_path.exists():
        try:
            return json.loads(docs_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            pass
    return None


def get_document_by_number(case_dir: Path, doc_number: str) -> Optional[dict]:
    """Get document info by number from cached metadata.

    Args:
        case_dir: Path to case directory
        doc_number: Document number to find

    Returns:
        Document dict with url, date, description or None
    """
    docs = load_cached_documents(case_dir)
    if docs:
        for doc in docs.get("documents", []):
            if doc.get("doc_num") == doc_number:
                return doc
    return None


class DocketDownloader:
    """Downloads dockets from CM/ECF court systems."""

    def __init__(self, config: PacerConfig, verbose: bool = False):
        self.config = config
        self.verbose = verbose
        self.session = requests.Session()
        self.token: Optional[str] = None

    def _log(self, msg: str):
        """Print trace message if verbose mode enabled."""
        if self.verbose:
            print(f"[TRACE] {msg}")

    def authenticate(self) -> bool:
        """Authenticate with PACER and get session token."""
        self._log("Authenticating with PACER...")
        result = authenticate(self.config)

        if result.success and result.token:
            self.token = result.token
            self._log(f"Authentication successful, token length: {len(self.token)}")
            return True
        else:
            self._log(f"Authentication failed: {result.error}")
            return False

    def _cso_login(self, court_id: str, app_url: str) -> bool:
        """Perform CSO (Central Sign-On) login for CM/ECF access.

        The CM/ECF systems redirect to pacer.login.uscourts.gov for authentication.
        We need to POST credentials there and follow redirects to establish a session.

        Args:
            court_id: Court ID (e.g., 'NYSDC' for NYSD)
            app_url: The app URL to redirect back to after login

        Returns:
            True if login successful (session cookies set)
        """
        # CSO login URL
        cso_url = "https://pacer.login.uscourts.gov/csologin/login.jsf"

        self._log(f"Performing CSO login for {court_id}...")

        # First, get the login page to obtain any required tokens (CSRF, etc.)
        try:
            resp = self.session.get(cso_url, params={
                "pscCourtId": court_id,
                "appurl": app_url,
            }, timeout=30)
            self._log(f"Login page response: {resp.status_code}")

            # Extract the ViewState (JSF CSRF token) - both javax and jakarta variants
            viewstate = None
            import re
            vs_match = re.search(r'name="(?:javax|jakarta)\.faces\.ViewState"[^>]*value="([^"]*)"', resp.text)
            if vs_match:
                viewstate = vs_match.group(1)
                self._log(f"Found ViewState: {viewstate[:50]}...")

            # Prepare login form data - using loginForm: prefix
            form_data = {
                "loginForm": "loginForm",
                "loginForm:loginName": self.config.username,
                "loginForm:password": self.config.password.get_secret_value(),
                "loginForm:clientCode": self.config.client_code or "",
                "loginForm:fbtnLogin": "",  # Submit button
            }

            # Add ViewState with correct name based on what's in the page
            if "jakarta.faces.ViewState" in resp.text:
                form_data["jakarta.faces.ViewState"] = viewstate or ""
            else:
                form_data["javax.faces.ViewState"] = viewstate or ""

            self._log(f"Login form data keys: {list(form_data.keys())}")

            # Submit login form
            resp = self.session.post(
                cso_url,
                data=form_data,
                params={"pscCourtId": court_id, "appurl": app_url},
                allow_redirects=True,
                timeout=60,
            )

            self._log(f"Login POST response: {resp.status_code}, final URL: {resp.url}")
            self._log(f"Response length: {len(resp.text)}")

            # Check if MFA is now required (shows after initial login)
            if "mfaForm" in resp.text and self.config.has_mfa and self.config.totp_secret:
                self._log("MFA step required, submitting OTP via PrimeFaces AJAX...")

                # Get new ViewState for MFA form
                vs_match = re.search(r'name="(?:javax|jakarta)\.faces\.ViewState"[^>]*value="([^"]*)"', resp.text)
                mfa_viewstate = vs_match.group(1) if vs_match else ""

                from .auth import generate_totp
                import time
                time.sleep(1)  # Brief delay to ensure fresh OTP window
                otp = generate_totp(self.config.totp_secret.get_secret_value())

                # PrimeFaces uses AJAX for MFA button - must include partial.* params
                mfa_data = {
                    "mfaForm": "mfaForm",
                    "mfaForm:mfaInput": otp,
                    "mfaForm:btnOk": "",
                    "jakarta.faces.partial.ajax": "true",
                    "jakarta.faces.source": "mfaForm:btnOk",
                    "jakarta.faces.partial.execute": "@all",
                    "jakarta.faces.partial.render": "@all",
                }

                if "jakarta.faces.ViewState" in resp.text:
                    mfa_data["jakarta.faces.ViewState"] = mfa_viewstate
                else:
                    mfa_data["javax.faces.ViewState"] = mfa_viewstate

                mfa_headers = {
                    "X-Requested-With": "XMLHttpRequest",
                    "Faces-Request": "partial/ajax",
                }

                resp = self.session.post(
                    cso_url,
                    data=mfa_data,
                    params={"pscCourtId": court_id, "appurl": app_url},
                    headers=mfa_headers,
                    allow_redirects=True,
                    timeout=60,
                )
                self._log(f"MFA AJAX response: {resp.status_code}")

                # PrimeFaces returns XML with redirect URL
                if "redirect" in resp.text.lower():
                    redirect_match = re.search(r'<redirect url="([^"]+)"', resp.text)
                    if redirect_match:
                        redirect_url = redirect_match.group(1).replace("&amp;", "&")
                        self._log(f"Following MFA redirect to: {redirect_url}")
                        resp = self.session.get(redirect_url, allow_redirects=True, timeout=30)

            # Check if we ended up at the target app URL (successful login)
            if app_url in resp.url or "DktRpt" in resp.url or "iqquerymenu" in resp.url:
                self._log("CSO login successful - redirected to app")
                return True

            # Check for login errors
            if "login" in resp.url.lower() or "error" in resp.text.lower():
                self._log(f"CSO login may have failed, checking response...")
                if "Invalid" in resp.text or "incorrect" in resp.text.lower():
                    self._log("Login failed: Invalid credentials")
                    return False

            # If we have cookies, we might be authenticated
            if "PacerUser" in self.session.cookies or "KEY" in self.session.cookies:
                self._log("CSO login successful - have session cookies")
                return True

            self._log(f"CSO login status uncertain, cookies: {list(self.session.cookies.keys())}")
            return True  # Proceed and see if requests work

        except Exception as e:
            self._log(f"CSO login error: {e}")
            return False

    def _get_ecf_base_url(self, court_id: str) -> str:
        """Get the CM/ECF base URL for a court.

        Args:
            court_id: Court identifier (e.g., 'nysdce', 'cacdce')

        Returns:
            Base URL for the court's CM/ECF system
        """
        # Map court IDs to ECF domains
        # Format: {court_abbrev}dc -> {court_abbrev}d.uscourts.gov
        # e.g., nysdce -> nysd, cacdce -> cacd

        # Strip 'ce' or 'e' suffix if present (civil/electronic)
        court_abbrev = court_id.rstrip('e').rstrip('c')

        # Handle bankruptcy courts (bk suffix)
        if court_abbrev.endswith('bk'):
            return f"https://ecf.{court_abbrev}.uscourts.gov"

        # District courts typically use format like nysd, cacd
        return f"https://ecf.{court_abbrev}.uscourts.gov"

    def _get_case_id_from_link(self, case_link: str) -> Optional[str]:
        """Extract case ID from a PCL case link URL.

        Args:
            case_link: URL like https://ecf.nysd.uscourts.gov/cgi-bin/iqquerymenu.pl?500997

        Returns:
            Case ID string (e.g., '500997')
        """
        match = re.search(r'\?(\d+)$', case_link)
        return match.group(1) if match else None

    def download_docket_by_link(
        self,
        case_link: str,
        output_dir: Path,
        filename: Optional[str] = None,
    ) -> DownloadResult:
        """Download docket using a PCL case link URL.

        Args:
            case_link: CM/ECF case link from PCL search results
            output_dir: Directory to save the docket HTML
            filename: Optional custom filename (defaults to case_id.html)

        Returns:
            DownloadResult with success status and filepath
        """
        if not self.token:
            if not self.authenticate():
                return DownloadResult(
                    success=False,
                    error="Authentication failed"
                )

        self._log(f"Downloading docket from: {case_link}")

        # Parse the case link
        parsed = urlparse(case_link)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        case_id = self._get_case_id_from_link(case_link)

        if not case_id:
            return DownloadResult(
                success=False,
                error=f"Could not extract case ID from link: {case_link}"
            )

        self._log(f"Base URL: {base_url}, Case ID: {case_id}")

        # Set up headers with authentication token
        # Note: CM/ECF requires Referer header set to "https://external" to avoid CSRF warning
        headers = {
            "X-NEXT-GEN-CSO": self.token,
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "Mozilla/5.0 (compatible; PACER-CLI/1.0)",
            "Referer": "https://external",  # Magic value to skip CSRF confirmation
        }

        # Step 1: Access the query menu - check if we need to authenticate
        self._log("Accessing query menu...")
        try:
            resp = self.session.get(case_link, headers=headers, timeout=30, allow_redirects=True)
            self._log(f"Query menu response: {resp.status_code}, length: {len(resp.text)}")

            # Check for JavaScript redirect to CSO login (CM/ECF uses JS redirects)
            # Pattern: location.assign("https://pacer.login.uscourts.gov/csologin/login.jsf?...")
            if "location.assign" in resp.text and "csologin" in resp.text:
                self._log("Detected JavaScript redirect to CSO login")
                import re
                js_redirect_match = re.search(
                    r'location\.assign\(["\']([^"\']+csologin[^"\']+)["\']',
                    resp.text
                )
                if js_redirect_match:
                    redirect_url = js_redirect_match.group(1)
                    self._log(f"JS redirect URL: {redirect_url}")

                    # Extract court ID and app URL from the redirect
                    court_match = re.search(r'pscCourtId=([A-Z]+)', redirect_url)
                    psc_court_id = court_match.group(1) if court_match else "NYSDC"

                    appurl_match = re.search(r'appurl=([^&\s]+)', redirect_url)
                    app_url = appurl_match.group(1) if appurl_match else case_link

                    self._log(f"CSO login required for court: {psc_court_id}")
                    self._log(f"App URL: {app_url}")

                    # Perform CSO login
                    if not self._cso_login(psc_court_id, app_url):
                        return DownloadResult(
                            success=False,
                            error="CSO login failed"
                        )

                    # Retry the request after login
                    resp = self.session.get(case_link, headers=headers, timeout=30)
                    self._log(f"After CSO login, response: {resp.status_code}, length: {len(resp.text)}")

                    # Check again for JS redirect (login may have failed)
                    if "location.assign" in resp.text and "csologin" in resp.text:
                        return DownloadResult(
                            success=False,
                            error="CSO login failed - still being redirected to login"
                        )

            if resp.status_code == 401:
                return DownloadResult(
                    success=False,
                    error="Authentication token rejected by CM/ECF"
                )

            # Check if still on login page
            if "csologin" in resp.url or "login.jsf" in resp.url:
                return DownloadResult(
                    success=False,
                    error="Session expired or authentication failed"
                )

        except requests.RequestException as e:
            return DownloadResult(success=False, error=f"Network error: {e}")

        # Step 2: Request the docket report
        # The docket report URL pattern varies but typically:
        # /cgi-bin/DktRpt.pl?{case_id}
        docket_url = urljoin(base_url, f"/cgi-bin/DktRpt.pl?{case_id}")
        self._log(f"Requesting docket report: {docket_url}")

        try:
            # First request to DktRpt.pl may return a form to configure report options
            resp = self.session.get(docket_url, headers=headers, timeout=30)
            self._log(f"Docket report response: {resp.status_code}, length: {len(resp.text)}")

            # Check if this is the docket or a form
            if "Sort by" in resp.text or "date_from" in resp.text:
                # This is the report configuration form - submit it for all entries
                self._log("Got report config form, submitting for full docket...")

                # Extract the form action URL (contains session token)
                import re
                form_action_match = re.search(r'<FORM[^>]*action="([^"]+)"', resp.text, re.IGNORECASE)
                if form_action_match:
                    form_action = form_action_match.group(1)
                    # Handle relative URLs
                    if form_action.startswith("../"):
                        form_action = form_action.replace("../", "/")
                    form_url = urljoin(base_url, form_action)
                    self._log(f"Form action URL: {form_url}")
                else:
                    form_url = docket_url
                    self._log("No form action found, using docket URL")

                # Extract hidden form fields
                hidden_fields = re.findall(r'<input[^>]*type="hidden"[^>]*name="([^"]*)"[^>]*value="([^"]*)"', resp.text, re.IGNORECASE)

                # Submit form with default options (all entries)
                form_data = {
                    "all_case_ids": case_id,
                    "sort1": "oldest date first",
                    "date_from": "",
                    "date_to": "",
                    "documents_numbered_from_": "",
                    "documents_numbered_to_": "",
                    "terminated_parties": "on",
                    "pdf_header": "1",
                    "pdf_toggle_possible": "1",
                }

                # Add hidden fields
                for name, value in hidden_fields:
                    if name not in form_data:
                        form_data[name] = value

                self._log(f"Submitting form with {len(form_data)} fields")
                resp = self.session.post(form_url, data=form_data, headers=headers, timeout=60)
                self._log(f"Form submission response: {resp.status_code}, length: {len(resp.text)}")

            # Validate we got actual docket content
            if len(resp.text) < 1000:
                self._log(f"Response too short, content: {resp.text[:500]}")
                return DownloadResult(
                    success=False,
                    error="Received empty or invalid docket response"
                )

            # Calculate approximate page count (for cost estimation)
            # PACER charges per page, ~54 lines per page
            lines = resp.text.count('\n')
            pages = max(1, lines // 54)
            cost = pages * 0.10

            # Save the docket
            output_dir.mkdir(parents=True, exist_ok=True)

            if not filename:
                # Extract court from URL for filename
                court = parsed.netloc.split('.')[1]  # e.g., 'nysd' from 'ecf.nysd.uscourts.gov'
                filename = f"{court}_{case_id}.html"

            filepath = output_dir / filename
            filepath.write_text(resp.text, encoding='utf-8')
            self._log(f"Saved docket to: {filepath}")

            # Extract and save document metadata (docs.json)
            docs_filepath = None
            try:
                import json
                court = parsed.netloc.split('.')[1] if '.' in parsed.netloc else ""
                docs_meta = extract_document_metadata(
                    html=resp.text,
                    base_url=base_url,
                    case_number=case_id,
                    court_id=court,
                )
                docs_filepath = output_dir / "docs.json"
                docs_filepath.write_text(json.dumps(docs_meta, indent=2), encoding="utf-8")
                self._log(f"Saved docs.json to: {docs_filepath} ({docs_meta.get('document_count', 0)} docs)")
            except Exception as e:
                self._log(f"Warning: Could not save docs.json: {e}")

            return DownloadResult(
                success=True,
                filepath=filepath,
                docs_filepath=docs_filepath,
                pages=pages,
                cost=cost,
            )

        except requests.RequestException as e:
            return DownloadResult(success=False, error=f"Network error: {e}")

    def download_docket_by_case_number(
        self,
        case_number: str,
        court_id: str,
        output_dir: Path,
        filename: Optional[str] = None,
    ) -> DownloadResult:
        """Download docket by case number and court ID.

        This first searches PCL to get the case link, then downloads.

        Args:
            case_number: Case number (e.g., '1:2018cv08434')
            court_id: Court identifier (e.g., 'nysdce')
            output_dir: Directory to save the docket
            filename: Optional custom filename (defaults to court_case.html)

        Returns:
            DownloadResult with success status
        """
        from .pcl import PCLClient

        self._log(f"Searching for case {case_number} in {court_id}...")

        # Search PCL for the case
        pcl = PCLClient(self.config)

        # Normalize court ID for PCL (remove 'ce' suffix)
        pcl_court_id = court_id.rstrip('e').rstrip('c')
        if not pcl_court_id.endswith('bk') and not pcl_court_id.endswith('dc'):
            pcl_court_id += 'dc'  # Add district court suffix

        criteria = CaseSearchCriteria(
            case_number_full=case_number,
            court_id=[pcl_court_id],
        )

        results = pcl.search_cases(criteria)

        if not results or not results.content:
            return DownloadResult(
                success=False,
                error=f"Case not found: {case_number} in {court_id}"
            )

        # Get the case link from the first result
        case = results.content[0]
        case_link = case.case_link

        if not case_link:
            return DownloadResult(
                success=False,
                error="Case found but no caseLink available"
            )

        self._log(f"Found case link: {case_link}")

        # Generate filename from case number if not provided
        if filename is None:
            filename = f"{court_id}_{case_number.replace(':', '+')}.html"

        return self.download_docket_by_link(case_link, output_dir, filename)


def download_docket(
    config: PacerConfig,
    case_number: str,
    court_id: str,
    output_dir: Path,
    verbose: bool = False,
    filename: Optional[str] = None,
) -> DownloadResult:
    """Convenience function to download a docket.

    Args:
        config: PACER configuration
        case_number: Case number (e.g., '1:2018cv08434')
        court_id: Court identifier (e.g., 'nysdce')
        output_dir: Directory to save the docket
        verbose: Enable trace logging
        filename: Optional custom filename

    Returns:
        DownloadResult with success status and filepath
    """
    downloader = DocketDownloader(config, verbose=verbose)
    return downloader.download_docket_by_case_number(
        case_number, court_id, output_dir, filename=filename
    )


class DocumentDownloader:
    """Downloads individual documents from CM/ECF."""

    def __init__(self, config: PacerConfig, verbose: bool = False):
        self.config = config
        self.verbose = verbose
        self._docket_dl: Optional[DocketDownloader] = None
        self.authenticated_courts: set[str] = set()

    def _log(self, msg: str):
        if self.verbose:
            print(f"[TRACE] {msg}")

    @property
    def session(self) -> requests.Session:
        """Share session with DocketDownloader to avoid cookie desync."""
        if self._docket_dl is None:
            self._docket_dl = DocketDownloader(self.config, verbose=self.verbose)
        return self._docket_dl.session

    def _is_login_redirect(self, resp: requests.Response) -> bool:
        """Check if response indicates we need to login."""
        if "csologin" in resp.url or "login.jsf" in resp.url:
            return True
        if "location.assign" in resp.text and "csologin" in resp.text:
            return True
        return False

    def _is_valid_pdf(self, content: bytes) -> bool:
        """Check if content is a valid PDF (has magic bytes)."""
        return len(content) > 4 and content[:4] == b'%PDF'

    def _get_court_from_url(self, url: str) -> str:
        """Extract court ID from ECF URL."""
        return get_ecf_domain_from_url(url) or ""

    def _ensure_authenticated(self, doc_url: str) -> bool:
        """Ensure we're authenticated with the court's CM/ECF system."""
        court = self._get_court_from_url(doc_url)
        if court in self.authenticated_courts:
            return True

        self._log(f"Authenticating with {court}...")

        # Initialize shared session via property if needed
        if self._docket_dl is None:
            self._docket_dl = DocketDownloader(self.config, verbose=self.verbose)

        if not self._docket_dl.authenticate():
            return False

        # Access the court to establish session (session is shared, no cookie copy needed)
        base_url = f"https://ecf.{court}.uscourts.gov"
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; PACER-CLI/1.0)",
            "Referer": "https://external",
        }

        resp = self.session.get(f"{base_url}/cgi-bin/iquery.pl", headers=headers, timeout=30)

        # Check for CSO login redirect
        if self._is_login_redirect(resp):
            self._log("CSO login required...")
            psc_court = get_cso_court_id(court) or court.upper() + "C"

            if not self._docket_dl._cso_login(psc_court, f"{base_url}/cgi-bin/iquery.pl"):
                return False

        self.authenticated_courts.add(court)
        return True

    def download_document(
        self,
        doc_url: str,
        output_dir: Path,
        filename: Optional[str] = None,
    ) -> DownloadResult:
        """Download a document from CM/ECF.

        Args:
            doc_url: Full URL to the document (e.g., https://ecf.nysd.uscourts.gov/doc1/127133396215)
            output_dir: Directory to save the document
            filename: Optional filename (defaults to doc ID + extension)

        Returns:
            DownloadResult with success status and filepath
        """
        if not self._ensure_authenticated(doc_url):
            return DownloadResult(success=False, error="Authentication failed")

        self._log(f"Downloading document: {doc_url}")

        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; PACER-CLI/1.0)",
            "Referer": "https://external",
            "Accept": "text/html,application/xhtml+xml,application/pdf,*/*",
        }

        try:
            resp = self.session.get(doc_url, headers=headers, timeout=60, allow_redirects=True)
            self._log(f"Response: {resp.status_code}, content-type: {resp.headers.get('content-type', 'unknown')}")

            # Check for login redirect early (before following any links)
            if self._is_login_redirect(resp):
                return DownloadResult(success=False, error="Session expired - login required")

            # PACER may show an intermediate page before the actual document
            # Check if this is an HTML page with a link to the actual PDF
            content_type = resp.headers.get('content-type', '')

            if 'text/html' in content_type:
                self._log("Got HTML response, checking for document link or receipt...")

                # Check for PDF link in the page
                pdf_match = re.search(r'<a[^>]*href="([^"]*\.pdf[^"]*)"', resp.text, re.IGNORECASE)
                if pdf_match:
                    pdf_url = pdf_match.group(1)
                    if not pdf_url.startswith('http'):
                        parsed = urlparse(doc_url)
                        pdf_url = f"{parsed.scheme}://{parsed.netloc}{pdf_url}"
                    self._log(f"Following PDF link: {pdf_url}")
                    resp = self.session.get(pdf_url, headers=headers, timeout=60)

                # Check for iframe with document
                iframe_match = re.search(r'<iframe[^>]*src="([^"]+)"', resp.text, re.IGNORECASE)
                if iframe_match and 'text/html' in resp.headers.get('content-type', ''):
                    iframe_url = iframe_match.group(1)
                    if not iframe_url.startswith('http'):
                        parsed = urlparse(doc_url)
                        iframe_url = f"{parsed.scheme}://{parsed.netloc}{iframe_url}"
                    self._log(f"Following iframe: {iframe_url}")
                    resp = self.session.get(iframe_url, headers=headers, timeout=60)

                # Check for PACER receipt/acknowledgment page (View Document button)
                # The JavaScript goDLS() function extracts params and POSTs them
                if 'View Document' in resp.text and 'goDLS' in resp.text:
                    self._log("PACER receipt page detected, extracting goDLS params...")

                    # Extract goDLS parameters: goDLS(path, caseid, de_seq, got_receipt, pdf_hdr, pdf_toggle, magic, hdr, psf)
                    godls_match = re.search(
                        r"goDLS\('([^']+)','([^']+)','([^']+)','([^']*)','([^']*)','([^']*)','([^']*)','([^']*)','([^']*)'\)",
                        resp.text
                    )
                    if godls_match:
                        path, caseid, de_seq, got_receipt, pdf_hdr, pdf_toggle, magic, hdr, psf = godls_match.groups()

                        # Build POST data from goDLS params
                        form_data = {}
                        if caseid: form_data['caseid'] = caseid
                        if de_seq: form_data['de_seq_num'] = de_seq
                        if got_receipt: form_data['got_receipt'] = got_receipt
                        if pdf_hdr: form_data['pdf_header'] = pdf_hdr
                        if pdf_toggle: form_data['pdf_toggle_possible'] = pdf_toggle
                        if magic: form_data['magic_num'] = magic
                        if hdr: form_data['hdr'] = hdr
                        if psf: form_data['psf_report'] = psf

                        parsed = urlparse(doc_url)
                        form_url = f"{parsed.scheme}://{parsed.netloc}{path}"

                        self._log(f"POSTing to {form_url} with goDLS params: {form_data}")
                        resp = self.session.post(form_url, data=form_data, headers=headers, timeout=120)
                        self._log(f"goDLS POST response: {resp.status_code}, type: {resp.headers.get('content-type', 'unknown')}")

                        # PACER returns HTML with iframe containing PDF URL
                        if 'text/html' in resp.headers.get('content-type', '') and '<iframe' in resp.text:
                            iframe_match = re.search(r'<iframe[^>]+src="([^"]+)"', resp.text)
                            if iframe_match:
                                pdf_path = iframe_match.group(1)
                                pdf_url = f"{parsed.scheme}://{parsed.netloc}{pdf_path}"
                                self._log(f"Following iframe to PDF: {pdf_url}")
                                resp = self.session.get(pdf_url, headers=headers, timeout=120)
                                self._log(f"PDF response: {resp.status_code}, type: {resp.headers.get('content-type', 'unknown')}, size: {len(resp.content)}")

                # Fallback: check for other form types
                elif '<form' in resp.text.lower():
                    self._log("Other form detected, extracting hidden fields...")
                    form_action_match = re.search(r"<form[^>]*action=['\"]([^'\"]+)['\"]", resp.text, re.IGNORECASE)
                    if form_action_match:
                        form_url = form_action_match.group(1)
                        if not form_url.startswith('http'):
                            parsed = urlparse(doc_url)
                            form_url = f"{parsed.scheme}://{parsed.netloc}{form_url}"

                        hidden_fields = re.findall(
                            r'<input[^>]*type="hidden"[^>]*name="([^"]*)"[^>]*value="([^"]*)"',
                            resp.text, re.IGNORECASE
                        )
                        form_data = dict(hidden_fields)
                        resp = self.session.post(form_url, data=form_data, headers=headers, timeout=60)
                        self._log(f"Form submission response: {resp.status_code}")

            # Check for login redirect after following links
            if self._is_login_redirect(resp):
                return DownloadResult(success=False, error="Session expired during document fetch")

            # Determine file extension from content type and validate
            content_type = resp.headers.get('content-type', '')
            warning = None

            if 'pdf' in content_type or self._is_valid_pdf(resp.content):
                ext = '.pdf'
                if not self._is_valid_pdf(resp.content):
                    warning = "Content-type says PDF but missing magic bytes"
                    self._log(f"WARNING: {warning}")
            elif 'text/html' in content_type:
                ext = '.html'
                warning = "Got HTML instead of PDF - may be error page or sealed document"
                self._log(f"WARNING: {warning}")
            else:
                ext = '.bin'

            # Generate filename
            if not filename:
                doc_id_match = re.search(r'/doc1/(\d+)', doc_url)
                doc_id = doc_id_match.group(1) if doc_id_match else "document"
                filename = f"{doc_id}{ext}"

            # Calculate pages/cost for PDFs
            pages = 0
            cost = 0.0
            if ext == '.pdf' and self._is_valid_pdf(resp.content):
                # Rough estimate: ~3KB per page for court documents
                pages = max(1, len(resp.content) // 3000)
                cost = pages * 0.10

            # Save the document
            output_dir.mkdir(parents=True, exist_ok=True)
            filepath = output_dir / filename
            filepath.write_bytes(resp.content)

            self._log(f"Saved to: {filepath} ({len(resp.content)} bytes)")

            # Return success but include warning in error field if applicable
            return DownloadResult(
                success=True,
                filepath=filepath,
                pages=pages,
                cost=cost,
                error=warning,  # Using error field for warnings
            )

        except requests.RequestException as e:
            return DownloadResult(success=False, error=f"Network error: {e}")
