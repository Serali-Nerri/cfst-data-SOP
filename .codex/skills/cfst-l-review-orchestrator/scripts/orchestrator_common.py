"""Shared helpers for CFST L-review orchestration scripts."""

from __future__ import annotations

import csv
import io
import json
import os
import re
from pathlib import Path
from typing import Any


PAPER_ID_PATTERN = re.compile(r"^\[?([A-Za-z]+\d*-\d+)\]?")
HTML_TABLE_RE = re.compile(r"<table\b", re.IGNORECASE)

PACKAGE_READY_STATUS = "prepared"
READY_FOR_PUBLICATION_STATUS = "ready_for_publication"
PUBLISHED_STATUS = "published"
PUBLISH_FAILED_STATUS = "publish_failed"
ALLOWED_BATCH_STATUSES = {
    PACKAGE_READY_STATUS,
    "unprepared_package",
    "ambiguous_unprepared_package",
    "duplicate_prepared_package",
    "missing_pending_package",
    "invalid_package",
    "running",
    READY_FOR_PUBLICATION_STATUS,
    "failed",
    PUBLISHED_STATUS,
    PUBLISH_FAILED_STATUS,
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp_path, path)


def parse_paper_id(name: str) -> str | None:
    match = PAPER_ID_PATTERN.match(name)
    if not match:
        return None
    return match.group(1)


def normalize_paper_id(raw: str) -> str:
    value = raw.strip()
    value = value[1:-1] if value.startswith("[") and value.endswith("]") else value
    match = PAPER_ID_PATTERN.match(value)
    if not match:
        raise ValueError(f"invalid paper id: {raw}")
    return match.group(1)


def sort_key(paper_id: str) -> tuple[int, ...]:
    numbers = tuple(int(value) for value in re.findall(r"\d+", paper_id))
    return numbers or (10**9,)


def is_under(base: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def unique_origin_pdf(package_dir: Path) -> tuple[Path | None, list[str]]:
    origin_pdfs = sorted(package_dir.glob("*_origin.pdf"))
    if len(origin_pdfs) == 1:
        return origin_pdfs[0], []
    if not origin_pdfs:
        return None, ["missing_origin_pdf"]
    return None, [f"multiple_origin_pdfs:{len(origin_pdfs)}"]


def inspect_l_review_package(package_dir: Path, paper_id: str) -> dict[str, Any]:
    """Verify the package contains every member required for L review."""
    issues: list[str] = []
    full_md = package_dir / "full.md"
    images_dir = package_dir / "images"
    content_list = package_dir / "content_list_v2.json"
    extracted_csv = package_dir / f"{paper_id}.csv"
    owned_pdf, pdf_issues = unique_origin_pdf(package_dir)

    if not package_dir.is_dir():
        issues.append("missing_package_dir")
    if not full_md.is_file():
        issues.append("missing_full_md")
    if not images_dir.is_dir():
        issues.append("missing_images_dir")
    if not content_list.is_file():
        issues.append("missing_content_list_v2_json")
    if not extracted_csv.is_file():
        issues.append("missing_extracted_csv")
    issues.extend(pdf_issues)
    if full_md.is_file() and HTML_TABLE_RE.search(full_md.read_text(encoding="utf-8")):
        issues.append("unreplaced_html_tables_in_full_md")
    if extracted_csv.is_file():
        try:
            text = extracted_csv.read_text(encoding="utf-8-sig")
            first_line = text.split("\n", 1)[0]
            counts = {delim: first_line.count(delim) for delim in (",", "\t", ";")}
            best = max(counts, key=counts.__getitem__)
            delimiter = best if counts[best] > 0 else ","
            reader = csv.reader(io.StringIO(text), delimiter=delimiter)
            header = next(reader, None)
            first_row = next(reader, None)
            if not header or "Specimen" not in header:
                issues.append("extracted_csv_missing_specimen_column")
            if first_row is None:
                issues.append("extracted_csv_has_no_data_rows")
        except (OSError, UnicodeDecodeError) as exc:
            issues.append(f"extracted_csv_unreadable:{exc.__class__.__name__}")

    return {
        "ready": not issues,
        "issues": issues,
        "rawdata_dir": str(package_dir),
        "full_md_path": str(full_md) if full_md.exists() else None,
        "images_dir": str(images_dir) if images_dir.exists() else None,
        "content_list_path": str(content_list) if content_list.exists() else None,
        "owned_pdf_path": str(owned_pdf) if owned_pdf else None,
        "extracted_csv_path": str(extracted_csv) if extracted_csv.exists() else None,
    }


def validate_status(status: str) -> None:
    if status not in ALLOWED_BATCH_STATUSES:
        allowed = ", ".join(sorted(ALLOWED_BATCH_STATUSES))
        raise ValueError(f"unknown batch status: {status!r}; allowed: {allowed}")
