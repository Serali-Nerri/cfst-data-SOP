#!/usr/bin/env python3
"""Prepare a CFST rawdata package for worker extraction.

This is the parent-side rawdata preprocessing step:

1. Rename a long rawdata directory like "[A1-1] Citation..." to "[A1-1]".
2. Crop table images from content_list_v2.json + *_origin.pdf and replace
   HTML table blocks in full.md.
3. Remove top-level parser byproducts so the package keeps only full.md,
   *_origin.pdf, content_list_v2.json, and images/.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from replace_html_tables_with_images import ProcessResult, RawdataError, process_rawdata, report_dict


PAPER_ID_RE = re.compile(r"^\[?([A-Za-z]+\d+-\d+)\]?")
KEEP_FILE_NAMES = {"full.md", "content_list_v2.json"}
KEEP_DIR_NAMES = {"images"}


@dataclass
class CleanupResult:
    removed: list[Path]
    kept: list[Path]
    warnings: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare one rawdata package for CFST extraction workers.")
    parser.add_argument("rawdata_dir", type=Path, help="Rawdata paper directory.")
    parser.add_argument(
        "--paper-id",
        help="Paper id such as A1-1. Defaults to parsing the rawdata directory name.",
    )
    parser.add_argument(
        "--no-shorten-dir",
        action="store_true",
        help="Do not rename the rawdata directory to [paper-id].",
    )
    parser.add_argument(
        "--cleanup",
        choices=("none", "known", "strict"),
        default="strict",
        help="Cleanup mode. strict keeps only full.md, *_origin.pdf, content_list_v2.json, and images/.",
    )
    parser.add_argument("--dpi", type=int, default=300, help="PDF render DPI for cropped table images.")
    parser.add_argument(
        "--no-overwrite-images",
        action="store_true",
        help="Do not overwrite existing caption-named table images.",
    )
    parser.add_argument(
        "--allow-count-mismatch",
        action="store_true",
        help="Allow content_list/full.md table-count mismatches. Default is to block extraction on mismatch.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print actions without changing files.")
    parser.add_argument("--report-json", type=Path, help="Optional path for a JSON processing report.")
    return parser.parse_args()


def parse_paper_id(rawdata_dir: Path, paper_id: str | None) -> str:
    if paper_id:
        value = paper_id.strip()
        value = value[1:-1] if value.startswith("[") and value.endswith("]") else value
        match = PAPER_ID_RE.match(value)
        if not match:
            raise RawdataError(f"invalid paper id: {paper_id}")
        return match.group(1)
    match = PAPER_ID_RE.match(rawdata_dir.name)
    if not match:
        raise RawdataError(f"cannot parse paper id from rawdata directory name: {rawdata_dir.name}")
    return match.group(1)


def shorten_rawdata_dir(rawdata_dir: Path, paper_id: str, dry_run: bool) -> Path:
    source = rawdata_dir.resolve()
    target = source.parent / f"[{paper_id}]"
    if source == target:
        print(f"[INFO] rawdata directory already shortened: {target}")
        return source
    if target.exists():
        raise RawdataError(f"cannot rename {source} to {target}: target already exists")
    print(f"[INFO] rename {source} -> {target}")
    if not dry_run:
        source.rename(target)
    return target


def is_origin_pdf(path: Path) -> bool:
    return path.is_file() and path.name.endswith("_origin.pdf")


def should_remove_known(path: Path) -> bool:
    name = path.name
    if path.is_dir():
        return False
    if name == "layout.json":
        return True
    if name.endswith("_model.json"):
        return True
    if name.endswith("_content_list.json") and name != "content_list_v2.json":
        return True
    return False


def should_keep_strict(path: Path) -> bool:
    if path.is_dir():
        return path.name in KEEP_DIR_NAMES
    return path.name in KEEP_FILE_NAMES or is_origin_pdf(path)


def cleanup_rawdata_dir(rawdata_dir: Path, mode: str, dry_run: bool) -> CleanupResult:
    removed: list[Path] = []
    kept: list[Path] = []
    warnings: list[str] = []
    if mode == "none":
        return CleanupResult(removed, sorted(rawdata_dir.iterdir()), warnings)

    for path in sorted(rawdata_dir.iterdir()):
        if mode == "known":
            remove = should_remove_known(path)
        else:
            remove = not should_keep_strict(path)

        if remove:
            removed.append(path)
            print(f"[INFO] remove {path}")
            if not dry_run:
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
        else:
            kept.append(path)

    origin_pdfs = [path for path in rawdata_dir.iterdir() if is_origin_pdf(path)] if not dry_run else [
        path for path in kept if is_origin_pdf(path)
    ]
    if len(origin_pdfs) != 1:
        warnings.append(f"expected exactly one *_origin.pdf after cleanup, found {len(origin_pdfs)}")
    return CleanupResult(removed, kept, warnings)


def print_cleanup_result(result: CleanupResult) -> None:
    for warning in result.warnings:
        print(f"[WARN] {warning}", file=sys.stderr)
    print(f"[INFO] cleanup removed={len(result.removed)} kept={len(result.kept)}")


def main() -> int:
    args = parse_args()
    try:
        rawdata_dir = args.rawdata_dir.resolve()
        if not rawdata_dir.exists() or not rawdata_dir.is_dir():
            raise RawdataError(f"rawdata directory not found: {rawdata_dir}")
        paper_id = parse_paper_id(rawdata_dir, args.paper_id)
        if not args.no_shorten_dir:
            rawdata_dir = shorten_rawdata_dir(rawdata_dir, paper_id, args.dry_run)

        table_result: ProcessResult | None = None
        if args.dry_run:
            process_dir = rawdata_dir if rawdata_dir.exists() else args.rawdata_dir.resolve()
        else:
            process_dir = rawdata_dir
        table_result = process_rawdata(
            process_dir,
            dpi=args.dpi,
            overwrite=not args.no_overwrite_images,
            in_place=True,
            strict_count=not args.allow_count_mismatch,
            dry_run=args.dry_run,
        )
        cleanup_result = cleanup_rawdata_dir(process_dir, args.cleanup, args.dry_run)
    except RawdataError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1

    from replace_html_tables_with_images import print_result

    print_result(table_result)
    print_cleanup_result(cleanup_result)

    if args.report_json:
        payload = {
            "paper_id": paper_id,
            "rawdata_dir": str(process_dir),
            "table_processing": report_dict(table_result),
            "cleanup": {
                "mode": args.cleanup,
                "removed": [str(path) for path in cleanup_result.removed],
                "kept": [str(path) for path in cleanup_result.kept],
                "warnings": cleanup_result.warnings,
            },
        }
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if table_result.images_ready != table_result.table_count:
        return 2
    if table_result.count_mismatch and not args.allow_count_mismatch:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
