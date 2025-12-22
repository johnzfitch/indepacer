#!/usr/bin/env python3
"""Extract word contexts around search terms from markdown files.

Usage:
    python extract_context.py <input.md> <search_term> [--words 200] [-o output.md]
"""

import argparse
import re
from pathlib import Path


def extract_contexts(text: str, term: str, window: int = 200) -> str:
    """Extract contexts around all occurrences of a term, merging overlaps.

    Args:
        text: Full text content
        term: Search term (case-insensitive)
        window: Number of words on each side

    Returns:
        Merged context passages in document order
    """
    # Tokenize into words while preserving positions
    words = text.split()
    total_words = len(words)

    if total_words == 0:
        return ""

    # Find all word indices containing the search term
    pattern = re.compile(re.escape(term), re.IGNORECASE)
    match_indices = []

    for i, word in enumerate(words):
        if pattern.search(word):
            match_indices.append(i)

    if not match_indices:
        return f"No matches found for '{term}'"

    # Build intervals [start, end] for each match
    intervals = []
    for idx in match_indices:
        start = max(0, idx - window)
        end = min(total_words - 1, idx + window)
        intervals.append([start, end])

    # Merge overlapping intervals
    merged = []
    for interval in sorted(intervals):
        if merged and interval[0] <= merged[-1][1] + 1:
            # Overlapping or adjacent - extend
            merged[-1][1] = max(merged[-1][1], interval[1])
        else:
            merged.append(interval)

    # Extract and join passages
    passages = []
    for start, end in merged:
        passage_words = words[start : end + 1]
        passages.append(" ".join(passage_words))

    # Join with separator
    result = "\n\n---\n\n".join(passages)

    # Add header
    header = f"# Extracted contexts for '{term}'\n\n"
    header += f"Found {len(match_indices)} occurrences in {len(merged)} passage(s)\n"
    header += f"Window: {window} words on each side\n\n---\n\n"

    return header + result


def main():
    parser = argparse.ArgumentParser(
        description="Extract word contexts around search terms from markdown"
    )
    parser.add_argument("input", type=Path, help="Input markdown file")
    parser.add_argument("term", help="Search term")
    parser.add_argument(
        "-w", "--words", type=int, default=200, help="Words on each side (default: 200)"
    )
    parser.add_argument(
        "-o", "--output", type=Path, default=None, help="Output file (default: stdout)"
    )

    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: {args.input} not found")
        return 1

    text = args.input.read_text(encoding="utf-8", errors="ignore")
    result = extract_contexts(text, args.term, args.words)

    if args.output:
        args.output.write_text(result)
        print(f"Wrote to {args.output}")
    else:
        print(result)

    return 0


if __name__ == "__main__":
    exit(main())
