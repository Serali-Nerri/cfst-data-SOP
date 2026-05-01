#!/usr/bin/env python3
"""Replace HTML table blocks in full.md with semantic table images.

The script expects a parsed rawdata package where table images are named from
the printed table caption, for example:

    表 $1$ 钢管高强混凝土的试件参数
    images/表1钢管高强混凝土的试件参数.png

It removes only the <table>...</table> block. Captions, existing image links,
and notes below the table are preserved.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path


TABLE_RE = re.compile(r"<table\b[\s\S]*?</table>", re.IGNORECASE)
CAPTION_RE = re.compile(
    r"(?m)^[ \t]*(表[ \t]*(?:\$?[ \t]*\d+[ \t]*\$?|[一二三四五六七八九十]+)[^\n]*)[ \t]*$"
)
IMAGE_RE = re.compile(r"!\[[^\]\n]*\]\(([^)\n]+)\)")
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")


@dataclass(frozen=True)
class Replacement:
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class TableDecision:
    index: int
    caption: str | None
    image_ref: str | None
    action: str
    reason: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replace HTML tables in a full.md file with caption-matched table image references."
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Path to full.md or to a rawdata directory containing full.md.",
    )
    parser.add_argument(
        "--images-dir",
        type=Path,
        default=None,
        help="Directory containing table images. Defaults to <rawdata>/images or <full.md parent>/images.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--in-place", action="store_true", help="Overwrite the input full.md.")
    mode.add_argument("--output", type=Path, help="Write the transformed Markdown to this path.")
    mode.add_argument("--dry-run", action="store_true", help="Report replacements without writing files.")
    parser.add_argument(
        "--allow-missing-images",
        action="store_true",
        help="Skip tables whose matching image cannot be found instead of exiting nonzero.",
    )
    return parser.parse_args()


def resolve_paths(input_path: Path, images_dir: Path | None) -> tuple[Path, Path]:
    source = input_path
    if source.is_dir():
        source = source / "full.md"
    if not source.exists():
        raise FileNotFoundError(f"full.md not found: {source}")
    if images_dir is None:
        images_dir = source.parent / "images"
    if not images_dir.exists():
        raise FileNotFoundError(f"images directory not found: {images_dir}")
    return source, images_dir


def normalize_caption(caption: str) -> str:
    text = caption.strip()
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = text.replace("$", "")
    text = re.sub(r"[ \t\r\n]+", "", text)
    text = text.strip(" :：.;；,，")
    return text


def markdown_path(md_path: Path, image_path: Path) -> str:
    rel = os.path.relpath(image_path.resolve(), md_path.parent.resolve())
    return Path(rel).as_posix()


def image_path_from_ref(md_path: Path, ref: str) -> Path:
    ref = ref.strip()
    if ref.startswith("<") and ref.endswith(">"):
        ref = ref[1:-1]
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", ref):
        return Path(ref)
    return (md_path.parent / ref).resolve()


def find_caption(text: str, table_start: int, window: int = 3000) -> re.Match[str] | None:
    search_start = max(0, table_start - window)
    matches = list(CAPTION_RE.finditer(text, search_start, table_start))
    return matches[-1] if matches else None


def find_existing_image(segment: str) -> re.Match[str] | None:
    matches = list(IMAGE_RE.finditer(segment))
    return matches[-1] if matches else None


def find_caption_image(caption: str, images_dir: Path) -> Path | None:
    stem = normalize_caption(caption)
    for ext in IMAGE_EXTENSIONS:
        candidate = images_dir / f"{stem}{ext}"
        if candidate.exists():
            return candidate

    table_no_match = re.match(r"表([0-9一二三四五六七八九十]+)", stem)
    if not table_no_match:
        return None
    prefix = table_no_match.group(0)
    matches = []
    for ext in IMAGE_EXTENSIONS:
        matches.extend(images_dir.glob(f"{prefix}*{ext}"))
    if len(matches) == 1:
        return matches[0]
    return None


def transform(text: str, md_path: Path, images_dir: Path, allow_missing: bool) -> tuple[str, list[TableDecision], bool]:
    replacements: list[Replacement] = []
    decisions: list[TableDecision] = []
    had_missing = False

    for idx, table_match in enumerate(TABLE_RE.finditer(text), start=1):
        caption_match = find_caption(text, table_match.start())
        if caption_match is None:
            had_missing = True
            decisions.append(TableDecision(idx, None, None, "skipped", "no preceding table caption found"))
            continue

        caption = caption_match.group(1).strip()
        segment = text[caption_match.end() : table_match.start()]
        existing_image = find_existing_image(segment)
        caption_image = find_caption_image(caption, images_dir)

        image_ref: str | None = None
        if existing_image is not None:
            raw_ref = existing_image.group(1)
            existing_path = image_path_from_ref(md_path, raw_ref)
            if existing_path.exists():
                image_ref = raw_ref
            elif caption_image is not None:
                image_ref = markdown_path(md_path, caption_image)
        elif caption_image is not None:
            image_ref = markdown_path(md_path, caption_image)

        if image_ref is None:
            had_missing = True
            decisions.append(TableDecision(idx, caption, None, "skipped", "matching table image not found"))
            continue

        replacement_text = "" if existing_image is not None else f"![]({image_ref})\n"
        replacements.append(Replacement(table_match.start(), table_match.end(), replacement_text))
        decisions.append(TableDecision(idx, caption, image_ref, "replaced"))

    if had_missing and not allow_missing:
        return text, decisions, had_missing

    output = text
    for replacement in reversed(replacements):
        output = output[: replacement.start] + replacement.text + output[replacement.end :]
    output = re.sub(r"\n{4,}", "\n\n\n", output)
    return output, decisions, had_missing


def main() -> int:
    args = parse_args()
    try:
        md_path, images_dir = resolve_paths(args.input, args.images_dir)
    except FileNotFoundError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1

    source = md_path.read_text(encoding="utf-8")
    output, decisions, had_missing = transform(source, md_path, images_dir, args.allow_missing_images)

    for decision in decisions:
        caption = decision.caption or "(no caption)"
        if decision.action == "replaced":
            print(f"[OK] table {decision.index}: {caption} -> {decision.image_ref}")
        else:
            print(f"[WARN] table {decision.index}: {caption} skipped: {decision.reason}")

    replaced_count = sum(1 for decision in decisions if decision.action == "replaced")
    skipped_count = sum(1 for decision in decisions if decision.action == "skipped")
    print(f"[INFO] HTML tables found: {len(decisions)}; replaced: {replaced_count}; skipped: {skipped_count}")

    if had_missing and not args.allow_missing_images:
        print("[FAIL] Missing table images; no file was written. Use --allow-missing-images to skip them.", file=sys.stderr)
        return 2

    if args.dry_run:
        return 0
    if args.in_place:
        md_path.write_text(output, encoding="utf-8")
        print(f"[INFO] wrote {md_path}")
        return 0
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
        print(f"[INFO] wrote {args.output}")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
