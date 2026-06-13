"""Fast PACER docket parser using selectolax.

Provides quick parsing for display and LLM context windows.
For comprehensive metadata extraction, use reader.py instead.
"""

from __future__ import annotations

import re
from pathlib import Path

try:
    from selectolax.parser import HTMLParser
    HAS_SELECTOLAX = True
except ImportError:
    HAS_SELECTOLAX = False

from .docket_types import (
    DocketEntry,
    DocketMeta,
    ParsedDocket,
)


def _clean_text(text: str) -> str:
    """Clean up extracted text."""
    from html import unescape
    text = unescape(text)  # Decode &amp; &#036; etc.
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _extract_ecf_domain(html: str) -> str:
    """Extract ECF court domain from HTML."""
    # From title like "CM/ECF - scd" or "CM/ECF - nysd"
    match = re.search(r'<title>CM/ECF\s*-\s*(\w+)', html, re.IGNORECASE)
    if match:
        return match.group(1).lower()

    # From URL patterns
    match = re.search(r'ecf\.(\w+)\.uscourts\.gov', html)
    if match:
        return match.group(1).lower()

    return "unknown"


def parse_docket_selectolax(html: str) -> ParsedDocket:
    """Parse PACER docket HTML using selectolax (fast)."""
    tree = HTMLParser(html)

    # Extract court from title or URL
    court_id = _extract_ecf_domain(html)

    # Extract case number from h3
    case_number = "Unknown"
    h3 = tree.css_first('h3')
    if h3:
        h3_text = h3.text()
        match = re.search(r'CASE #:\s*([\w:\-\.]+)', h3_text)
        if match:
            case_number = match.group(1)

    # Extract header table data
    case_title = ""
    judge = ""
    magistrate = None
    date_filed = ""
    date_closed = None
    nos_code = ""
    nos_desc = ""
    cause = ""
    jurisdiction = ""
    jury_demand = None
    lead_case = None
    member_cases = []

    # Find the header table (width='100%' border=0 CELLSPACING=5)
    header_table = tree.css_first("table[cellspacing='5']")
    if header_table:
        cells = header_table.css('td')
        for cell in cells:
            cell_text = cell.text()
            cell_html = cell.html

            # Left column (60%)
            if 'v.' in cell_text or 'v ' in cell_text:
                # First line is case title
                lines = [ln.strip() for ln in cell_text.split('\n') if ln.strip()]
                if lines:
                    case_title = lines[0]

            if 'Assigned to:' in cell_text:
                match = re.search(r'Assigned to:\s*(.+?)(?:\n|$)', cell_text)
                if match:
                    judge = match.group(1).strip()

            if 'Referred to:' in cell_text:
                match = re.search(r'Referred to:\s*(.+?)(?:\n|$)', cell_text)
                if match:
                    magistrate = match.group(1).strip()

            if 'Lead case:' in cell_html:
                link = cell.css_first('a')
                if link:
                    lead_case = link.text()

            if 'Cause:' in cell_text:
                match = re.search(r'Cause:\s*(.+?)(?:\n|$)', cell_text)
                if match:
                    cause = match.group(1).strip()

            # Right column (40%)
            if 'Date Filed:' in cell_text:
                match = re.search(r'Date Filed:\s*(\d{2}/\d{2}/\d{4})', cell_text)
                if match:
                    # Convert MM/DD/YYYY to YYYY-MM-DD
                    parts = match.group(1).split('/')
                    date_filed = f"{parts[2]}-{parts[0]}-{parts[1]}"

            if 'Date Terminated:' in cell_text:
                match = re.search(r'Date Terminated:\s*(\d{2}/\d{2}/\d{4})', cell_text)
                if match:
                    parts = match.group(1).split('/')
                    date_closed = f"{parts[2]}-{parts[0]}-{parts[1]}"

            if 'Nature of Suit:' in cell_text:
                match = re.search(r'Nature of Suit:\s*(\d+)\s*(.+?)(?:\n|$)', cell_text)
                if match:
                    nos_code = match.group(1)
                    nos_desc = match.group(2).strip()

            if 'Jurisdiction:' in cell_text:
                match = re.search(r'Jurisdiction:\s*(.+?)(?:\n|$)', cell_text)
                if match:
                    jurisdiction = match.group(1).strip()

            if 'Jury Demand:' in cell_text:
                match = re.search(r'Jury Demand:\s*(.+?)(?:\n|$)', cell_text)
                if match:
                    jury_demand = match.group(1).strip()

    # Extract docket entries from table with rules=all
    entries: list[DocketEntry] = []
    docket_table = tree.css_first("table[rules='all']")

    if docket_table:
        rows = docket_table.css('tr')
        for seq, row in enumerate(rows):
            cells = row.css('td')
            if len(cells) < 3:
                continue  # Skip header row

            # Date
            date_cell = cells[0].text().strip()
            if not re.match(r'\d{2}/\d{2}/\d{4}', date_cell):
                continue
            parts = date_cell.split('/')
            entry_date = f"{parts[2]}-{parts[0]}-{parts[1]}"

            # Doc number and URL
            doc_num = None
            doc_url = None
            link = cells[1].css_first('a')
            if link:
                doc_num = link.text().strip()
                doc_url = link.attributes.get('href', '')
            else:
                # Check for plain number
                num_text = cells[1].text().strip()
                if num_text and num_text.isdigit():
                    doc_num = num_text

            # Docket text - remove <!--SB--> comment marker
            text_html = cells[2].html or ""
            text_clean = re.sub(r'<!--.*?-->', '', text_html)
            text = _clean_text(HTMLParser(text_clean).text())

            # Check for attachments
            attachment_links = cells[2].css('a')
            has_attachments = len(attachment_links) > 1  # More than main doc link
            attachment_count = max(0, len(attachment_links) - 1)

            entries.append(DocketEntry(
                seq=len(entries),
                date=entry_date,
                doc_num=doc_num,
                doc_url=doc_url,
                text=text,
                has_attachments=has_attachments,
                attachment_count=attachment_count,
            ))

    # Build metadata
    meta = DocketMeta(
        court_id=court_id,
        case_number=case_number,
        case_title=case_title,
        date_filed=date_filed,
        date_closed=date_closed,
        judge=judge,
        magistrate=magistrate,
        nature_of_suit=nos_code,
        nos_description=nos_desc,
        cause=cause,
        jurisdiction=jurisdiction,
        jury_demand=jury_demand,
        lead_case=lead_case,
        member_cases=member_cases,
    )

    return ParsedDocket(meta=meta, entries=entries, parties=[])


def parse_docket_regex(html: str) -> ParsedDocket:
    """Fallback parser using regex (no dependencies)."""
    court_id = _extract_ecf_domain(html)

    # Case number
    case_match = re.search(r'CASE #:\s*([\w:\-\.]+)', html)
    case_number = case_match.group(1) if case_match else "Unknown"

    # Case title (plaintiff v. defendant)
    title_match = re.search(r'<br>([^<]+v\.[^<]+)<br>', html, re.IGNORECASE)
    case_title = _clean_text(title_match.group(1)) if title_match else "Unknown"

    # Judge
    judge_match = re.search(r'Assigned to:\s*([^<\n]+)', html)
    judge = _clean_text(judge_match.group(1)) if judge_match else ""

    # Filed date
    filed_match = re.search(r'Date Filed:\s*(\d{2}/\d{2}/\d{4})', html)
    if filed_match:
        parts = filed_match.group(1).split('/')
        date_filed = f"{parts[2]}-{parts[0]}-{parts[1]}"
    else:
        date_filed = ""

    # Nature of suit
    nos_match = re.search(r'Nature of Suit:\s*(\d+)\s*([^<\n]+)', html)
    nos_code = nos_match.group(1) if nos_match else ""
    nos_desc = _clean_text(nos_match.group(2)) if nos_match else ""

    # Extract entries with regex
    entries: list[DocketEntry] = []
    row_pattern = re.compile(
        r"<tr><td[^>]*>(\d{2}/\d{2}/\d{4})</td>"
        r"<td[^>]*>(?:<a href=['\"]([^'\"]+)['\"][^>]*>(\d+)</a>|(\d+))?[^<]*</td>"
        r"<td[^>]*><!--SB-->(.+?)</td></tr>",
        re.DOTALL | re.IGNORECASE
    )

    for seq, match in enumerate(row_pattern.finditer(html)):
        date_str = match.group(1)
        parts = date_str.split('/')
        entry_date = f"{parts[2]}-{parts[0]}-{parts[1]}"

        doc_url = match.group(2)
        doc_num = match.group(3) or match.group(4)
        text = _clean_text(re.sub(r'<[^>]+>', ' ', match.group(5)))

        entries.append(DocketEntry(
            seq=seq,
            date=entry_date,
            doc_num=doc_num,
            doc_url=doc_url,
            text=text[:500],
        ))

    meta = DocketMeta(
        court_id=court_id,
        case_number=case_number,
        case_title=case_title,
        date_filed=date_filed,
        judge=judge,
        nature_of_suit=nos_code,
        nos_description=nos_desc,
    )

    return ParsedDocket(meta=meta, entries=entries, parties=[])


def parse_docket(html: str) -> ParsedDocket:
    """Parse PACER docket HTML. Uses selectolax if available, else regex."""
    if HAS_SELECTOLAX:
        return parse_docket_selectolax(html)
    return parse_docket_regex(html)


def parse_docket_file(filepath: Path, output_format: str = "compact") -> str:
    """Parse a docket file and return formatted output.

    Args:
        filepath: Path to HTML docket file
        output_format: "compact" (LLM), "markdown" (human), "json"

    Returns:
        Formatted docket string
    """
    html = filepath.read_text(encoding='utf-8', errors='ignore')
    docket = parse_docket(html)

    if output_format == "json":
        return docket.to_json()
    elif output_format == "markdown":
        return docket.to_markdown()
    else:
        return docket.to_compact()


# Legacy compatibility functions

def clean_text(html: str) -> str:
    """Strip HTML tags and clean up text (legacy)."""
    text = re.sub(r'<[^>]+>', ' ', html)
    from html import unescape
    text = unescape(text)
    return _clean_text(text)


def format_docket_text(docket: ParsedDocket, verbose: bool = False) -> str:
    """Format docket for display (legacy wrapper)."""
    if verbose:
        return docket.to_markdown(verbose=True)
    return docket.to_compact()
