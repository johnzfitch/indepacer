"""Type definitions for parsed PACER dockets.

Provides dataclasses for structured representation of PACER docket data
with multiple output formats (compact, JSON, Markdown).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Optional


# Key filing terms for filtering significant entries
KEY_TERMS = frozenset({
    'COMPLAINT', 'MOTION', 'ORDER', 'OPINION', 'JUDGMENT',
    'SETTLEMENT', 'DISMISS', 'SEALED', 'AMENDED', 'ANSWER',
    'STIPULATION', 'MEMORANDUM', 'BRIEF', 'OPPOSITION',
    'REPLY', 'NOTICE', 'SUBPOENA', 'SUMMONS', 'VERDICT',
})


@dataclass
class Attorney:
    """Attorney information."""
    name: str
    firm: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    pro_hac_vice: bool = False


@dataclass
class Party:
    """Party to the case."""
    role: str  # Plaintiff, Defendant, etc.
    name: str
    attorneys: list[Attorney] = field(default_factory=list)
    pro_se: bool = False

    def to_compact(self) -> str:
        """Format as compact string."""
        role_abbrev = {'Plaintiff': 'P', 'Defendant': 'D'}.get(self.role, self.role[:3])
        if self.pro_se:
            return f"{role_abbrev}: {self.name} (pro se)"
        atty_names = ', '.join(a.name for a in self.attorneys[:2])
        if len(self.attorneys) > 2:
            atty_names += f" +{len(self.attorneys) - 2}"
        return f"{role_abbrev}: {self.name} | Atty: {atty_names}" if atty_names else f"{role_abbrev}: {self.name}"


@dataclass
class DocketEntry:
    """Single docket entry."""
    seq: int
    date: str  # ISO format YYYY-MM-DD
    doc_num: Optional[str] = None
    doc_url: Optional[str] = None
    text: str = ""
    has_attachments: bool = False
    attachment_count: int = 0

    @property
    def is_key_filing(self) -> bool:
        """Check if this is a significant filing."""
        text_upper = self.text.upper()
        return any(term in text_upper for term in KEY_TERMS)

    def to_compact(self, max_len: int = 80) -> str:
        """Format as compact single line."""
        doc = f"[{self.doc_num}]" if self.doc_num else "    "
        text = self.text[:max_len] + "..." if len(self.text) > max_len else self.text
        return f"{self.date} {doc:>6} {text}"


@dataclass
class DocketMeta:
    """Case-level metadata."""
    court_id: str  # e.g., "nysd"
    case_number: str  # e.g., "1:18-cv-08434-VEC-SLC"
    case_title: str
    date_filed: str  # ISO format
    date_closed: Optional[str] = None
    judge: str = ""
    magistrate: Optional[str] = None
    nature_of_suit: str = ""  # Code like "442"
    nos_description: str = ""  # "Civil Rights: Jobs"
    cause: str = ""
    jurisdiction: str = ""
    jury_demand: Optional[str] = None
    demand: Optional[str] = None
    lead_case: Optional[str] = None
    member_cases: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)  # CLOSED, MDL, etc.


@dataclass
class ParsedDocket:
    """Complete parsed docket with all data."""
    meta: DocketMeta
    entries: list[DocketEntry]
    parties: list[Party] = field(default_factory=list)
    download_meta: Optional[dict] = None

    def key_entries(self, limit: int = 20) -> list[DocketEntry]:
        """Return most significant docket entries."""
        key = [e for e in self.entries if e.is_key_filing]
        return key[:limit]

    def to_compact(self, max_entries: int = 25) -> str:
        """Export as compact YAML-like format for LLM context.

        Optimized for minimal token usage while preserving key info.
        """
        lines = [
            f"# PACER Docket: {self.meta.case_number}",
            f"court: {self.meta.court_id.upper()}",
            f"filed: {self.meta.date_filed}",
        ]

        if self.meta.date_closed:
            lines.append(f"closed: {self.meta.date_closed}")
        if self.meta.judge:
            lines.append(f"judge: {self.meta.judge}")
        if self.meta.magistrate:
            lines.append(f"mag: {self.meta.magistrate}")
        if self.meta.nature_of_suit:
            nos = f"{self.meta.nature_of_suit} {self.meta.nos_description}".strip()
            lines.append(f"nos: {nos}")
        if self.meta.cause:
            lines.append(f"cause: {self.meta.cause}")

        lines.append(f"title: {self.meta.case_title}")
        lines.append(f"entries: {len(self.entries)}")

        # Key filings
        key = self.key_entries(max_entries)
        if key:
            lines.append("")
            lines.append("## Key Filings")
            for entry in key:
                lines.append(entry.to_compact())

        # Parties (compact)
        if self.parties:
            lines.append("")
            lines.append("## Parties")
            for party in self.parties:
                lines.append(party.to_compact())

        return "\n".join(lines)

    def to_markdown(self, verbose: bool = False) -> str:
        """Export as Markdown for human reading."""
        lines = [
            f"# {self.meta.case_title}",
            "",
            f"**Case:** {self.meta.case_number}  ",
            f"**Court:** {self.meta.court_id.upper()}  ",
            f"**Filed:** {self.meta.date_filed}  ",
        ]

        if self.meta.date_closed:
            lines.append(f"**Closed:** {self.meta.date_closed}  ")
        if self.meta.judge:
            lines.append(f"**Judge:** {self.meta.judge}  ")
        if self.meta.nature_of_suit:
            lines.append(f"**Nature of Suit:** {self.meta.nature_of_suit} - {self.meta.nos_description}  ")

        # Parties
        if self.parties:
            lines.extend(["", "## Parties", ""])
            for party in self.parties:
                atty_list = ", ".join(a.name for a in party.attorneys) if party.attorneys else "(none)"
                lines.append(f"- **{party.role}:** {party.name}")
                if party.pro_se:
                    lines.append(f"  - *Pro Se*")
                else:
                    lines.append(f"  - Attorneys: {atty_list}")

        # Docket entries
        lines.extend(["", "## Docket Entries", ""])
        lines.append(f"*{len(self.entries)} entries total*")
        lines.append("")
        lines.append("| Date | Doc | Description |")
        lines.append("|------|-----|-------------|")

        entries_to_show = self.entries if verbose else self.key_entries(30)
        for entry in entries_to_show:
            doc = entry.doc_num or ""
            text = entry.text[:100] + "..." if len(entry.text) > 100 else entry.text
            lines.append(f"| {entry.date} | {doc} | {text} |")

        return "\n".join(lines)

    def to_json(self, indent: int = 2) -> str:
        """Export as JSON."""
        data = {
            "meta": asdict(self.meta),
            "entries": [asdict(e) for e in self.entries],
            "parties": [
                {
                    "role": p.role,
                    "name": p.name,
                    "pro_se": p.pro_se,
                    "attorneys": [asdict(a) for a in p.attorneys],
                }
                for p in self.parties
            ],
        }
        if self.download_meta:
            data["download_meta"] = self.download_meta
        return json.dumps(data, indent=indent)

    def to_dict(self) -> dict:
        """Export as dictionary."""
        return {
            "meta": asdict(self.meta),
            "entries": [asdict(e) for e in self.entries],
            "parties": [
                {
                    "role": p.role,
                    "name": p.name,
                    "pro_se": p.pro_se,
                    "attorneys": [asdict(a) for a in p.attorneys],
                }
                for p in self.parties
            ],
            "download_meta": self.download_meta,
        }
