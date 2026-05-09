#!/usr/bin/env python3
"""Install bundled CFST review references into a workspace tmp directory."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


REFERENCE_FILES = ("表头信息.md", "section_shapes.jpg")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Copy bundled CFST review reference files into workspace tmp/."
    )
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=Path("."),
        help="Workspace root where tmp/ should be prepared.",
    )
    parser.add_argument(
        "--reference-dir-name",
        default="tmp",
        help="Destination directory name under the workspace root.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    skill_dir = Path(__file__).resolve().parents[1]
    source_dir = skill_dir / "references"
    dest_dir = args.workspace_root.resolve() / args.reference_dir_name
    dest_dir.mkdir(parents=True, exist_ok=True)

    copied: list[Path] = []
    for name in REFERENCE_FILES:
        source = source_dir / name
        if not source.exists():
            print(f"[FAIL] Missing bundled reference: {source}")
            return 1
        dest = dest_dir / name
        shutil.copy2(source, dest)
        copied.append(dest)

    for path in copied:
        print(f"[OK] Prepared reference: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
