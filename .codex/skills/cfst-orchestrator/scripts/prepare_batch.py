#!/usr/bin/env python3
"""Prepare a CFST batch workspace from Pending paper packages."""

from __future__ import annotations

import argparse
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from orchestrator_common import (
    PACKAGE_READY_STATUS,
    inspect_package,
    normalize_paper_id,
    parse_paper_id,
    read_json,
    sort_key,
    validate_status,
    write_json,
)


SHORT_PACKAGE_PATTERN = re.compile(r"^\[([A-Za-z]+\d+-\d+)\]$")


def is_short_package_name(name: str, paper_id: str) -> bool:
    match = SHORT_PACKAGE_PATTERN.match(name)
    return bool(match and match.group(1) == paper_id)


def discover_pending_dirs(pending_root: Path) -> dict[str, list[Path]]:
    grouped: dict[str, list[Path]] = {}
    for item in sorted(pending_root.iterdir()):
        if not item.is_dir():
            continue
        paper_id = parse_paper_id(item.name)
        if not paper_id:
            continue
        grouped.setdefault(paper_id, []).append(item)
    return grouped


def select_package(
    pending_root: Path,
    paper_id: str,
    grouped_dirs: dict[str, list[Path]],
) -> tuple[Path | None, str, list[str]]:
    candidates = grouped_dirs.get(paper_id, [])
    if not candidates:
        return None, "missing_pending_package", ["package_not_found"]

    exact = [path for path in candidates if is_short_package_name(path.name, paper_id)]
    long_dirs = [path for path in candidates if path not in exact]

    if len(exact) > 1:
        return exact[0], "duplicate_prepared_package", [
            f"multiple_short_packages:{len(exact)}",
            *[f"candidate:{path.relative_to(pending_root).as_posix()}" for path in exact],
        ]
    if not exact:
        if len(long_dirs) > 1:
            return long_dirs[0], "ambiguous_unprepared_package", [
                f"multiple_unprepared_packages:{len(long_dirs)}",
                *[f"candidate:{path.relative_to(pending_root).as_posix()}" for path in long_dirs],
            ]
        return long_dirs[0], "unprepared_package", [
            "package_not_shortened",
            f"run_prepare_rawdata_package:{long_dirs[0]}",
        ]

    warnings = [
        f"unprepared_duplicate_exists:{path.relative_to(pending_root).as_posix()}"
        for path in long_dirs
    ]
    return exact[0], "candidate", warnings


def build_entries(
    *,
    pending_root: Path,
    output_root: Path,
    paper_ids: list[str],
    grouped_dirs: dict[str, list[Path]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    batch_entries: list[dict[str, Any]] = []
    worker_jobs: list[dict[str, Any]] = []
    state_entries: list[dict[str, Any]] = []

    for paper_id in paper_ids:
        package_dir, selection_status, selection_issues = select_package(
            pending_root, paper_id, grouped_dirs
        )
        package_info: dict[str, Any] = {}
        status = selection_status
        issues = list(selection_issues)

        if package_dir and selection_status == "candidate":
            package_info = inspect_package(package_dir)
            status = PACKAGE_READY_STATUS if package_info["ready"] else "invalid_package"
            issues.extend(package_info["issues"])
        validate_status(status)

        tmp_json = output_root / "tmp" / paper_id / f"{paper_id}.json"
        final_json = output_root / "output" / f"{paper_id}.json"
        workspace_json = f"output/tmp/{paper_id}/{paper_id}.json"

        batch_entry = {
            "paper_id": paper_id,
            "citation_tag": f"[{paper_id}]",
            "expected_specimen_count": None,
            "package_dir": str(package_dir) if package_dir else None,
            "worker_output_json_path": str(tmp_json),
            "worker_output_workspace_path": workspace_json,
            "final_output_json_path": str(final_json),
            "status": status,
            "issues": issues,
            "package": package_info,
        }
        worker_job = {
            "paper_id": paper_id,
            "package_dir": package_info.get("rawdata_dir") or (str(package_dir) if package_dir else None),
            "owned_pdf_path": package_info.get("owned_pdf_path"),
            "full_md_path": package_info.get("full_md_path"),
            "images_dir": package_info.get("images_dir"),
            "content_list_path": package_info.get("content_list_path"),
            "worker_output_json_path": str(tmp_json),
            "worker_output_workspace_path": workspace_json,
            "final_output_json_path": str(final_json),
            "expected_specimen_count": None,
            "status": status,
            "issues": issues,
        }
        state_entry = {
            "paper_id": paper_id,
            "status": status,
            "retry_count": 0,
            "validated": False,
            "published": False,
            "last_error": None,
        }
        batch_entries.append(batch_entry)
        worker_jobs.append(worker_job)
        state_entries.append(state_entry)

    return batch_entries, worker_jobs, state_entries


def merge_state_entries(
    batch_state_path: Path,
    new_entries: list[dict[str, Any]],
    reset_state: bool,
) -> list[dict[str, Any]]:
    if reset_state or not batch_state_path.is_file():
        return new_entries

    previous_payload = read_json(batch_state_path)
    previous_by_id = {
        item.get("paper_id"): item
        for item in previous_payload.get("papers", [])
        if isinstance(item, dict)
    }
    merged: list[dict[str, Any]] = []
    for entry in new_entries:
        previous = previous_by_id.get(entry["paper_id"])
        if previous and entry["status"] == PACKAGE_READY_STATUS:
            merged_entry = dict(entry)
            for key in ("status", "retry_count", "validated", "published", "last_error"):
                if key in previous:
                    if key == "status":
                        validate_status(str(previous[key]))
                    merged_entry[key] = previous[key]
            merged.append(merged_entry)
        else:
            merged.append(entry)
    return merged


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare CFST batch workspace from Pending packages.")
    parser.add_argument(
        "--pending-root",
        type=Path,
        default=Path("Pending"),
        help="Root containing rawdata packages. Long package names are unprepared; [paper_id] directories are prepared candidates.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("output"),
        help="Batch output root (default: output/).",
    )
    parser.add_argument(
        "--paper-ids",
        nargs="*",
        default=None,
        help="Optional explicit list like A1-1 A1-2.",
    )
    parser.add_argument(
        "--reset-state",
        action="store_true",
        help="Overwrite existing batch_state.json instead of preserving operational state by paper_id.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Do not write files.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pending_root = args.pending_root.resolve()
    if not pending_root.exists():
        print(f"[FAIL] Pending root not found: {pending_root}")
        return 1
    if not pending_root.is_dir():
        print(f"[FAIL] Pending root is not a directory: {pending_root}")
        return 1

    try:
        explicit_ids = [normalize_paper_id(value) for value in args.paper_ids] if args.paper_ids else None
    except ValueError as exc:
        print(f"[FAIL] {exc}")
        return 1

    output_root = args.output_root.resolve()
    manifests_dir = output_root / "manifests"
    logs_dir = output_root / "logs"
    tmp_dir = output_root / "tmp"
    final_output_dir = output_root / "output"

    grouped_dirs = discover_pending_dirs(pending_root)
    selected_ids = explicit_ids or sorted(grouped_dirs.keys(), key=sort_key)

    batch_entries, worker_jobs, state_entries = build_entries(
        pending_root=pending_root,
        output_root=output_root,
        paper_ids=selected_ids,
        grouped_dirs=grouped_dirs,
    )

    state_entries = merge_state_entries(manifests_dir / "batch_state.json", state_entries, args.reset_state)

    batch_manifest = {
        "schema_version": "cfst-batch-manifest-v4",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_layout": "pending-package",
        "pending_root": str(pending_root),
        "output_root": str(output_root),
        "paper_count": len(batch_entries),
        "papers": batch_entries,
    }
    batch_state = {
        "schema_version": "cfst-batch-state-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "paper_count": len(state_entries),
        "papers": state_entries,
    }

    if not args.dry_run:
        for directory in (manifests_dir, logs_dir, tmp_dir, final_output_dir):
            directory.mkdir(parents=True, exist_ok=True)
        write_json(manifests_dir / "batch_manifest.json", batch_manifest)
        write_json(manifests_dir / "worker_jobs.json", worker_jobs)
        write_json(manifests_dir / "batch_state.json", batch_state)

    counts: dict[str, int] = {}
    for item in batch_entries:
        counts[item["status"]] = counts.get(item["status"], 0) + 1

    print(f"[OK] Indexed {len(batch_entries)} papers from Pending root.")
    for status in sorted(counts):
        print(f"[INFO] {status}={counts[status]}")
    print(f"[INFO] Output root: {output_root}")
    if not args.dry_run:
        print(f"[OK] Batch manifest: {manifests_dir / 'batch_manifest.json'}")
        print(f"[OK] Worker jobs: {manifests_dir / 'worker_jobs.json'}")
        print(f"[OK] Batch state: {manifests_dir / 'batch_state.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
