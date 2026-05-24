#!/usr/bin/env python3
"""Aggregate per-paper review.md summaries into a cross-paper summary."""

from __future__ import annotations

import argparse
import csv
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERDICT_KEYS = ("reviewed", "OK", "CHANGE", "UNDETERMINED")
SUMMARY_HEADER_PATTERN = re.compile(r"^##\s+4\.\s+Summary\s*$", re.MULTILINE)
NEXT_HEADER_PATTERN = re.compile(r"^##\s+", re.MULTILINE)


def parse_summary_block(text: str) -> dict[str, int] | None:
    header_match = SUMMARY_HEADER_PATTERN.search(text)
    if not header_match:
        return None
    start = header_match.end()
    next_match = NEXT_HEADER_PATTERN.search(text, start)
    end = next_match.start() if next_match else len(text)
    section = text[start:end]
    found: dict[str, int] = {}
    for line in section.split("\n"):
        for key in VERDICT_KEYS:
            if key in found:
                continue
            key_match = re.search(rf"\b{re.escape(key)}\b", line, re.IGNORECASE)
            if not key_match:
                continue
            tail = line[key_match.end():]
            num_match = re.search(r"\d+", tail)
            if num_match:
                found[key] = int(num_match.group())
    if not all(key in found for key in VERDICT_KEYS):
        return None
    return found


def discover_reviews(output_dir: Path) -> list[tuple[str, Path]]:
    items: list[tuple[str, Path]] = []
    for paper_dir in sorted(output_dir.iterdir()):
        if not paper_dir.is_dir() or paper_dir.name.startswith("_"):
            continue
        review_path = paper_dir / "review.md"
        if review_path.is_file():
            items.append((paper_dir.name, review_path))
    return items


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate per-paper L-review summaries.")
    parser.add_argument("--output-dir", type=Path, required=True, help="L-review final output directory.")
    parser.add_argument("--summary-md", type=Path, required=True, help="Output Markdown summary path.")
    parser.add_argument("--summary-csv", type=Path, required=True, help="Output CSV summary path.")
    args = parser.parse_args()

    if not args.output_dir.is_dir():
        print(f"[FAIL] output dir not found: {args.output_dir}")
        return 1

    rows: list[dict[str, Any]] = []
    skipped: list[tuple[str, str]] = []
    for paper_id, review_path in discover_reviews(args.output_dir):
        try:
            text = review_path.read_text(encoding="utf-8")
        except OSError as exc:
            skipped.append((paper_id, f"unreadable:{exc}"))
            continue
        counts = parse_summary_block(text)
        if counts is None:
            skipped.append((paper_id, "summary_unparseable"))
            continue
        recommended_csv = review_path.parent / f"{paper_id}_recommended.csv"
        rows.append(
            {
                "paper_id": paper_id,
                "reviewed": counts["reviewed"],
                "OK": counts["OK"],
                "CHANGE": counts["CHANGE"],
                "UNDETERMINED": counts["UNDETERMINED"],
                "recommended_csv_present": recommended_csv.is_file(),
                "review_path": str(review_path),
            }
        )

    rows.sort(
        key=lambda row: (
            -int(row["CHANGE"]),
            -int(row["UNDETERMINED"]),
            row["paper_id"],
        )
    )

    args.summary_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.summary_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["paper_id", "reviewed", "OK", "CHANGE", "UNDETERMINED", "recommended_csv_present"])
        for row in rows:
            writer.writerow(
                [
                    row["paper_id"],
                    row["reviewed"],
                    row["OK"],
                    row["CHANGE"],
                    row["UNDETERMINED"],
                    "true" if row["recommended_csv_present"] else "false",
                ]
            )

    totals = {
        "papers": len(rows),
        "reviewed": sum(int(r["reviewed"]) for r in rows),
        "OK": sum(int(r["OK"]) for r in rows),
        "CHANGE": sum(int(r["CHANGE"]) for r in rows),
        "UNDETERMINED": sum(int(r["UNDETERMINED"]) for r in rows),
        "papers_with_change": sum(1 for r in rows if int(r["CHANGE"]) > 0),
        "papers_with_undetermined": sum(1 for r in rows if int(r["UNDETERMINED"]) > 0),
    }

    args.summary_md.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# CFST L Review Summary")
    lines.append("")
    lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"Output dir: `{args.output_dir}`")
    lines.append("")
    lines.append("## Totals")
    lines.append("")
    lines.append(f"- papers: {totals['papers']}")
    lines.append(f"- specimens reviewed: {totals['reviewed']}")
    lines.append(f"- OK: {totals['OK']}")
    lines.append(f"- CHANGE: {totals['CHANGE']}")
    lines.append(f"- UNDETERMINED: {totals['UNDETERMINED']}")
    lines.append(f"- papers with any CHANGE: {totals['papers_with_change']}")
    lines.append(f"- papers with any UNDETERMINED: {totals['papers_with_undetermined']}")
    lines.append("")
    lines.append("## Per-paper (sorted by CHANGE then UNDETERMINED)")
    lines.append("")
    lines.append("| paper_id | reviewed | OK | CHANGE | UNDETERMINED | recommended.csv |")
    lines.append("|---|---|---|---|---|---|")
    for row in rows:
        lines.append(
            "| {paper_id} | {reviewed} | {ok} | {change} | {und} | {rec} |".format(
                paper_id=row["paper_id"],
                reviewed=row["reviewed"],
                ok=row["OK"],
                change=row["CHANGE"],
                und=row["UNDETERMINED"],
                rec="yes" if row["recommended_csv_present"] else "no",
            )
        )
    if skipped:
        lines.append("")
        lines.append("## Skipped (could not parse Summary section)")
        lines.append("")
        for paper_id, reason in skipped:
            lines.append(f"- {paper_id}: {reason}")
    lines.append("")
    args.summary_md.write_text("\n".join(lines), encoding="utf-8")

    print(f"[OK] Aggregated {len(rows)} review(s); skipped {len(skipped)}.")
    print(f"[OK] Summary Markdown: {args.summary_md}")
    print(f"[OK] Summary CSV: {args.summary_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
