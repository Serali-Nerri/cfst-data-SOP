#!/usr/bin/env python3
"""Export CFST JSON outputs to one CSV per Pending paper folder."""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Any


GROUP_KEYS = ("Group_A", "Group_B", "Group_C", "Group_D")
SCHEMA_VERSION = "3.0"

CSV_HEADERS = [
    "Ref.info.",
    "fco (MPa)",
    "fc_type",
    "Specimen",
    "fy (MPa)",
    "fcy150(Mpa)",
    "R (%)",
    "b (mm)",
    "h (mm)",
    "t (mm)",
    "r0 (mm)",
    "L (mm)",
    "e1 (mm)",
    "e2 (mm)",
    "Nexp (kN)",
    "Group",
    "Material.steel",
    "Material.concrete",
    "loading mode",
    "condition tags",
    "condition notes",
]

REQUIRED_EFFECTIVE_FIELDS = [
    "fco",
    "fc_type",
    "fy",
    "r_ratio",
    "b",
    "h",
    "t",
    "r0",
    "L",
    "e1",
    "e2",
    "n_exp",
    "loading_mode",
    "condition.tags",
    "condition.notes",
    "material.steel",
    "material.concrete",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export output JSON files to Pending/[paper_id]/paper_id.csv."
    )
    parser.add_argument("--pending-root", type=Path, required=True)
    parser.add_argument(
        "--output-root",
        type=Path,
        required=True,
        help="Directory containing JSON files, or an output root containing output/*.json.",
    )
    parser.add_argument(
        "--paper-id",
        action="append",
        default=None,
        help="Optional paper ID to export. Repeat for multiple IDs.",
    )
    parser.add_argument(
        "--encoding",
        choices=("utf-8", "utf-8-sig"),
        default="utf-8-sig",
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Write blank cells for missing effective fields instead of failing.",
    )
    return parser.parse_args()


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def clean_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return " ".join(value.split())
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def deep_merge_data(*objects: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in objects:
        if not isinstance(item, dict):
            continue
        for key, value in item.items():
            if key == "material" and isinstance(value, dict):
                current = result.get("material")
                merged = dict(current) if isinstance(current, dict) else {}
                merged.update(value)
                result["material"] = merged
            else:
                result[key] = value
    return result


def nested_get(data: dict[str, Any], field: str) -> Any:
    if "." not in field:
        return data.get(field)
    outer, inner = field.split(".", 1)
    value = data.get(outer)
    if not isinstance(value, dict):
        return None
    return value.get(inner)


def ref_info_cell(paper: dict[str, Any]) -> str:
    ref_info = paper.get("ref_info")
    if not isinstance(ref_info, dict):
        return ""
    authors = ref_info.get("authors")
    first_author = authors[0] if isinstance(authors, list) and authors else ""
    parts = [
        first_author,
        ref_info.get("title"),
        ref_info.get("journal"),
        ref_info.get("year"),
    ]
    return ",".join(clean_cell(part) for part in parts)


def missing_effective_fields(effective: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for field in REQUIRED_EFFECTIVE_FIELDS:
        if field == "condition.notes":
            condition = effective.get("condition")
            if not isinstance(condition, dict) or "notes" not in condition:
                missing.append(field)
            continue
        if nested_get(effective, field) is None:
            missing.append(field)
    return missing


def condition_tags_cell(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    tags = value.get("tags")
    if not isinstance(tags, list):
        return ""
    return ";".join(clean_cell(tag) for tag in tags)


def build_specimen_row(
    *,
    paper: dict[str, Any],
    group_key: str,
    group: dict[str, Any],
    specimen: dict[str, Any],
) -> tuple[list[str], list[str]]:
    defaults = paper.get("defaults")
    shared = group.get("shared")
    defaults = defaults if isinstance(defaults, dict) else {}
    shared = shared if isinstance(shared, dict) else {}
    effective = deep_merge_data(defaults, shared, specimen)

    row = [
        ref_info_cell(paper),
        clean_cell(effective.get("fco")),
        clean_cell(effective.get("fc_type")),
        clean_cell(specimen.get("specimen_label")),
        clean_cell(effective.get("fy")),
        "",
        clean_cell(effective.get("r_ratio")),
        clean_cell(effective.get("b")),
        clean_cell(effective.get("h")),
        clean_cell(effective.get("t")),
        clean_cell(effective.get("r0")),
        clean_cell(effective.get("L")),
        clean_cell(effective.get("e1")),
        clean_cell(effective.get("e2")),
        clean_cell(effective.get("n_exp")),
        group_key.removeprefix("Group_"),
        clean_cell(nested_get(effective, "material.steel")),
        clean_cell(nested_get(effective, "material.concrete")),
        clean_cell(effective.get("loading_mode")),
        condition_tags_cell(effective.get("condition")),
        clean_cell(nested_get(effective, "condition.notes")),
    ]
    return row, missing_effective_fields(effective)


def read_rows_from_json(json_path: Path) -> tuple[list[list[str]], list[str], list[str]]:
    payload = read_json(json_path)
    errors: list[str] = []
    warnings: list[str] = []
    rows: list[list[str]] = []

    if not isinstance(payload, dict):
        return rows, [f"{json_path}: top-level JSON value is not an object"], warnings
    if payload.get("schema_version") != SCHEMA_VERSION:
        return rows, [f"{json_path}: not a CFST schema {SCHEMA_VERSION} output"], warnings

    paper = payload.get("paper")
    if not isinstance(paper, dict):
        return rows, [f"{json_path}: missing paper object"], warnings

    for group_key in GROUP_KEYS:
        group = payload.get(group_key)
        if not isinstance(group, dict):
            errors.append(f"{json_path}: missing {group_key} object")
            continue
        specimens = group.get("specimens")
        if not isinstance(specimens, list):
            errors.append(f"{json_path}: {group_key}.specimens is not a list")
            continue
        for index, specimen in enumerate(specimens, start=1):
            if not isinstance(specimen, dict):
                errors.append(f"{json_path}: {group_key}.specimens[{index}] is not an object")
                continue
            row, missing = build_specimen_row(
                paper=paper,
                group_key=group_key,
                group=group,
                specimen=specimen,
            )
            if missing:
                label = clean_cell(specimen.get("specimen_label")) or f"row {index}"
                errors.append(
                    f"{json_path}: {group_key} {label} missing effective fields: "
                    + ", ".join(missing)
                )
            rows.append(row)

    if not rows:
        validity = paper.get("validity")
        reason = None
        if isinstance(validity, dict):
            reason = validity.get("reason")
        warnings.append(f"{json_path}: no specimen rows exported; reason={clean_cell(reason) or 'none'}")
    return rows, errors, warnings


def discover_json_dir(output_root: Path) -> Path:
    nested = output_root / "output"
    if nested.is_dir() and any(nested.glob("*.json")):
        return nested
    return output_root


def discover_json_paths(output_root: Path, paper_ids: list[str] | None) -> list[Path]:
    json_dir = discover_json_dir(output_root)
    if paper_ids:
        return [json_dir / f"{paper_id}.json" for paper_id in paper_ids]
    return sorted(json_dir.glob("*.json"), key=lambda path: path.name)


def pending_dir_for(pending_root: Path, paper_id: str) -> Path | None:
    bracketed = pending_root / f"[{paper_id}]"
    if bracketed.is_dir():
        return bracketed
    plain = pending_root / paper_id
    if plain.is_dir():
        return plain
    return None


def atomic_write_csv(path: Path, headers: list[str], rows: list[list[str]], encoding: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        with tmp_path.open("w", encoding=encoding, newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(headers)
            writer.writerows(rows)
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def main() -> int:
    args = parse_args()
    if not args.pending_root.is_dir():
        print(f"[FAIL] Pending root does not exist: {args.pending_root}")
        return 1
    if not args.output_root.is_dir():
        print(f"[FAIL] Output root does not exist: {args.output_root}")
        return 1

    json_paths = discover_json_paths(args.output_root, args.paper_id)
    if not json_paths:
        print(f"[FAIL] No JSON files found under {discover_json_dir(args.output_root)}")
        return 1

    total_rows = 0
    failures: list[str] = []
    exported = 0
    for json_path in json_paths:
        paper_id = json_path.stem
        if not json_path.is_file():
            failures.append(f"{paper_id}: JSON file not found: {json_path}")
            continue
        paper_dir = pending_dir_for(args.pending_root, paper_id)
        if paper_dir is None:
            failures.append(f"{paper_id}: Pending directory not found under {args.pending_root}")
            continue
        output_csv = paper_dir / f"{paper_id}.csv"

        try:
            rows, errors, warnings = read_rows_from_json(json_path)
        except (OSError, json.JSONDecodeError) as exc:
            failures.append(f"{paper_id}: {exc}")
            continue
        for warning in warnings:
            print(f"[WARN] {warning}")
        if errors and not args.allow_missing:
            failures.extend(errors)
            continue
        for error in errors:
            print(f"[WARN] {error}")
        if not rows:
            failures.append(f"{paper_id}: no specimen rows exported")
            continue

        atomic_write_csv(output_csv, CSV_HEADERS, rows, args.encoding)
        exported += 1
        total_rows += len(rows)
        print(f"[OK] {paper_id}: wrote {len(rows)} rows -> {output_csv}")

    if failures:
        for failure in failures:
            print(f"[FAIL] {failure}")
        print(f"[FAIL] Exported {exported}/{len(json_paths)} CSV files before failures.")
        return 1

    print(f"[OK] Exported {exported} CSV files with {total_rows} specimen rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
