#!/usr/bin/env python3
"""Remove one generated L-review worker workspace after the parent no longer needs it."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from orchestrator_common import is_under, read_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Remove a generated CFST L-review worker workspace.")
    parser.add_argument("--job-spec", type=Path, required=True, help="Path to l_review_worker_job_spec.json.")
    parser.add_argument(
        "--worker-spaces-root",
        type=Path,
        default=Path("tmp/cfst-l-review-worker-spaces"),
        help="Allowed generated workspace root.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the workspace path without removing it.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        spec = read_json(args.job_spec)
        workspace_value = spec.get("workspace", {}).get("path")
        if not isinstance(workspace_value, str) or not workspace_value:
            raise ValueError("l_review_worker_job_spec.json missing workspace.path")

        workspace_path = Path(workspace_value).resolve()
        worker_spaces_root = args.worker_spaces_root.resolve()
        if not is_under(worker_spaces_root, workspace_path):
            raise ValueError(f"workspace is outside worker-spaces root: {workspace_path}")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[FAIL] {exc}")
        return 1

    if not workspace_path.exists():
        print(f"[OK] Workspace already absent: {workspace_path}")
        return 0
    if not workspace_path.is_dir():
        print(f"[FAIL] Workspace path is not a directory: {workspace_path}")
        return 1
    if args.dry_run:
        print(f"[DRY-RUN] Would remove workspace: {workspace_path}")
        return 0

    shutil.rmtree(workspace_path)
    print(f"[OK] Removed workspace: {workspace_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
