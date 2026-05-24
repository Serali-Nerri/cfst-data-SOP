#!/usr/bin/env python3
"""Lightweight structural validator for cfst-l-reviewer review.md output.

Checks:
  1. Five required level-2 headers appear in order with exact titles.
  2. Every specimen ID in the input CSV appears at least once in section 3.
  3. Section 4 (Summary) yields four integers (reviewed, OK, CHANGE,
     UNDETERMINED) and the three verdict counts sum to `reviewed`, which
     must also match the CSV specimen count.
  4. If `CHANGE > 0`, the recommended CSV exists, shares the original
     header, and has exactly `CHANGE` data rows. If `CHANGE == 0`, the
     recommended CSV must not exist.

No semantic check of L values, verdict reasoning, or methodology text.
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
from pathlib import Path

REQUIRED_HEADERS = [
    "1. Source identification",
    "2. L methodology for this paper",
    "3. Per-specimen review",
    "4. Summary",
    "5. Recommended replacement",
]

VERDICT_KEYS = ("reviewed", "OK", "CHANGE", "UNDETERMINED")


def detect_delimiter(text: str) -> str:
    first_line = text.split("\n", 1)[0]
    counts = {delim: first_line.count(delim) for delim in (",", "\t", ";")}
    best = max(counts, key=counts.__getitem__)
    return best if counts[best] > 0 else ","


def read_csv_specimens(csv_path: Path) -> tuple[list[str], list[str], str]:
    text = csv_path.read_text(encoding="utf-8-sig")
    delimiter = detect_delimiter(text)
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    try:
        header = next(reader)
    except StopIteration as exc:
        raise ValueError(f"input CSV is empty: {csv_path}") from exc
    if "Specimen" not in header:
        raise ValueError(f"input CSV missing 'Specimen' column: {csv_path}")
    spec_idx = header.index("Specimen")
    specimens: list[str] = []
    for row in reader:
        if len(row) > spec_idx and row[spec_idx].strip():
            specimens.append(row[spec_idx].strip())
    if not specimens:
        raise ValueError(f"input CSV has no specimen rows: {csv_path}")
    return header, specimens, delimiter


def find_h2_positions(text: str) -> tuple[list[int], list[str]]:
    positions: list[int] = []
    missing: list[str] = []
    for title in REQUIRED_HEADERS:
        pattern = re.compile(rf"^##\s+{re.escape(title)}\s*$", re.MULTILINE)
        match = pattern.search(text)
        if match:
            positions.append(match.start())
        else:
            missing.append(title)
    return positions, missing


def specimen_appears(text: str, specimen_id: str) -> bool:
    pattern = re.compile(
        rf"(?<![A-Za-z0-9_]){re.escape(specimen_id)}(?![A-Za-z0-9_])"
    )
    return bool(pattern.search(text))


def parse_summary_numbers(section_text: str) -> dict[str, int]:
    found: dict[str, int] = {}
    for line in section_text.split("\n"):
        for canonical in VERDICT_KEYS:
            if canonical in found:
                continue
            key_match = re.search(rf"\b{re.escape(canonical)}\b", line, re.IGNORECASE)
            if not key_match:
                continue
            tail = line[key_match.end():]
            num_match = re.search(r"\d+", tail)
            if num_match:
                found[canonical] = int(num_match.group())
    return found


def read_recommended_rows(csv_path: Path, delimiter: str) -> tuple[list[str], list[list[str]]]:
    text = csv_path.read_text(encoding="utf-8-sig")
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    try:
        header = next(reader)
    except StopIteration:
        return [], []
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    return header, rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate one cfst-l-reviewer review.md output.")
    parser.add_argument("--review-md", type=Path, required=True, help="Path to review.md to validate.")
    parser.add_argument("--csv", type=Path, required=True, help="Original extracted CSV (tab-delimited).")
    parser.add_argument(
        "--recommended-csv",
        type=Path,
        required=True,
        help="Expected path for the companion recommended CSV (need not exist if CHANGE==0).",
    )
    args = parser.parse_args()

    errors: list[str] = []

    if not args.review_md.is_file():
        print(f"[FAIL] review.md not found: {args.review_md}", file=sys.stderr)
        return 1
    if not args.csv.is_file():
        print(f"[FAIL] input CSV not found: {args.csv}", file=sys.stderr)
        return 1

    try:
        csv_header, specimens, csv_delimiter = read_csv_specimens(args.csv)
    except ValueError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1

    text = args.review_md.read_text(encoding="utf-8")
    positions, missing_headers = find_h2_positions(text)
    for title in missing_headers:
        errors.append(f"missing required h2 header: '## {title}'")

    if len(positions) == len(REQUIRED_HEADERS) and positions != sorted(positions):
        errors.append("required h2 headers are out of order")

    if len(positions) >= 4:
        section3 = text[positions[2]:positions[3]]
        missing_specs = [sid for sid in specimens if not specimen_appears(section3, sid)]
        if missing_specs:
            shown = ", ".join(missing_specs[:10])
            suffix = " (truncated)" if len(missing_specs) > 10 else ""
            errors.append(f"specimens missing from per-specimen review section: {shown}{suffix}")

    counts: dict[str, int] = {}
    if len(positions) >= 5:
        section4 = text[positions[3]:positions[4]]
        counts = parse_summary_numbers(section4)
        missing_keys = [k for k in VERDICT_KEYS if k not in counts]
        if missing_keys:
            errors.append(f"summary section missing key(s): {', '.join(missing_keys)}")
        else:
            verdict_sum = counts["OK"] + counts["CHANGE"] + counts["UNDETERMINED"]
            if verdict_sum != counts["reviewed"]:
                errors.append(
                    f"summary counts inconsistent: reviewed={counts['reviewed']} "
                    f"but OK+CHANGE+UNDETERMINED={verdict_sum}"
                )
            if counts["reviewed"] != len(specimens):
                errors.append(
                    f"summary reviewed={counts['reviewed']} does not match CSV specimen count={len(specimens)}"
                )

    change_count = counts.get("CHANGE")
    if change_count is not None:
        if change_count > 0:
            if not args.recommended_csv.is_file():
                errors.append(
                    f"summary reports CHANGE={change_count} but recommended CSV is missing: {args.recommended_csv}"
                )
            else:
                rec_header, rec_rows = read_recommended_rows(args.recommended_csv, csv_delimiter)
                if rec_header != csv_header:
                    errors.append(
                        "recommended CSV header does not match original CSV header "
                        "(check delimiter and encoding match the input CSV)"
                    )
                if len(rec_rows) != change_count:
                    errors.append(
                        f"recommended CSV row count={len(rec_rows)} does not match summary CHANGE={change_count}"
                    )
        else:
            if args.recommended_csv.is_file():
                errors.append(
                    f"summary reports CHANGE=0 but recommended CSV exists: {args.recommended_csv}"
                )

    if errors:
        for err in errors:
            print(f"[FAIL] {err}", file=sys.stderr)
        return 1

    print(f"[OK] review.md valid: {args.review_md}")
    print(
        f"  specimens={len(specimens)} "
        f"OK={counts.get('OK', 0)} CHANGE={counts.get('CHANGE', 0)} UNDETERMINED={counts.get('UNDETERMINED', 0)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
