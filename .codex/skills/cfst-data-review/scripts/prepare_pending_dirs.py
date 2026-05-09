#!/usr/bin/env python3
"""Prepare numbered Pending paper directories for CFST CSV review."""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path


PAPER_DIR_RE = re.compile(r"^\[[A-Za-z][0-9]+-[0-9]+\]$")
KNOWN_ARTIFACTS = {"images", "content_list_v2.json", "full.md"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Clean numbered Pending folders and create per-paper tmp/ folders."
    )
    parser.add_argument("--pending-root", type=Path, required=True)
    parser.add_argument(
        "--delete-all-non-pdf",
        action="store_true",
        help="Delete every first-level non-PDF entry except tmp/. Without this, only known extraction artifacts are removed.",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def is_pdf(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() == ".pdf"


def remove_path(path: Path, dry_run: bool) -> None:
    if dry_run:
        print(f"[DRY-RUN] remove {path}")
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def should_remove(path: Path, delete_all_non_pdf: bool) -> bool:
    if path.name == "tmp":
        return False
    if is_pdf(path):
        return False
    if delete_all_non_pdf:
        return True
    return path.name in KNOWN_ARTIFACTS


def main() -> int:
    args = parse_args()
    pending_root = args.pending_root
    if not pending_root.is_dir():
        print(f"[FAIL] Pending root does not exist: {pending_root}")
        return 1

    paper_dirs = sorted(
        path for path in pending_root.iterdir() if path.is_dir() and PAPER_DIR_RE.match(path.name)
    )
    removed = 0
    for paper_dir in paper_dirs:
        for child in sorted(paper_dir.iterdir(), key=lambda item: item.name):
            if should_remove(child, args.delete_all_non_pdf):
                remove_path(child, args.dry_run)
                removed += 1
        tmp_dir = paper_dir / "tmp"
        if args.dry_run:
            print(f"[DRY-RUN] ensure {tmp_dir}")
        else:
            tmp_dir.mkdir(exist_ok=True)

    mode = "all non-PDF entries" if args.delete_all_non_pdf else "known extraction artifacts"
    print(
        f"[OK] Prepared {len(paper_dirs)} Pending paper dirs; "
        f"removed {removed} {mode}; tmp/ ensured."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
