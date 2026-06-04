"""Tests for the docket reader module (DocketParser and DocketProcessor)."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from pacer_cli.docket_types import ParsedDocket
from pacer_cli.reader import (
    HAS_BS4,
    DocketParser,
    DocketProcessor,
)

CSV_HEADERS = [
    "date_filed", "document_number", "docket_description",
    "link_exist", "document_link", "unique_id",
]


def _write_docket_csv(path: Path, rows: list[list[str]]) -> None:
    """Write a parsed-docket CSV (header + rows) the way DocketParser does."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, dialect="excel")
        writer.writerow(CSV_HEADERS)
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# DocketParser construction and fast parsing (no bs4 required)
# ---------------------------------------------------------------------------


class TestDocketParserInit:
    def test_creates_output_directories(self, tmp_path):
        parser = DocketParser(
            docket_path=tmp_path / "in",
            output_path=tmp_path / "out",
        )
        assert parser.output_path.is_dir()
        assert parser.bugged_path.is_dir()
        assert parser.output_meta_path.is_dir()
        assert (parser.output_meta_path / "case_meta").is_dir()
        assert (parser.output_meta_path / "download_meta").is_dir()

    def test_paths_stored_as_path_objects(self, tmp_path):
        parser = DocketParser(docket_path=str(tmp_path / "in"), output_path=tmp_path / "out")
        assert isinstance(parser.docket_path, Path)
        assert parser.output_path == tmp_path / "out" / "parsed_dockets"
        assert parser.bugged_path == tmp_path / "out" / "bugged_dockets"


class TestDocketParserFastParse:
    """parse()/parse_file() use the selectolax fast parser (no bs4)."""

    def test_parse_returns_parsed_docket(self, tmp_path, sample_docket_html):
        parser = DocketParser(docket_path=tmp_path / "in", output_path=tmp_path / "out")
        result = parser.parse(sample_docket_html)
        assert isinstance(result, ParsedDocket)
        assert result.meta.case_number == "1:18-cv-08434-VEC-SLC"
        assert result.meta.court_id == "nysd"
        assert len(result.entries) >= 2

    def test_parse_file_reads_and_parses(self, tmp_path, sample_docket_file):
        parser = DocketParser(docket_path=tmp_path / "in", output_path=tmp_path / "out")
        result = parser.parse_file(sample_docket_file)
        assert isinstance(result, ParsedDocket)
        assert result.meta.case_number == "1:18-cv-08434-VEC-SLC"

    def test_parse_empty_html(self, tmp_path):
        parser = DocketParser(docket_path=tmp_path / "in", output_path=tmp_path / "out")
        result = parser.parse("<html></html>")
        assert isinstance(result, ParsedDocket)
        assert result.entries == []


# ---------------------------------------------------------------------------
# bs4-fallback branches (these run *because* bs4 is absent in this env)
# ---------------------------------------------------------------------------


class TestDocketParserNoBs4Fallbacks:
    """Cover the `if not HAS_BS4` early-return branches."""

    @pytest.fixture
    def parser(self, tmp_path):
        return DocketParser(docket_path=tmp_path / "in", output_path=tmp_path / "out")

    def test_parse_data_raises_without_bs4(self, parser, sample_docket_html):
        if HAS_BS4:
            pytest.skip("bs4 installed; ImportError branch not reachable")
        with pytest.raises(ImportError):
            parser.parse_data(sample_docket_html)

    def test_extract_download_meta_without_bs4(self, parser, sample_docket_html):
        if HAS_BS4:
            pytest.skip("bs4 installed")
        result = parser.extract_download_meta(sample_docket_html)
        assert "Error_download_meta" in result

    def test_extract_lawyer_meta_without_bs4(self, parser, sample_docket_html):
        if HAS_BS4:
            pytest.skip("bs4 installed")
        result = parser.extract_lawyer_meta(sample_docket_html)
        assert "Error_lawyer_meta" in result

    def test_extract_case_meta_without_bs4(self, parser, sample_docket_html):
        if HAS_BS4:
            pytest.skip("bs4 installed")
        result = parser.extract_case_meta(sample_docket_html)
        assert "Error_case_meta" in result

    def test_extract_all_meta_without_bs4_non_debug(self, parser, sample_docket_html):
        """Without debug, error dicts are swept away into empty dicts."""
        if HAS_BS4:
            pytest.skip("bs4 installed")
        download_meta, docket_meta = parser.extract_all_meta(sample_docket_html, debug=False)
        assert download_meta == {}
        assert docket_meta == {}

    def test_extract_all_meta_without_bs4_debug(self, parser, sample_docket_html):
        """With debug=True, error dicts are preserved."""
        if HAS_BS4:
            pytest.skip("bs4 installed")
        download_meta, docket_meta = parser.extract_all_meta(sample_docket_html, debug=True)
        assert "Error_download_meta" in download_meta
        # docket_meta is case_meta + lawyer_meta merged; both carry error keys
        assert "Error_case_meta" in docket_meta or "Error_lawyer_meta" in docket_meta


# ---------------------------------------------------------------------------
# bs4-dependent behaviour (skipped if bs4 not present)
# ---------------------------------------------------------------------------


class TestDocketParserWithBs4:
    """Exercise the real bs4 parsing paths when bs4 is available."""

    @pytest.fixture
    def parser(self, tmp_path):
        return DocketParser(docket_path=tmp_path / "in", output_path=tmp_path / "out")

    def test_parse_data_extracts_entries(self, parser, sample_docket_html):
        pytest.importorskip("bs4")
        result = parser.parse_data(sample_docket_html)
        assert isinstance(result, list)
        assert len(result) == 2
        # First parsed row: the MOTION entry, which carries a document link.
        # Columns: [date, doc_num, description, link_exist, link, unique_id]
        first = result[0]
        assert first[0] == "09/20/2018"
        assert first[1] == "2"  # doc_num
        assert first[3] == "1"  # link_exist
        assert first[4] == "/doc1/124"  # link
        assert first[-1] == "0"  # unique id
        # The ORDER row has no document link.
        assert result[1][3] == "0"
        assert result[1][4] == ""

    def test_parse_data_no_docket_table_returns_error(self, parser):
        pytest.importorskip("bs4")
        result = parser.parse_data("<html><body><p>no table</p></body></html>")
        assert isinstance(result, str)
        assert "Error" in result

    def test_extract_case_meta_handles_missing_meta(self, parser, sample_docket_html):
        pytest.importorskip("bs4")
        # The sample docket has no "case_meta" column structure, so extraction
        # must degrade gracefully to a reported error dict (not raise).
        result = parser.extract_case_meta(sample_docket_html)
        assert isinstance(result, dict)
        assert "Error_case_meta" in result

    def test_parse_dir_writes_outputs(self, parser, tmp_path, sample_docket_html):
        pytest.importorskip("bs4")
        in_dir = parser.docket_path
        in_dir.mkdir(parents=True, exist_ok=True)
        (in_dir / "case1.html").write_text(sample_docket_html, encoding="utf-8")
        parser.parse_dir(overwrite=True)
        out_csv = parser.output_path / "case1.csv"
        assert out_csv.exists()
        rows = list(csv.reader(out_csv.open(encoding="utf-8")))
        assert rows[0] == CSV_HEADERS

    def test_parse_dir_bugged_on_unparseable(self, parser):
        pytest.importorskip("bs4")
        in_dir = parser.docket_path
        in_dir.mkdir(parents=True, exist_ok=True)
        (in_dir / "bad.html").write_text("<html><body>no table</body></html>", encoding="utf-8")
        parser.parse_dir(overwrite=True)
        assert (parser.bugged_path / "bad.html").exists()


# ---------------------------------------------------------------------------
# DocketProcessor: search_text
# ---------------------------------------------------------------------------


class TestSearchText:
    @pytest.fixture
    def proc(self, tmp_path):
        return DocketProcessor(
            processed_path=tmp_path / "parsed", output_path=tmp_path / "out"
        )

    def test_requires_a_term(self, proc):
        with pytest.raises(ValueError):
            proc.search_text("some text")

    def test_require_term_match(self, proc):
        assert proc.search_text("MOTION to dismiss", require_term="motion") is True

    def test_require_term_no_match(self, proc):
        assert proc.search_text("ORDER granting", require_term="motion") is False

    def test_require_term_as_list_all_must_match(self, proc):
        assert proc.search_text("motion to dismiss", require_term=["motion", "dismiss"]) is True
        assert proc.search_text("motion to compel", require_term=["motion", "dismiss"]) is False

    def test_exclude_term_blocks_match(self, proc):
        assert proc.search_text("sealed motion", exclude_term="sealed") is False

    def test_exclude_term_allows_when_absent(self, proc):
        assert proc.search_text("public motion", exclude_term="sealed") is True

    def test_case_sensitive(self, proc):
        assert proc.search_text("Motion", require_term="motion", case_sensitive=True) is False
        assert proc.search_text("Motion", require_term="Motion", case_sensitive=True) is True


# ---------------------------------------------------------------------------
# DocketProcessor: search_docket
# ---------------------------------------------------------------------------


class TestSearchDocket:
    @pytest.fixture
    def proc(self, tmp_path):
        parsed = tmp_path / "parsed"
        parsed.mkdir(parents=True, exist_ok=True)
        _write_docket_csv(
            parsed / "case1.csv",
            [
                ["09/15/2018", "1", "COMPLAINT filed", "1", "/doc1/123", "0"],
                ["09/20/2018", "2", "MOTION to dismiss", "1", "/doc1/124", "1"],
                ["10/01/2018", "3", "ORDER denying motion", "0", "", "2"],
            ],
        )
        return DocketProcessor(processed_path=parsed, output_path=tmp_path / "out")

    def test_finds_matching_rows(self, proc):
        matches = proc.search_docket("case1.csv", require_term="motion")
        # both MOTION and ORDER ... motion match
        descriptions = [row[2] for row in matches]
        assert "MOTION to dismiss" in descriptions
        assert "ORDER denying motion" in descriptions

    def test_no_match_returns_empty(self, proc):
        matches = proc.search_docket("case1.csv", require_term="bankruptcy")
        assert matches == []

    def test_exclude_filters_rows(self, proc):
        matches = proc.search_docket(
            "case1.csv", require_term="motion", exclude_term="order"
        )
        descriptions = [row[2] for row in matches]
        assert "ORDER denying motion" not in descriptions
        assert "MOTION to dismiss" in descriptions

    def test_within_limits_search_scope(self, proc):
        # "dismiss" appears after char 7 in "MOTION to dismiss";
        # within=5 should not find it.
        matches = proc.search_docket("case1.csv", require_term="dismiss", within=5)
        assert matches == []

    def test_skips_short_rows(self, tmp_path):
        parsed = tmp_path / "parsed2"
        parsed.mkdir(parents=True, exist_ok=True)
        with open(parsed / "short.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, dialect="excel")
            writer.writerow(CSV_HEADERS)
            writer.writerow(["09/15/2018", "1"])  # too short
            writer.writerow(["09/20/2018", "2", "MOTION", "1", "x", "1"])
        proc = DocketProcessor(processed_path=parsed, output_path=tmp_path / "o")
        matches = proc.search_docket("short.csv", require_term="motion")
        assert len(matches) == 1


# ---------------------------------------------------------------------------
# DocketProcessor: search_dir + write methods
# ---------------------------------------------------------------------------


class TestSearchDirAndWrite:
    @pytest.fixture
    def proc(self, tmp_path):
        parsed = tmp_path / "parsed"
        parsed.mkdir(parents=True, exist_ok=True)
        _write_docket_csv(
            parsed / "case1.csv",
            [
                ["09/20/2018", "2", "MOTION to dismiss", "1", "/d/124", "1"],
                ["10/01/2018", "3", "ORDER on motion", "0", "", "2"],
            ],
        )
        _write_docket_csv(
            parsed / "case2.csv",
            [
                ["01/05/2019", "1", "COMPLAINT only", "1", "/d/200", "0"],
            ],
        )
        # a non-csv file that must be ignored
        (parsed / "notes.txt").write_text("ignore me", encoding="utf-8")
        return DocketProcessor(processed_path=parsed, output_path=tmp_path / "out")

    def test_creates_docket_hits_dir(self, proc, tmp_path):
        assert proc.output_path == tmp_path / "out" / "docket_hits"
        assert proc.output_path.is_dir()

    def test_search_dir_populates_hit_list(self, proc):
        proc.search_dir(require_term="motion")
        assert "case1" in proc.hit_list
        assert "case2" not in proc.hit_list

    def test_search_dir_merges_without_duplicates(self, proc):
        proc.search_dir(require_term="motion")
        before = len(proc.hit_list["case1"])
        # Run again: existing key path should dedupe
        proc.search_dir(require_term="motion")
        assert len(proc.hit_list["case1"]) == before

    def test_write_all_matches(self, proc):
        proc.search_dir(require_term="motion")
        proc.write_all_matches(suffix="motion search")
        out = proc.output_path / "all_match__motionsearch.csv"
        assert out.exists()
        rows = list(csv.reader(out.open(encoding="utf-8")))
        assert rows[0][0] == "case_number"
        # Data rows should be prefixed with the case key
        assert any(r[0] == "case1" for r in rows[1:])

    def test_write_all_matches_no_overwrite_raises(self, proc):
        proc.search_dir(require_term="motion")
        proc.write_all_matches(suffix="x", overwrite_flag=True)
        with pytest.raises(IOError):
            proc.write_all_matches(suffix="x", overwrite_flag=False)

    def test_write_all_matches_overwrite_ok(self, proc):
        proc.search_dir(require_term="motion")
        proc.write_all_matches(suffix="x", overwrite_flag=True)
        proc.write_all_matches(suffix="x", overwrite_flag=True)  # should not raise

    def test_write_individual_matches(self, proc):
        proc.search_dir(require_term="motion")
        proc.write_individual_matches(suffix="run1")
        result_dir = proc.output_path / "run1"
        assert result_dir.is_dir()
        files = list(result_dir.glob("*.csv"))
        assert len(files) == 1
        rows = list(csv.reader(files[0].open(encoding="utf-8")))
        assert rows[0][0] == "case_number"

    def test_write_individual_matches_existing_no_overwrite_raises(self, proc):
        proc.search_dir(require_term="motion")
        proc.write_individual_matches(suffix="run2")
        with pytest.raises(IOError):
            proc.write_individual_matches(suffix="run2", overwrite_flag=False)

    def test_write_individual_matches_overwrite_clears_dir(self, proc):
        proc.search_dir(require_term="motion")
        proc.write_individual_matches(suffix="run3")
        # second run with overwrite clears and rewrites
        proc.write_individual_matches(suffix="run3", overwrite_flag=True)
        result_dir = proc.output_path / "run3"
        assert result_dir.is_dir()


# ---------------------------------------------------------------------------
# Metadata extractors that need richly-structured HTML (bs4 only)
# ---------------------------------------------------------------------------

_DOWNLOAD_META_DICT_HTML = (
    "<html><!-- detailed_info:\n"
    "{'searched_case_no': '1:20-cv-1', 'court_id': 'nysd', 'case_name': 'Acme'} -->"
    "<body></body></html>"
)

_DOWNLOAD_META_TUPLE_HTML = (
    "<html><!-- detailed_info: "
    "('1:20-cv-1', 'nysd', 'Acme', '470', '2020-01-01', '', 'http://x/1') -->"
    "<body></body></html>"
)

_LAWYER_HTML = """
<html><body>
<table border="0" cellspacing="5" width="100%">
  <tr><td>Plaintiff</td></tr>
  <tr>
    <td width="40%"><b>Acme Corp</b></td>
    <td width="40%">represented by<br><b>Jane Smith</b><br>Smith LLP</td>
  </tr>
  <tr><td>Defendant</td></tr>
  <tr>
    <td width="40%"><b>Beta Inc</b></td>
    <td width="40%">represented by<br><b>John Doe</b><br>Doe LLP</td>
  </tr>
</table>
</body></html>
"""


class TestMetadataExtractors:
    @pytest.fixture
    def parser(self, tmp_path):
        return DocketParser(docket_path=tmp_path / "in", output_path=tmp_path / "out")

    def test_download_meta_new_dict_format(self, parser):
        pytest.importorskip("bs4")
        result = parser.extract_download_meta(_DOWNLOAD_META_DICT_HTML)
        assert result["court_id"] == "nysd"
        assert result["case_name"] == "Acme"

    def test_download_meta_legacy_tuple_format(self, parser):
        pytest.importorskip("bs4")
        result = parser.extract_download_meta(_DOWNLOAD_META_TUPLE_HTML)
        assert result["searched_case_no"] == "1:20-cv-1"
        assert result["court_id"] == "nysd"
        assert result["link"] == "http://x/1"

    def test_download_meta_no_comment(self, parser):
        pytest.importorskip("bs4")
        result = parser.extract_download_meta("<html><body>no comment</body></html>")
        assert "Error_download_meta" in result

    def test_download_meta_comment_without_marker(self, parser):
        pytest.importorskip("bs4")
        result = parser.extract_download_meta("<html><!-- just a note --><body></body></html>")
        assert "Error_download_meta" in result

    def test_lawyer_meta_extracts_parties_and_attorneys(self, parser):
        pytest.importorskip("bs4")
        result = parser.extract_lawyer_meta(_LAWYER_HTML)
        assert result["plaintiffs"] == ["Acme Corp"]
        assert result["plaintiffs_attorneys"] == ["Jane Smith"]
        assert result["defendants"] == ["Beta Inc"]
        assert result["defendants_attorneys"] == ["John Doe"]

    def test_lawyer_meta_no_table(self, parser):
        pytest.importorskip("bs4")
        result = parser.extract_lawyer_meta("<html><body><p>nothing</p></body></html>")
        assert "Error_lawyer_meta" in result

    def test_extract_all_meta_combines(self, parser):
        pytest.importorskip("bs4")
        download_meta, docket_meta = parser.extract_all_meta(_LAWYER_HTML, debug=True)
        assert isinstance(download_meta, dict)
        assert isinstance(docket_meta, dict)
        # The lawyer table parsed, so party info is merged into docket_meta.
        assert docket_meta.get("plaintiffs") == ["Acme Corp"]
