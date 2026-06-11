"""Tests for the CM/ECF docket and document downloaders.

All network access is mocked: the downloaders' ``session`` is replaced with a
MagicMock and ``pacer_cli.downloader.authenticate`` is patched so no real login
occurs. The pure helpers (metadata extraction, cache loading) need no network.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from pacer_cli.auth import AuthResult
from pacer_cli.config import PacerConfig
from pacer_cli.downloader import (
    DocketDownloader,
    DocumentDownloader,
    DownloadResult,
    download_docket,
    extract_document_metadata,
    get_document_by_number,
    load_cached_documents,
)


@pytest.fixture
def config() -> PacerConfig:
    return PacerConfig(username="user", password="pass")


def _resp(status_code=200, text="", content=None, headers=None, url="https://ecf.nysd.uscourts.gov"):
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.text = text
    resp.content = content if content is not None else text.encode()
    resp.headers = headers or {}
    resp.url = url
    resp.cookies = {}
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(response=resp)
    else:
        resp.raise_for_status.return_value = None
    return resp


# Realistic docket HTML, long enough (>1000 chars) to pass the length check.
DOCKET_HTML = (
    "<html><head><title>CM/ECF - nysd</title></head><body>\n"
    "<h3>CASE #: 1:18-cv-08434-VEC-SLC</h3>\n"
    "<table width='100%' border=0 CELLSPACING=5>\n"
    "<tr><td width='60%'>\n"
    "Apple Inc. v. Samsung Electronics Co.<br>\n"
    "Assigned to: Judge Vernon S. Broderick<br>\n"
    "Cause: 28:1332 Diversity\n"
    "</td><td width='40%'>\n"
    "Date Filed: 09/15/2018<br>\n"
    "</td></tr></table>\n"
    "<table rules='all'>\n"
    "<tr><td>09/15/2018</td><td><a href='/doc1/123'>1</a></td>"
    "<td><!--SB-->COMPLAINT filed</td></tr>\n"
    "<tr><td>09/20/2018</td><td><a href='/doc1/124'>2</a></td>"
    "<td><!--SB-->MOTION to dismiss</td></tr>\n"
    "</table>\n" + ("<!-- padding line -->\n" * 60) + "</body></html>"
)


# ---------------------------------------------------------------------------
# DownloadResult dataclass
# ---------------------------------------------------------------------------


class TestDownloadResult:
    def test_defaults(self):
        r = DownloadResult(success=True)
        assert r.success is True
        assert r.filepath is None
        assert r.docs_filepath is None
        assert r.error is None
        assert r.pages == 0
        assert r.cost == 0.0

    def test_full(self):
        r = DownloadResult(
            success=False, filepath=Path("/tmp/x.html"), error="boom", pages=3, cost=0.3
        )
        assert r.error == "boom"
        assert r.pages == 3
        assert r.cost == 0.3


# ---------------------------------------------------------------------------
# extract_document_metadata
# ---------------------------------------------------------------------------


class TestExtractDocumentMetadata:
    def test_extracts_documents(self):
        meta = extract_document_metadata(
            DOCKET_HTML, "https://ecf.nysd.uscourts.gov", case_number="500997", court_id="nysd"
        )
        assert meta["case_number"] == "500997"
        assert meta["court_id"] == "nysd"
        assert meta["case_title"] == "Apple Inc. v. Samsung Electronics Co."
        assert meta["document_count"] == 2
        urls = [d["url"] for d in meta["documents"]]
        assert "https://ecf.nysd.uscourts.gov/doc1/123" in urls
        assert "https://ecf.nysd.uscourts.gov/doc1/124" in urls
        assert "downloaded_at" in meta and meta["downloaded_at"].endswith("Z")

    def test_falls_back_to_parsed_meta(self):
        # No explicit case_number/court_id -> uses parsed docket meta.
        meta = extract_document_metadata(DOCKET_HTML, "https://ecf.nysd.uscourts.gov")
        assert meta["case_number"] == "1:18-cv-08434-VEC-SLC"
        assert meta["court_id"] == "nysd"

    def test_parse_failure_returns_empty_manifest(self):
        with patch("pacer_cli.parser.parse_docket", side_effect=ValueError("boom")):
            meta = extract_document_metadata(
                "<garbage>", "https://ecf.x.uscourts.gov", case_number="1", court_id="x"
            )
        assert meta["parse_error"] is True
        assert meta["documents"] == []
        assert meta["case_number"] == "1"

    def test_entries_without_docnum_are_skipped(self):
        # Third row has no link and no doc number -> excluded.
        html = DOCKET_HTML.replace(
            "</table>\n",
            "<tr><td>10/01/2018</td><td></td><td><!--SB-->ORDER text</td></tr>\n</table>\n",
            1,
        )
        meta = extract_document_metadata(html, "https://ecf.nysd.uscourts.gov")
        # Still only the two linked documents.
        assert meta["document_count"] == 2


# ---------------------------------------------------------------------------
# load_cached_documents / get_document_by_number
# ---------------------------------------------------------------------------


class TestCacheHelpers:
    def _write_docs(self, case_dir: Path, payload: dict) -> None:
        case_dir.mkdir(parents=True, exist_ok=True)
        (case_dir / "docs.json").write_text(json.dumps(payload), encoding="utf-8")

    def test_load_missing_returns_none(self, tmp_path):
        assert load_cached_documents(tmp_path) is None

    def test_load_valid(self, tmp_path):
        payload = {"documents": [{"doc_num": "1"}]}
        self._write_docs(tmp_path, payload)
        assert load_cached_documents(tmp_path) == payload

    def test_load_corrupt_returns_none(self, tmp_path):
        (tmp_path / "docs.json").write_text("{not json", encoding="utf-8")
        assert load_cached_documents(tmp_path) is None

    def test_get_document_by_number_found(self, tmp_path):
        self._write_docs(
            tmp_path,
            {"documents": [{"doc_num": "1", "url": "u1"}, {"doc_num": "2", "url": "u2"}]},
        )
        doc = get_document_by_number(tmp_path, "2")
        assert doc["url"] == "u2"

    def test_get_document_by_number_not_found(self, tmp_path):
        self._write_docs(tmp_path, {"documents": [{"doc_num": "1"}]})
        assert get_document_by_number(tmp_path, "99") is None

    def test_get_document_by_number_no_cache(self, tmp_path):
        assert get_document_by_number(tmp_path, "1") is None


# ---------------------------------------------------------------------------
# DocketDownloader.authenticate
# ---------------------------------------------------------------------------


class TestDocketAuth:
    def test_authenticate_success(self, config):
        dl = DocketDownloader(config, verbose=True)
        with patch("pacer_cli.downloader.authenticate") as m:
            m.return_value = AuthResult(success=True, token="tok" + "x" * 100)
            assert dl.authenticate() is True
        assert dl.token.startswith("tok")

    def test_authenticate_failure(self, config):
        dl = DocketDownloader(config)
        with patch("pacer_cli.downloader.authenticate") as m:
            m.return_value = AuthResult(success=False, error="bad creds")
            assert dl.authenticate() is False
        assert dl.token is None


# ---------------------------------------------------------------------------
# DocketDownloader._cso_login
# ---------------------------------------------------------------------------


@pytest.fixture
def config_mfa() -> PacerConfig:
    return PacerConfig(username="user", password="pass", totp_secret="JBSWY3DPEHPK3PXP")


class TestCsoLogin:
    def _dl(self, config):
        dl = DocketDownloader(config, verbose=True)
        dl.session = MagicMock(spec=requests.Session)
        return dl

    def test_success_redirected_to_app(self, config):
        dl = self._dl(config)
        app_url = "https://ecf.nysd.uscourts.gov/cgi-bin/iquery.pl"
        login_page = (
            '<html>name="javax.faces.ViewState" id="x" value="vs123" '
            "loginForm</html>"
        )
        dl.session.get.return_value = _resp(text=login_page)
        dl.session.post.return_value = _resp(text="<html>logged in</html>", url=app_url)
        assert dl._cso_login("NYSDC", app_url) is True
        # ViewState carried into the form POST
        post_data = dl.session.post.call_args.kwargs["data"]
        assert post_data["javax.faces.ViewState"] == "vs123"
        assert post_data["loginForm:loginName"] == "user"

    def test_jakarta_viewstate_variant(self, config):
        dl = self._dl(config)
        app_url = "https://ecf.nysd.uscourts.gov/app"
        login_page = '<html>name="jakarta.faces.ViewState" value="vsJ"</html>'
        dl.session.get.return_value = _resp(text=login_page)
        dl.session.post.return_value = _resp(text="DktRpt", url="https://x/DktRpt.pl")
        assert dl._cso_login("NYSDC", app_url) is True
        post_data = dl.session.post.call_args.kwargs["data"]
        assert post_data["jakarta.faces.ViewState"] == "vsJ"

    def test_invalid_credentials(self, config):
        dl = self._dl(config)
        dl.session.get.return_value = _resp(text="<html>login page</html>")
        # ends back on a login URL with an Invalid message
        dl.session.post.return_value = _resp(
            text="<html>Invalid username or password error</html>",
            url="https://pacer.login.uscourts.gov/csologin/login.jsf",
        )
        assert dl._cso_login("NYSDC", "https://ecf.nysd.uscourts.gov/app") is False

    def test_proceeds_with_session_cookies(self, config):
        dl = self._dl(config)
        dl.session.get.return_value = _resp(text="<html>login</html>")
        post = _resp(text="<html>neutral page</html>", url="https://somewhere/else")
        dl.session.post.return_value = post
        dl.session.cookies = {"PacerUser": "v"}
        assert dl._cso_login("NYSDC", "https://ecf.nysd.uscourts.gov/app") is True

    def test_uncertain_returns_true(self, config):
        dl = self._dl(config)
        dl.session.get.return_value = _resp(text="<html>login</html>")
        dl.session.post.return_value = _resp(
            text="<html>neutral</html>", url="https://somewhere/else"
        )
        dl.session.cookies = {}
        assert dl._cso_login("NYSDC", "https://ecf.nysd.uscourts.gov/app") is True

    def test_exception_returns_false(self, config):
        dl = self._dl(config)
        dl.session.get.side_effect = requests.ConnectionError("down")
        assert dl._cso_login("NYSDC", "https://ecf.nysd.uscourts.gov/app") is False

    def test_mfa_flow_with_redirect(self, config_mfa):
        dl = self._dl(config_mfa)
        app_url = "https://ecf.nysd.uscourts.gov/app"
        login_page = '<html>name="jakarta.faces.ViewState" value="vs1"</html>'
        # initial POST returns an mfaForm; MFA AJAX POST returns a redirect XML
        mfa_page = '<html>mfaForm name="jakarta.faces.ViewState" value="vs2"</html>'
        mfa_redirect = '<partial-response><redirect url="https://ecf.nysd.uscourts.gov/app?x=1&amp;y=2"/></partial-response>'  # noqa: E501
        dl.session.get.side_effect = [
            _resp(text=login_page),  # GET login page
            _resp(text="<html>final app</html>", url=app_url),  # GET redirect target
        ]
        dl.session.post.side_effect = [
            _resp(text=mfa_page, url="https://pacer.login.uscourts.gov/csologin/login.jsf"),
            _resp(text=mfa_redirect),
        ]
        with patch("pacer_cli.auth.generate_totp", return_value="123456"), patch(
            "pacer_cli.downloader.time.sleep"
        ):
            assert dl._cso_login("NYSDC", app_url) is True
        # MFA AJAX POST included the OTP
        mfa_data = dl.session.post.call_args_list[1].kwargs["data"]
        assert mfa_data["mfaForm:mfaInput"] == "123456"


# ---------------------------------------------------------------------------
# DocketDownloader helpers
# ---------------------------------------------------------------------------


class TestDocketHelpers:
    def test_get_case_id_from_link(self, config):
        dl = DocketDownloader(config)
        assert (
            dl._get_case_id_from_link(
                "https://ecf.nysd.uscourts.gov/cgi-bin/iqquerymenu.pl?500997"
            )
            == "500997"
        )

    def test_get_case_id_from_link_none(self, config):
        dl = DocketDownloader(config)
        assert dl._get_case_id_from_link("https://ecf.nysd.uscourts.gov/cgi-bin/x.pl") is None

    def test_get_ecf_base_url(self, config):
        dl = DocketDownloader(config)
        assert dl._get_ecf_base_url("nysdce") == "https://ecf.nysd.uscourts.gov"

    def test_get_ecf_base_url_bankruptcy(self, config):
        dl = DocketDownloader(config)
        # ends with 'bk' after stripping -> bankruptcy branch
        assert dl._get_ecf_base_url("nybbk").startswith("https://ecf.")


# ---------------------------------------------------------------------------
# DocketDownloader.download_docket_by_link
# ---------------------------------------------------------------------------


class TestDownloadDocketByLink:
    def _dl(self, config, token="tok" + "x" * 100):
        dl = DocketDownloader(config)
        dl.session = MagicMock(spec=requests.Session)
        dl.token = token
        return dl

    def test_auth_failure_returns_error(self, config, tmp_path):
        dl = DocketDownloader(config)
        dl.session = MagicMock(spec=requests.Session)
        # token is None -> authenticate() runs and fails
        with patch.object(dl, "authenticate", return_value=False):
            result = dl.download_docket_by_link(
                "https://ecf.nysd.uscourts.gov/cgi-bin/iqquerymenu.pl?500997", tmp_path
            )
        assert result.success is False
        assert result.error == "Authentication failed"

    def test_bad_case_link_no_id(self, config, tmp_path):
        dl = self._dl(config)
        result = dl.download_docket_by_link(
            "https://ecf.nysd.uscourts.gov/cgi-bin/iqquerymenu.pl", tmp_path
        )
        assert result.success is False
        assert "Could not extract case ID" in result.error

    def test_successful_direct_docket(self, config, tmp_path):
        dl = self._dl(config)
        # query menu returns a normal page, then DktRpt returns the full docket directly.
        dl.session.get.side_effect = [
            _resp(text="<html>query menu ok</html>", url="https://ecf.nysd.uscourts.gov/x"),
            _resp(text=DOCKET_HTML, url="https://ecf.nysd.uscourts.gov/cgi-bin/DktRpt.pl"),
        ]
        result = dl.download_docket_by_link(
            "https://ecf.nysd.uscourts.gov/cgi-bin/iqquerymenu.pl?500997", tmp_path
        )
        assert result.success is True
        assert result.filepath.exists()
        assert result.filepath.name == "nysd_500997.html"
        assert result.docs_filepath.exists()
        docs = json.loads(result.docs_filepath.read_text())
        assert docs["document_count"] == 2
        assert result.pages >= 1

    def test_custom_filename(self, config, tmp_path):
        dl = self._dl(config)
        dl.session.get.side_effect = [
            _resp(text="<html>ok</html>"),
            _resp(text=DOCKET_HTML),
        ]
        result = dl.download_docket_by_link(
            "https://ecf.nysd.uscourts.gov/cgi-bin/iqquerymenu.pl?500997",
            tmp_path,
            filename="custom.html",
        )
        assert result.filepath.name == "custom.html"

    def test_report_config_form_submitted(self, config, tmp_path):
        dl = self._dl(config)
        form_page = (
            '<html><FORM action="../cgi-bin/DktRpt.pl?500997">'
            'Sort by <input type="hidden" name="hidtok" value="abc">'
            '<input type="hidden" name="date_from" value=""></FORM></html>'
        )
        dl.session.get.side_effect = [
            _resp(text="<html>query menu</html>"),
            _resp(text=form_page),  # DktRpt returns config form
        ]
        dl.session.post.return_value = _resp(text=DOCKET_HTML)
        result = dl.download_docket_by_link(
            "https://ecf.nysd.uscourts.gov/cgi-bin/iqquerymenu.pl?500997", tmp_path
        )
        assert result.success is True
        # the hidden field 'hidtok' should be carried into POST data
        post_data = dl.session.post.call_args.kwargs["data"]
        assert post_data["hidtok"] == "abc"
        assert post_data["all_case_ids"] == "500997"

    def test_form_without_action_uses_docket_url(self, config, tmp_path):
        dl = self._dl(config)
        form_page = "<html>Sort by date_from no form action here</html>"
        dl.session.get.side_effect = [
            _resp(text="<html>query menu</html>"),
            _resp(text=form_page),
        ]
        dl.session.post.return_value = _resp(text=DOCKET_HTML)
        result = dl.download_docket_by_link(
            "https://ecf.nysd.uscourts.gov/cgi-bin/iqquerymenu.pl?500997", tmp_path
        )
        assert result.success is True

    def test_js_redirect_triggers_cso_login(self, config, tmp_path):
        dl = self._dl(config)
        js_page = (
            "<html><script>location.assign("
            '"https://pacer.login.uscourts.gov/csologin/login.jsf?'
            'pscCourtId=NYSDC&appurl=https://ecf.nysd.uscourts.gov/app")'
            "</script></html>"
        )
        dl.session.get.side_effect = [
            _resp(text=js_page),  # query menu -> JS redirect
            _resp(text="<html>after login ok</html>"),  # retry after login
            _resp(text=DOCKET_HTML),  # DktRpt
        ]
        with patch.object(dl, "_cso_login", return_value=True) as cso:
            result = dl.download_docket_by_link(
                "https://ecf.nysd.uscourts.gov/cgi-bin/iqquerymenu.pl?500997", tmp_path
            )
        cso.assert_called_once()
        assert cso.call_args[0][0] == "NYSDC"
        assert result.success is True

    def test_js_redirect_cso_login_fails(self, config, tmp_path):
        dl = self._dl(config)
        js_page = (
            "<html>location.assign("
            '"https://pacer.login.uscourts.gov/csologin/login.jsf?pscCourtId=NYSDC")'
            "</html>"
        )
        dl.session.get.side_effect = [_resp(text=js_page)]
        with patch.object(dl, "_cso_login", return_value=False):
            result = dl.download_docket_by_link(
                "https://ecf.nysd.uscourts.gov/cgi-bin/iqquerymenu.pl?500997", tmp_path
            )
        assert result.success is False
        assert result.error == "CSO login failed"

    def test_js_redirect_still_redirected_after_login(self, config, tmp_path):
        dl = self._dl(config)
        js_page = (
            "<html>location.assign("
            '"https://pacer.login.uscourts.gov/csologin/login.jsf?pscCourtId=NYSDC")'
            "</html>"
        )
        dl.session.get.side_effect = [
            _resp(text=js_page),  # query menu
            _resp(text=js_page),  # still redirecting after login
        ]
        with patch.object(dl, "_cso_login", return_value=True):
            result = dl.download_docket_by_link(
                "https://ecf.nysd.uscourts.gov/cgi-bin/iqquerymenu.pl?500997", tmp_path
            )
        assert result.success is False
        assert "still being redirected" in result.error

    def test_401_from_query_menu(self, config, tmp_path):
        dl = self._dl(config)
        dl.session.get.side_effect = [_resp(status_code=401, text="<html>denied</html>")]
        result = dl.download_docket_by_link(
            "https://ecf.nysd.uscourts.gov/cgi-bin/iqquerymenu.pl?500997", tmp_path
        )
        assert result.success is False
        assert "token rejected" in result.error

    def test_login_page_url_detected(self, config, tmp_path):
        dl = self._dl(config)
        dl.session.get.side_effect = [
            _resp(text="<html>ok</html>", url="https://pacer.login.uscourts.gov/login.jsf")
        ]
        result = dl.download_docket_by_link(
            "https://ecf.nysd.uscourts.gov/cgi-bin/iqquerymenu.pl?500997", tmp_path
        )
        assert result.success is False
        assert "Session expired" in result.error

    def test_network_error_on_query_menu(self, config, tmp_path):
        dl = self._dl(config)
        dl.session.get.side_effect = requests.ConnectionError("down")
        result = dl.download_docket_by_link(
            "https://ecf.nysd.uscourts.gov/cgi-bin/iqquerymenu.pl?500997", tmp_path
        )
        assert result.success is False
        assert "Network error" in result.error

    def test_short_response_is_invalid(self, config, tmp_path):
        dl = self._dl(config)
        dl.session.get.side_effect = [
            _resp(text="<html>query menu ok padding to pass</html>"),
            _resp(text="too short"),  # DktRpt response < 1000 chars
        ]
        result = dl.download_docket_by_link(
            "https://ecf.nysd.uscourts.gov/cgi-bin/iqquerymenu.pl?500997", tmp_path
        )
        assert result.success is False
        assert "empty or invalid" in result.error

    def test_network_error_on_docket_request(self, config, tmp_path):
        dl = self._dl(config)
        dl.session.get.side_effect = [
            _resp(text="<html>query menu ok</html>"),
            requests.ConnectionError("down"),
        ]
        result = dl.download_docket_by_link(
            "https://ecf.nysd.uscourts.gov/cgi-bin/iqquerymenu.pl?500997", tmp_path
        )
        assert result.success is False
        assert "Network error" in result.error


# ---------------------------------------------------------------------------
# DocketDownloader.download_docket_by_case_number
# ---------------------------------------------------------------------------


class TestDownloadDocketByCaseNumber:
    def test_case_not_found(self, config, tmp_path):
        dl = DocketDownloader(config)
        empty = MagicMock()
        empty.content = []
        with patch("pacer_cli.pcl.PCLClient") as pcl_cls:
            pcl_cls.return_value.search_cases.return_value = empty
            result = dl.download_docket_by_case_number(
                "1:2018cv08434", "nysdce", tmp_path
            )
        assert result.success is False
        assert "Case not found" in result.error

    def test_no_case_link(self, config, tmp_path):
        dl = DocketDownloader(config)
        case = MagicMock()
        case.case_link = None
        results = MagicMock()
        results.content = [case]
        with patch("pacer_cli.pcl.PCLClient") as pcl_cls:
            pcl_cls.return_value.search_cases.return_value = results
            result = dl.download_docket_by_case_number(
                "1:2018cv08434", "nysdce", tmp_path
            )
        assert result.success is False
        assert "no caseLink" in result.error

    def test_found_delegates_to_by_link(self, config, tmp_path):
        dl = DocketDownloader(config)
        case = MagicMock()
        case.case_link = "https://ecf.nysd.uscourts.gov/cgi-bin/iqquerymenu.pl?500997"
        results = MagicMock()
        results.content = [case]
        sentinel = DownloadResult(success=True, filepath=tmp_path / "x.html")
        with patch("pacer_cli.pcl.PCLClient"), patch.object(
            dl, "download_docket_by_link", return_value=sentinel
        ) as by_link:
            result = dl.download_docket_by_case_number(
                "1:2018cv08434", "nysdce", tmp_path
            )
        assert result is sentinel
        # default filename derived from case number (':' -> '+'), passed positionally
        assert by_link.call_args[0][2] == "nysdce_1+2018cv08434.html"


# ---------------------------------------------------------------------------
# download_docket convenience function
# ---------------------------------------------------------------------------


class TestDownloadDocketFunction:
    def test_delegates(self, config, tmp_path):
        sentinel = DownloadResult(success=True)
        with patch.object(
            DocketDownloader, "download_docket_by_case_number", return_value=sentinel
        ) as m:
            result = download_docket(config, "1:2018cv08434", "nysdce", tmp_path)
        assert result is sentinel
        m.assert_called_once()


# ---------------------------------------------------------------------------
# DocumentDownloader helpers
# ---------------------------------------------------------------------------


class TestDocumentDownloaderHelpers:
    def test_session_lazily_creates_docket_downloader(self, config):
        dd = DocumentDownloader(config)
        assert dd._docket_dl is None
        sess = dd.session
        assert dd._docket_dl is not None
        assert sess is dd._docket_dl.session

    def test_is_valid_pdf(self, config):
        dd = DocumentDownloader(config)
        assert dd._is_valid_pdf(b"%PDF-1.7 stuff") is True
        assert dd._is_valid_pdf(b"<html>") is False
        assert dd._is_valid_pdf(b"%PD") is False

    def test_get_court_from_url(self, config):
        dd = DocumentDownloader(config)
        assert dd._get_court_from_url("https://ecf.nysd.uscourts.gov/doc1/1") == "nysd"

    def test_is_login_redirect_by_url(self, config):
        dd = DocumentDownloader(config)
        resp = _resp(text="", url="https://x/csologin/login.jsf")
        assert dd._is_login_redirect(resp) is True

    def test_is_login_redirect_by_body(self, config):
        dd = DocumentDownloader(config)
        resp = _resp(text='location.assign("https://x/csologin/login.jsf")', url="https://ok")
        assert dd._is_login_redirect(resp) is True

    def test_is_login_redirect_false(self, config):
        dd = DocumentDownloader(config)
        resp = _resp(text="<html>fine</html>", url="https://ecf.nysd.uscourts.gov/doc1/1")
        assert dd._is_login_redirect(resp) is False


# ---------------------------------------------------------------------------
# DocumentDownloader._ensure_authenticated
# ---------------------------------------------------------------------------


class TestEnsureAuthenticated:
    def test_cached_court_short_circuits(self, config):
        dd = DocumentDownloader(config)
        dd.authenticated_courts.add("nysd")
        assert dd._ensure_authenticated("https://ecf.nysd.uscourts.gov/doc1/1") is True

    def test_auth_failure(self, config):
        dd = DocumentDownloader(config)
        with patch.object(DocketDownloader, "authenticate", return_value=False):
            assert dd._ensure_authenticated("https://ecf.nysd.uscourts.gov/doc1/1") is False

    def test_success_no_login_redirect(self, config):
        dd = DocumentDownloader(config)
        with patch.object(DocketDownloader, "authenticate", return_value=True):
            dd._docket_dl = DocketDownloader(config)
            dd._docket_dl.session = MagicMock(spec=requests.Session)
            dd._docket_dl.session.get.return_value = _resp(
                text="<html>ok</html>", url="https://ecf.nysd.uscourts.gov/cgi-bin/iquery.pl"
            )
            assert dd._ensure_authenticated("https://ecf.nysd.uscourts.gov/doc1/1") is True
        assert "nysd" in dd.authenticated_courts

    def test_cso_login_required_and_succeeds(self, config):
        dd = DocumentDownloader(config)
        dd._docket_dl = DocketDownloader(config)
        dd._docket_dl.session = MagicMock(spec=requests.Session)
        dd._docket_dl.session.get.return_value = _resp(
            text="ok", url="https://x/csologin/login.jsf"
        )
        with patch.object(DocketDownloader, "authenticate", return_value=True), patch.object(
            dd._docket_dl, "_cso_login", return_value=True
        ):
            assert dd._ensure_authenticated("https://ecf.nysd.uscourts.gov/doc1/1") is True

    def test_cso_login_required_and_fails(self, config):
        dd = DocumentDownloader(config)
        dd._docket_dl = DocketDownloader(config)
        dd._docket_dl.session = MagicMock(spec=requests.Session)
        dd._docket_dl.session.get.return_value = _resp(
            text="ok", url="https://x/csologin/login.jsf"
        )
        with patch.object(DocketDownloader, "authenticate", return_value=True), patch.object(
            dd._docket_dl, "_cso_login", return_value=False
        ):
            assert dd._ensure_authenticated("https://ecf.nysd.uscourts.gov/doc1/1") is False


# ---------------------------------------------------------------------------
# DocumentDownloader.download_document
# ---------------------------------------------------------------------------


class TestDownloadDocument:
    def _dd(self, config):
        dd = DocumentDownloader(config)
        dd._docket_dl = DocketDownloader(config)
        dd._docket_dl.session = MagicMock(spec=requests.Session)
        dd.authenticated_courts.add("nysd")  # skip the auth dance
        return dd

    def test_auth_failure(self, config, tmp_path):
        dd = DocumentDownloader(config)
        with patch.object(dd, "_ensure_authenticated", return_value=False):
            result = dd.download_document("https://ecf.nysd.uscourts.gov/doc1/1", tmp_path)
        assert result.success is False
        assert result.error == "Authentication failed"

    def test_direct_pdf(self, config, tmp_path):
        dd = self._dd(config)
        pdf = b"%PDF-1.7" + b"x" * 6000
        dd.session.get.return_value = _resp(
            content=pdf, headers={"content-type": "application/pdf"}
        )
        result = dd.download_document(
            "https://ecf.nysd.uscourts.gov/doc1/127133396215", tmp_path
        )
        assert result.success is True
        assert result.filepath.suffix == ".pdf"
        assert result.filepath.name == "127133396215.pdf"
        assert result.filepath.read_bytes() == pdf
        assert result.pages >= 1
        assert result.cost > 0
        assert result.error is None

    def test_login_redirect_early(self, config, tmp_path):
        dd = self._dd(config)
        dd.session.get.return_value = _resp(text="x", url="https://x/csologin/login.jsf")
        result = dd.download_document("https://ecf.nysd.uscourts.gov/doc1/1", tmp_path)
        assert result.success is False
        assert "login required" in result.error

    def test_html_with_pdf_link_followed(self, config, tmp_path):
        dd = self._dd(config)
        html = '<html><a href="/doc1/123.pdf">View</a></html>'
        pdf = b"%PDF-1.7" + b"y" * 3000
        dd.session.get.side_effect = [
            _resp(text=html, headers={"content-type": "text/html"}),
            _resp(content=pdf, headers={"content-type": "application/pdf"}),
        ]
        result = dd.download_document("https://ecf.nysd.uscourts.gov/doc1/1", tmp_path)
        assert result.success is True
        assert result.filepath.read_bytes() == pdf
        # the followed PDF link is absolutized
        assert dd.session.get.call_args_list[1][0][0] == (
            "https://ecf.nysd.uscourts.gov/doc1/123.pdf"
        )

    def test_godls_receipt_flow(self, config, tmp_path):
        dd = self._dd(config)
        receipt = (
            "<html>View Document "
            "<input type=button value='View Document' "
            "onclick=\"goDLS('/doc1/127133396215','500997','42','','1','1',"
            "'magic123','','psf')\"></html>"
        )
        iframe_page = '<html><iframe src="/cgi-bin/show_temp.pl?file=abc.pdf"></iframe></html>'
        pdf = b"%PDF-1.7" + b"z" * 4000
        dd.session.get.side_effect = [
            _resp(text=receipt, headers={"content-type": "text/html"}),  # initial
            _resp(content=pdf, headers={"content-type": "application/pdf"}),  # iframe pdf
        ]
        dd.session.post.return_value = _resp(
            text=iframe_page, headers={"content-type": "text/html"}
        )
        result = dd.download_document(
            "https://ecf.nysd.uscourts.gov/doc1/127133396215", tmp_path
        )
        assert result.success is True
        assert result.filepath.read_bytes() == pdf
        post_data = dd.session.post.call_args.kwargs["data"]
        assert post_data["caseid"] == "500997"
        assert post_data["de_seq_num"] == "42"
        assert post_data["magic_num"] == "magic123"

    def test_iframe_followed(self, config, tmp_path):
        dd = self._dd(config)
        html = '<html><iframe src="/show.pl?doc=1"></iframe></html>'
        pdf = b"%PDF-1.7" + b"q" * 3000
        dd.session.get.side_effect = [
            _resp(text=html, headers={"content-type": "text/html"}),
            _resp(content=pdf, headers={"content-type": "application/pdf"}),
        ]
        result = dd.download_document("https://ecf.nysd.uscourts.gov/doc1/9", tmp_path)
        assert result.success is True
        assert dd.session.get.call_args_list[1][0][0] == (
            "https://ecf.nysd.uscourts.gov/show.pl?doc=1"
        )

    def test_generic_form_submitted(self, config, tmp_path):
        dd = self._dd(config)
        html = (
            "<html><form action='/cgi-bin/submit.pl'>"
            '<input type="hidden" name="tok" value="abc">'
            "</form></html>"
        )
        pdf = b"%PDF-1.7" + b"w" * 3000
        dd.session.get.return_value = _resp(text=html, headers={"content-type": "text/html"})
        dd.session.post.return_value = _resp(
            content=pdf, headers={"content-type": "application/pdf"}
        )
        result = dd.download_document("https://ecf.nysd.uscourts.gov/doc1/3", tmp_path)
        assert result.success is True
        assert dd.session.post.call_args.kwargs["data"] == {"tok": "abc"}

    def test_html_instead_of_pdf_warning(self, config, tmp_path):
        dd = self._dd(config)
        html = "<html>This document is sealed</html>"
        dd.session.get.return_value = _resp(text=html, headers={"content-type": "text/html"})
        result = dd.download_document("https://ecf.nysd.uscourts.gov/doc1/5", tmp_path)
        # Success (file written) but with a warning in the error field.
        assert result.success is True
        assert result.filepath.suffix == ".html"
        assert "Got HTML instead of PDF" in result.error
        assert result.pages == 0

    def test_pdf_content_type_missing_magic_bytes(self, config, tmp_path):
        dd = self._dd(config)
        # content-type says pdf, but bytes are not a real PDF
        dd.session.get.return_value = _resp(
            content=b"not a pdf body", headers={"content-type": "application/pdf"}
        )
        result = dd.download_document("https://ecf.nysd.uscourts.gov/doc1/6", tmp_path)
        assert result.success is True
        assert result.filepath.suffix == ".pdf"
        assert "missing magic bytes" in result.error
        assert result.pages == 0  # not counted because not valid PDF

    def test_binary_fallback_extension(self, config, tmp_path):
        dd = self._dd(config)
        dd.session.get.return_value = _resp(
            content=b"\x00\x01\x02data", headers={"content-type": "application/octet-stream"}
        )
        result = dd.download_document("https://ecf.nysd.uscourts.gov/doc1/8", tmp_path)
        assert result.success is True
        assert result.filepath.suffix == ".bin"

    def test_custom_filename(self, config, tmp_path):
        dd = self._dd(config)
        pdf = b"%PDF-1.7" + b"x" * 3000
        dd.session.get.return_value = _resp(
            content=pdf, headers={"content-type": "application/pdf"}
        )
        result = dd.download_document(
            "https://ecf.nysd.uscourts.gov/doc1/1", tmp_path, filename="mydoc.pdf"
        )
        assert result.filepath.name == "mydoc.pdf"

    def test_no_doc_id_in_url_uses_default_name(self, config, tmp_path):
        dd = self._dd(config)
        pdf = b"%PDF-1.7" + b"x" * 3000
        dd.session.get.return_value = _resp(
            content=pdf, headers={"content-type": "application/pdf"}
        )
        # URL without /doc1/<id> -> filename uses "document"
        result = dd.download_document("https://ecf.nysd.uscourts.gov/other", tmp_path)
        assert result.filepath.name == "document.pdf"

    def test_login_redirect_after_following_links(self, config, tmp_path):
        dd = self._dd(config)
        # HTML with a PDF link, but the followed link is a login redirect.
        html = '<html><a href="/doc1/1.pdf">x</a></html>'
        dd.session.get.side_effect = [
            _resp(text=html, headers={"content-type": "text/html"}),
            _resp(text="x", url="https://x/csologin/login.jsf"),
        ]
        result = dd.download_document("https://ecf.nysd.uscourts.gov/doc1/1", tmp_path)
        assert result.success is False
        assert "Session expired during document fetch" in result.error

    def test_network_error(self, config, tmp_path):
        dd = self._dd(config)
        dd.session.get.side_effect = requests.ConnectionError("down")
        result = dd.download_document("https://ecf.nysd.uscourts.gov/doc1/1", tmp_path)
        assert result.success is False
        assert "Network error" in result.error
