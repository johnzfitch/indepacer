"""
PACER docket parser and processor module.

Modernized from pacer_lib 2.33 for Python 3.10+.

For fast parsing and LLM-friendly output, use parser.py instead.
This module provides comprehensive metadata extraction and CSV batch processing.
"""

from __future__ import annotations

import ast
import csv
import json
import os
from pathlib import Path
from typing import Any

# Import shared types
from .docket_types import ParsedDocket

# Optional BeautifulSoup for fallback/legacy support
try:
    from bs4 import BeautifulSoup, Comment
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False
    BeautifulSoup = None  # type: ignore
    Comment = None  # type: ignore

# Import fast parser
from .parser import parse_docket as parse_docket_fast


class DocketParser:
    """
    Parse PACER docket HTML files into structured CSV data.

    Built on BeautifulSoup 4. Loads .html PACER docket sheets,
    parses metadata, and converts to machine-readable CSV format.

    Args:
        docket_path: Path to folder containing .html docket files
        output_path: Path for output files. Creates subfolders:
            - parsed_dockets/
            - parsed_dockets_meta/case_meta/
            - parsed_dockets_meta/download_meta/
            - bugged_dockets/
    """

    def __init__(
        self,
        docket_path: str | Path = "./results/local_docket_archive",
        output_path: str | Path = "./results",
    ) -> None:
        self.docket_path = Path(docket_path)
        output = Path(output_path)

        self.bugged_path = output / "bugged_dockets"
        self.output_path = output / "parsed_dockets"
        self.output_meta_path = output / "parsed_dockets_meta"

        # Create directories
        self.output_path.mkdir(parents=True, exist_ok=True)
        self.bugged_path.mkdir(parents=True, exist_ok=True)
        self.output_meta_path.mkdir(parents=True, exist_ok=True)
        (self.output_meta_path / "case_meta").mkdir(exist_ok=True)
        (self.output_meta_path / "download_meta").mkdir(exist_ok=True)

    def parse(self, data: str) -> ParsedDocket:
        """Parse HTML to structured ParsedDocket object.

        Uses fast selectolax parser. For legacy CSV output, use parse_data().

        Args:
            data: HTML string from a PACER docket file

        Returns:
            ParsedDocket with metadata, entries, and parties
        """
        return parse_docket_fast(data)

    def parse_file(self, filepath: Path) -> ParsedDocket:
        """Parse a docket file to structured ParsedDocket object.

        Args:
            filepath: Path to HTML docket file

        Returns:
            ParsedDocket with metadata, entries, and parties
        """
        html = filepath.read_text(encoding="utf-8", errors="replace")
        return self.parse(html)

    def parse_data(self, data: str) -> list[list[str]] | str:
        """
        Parse docket entries from HTML data (legacy CSV format).

        Uses BeautifulSoup with html.parser, falls back to html5lib.
        Requires beautifulsoup4 and html5lib packages.
        For fast parsing, use parse() instead.

        Args:
            data: HTML string from a .html docket file

        Returns:
            List of docket entries (each entry is a list) or error string.
            Each entry contains:
            - 0: date_filed
            - 1: document_number
            - 2: docket_description
            - 3: link_exist ('1' or '0')
            - 4: document_link
            - 5: unique_id (position in docket)
        """
        if not HAS_BS4:
            raise ImportError(
                "BeautifulSoup4 required for parse_data(). "
                "Install with: pip install 'pacer-cli[full]'"
            )

        parsed_docket_table: list[list[str]] = []

        # Parse HTML, try html.parser first, then html5lib
        source = BeautifulSoup(data, "html.parser")
        for s in source("script"):
            s.extract()

        docket_table = source.find("table", {"rules": "all"})
        if not docket_table:
            source = BeautifulSoup(data, "html5lib")
            for s in source("script"):
                s.extract()
            docket_table = source.find("table", {"rules": "all"})
            if not docket_table:
                return "Error, could not find docket_table."

        docket_entries = docket_table.find_all("tr")
        if not docket_entries:
            source = BeautifulSoup(data, "html5lib")
            for s in source("script"):
                s.extract()
            docket_table = source.find("table", {"rules": "all"})
            if docket_table:
                docket_entries = docket_table.find_all("tr")
            if not docket_entries:
                return "Error, could not find docket_entries."

        # Parse each entry
        skip_first = True
        for entry in docket_entries:
            if skip_first:
                skip_first = False
                continue

            row_cells = entry.find_all("td")
            row_contents = [c.get_text(" ", strip=True) for c in row_cells]
            row_contents = [c.replace("\t", "").replace("\r\n", "") for c in row_contents]

            # Truncate extremely long cells
            for n, content in enumerate(row_contents):
                if len(content) > 20000:
                    row_contents[n] = content[:20001] + "(TRUNCATED)"

            # Replace missing info
            if len(row_contents) > 0 and row_contents[0] == "":
                row_contents[0] = "NA"
            if len(row_contents) > 1 and row_contents[1] == "":
                row_contents[1] = "NA"

            # Extract document link
            link_exist = "0"
            link = ""
            if len(row_cells) > 1:
                link_elem = row_cells[1].find("a")
                if link_elem:
                    link_exist = "1"
                    link = link_elem.get("href", "")

            row_contents.extend([link_exist, link])
            parsed_docket_table.append(row_contents)

        # Add unique IDs
        for number, line in enumerate(parsed_docket_table):
            line.append(str(number))

        return parsed_docket_table

    def extract_download_meta(self, data: str) -> dict[str, Any]:
        """
        Extract download metadata from docket HTML.

        Parses the detailed_info JSON comment added by pacer_lib.scraper()
        at download time for reproducibility.

        Args:
            data: HTML string from a .html docket file

        Returns:
            Dictionary with keys:
            - searched_case_no: Original query
            - court_id: Court abbreviation
            - case_name: Case title
            - nos: Nature of suit code
            - date_filed: Filing date
            - date_closed: Closure date
            - link: Docket link
            - downloaded: Download timestamp (newer versions)
            - listed_case_no: Preferred case number (newer versions)
            - result_no: Search result position (newer versions)

            Or dict with Error_download_meta key on failure.
        """
        if not HAS_BS4:
            return {"Error_download_meta": "BeautifulSoup4 not installed"}

        source = BeautifulSoup(data, "html.parser")
        comment = source.find(string=lambda text: isinstance(text, Comment))

        if not comment:
            return {"Error_download_meta": "no comments in source code"}

        comment_str = str(comment)

        if "detailed_info:" not in comment_str:
            return {"Error_download_meta": "'detailed_info:' not found"}

        # New format (JSON-like dict)
        if "{" in comment_str:
            try:
                cleaned = comment_str.replace("detailed_info:\n", "").strip()
                # Fix internal quotes for ast.literal_eval
                cleaned = cleaned.replace(' "', ' \\"').replace('" ', '\\" ')
                return ast.literal_eval(cleaned)
            except (ValueError, SyntaxError):
                return {"Error_download_meta": "Failed to parse detailed_info dict"}

        # Legacy format (tuple/list)
        if "(" in comment_str:
            try:
                cleaned = comment_str.replace("detailed_info:", "").strip()
                cleaned = cleaned.replace("(", "[").replace(")", "]")
                cleaned = cleaned.replace('""', '"')
                cleaned = cleaned.replace(' "', ' \\"').replace('" ', '\\" ')
                temp = ast.literal_eval(cleaned)
                return {
                    "searched_case_no": temp[0] if len(temp) > 0 else "",
                    "court_id": temp[1] if len(temp) > 1 else "",
                    "case_name": temp[2] if len(temp) > 2 else "",
                    "nos": temp[3] if len(temp) > 3 else "",
                    "date_filed": temp[4] if len(temp) > 4 else "",
                    "date_closed": temp[5] if len(temp) > 5 else "",
                    "link": temp[6] if len(temp) > 6 else "",
                }
            except (ValueError, SyntaxError):
                return {"Error_download_meta": "Failed to parse legacy detailed_info"}

        return {"Error_download_meta": "'detailed_info:' format not recognized"}

    def extract_lawyer_meta(self, data: str) -> dict[str, Any]:
        """
        Extract lawyer/party information from docket HTML.

        Currently handles single plaintiff/defendant listings.
        May not work for class actions or complex party structures.

        Args:
            data: HTML string from a .html docket file

        Returns:
            Dictionary with keys:
            - plaintiffs: List of plaintiff names
            - defendants: List of defendant names
            - plaintiffs_attorneys: List of plaintiff attorney names
            - defendants_attorneys: List of defendant attorney names
            - plaintiffs_attorneys_details: Raw attorney details string
            - defendants_attorneys_details: Raw attorney details string

            Or dict with Error_lawyer_meta key on failure.
        """
        if not HAS_BS4:
            return {"Error_lawyer_meta": "BeautifulSoup4 not installed"}

        source = BeautifulSoup(data, "html.parser")
        table_attrs = {"border": "0", "cellspacing": "5", "width": "100%"}
        tables = source.find_all("table", table_attrs)

        base = None
        for table in tables:
            filter_text = table.get_text().lower()
            if "jury demand" in filter_text or "date filed" in filter_text or "docket text" in filter_text:
                continue
            if "plaintiff" in filter_text and "defendant" in filter_text and "represented" in filter_text:
                base = table

        if not base:
            return {"Error_lawyer_meta": "Could not identify table"}

        rows = base.find_all("tr")
        plaintiff_row = None
        defendant_row = None
        parse_state = 0

        for row in rows:
            row_text = row.get_text()
            if "Plaintiff" in row_text:
                parse_state = 1
                continue
            if "Defendant" in row_text:
                parse_state = 2
                continue
            if "Fictitious Defendant" in row_text:
                parse_state = 3

            if not row_text.strip():
                continue

            if parse_state == 1 and not plaintiff_row:
                plaintiff_row = row
            if parse_state == 2 and not defendant_row:
                defendant_row = row

        if parse_state == 0:
            return {"Error_lawyer_meta": "Could not identify any rows."}

        if plaintiff_row is None or defendant_row is None:
            return {"Error_lawyer_meta": "Missing plaintiff or defendant row"}

        plaintiff_cells = plaintiff_row.find_all("td", {"width": "40%"})
        defendant_cells = defendant_row.find_all("td", {"width": "40%"})

        if len(defendant_cells) != 2 or len(plaintiff_cells) != 2:
            return {"Error_lawyer_meta": "Too many cells or not enough cells. Check source."}

        def clean_names(names: list) -> list[str]:
            result = []
            for name in names:
                new_name = name.get_text().strip().replace("\t", " ")
                while "  " in new_name:
                    new_name = new_name.replace("  ", " ")
                result.append(new_name)
            return result

        def clean_details(cell) -> str:
            details = cell.get_text().strip().replace("\r", "")
            while "  " in details:
                details = details.replace("  ", " ")
            while "\n " in details:
                details = details.replace("\n ", "\n")
            while "\n\n" in details:
                details = details.replace("\n\n", "\n")
            return details

        return {
            "plaintiffs": clean_names(plaintiff_cells[0].find_all("b")),
            "plaintiffs_attorneys": clean_names(plaintiff_cells[1].find_all("b")),
            "plaintiffs_attorneys_details": clean_details(plaintiff_cells[1]),
            "defendants": clean_names(defendant_cells[0].find_all("b")),
            "defendants_attorneys": clean_names(defendant_cells[1].find_all("b")),
            "defendants_attorneys_details": clean_details(defendant_cells[1]),
        }

    def extract_case_meta(self, data: str) -> dict[str, Any]:
        """
        Extract case metadata from docket HTML.

        Parses case info like case name, assigned judge, demand,
        nature of suit, jurisdiction, dates, etc.

        Args:
            data: HTML string from a .html docket file

        Returns:
            Dictionary with common keys:
            - Case name
            - Assigned to
            - Referred to
            - Demand
            - Case in other court
            - Cause
            - Date Filed
            - Date Terminated
            - Jury Demand
            - Nature of Suit
            - Jurisdiction
            - Member case (if lead case)
            - Lead case (if member case)
            - meta_links (if links present)

            Or dict with Error_case_meta key on failure.
        """
        if not HAS_BS4:
            return {"Error_case_meta": "BeautifulSoup4 not installed"}

        source = BeautifulSoup(data, "html.parser")
        case_meta = ""
        case_meta_dict: dict[str, Any] = {}
        meta_links: list[tuple[str, str]] = []

        # Find the case info columns
        left_column = source.find_all("td", {"valign": "top", "width": "60%"})
        for cell in left_column:
            if "Assigned to" in cell.prettify():
                case_meta += cell.text.strip()
                for link in cell.find_all("a"):
                    meta_links.append((link.text, link.get("href", "")))

        right_column = source.find_all("td", {"valign": "top", "width": "40%"})
        for cell in right_column:
            if "Date Filed:" in cell.prettify():
                case_meta += cell.text.strip()

        if not case_meta:
            return {"Error_case_meta": "case_meta string not found in columns"}

        # Clean the case_meta string
        case_meta = case_meta.strip().replace("\r", "")
        while "  " in case_meta:
            case_meta = case_meta.replace("  ", " ")
        while "\n " in case_meta:
            case_meta = case_meta.replace("\n ", "\n")
        while "\n\n" in case_meta:
            case_meta = case_meta.replace("\n\n", "\n")
        case_meta = case_meta.replace(":\n", ": ")

        # Parse into dictionary
        lines = case_meta.split("\n")
        for item in lines:
            item = item.replace("\xa0", " ").replace("\xc3", "")
            parts = item.split(":")
            parts = [p.strip() for p in parts]

            if len(parts) == 1:
                case_meta_dict["Case name"] = parts[0]
            elif len(parts) > 2:
                case_meta_dict[parts[0]] = ":".join(parts[1:])
            else:
                case_meta_dict[parts[0]] = parts[1] if len(parts) > 1 else ""

        if meta_links:
            case_meta_dict["meta_links"] = meta_links

        return case_meta_dict

    def extract_all_meta(
        self,
        data: str,
        debug: bool = False,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """
        Extract all metadata from docket HTML.

        Runs extract_case_meta(), extract_lawyer_meta(), and
        extract_download_meta() and combines results.

        Args:
            data: HTML string from a .html docket file
            debug: If True, include error dictionaries in output

        Returns:
            Tuple of (download_meta, docket_meta) dictionaries.
            docket_meta combines case_meta and lawyer_meta.
        """
        download_meta = self.extract_download_meta(data)
        if "Error_download_meta" in download_meta and not debug:
            download_meta = {}

        case_meta = self.extract_case_meta(data)
        if "Error_case_meta" in case_meta and not debug:
            case_meta = {}

        lawyer_meta = self.extract_lawyer_meta(data)
        if "Error_lawyer_meta" in lawyer_meta and not debug:
            lawyer_meta = {}

        # Check for duplicate keys
        common_keys = set(lawyer_meta.keys()) & set(case_meta.keys())
        if common_keys:
            return download_meta, {"Error": "Key Conflicts"}

        docket_meta = {**case_meta, **lawyer_meta}
        return download_meta, docket_meta

    def parse_dir(self, overwrite: bool = True) -> None:
        """
        Parse all dockets in the docket_path folder.

        Runs parse_data() and extract_all_meta() on each .html file.
        Saves parsed entries as CSV and metadata as JSON.

        Args:
            overwrite: If True, overwrite existing output files
        """
        csv_headers = [
            "date_filed", "document_number", "docket_description",
            "link_exist", "document_link", "unique_id",
        ]

        for root, dirs, files in os.walk(self.docket_path):
            for file in files:
                if not file.endswith(".html"):
                    continue

                base_name = file.replace(".html", "")
                output_file = self.output_path / f"{base_name}.csv"
                case_meta_file = self.output_meta_path / "case_meta" / f"case_meta_{base_name}.json"
                download_meta_file = self.output_meta_path / "download_meta" / f"download_meta_{base_name}.json"

                if not overwrite and output_file.exists():
                    continue

                input_path = Path(root) / file
                source = input_path.read_text(encoding="utf-8", errors="replace")
                download_meta, case_meta = self.extract_all_meta(source)
                content = self.parse_data(source)

                if isinstance(content, str):
                    print(f"{file}: {content}")
                    bugged_file = self.bugged_path / file
                    bugged_file.write_text(source, encoding="utf-8")
                    continue

                case_meta["docket_entries"] = len(content)

                with open(output_file, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f, dialect="excel")
                    writer.writerow(csv_headers)
                    writer.writerows(content)

                with open(download_meta_file, "w", encoding="utf-8") as f:
                    json.dump(download_meta, f)

                with open(case_meta_file, "w", encoding="utf-8") as f:
                    json.dump(case_meta, f)


class DocketProcessor:
    """
    Search parsed docket entries for keywords.

    Works with CSV files produced by DocketParser.

    Args:
        processed_path: Path to folder with parsed .csv docket files
        output_path: Path for search results. Creates 'docket_hits/' subfolder.
    """

    def __init__(
        self,
        processed_path: str | Path = "./results/parsed_dockets",
        output_path: str | Path = "./results/",
    ) -> None:
        self.processed_path = Path(processed_path)
        output = Path(output_path)

        self.output_path = output / "docket_hits"
        self.output_path.mkdir(parents=True, exist_ok=True)

        self.hit_list: dict[str, list[list[str]]] = {}

    def search_text(
        self,
        text: str,
        require_term: list[str] | str | None = None,
        exclude_term: list[str] | str | None = None,
        case_sensitive: bool = False,
    ) -> bool:
        """
        Check if text matches search criteria.

        Args:
            text: Text to search
            require_term: Terms that must be present (all must match)
            exclude_term: Terms that must be absent (none can match)
            case_sensitive: If False, search is case-insensitive

        Returns:
            True if all require_terms found and no exclude_terms found

        Raises:
            ValueError: If neither require_term nor exclude_term specified
        """
        if require_term is None:
            require_term = []
        if exclude_term is None:
            exclude_term = []

        if isinstance(require_term, str):
            require_term = [require_term]
        if isinstance(exclude_term, str):
            exclude_term = [exclude_term]

        if not require_term and not exclude_term:
            raise ValueError("You must search for at least one required or excluded term.")

        if not case_sensitive:
            text = text.lower()
            require_term = [t.lower() for t in require_term]
            exclude_term = [t.lower() for t in exclude_term]

        for term in require_term:
            if term not in text:
                return False

        for term in exclude_term:
            if term in text:
                return False

        return True

    def search_docket(
        self,
        docket: str,
        require_term: list[str] | str | None = None,
        exclude_term: list[str] | str | None = None,
        case_sensitive: bool = False,
        within: int = 0,
    ) -> list[list[str]]:
        """
        Search a single docket file for matching entries.

        Args:
            docket: Filename of the docket CSV to search
            require_term: Terms that must be present
            exclude_term: Terms that must be absent
            case_sensitive: If False, search is case-insensitive
            within: If > 0, only search first N characters of description

        Returns:
            List of matching docket entries
        """
        if require_term is None:
            require_term = []
        if exclude_term is None:
            exclude_term = []

        matched_list: list[list[str]] = []
        header_passed = False
        expected_header = [
            "date_filed", "document_number", "docket_description",
            "link_exist", "document_link", "unique_id",
        ]

        docket_path = self.processed_path / docket
        with open(docket_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f, dialect="excel")
            for row in reader:
                if not header_passed:
                    if row == expected_header:
                        header_passed = True
                    continue

                if len(row) < 3:
                    continue

                description = row[2]
                if within > 0:
                    description = description[: within - 1]

                if self.search_text(description, require_term, exclude_term, case_sensitive):
                    matched_list.append(row)

        return matched_list

    def search_dir(
        self,
        require_term: list[str] | str | None = None,
        exclude_term: list[str] | str | None = None,
        case_sensitive: bool = False,
        within: int = 0,
    ) -> None:
        """
        Search all dockets in processed_path for matches.

        Adds results to self.hit_list as {case_number: [entries]}.

        Args:
            require_term: Terms that must be present
            exclude_term: Terms that must be absent
            case_sensitive: If False, search is case-insensitive
            within: If > 0, only search first N characters of description
        """
        for root, dirs, files in os.walk(self.processed_path):
            for file in files:
                if not file.endswith(".csv"):
                    continue

                filename = file.replace(".csv", "")

                if filename not in self.hit_list:
                    matched = self.search_docket(
                        file, require_term, exclude_term, case_sensitive, within
                    )
                    if matched:
                        self.hit_list[filename] = matched
                else:
                    for match in self.search_docket(
                        file, require_term, exclude_term, case_sensitive, within
                    ):
                        if match not in self.hit_list[filename]:
                            self.hit_list[filename].append(match)

    def write_all_matches(self, suffix: str, overwrite_flag: bool = False) -> None:
        """
        Write all matches to a single CSV file.

        Args:
            suffix: Suffix for output filename (sanitized)
            overwrite_flag: If True, overwrite existing file

        Raises:
            IOError: If file exists and overwrite_flag is False
        """
        csv_headers = [
            "case_number", "date_filed", "document_number", "docket_description",
            "link_exist", "document_link", "unique_id",
        ]

        # Sanitize suffix
        for char in "/_\\?%*:|\"<>. ":
            suffix = suffix.replace(char, "")

        output_file = self.output_path / f"all_match__{suffix}.csv"

        if not overwrite_flag and output_file.exists():
            raise IOError(
                f'A .csv with the suffix "{suffix}" already exists. '
                "Choose new suffix or specify overwrite_flag."
            )

        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, dialect="excel")
            writer.writerow(csv_headers)

            for key, rows in self.hit_list.items():
                for row in rows:
                    writer.writerow([key] + row)

    def write_individual_matches(self, suffix: str, overwrite_flag: bool = False) -> None:
        """
        Write matches to separate CSV files per docket.

        Args:
            suffix: Suffix for output folder and filenames (sanitized)
            overwrite_flag: If True, overwrite existing files

        Raises:
            IOError: If files exist and overwrite_flag is False
        """
        csv_headers = [
            "case_number", "date_filed", "document_number", "docket_description",
            "link_exist", "document_link", "unique_id",
        ]

        # Sanitize suffix
        for char in "/_\\?%*:|\"<>. ":
            suffix = suffix.replace(char, "")

        result_path = self.output_path / suffix

        if result_path.exists():
            if overwrite_flag:
                for f in result_path.iterdir():
                    f.unlink()
            else:
                raise IOError(
                    f'.csv files with the suffix "{suffix}" already exist. '
                    "Choose new suffix or specify overwrite_flag."
                )
        else:
            result_path.mkdir(parents=True)

        for key, rows in self.hit_list.items():
            output_file = result_path / f"^{key}_{suffix}.csv"
            with open(output_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f, dialect="excel")
                writer.writerow(csv_headers)
                writer.writerows(rows)
