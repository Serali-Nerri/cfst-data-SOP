#!/usr/bin/env python3
"""Export published CFST extraction JSON files to one specimen-per-row CSV."""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Any

from orchestrator_common import read_json


GROUP_KEYS = ("Group_A", "Group_B", "Group_C", "Group_D")

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
    "condition",
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
    "condition",
    "material.steel",
    "material.concrete",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export CFST schema 2.0.0-draft JSON outputs to CSV."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("output/output"),
        help="Directory containing published extraction JSON files.",
    )
    parser.add_argument(
        "--input-json",
        nargs="*",
        type=Path,
        default=None,
        help="Optional explicit JSON files. Defaults to all *.json under --input-dir.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("output/output/cfst_specimens.csv"),
        help="Destination CSV path.",
    )
    parser.add_argument(
        "--encoding",
        choices=("utf-8", "utf-8-sig"),
        default="utf-8-sig",
        help="CSV encoding. utf-8-sig is Excel-friendly for Chinese text.",
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="Write blank cells for missing effective specimen fields instead of failing.",
    )
    return parser.parse_args()


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
        value = nested_get(effective, field)
        if value is None:
            missing.append(field)
    return missing


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
        clean_cell(effective.get("condition")),
    ]
    return row, missing_effective_fields(effective)


def read_rows_from_json(json_path: Path) -> tuple[list[list[str]], list[str], list[str]]:
    payload = read_json(json_path)
    errors: list[str] = []
    warnings: list[str] = []
    rows: list[list[str]] = []

    if not isinstance(payload, dict):
        return rows, [f"{json_path}: top-level JSON value is not an object"], warnings
    if payload.get("schema_version") != "2.0.0-draft":
        return rows, [f"{json_path}: not a CFST schema 2.0.0-draft output"], warnings

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


def discover_json_paths(input_dir: Path, input_json: list[Path] | None) -> list[Path]:
    if input_json is not None and input_json:
        return sorted(input_json, key=lambda path: path.name)
    return sorted(input_dir.glob("*.json"), key=lambda path: path.name)


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
    headers = list(CSV_HEADERS)

    json_paths = discover_json_paths(args.input_dir, args.input_json)
    if not json_paths:
        print(f"[FAIL] No JSON files found under {args.input_dir}")
        return 1

    all_rows: list[list[str]] = []
    all_errors: list[str] = []
    all_warnings: list[str] = []
    for json_path in json_paths:
        try:
            rows, errors, warnings = read_rows_from_json(json_path)
        except (OSError, json.JSONDecodeError) as exc:
            rows, errors, warnings = [], [f"{json_path}: {exc}"], []
        all_rows.extend(rows)
        all_errors.extend(errors)
        all_warnings.extend(warnings)

    for warning in all_warnings:
        print(f"[WARN] {warning}")

    if all_errors and not args.allow_missing:
        for error in all_errors:
            print(f"[FAIL] {error}")
        print("[FAIL] CSV not written. Use --allow-missing to write blanks for missing fields.")
        return 1
    if all_errors:
        for error in all_errors:
            print(f"[WARN] {error}")

    if not all_rows:
        print("[FAIL] No specimen rows were exported.")
        return 1

    atomic_write_csv(args.output_csv, headers, all_rows, args.encoding)
    print(
        f"[OK] Wrote {len(all_rows)} specimen rows from {len(json_paths)} JSON files "
        f"to {args.output_csv}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
