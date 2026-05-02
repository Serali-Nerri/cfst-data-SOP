#!/usr/bin/env python3
"""Crop table images from a rawdata package and replace HTML tables in full.md.

Expected package shape:

    <rawdata-paper-dir>/
      full.md
      *_origin.pdf
      content_list_v2.json
      images/

The table blocks in content_list_v2.json use the parsed document coordinate
system used by the current CFST rawdata packages: page coordinates are
normalized to a 1000 x 1000 box.  The script maps those boxes to the PDF page,
crops table images, names them from the printed table captions, and replaces
the corresponding <table>...</table> blocks in full.md with Markdown image
references.  If full.md and content_list_v2.json disagree about the number of
tables, the script prints a warning.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover - environment guard
    fitz = None  # type: ignore[assignment]

try:
    from PIL import Image
except ImportError:  # pragma: no cover - environment guard
    Image = None  # type: ignore[assignment]


HTML_TABLE_RE = re.compile(r"<table\b[\s\S]*?</table>", re.IGNORECASE)
CAPTION_LINE_RE = re.compile(
    r"(?im)^[ \t]*((?:table|表|裹)[ \t]*[0-9一二三四五六七八九十]*[\s\S]{0,240}?)\s*$"
)
INVALID_FILENAME_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
CJK_RE = re.compile(r"[\u3400-\u9fff]")


class RawdataError(RuntimeError):
    """Raised when a rawdata package cannot be processed."""


@dataclass(frozen=True)
class RawdataPaths:
    rawdata_dir: Path
    full_md: Path
    content_list: Path
    images_dir: Path
    origin_pdf: Path


@dataclass
class TableSpec:
    ordinal: int
    page_index: int
    block_index: int
    bbox: tuple[float, float, float, float]
    crop_bbox: tuple[float, float, float, float]
    caption: str
    footnote: str
    html: str
    image_path: Path
    status: str = "pending"
    warnings: list[str] = field(default_factory=list)

    @property
    def has_footnote(self) -> bool:
        return bool(self.footnote.strip())


@dataclass
class ProcessResult:
    rawdata_dir: Path
    full_md: Path
    table_count: int
    html_table_count: int
    count_mismatch: bool
    images_ready: int
    cropped_count: int
    replaced_count: int
    skipped_replacements: int
    warnings: list[str]
    table_specs: list[TableSpec]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Crop table images from content_list_v2.json and replace HTML table blocks in full.md."
    )
    parser.add_argument("input", type=Path, help="Rawdata directory or full.md path.")
    parser.add_argument("--content-list", type=Path, help="Path to content_list_v2.json.")
    parser.add_argument("--pdf", type=Path, help="Path to *_origin.pdf.")
    parser.add_argument("--images-dir", type=Path, help="Path to images directory.")
    parser.add_argument("--dpi", type=int, default=300, help="PDF render DPI for cropped table images.")
    parser.add_argument(
        "--image-format",
        choices=("png", "jpg", "jpeg"),
        default="png",
        help="Output image format for cropped tables.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing caption-named table images.",
    )
    parser.add_argument(
        "--no-trim-table-top",
        action="store_true",
        help="Do not trim caption fragments above the first table-top horizontal rule.",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite full.md after replacing HTML tables.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write transformed Markdown to this path instead of changing full.md.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions without writing images or Markdown.",
    )
    parser.add_argument(
        "--strict-count",
        action="store_true",
        help="Exit nonzero when content_list_v2.json and full.md table counts differ.",
    )
    parser.add_argument(
        "--report-json",
        type=Path,
        help="Optional path for a JSON processing report.",
    )
    return parser.parse_args()


def resolve_paths(
    input_path: Path,
    content_list: Path | None = None,
    pdf_path: Path | None = None,
    images_dir: Path | None = None,
) -> RawdataPaths:
    source = input_path.resolve()
    if source.is_dir():
        rawdata_dir = source
        full_md = rawdata_dir / "full.md"
    else:
        full_md = source
        rawdata_dir = source.parent

    content_list = (content_list or rawdata_dir / "content_list_v2.json").resolve()
    images_dir = (images_dir or rawdata_dir / "images").resolve()

    if pdf_path is None:
        candidates = sorted(rawdata_dir.glob("*_origin.pdf"))
        if len(candidates) != 1:
            raise RawdataError(
                f"expected exactly one *_origin.pdf in {rawdata_dir}, found {len(candidates)}"
            )
        pdf_path = candidates[0]
    pdf_path = pdf_path.resolve()

    required_files = {
        "full.md": full_md,
        "content_list_v2.json": content_list,
        "*_origin.pdf": pdf_path,
    }
    for label, path in required_files.items():
        if not path.exists():
            raise RawdataError(f"{label} not found: {path}")
        if not path.is_file():
            raise RawdataError(f"{label} is not a file: {path}")
    if not images_dir.exists():
        images_dir.mkdir(parents=True)
    if not images_dir.is_dir():
        raise RawdataError(f"images path is not a directory: {images_dir}")

    return RawdataPaths(rawdata_dir, full_md, content_list, images_dir, pdf_path)


def content_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(content_text(item) for item in value)
    if isinstance(value, dict):
        if isinstance(value.get("content"), str):
            return value["content"]
        pieces: list[str] = []
        for key in (
            "title_content",
            "paragraph_content",
            "table_caption",
            "table_footnote",
            "text",
        ):
            if key in value:
                pieces.append(content_text(value[key]))
        if pieces:
            return "".join(pieces)
    return ""


def load_pages(content_list_path: Path) -> list[list[dict[str, Any]]]:
    data = json.loads(content_list_path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("pages") or data.get("content") or data.get("data")
    if not isinstance(data, list):
        raise RawdataError(f"unsupported content list structure: {content_list_path}")

    pages: list[list[dict[str, Any]]] = []
    for page in data:
        if isinstance(page, dict):
            page = page.get("blocks") or page.get("items") or []
        if not isinstance(page, list):
            raise RawdataError(f"unsupported page entry in {content_list_path}")
        pages.append([block for block in page if isinstance(block, dict)])
    return pages


def clean_caption(caption: str) -> str:
    text = re.sub(r"`([^`]*)`", r"\1", caption)
    text = text.replace("$", "")
    text = re.sub(r"\\([A-Za-z]+)", r"\1", text)
    text = re.sub(r"[{}^]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if CJK_RE.search(text):
        text = re.sub(r"(?<=[\u3400-\u9fff表裹])\s+(?=[0-9一二三四五六七八九十A-Za-z\u3400-\u9fff])", "", text)
        text = re.sub(r"(?<=[0-9一二三四五六七八九十])\s+(?=[\u3400-\u9fff])", "", text)
    return text.strip(" .:：;；,，")


def filename_stem(caption: str, ordinal: int, page_index: int, block_index: int) -> str:
    stem = clean_caption(caption)
    if not stem:
        stem = f"table_p{page_index:03d}_b{block_index:03d}"
    stem = INVALID_FILENAME_CHARS_RE.sub(" ", stem)
    stem = re.sub(r"\s+", " ", stem).strip()
    if CJK_RE.search(stem):
        stem = stem.replace(" ", "")
    if len(stem) > 140:
        stem = stem[:140].rstrip()
    return stem or f"table_{ordinal:03d}"


def unique_image_paths(
    tables: list[TableSpec],
    images_dir: Path,
    image_format: str,
) -> None:
    seen: dict[str, int] = {}
    ext = "jpg" if image_format == "jpeg" else image_format
    for table in tables:
        base = filename_stem(table.caption, table.ordinal, table.page_index, table.block_index)
        count = seen.get(base, 0) + 1
        seen[base] = count
        stem = base if count == 1 else f"{base}_p{table.page_index:03d}_{count}"
        if count > 1:
            table.warnings.append(f"duplicate table caption; using unique filename {stem}.{ext}")
        table.image_path = images_dir / f"{stem}.{ext}"


def normalized_bbox(raw: Any) -> tuple[float, float, float, float] | None:
    if not isinstance(raw, list) or len(raw) != 4:
        return None
    try:
        x0, y0, x1, y1 = [float(value) for value in raw]
    except (TypeError, ValueError):
        return None
    if x1 <= x0 or y1 <= y0:
        return None
    return x0, y0, x1, y1


def horizontal_overlap_ratio(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> float:
    overlap = max(0.0, min(left[2], right[2]) - max(left[0], right[0]))
    width = max(1.0, min(left[2] - left[0], right[2] - right[0]))
    return overlap / width


def extend_for_footnote(
    page_blocks: list[dict[str, Any]],
    table_block_index: int,
    bbox: tuple[float, float, float, float],
    has_footnote: bool,
) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = bbox
    padding = 6.0
    if has_footnote:
        lower_candidates: list[float] = []
        for block in page_blocks[table_block_index + 1 :]:
            if block.get("type") == "page_number":
                continue
            other = normalized_bbox(block.get("bbox"))
            if other is None or other[1] < y1:
                continue
            if horizontal_overlap_ratio(bbox, other) >= 0.25:
                lower_candidates.append(other[1])
        if lower_candidates:
            y1 = max(y1, min(lower_candidates) - 5.0)
        else:
            y1 = y1 + 80.0
    return (
        max(0.0, x0 - padding),
        max(0.0, y0 - padding),
        min(1000.0, x1 + padding),
        min(1000.0, y1 + padding),
    )


def collect_tables(
    pages: list[list[dict[str, Any]]],
    images_dir: Path,
    image_format: str,
) -> list[TableSpec]:
    tables: list[TableSpec] = []
    for page_index, blocks in enumerate(pages, start=1):
        for block_index, block in enumerate(blocks):
            if block.get("type") != "table":
                continue
            bbox = normalized_bbox(block.get("bbox"))
            content = block.get("content") or {}
            caption = content_text(content.get("table_caption")).strip()
            footnote = content_text(content.get("table_footnote")).strip()
            html = content.get("html") if isinstance(content.get("html"), str) else ""
            ordinal = len(tables) + 1
            if bbox is None:
                spec = TableSpec(
                    ordinal=ordinal,
                    page_index=page_index,
                    block_index=block_index,
                    bbox=(0.0, 0.0, 0.0, 0.0),
                    crop_bbox=(0.0, 0.0, 0.0, 0.0),
                    caption=caption,
                    footnote=footnote,
                    html=html,
                    image_path=images_dir / f"table_{ordinal:03d}.{image_format}",
                    status="failed",
                    warnings=["invalid or missing table bbox"],
                )
            else:
                crop_bbox = extend_for_footnote(blocks, block_index, bbox, bool(footnote))
                spec = TableSpec(
                    ordinal=ordinal,
                    page_index=page_index,
                    block_index=block_index,
                    bbox=bbox,
                    crop_bbox=crop_bbox,
                    caption=caption,
                    footnote=footnote,
                    html=html,
                    image_path=images_dir / f"table_{ordinal:03d}.{image_format}",
                )
            tables.append(spec)
    unique_image_paths(tables, images_dir, image_format)
    return tables


def bbox_to_pdf_rect(
    bbox: tuple[float, float, float, float],
    page_rect: Any,
) -> Any:
    x0, y0, x1, y1 = bbox
    return fitz.Rect(  # type: ignore[union-attr]
        x0 / 1000.0 * page_rect.width,
        y0 / 1000.0 * page_rect.height,
        x1 / 1000.0 * page_rect.width,
        y1 / 1000.0 * page_rect.height,
    )


def crop_tables(
    paths: RawdataPaths,
    tables: list[TableSpec],
    dpi: int,
    overwrite: bool,
    trim_table_top: bool,
    dry_run: bool,
) -> tuple[int, int, list[str]]:
    if fitz is None:
        raise RawdataError("PyMuPDF is required: import fitz failed")
    if dpi < 72 or dpi > 1200:
        raise RawdataError("--dpi must be between 72 and 1200")

    warnings: list[str] = []
    cropped_count = 0
    ready_count = 0

    doc = fitz.open(paths.origin_pdf)  # type: ignore[union-attr]
    try:
        for table in tables:
            if table.status == "failed":
                warnings.extend(f"table {table.ordinal}: {msg}" for msg in table.warnings)
                continue
            if table.page_index < 1 or table.page_index > len(doc):
                table.status = "failed"
                table.warnings.append(
                    f"page {table.page_index} is outside PDF page count {len(doc)}"
                )
                warnings.extend(f"table {table.ordinal}: {msg}" for msg in table.warnings)
                continue

            if table.image_path.exists() and not overwrite:
                table.status = "existing"
                ready_count += 1
                continue

            if dry_run:
                table.status = "dry-run"
                ready_count += 1
                continue

            page = doc[table.page_index - 1]
            clip = bbox_to_pdf_rect(table.crop_bbox, page.rect)
            clip = clip & page.rect
            if clip.is_empty or clip.width <= 1 or clip.height <= 1:
                table.status = "failed"
                table.warnings.append(f"empty crop rectangle from bbox {table.crop_bbox}")
                warnings.extend(f"table {table.ordinal}: {msg}" for msg in table.warnings)
                continue

            table.image_path.parent.mkdir(parents=True, exist_ok=True)
            pix = page.get_pixmap(clip=clip, dpi=dpi, alpha=False)
            if pix.width <= 1 or pix.height <= 1:
                table.status = "failed"
                table.warnings.append(f"rendered crop is empty ({pix.width}x{pix.height})")
                warnings.extend(f"table {table.ordinal}: {msg}" for msg in table.warnings)
                continue
            pix.save(str(table.image_path))
            if trim_table_top:
                trim_top_to_first_horizontal_rule(table.image_path)
            table.status = "cropped"
            cropped_count += 1
            ready_count += 1
    finally:
        doc.close()

    if ready_count != len(tables):
        warnings.append(
            f"cropped/ready table image count mismatch: content_list tables={len(tables)}, ready={ready_count}"
        )
    return cropped_count, ready_count, warnings


def trim_top_to_first_horizontal_rule(image_path: Path) -> bool:
    """Remove caption fragments above a table's top horizontal rule.

    Captions remain as Markdown text in full.md.  The crop should contain the
    table body plus footnotes, not a clipped duplicate caption.  This function
    is intentionally conservative: if it cannot find a strong horizontal rule
    near the top, it leaves the image untouched.
    """
    if Image is None:
        return False
    with Image.open(image_path) as original:
        image = original.copy()
    gray = image.convert("L")
    width, height = gray.size
    if width < 50 or height < 50:
        return False

    scan_limit = min(max(20, height // 4), 260)
    pixels = gray.load()
    threshold = 105
    min_dark_fraction = 0.35
    for y in range(scan_limit):
        dark = 0
        for x in range(width):
            if pixels[x, y] <= threshold:
                dark += 1
        if dark / width < min_dark_fraction:
            continue

        crop_y = max(0, y - 4)
        if crop_y <= 2:
            return False
        cropped = image.crop((0, crop_y, width, height))
        cropped.save(image_path)
        return True
    return False


def markdown_path(md_path: Path, image_path: Path) -> str:
    rel = os.path.relpath(image_path.resolve(), md_path.parent.resolve())
    return Path(rel).as_posix()


def find_caption_before(text: str, table_start: int, window: int = 3000) -> re.Match[str] | None:
    search_start = max(0, table_start - window)
    matches = list(CAPTION_LINE_RE.finditer(text, search_start, table_start))
    return matches[-1] if matches else None


def normalized_caption_key(text: str) -> str:
    return re.sub(r"\W+", "", clean_caption(text).lower(), flags=re.UNICODE)


def choose_table_for_html(
    html_index: int,
    caption: str | None,
    tables: list[TableSpec],
    used: set[int],
) -> TableSpec | None:
    if caption:
        key = normalized_caption_key(caption)
        for table in tables:
            if table.ordinal in used:
                continue
            if key and key == normalized_caption_key(table.caption):
                return table
    if html_index - 1 < len(tables):
        table = tables[html_index - 1]
        if table.ordinal not in used:
            return table
    for table in tables:
        if table.ordinal not in used:
            return table
    return None


def replace_html_tables(
    md_path: Path,
    tables: list[TableSpec],
    output_path: Path | None,
    in_place: bool,
    strict_count: bool,
    dry_run: bool,
) -> tuple[int, int, int, list[str]]:
    source = md_path.read_text(encoding="utf-8")
    html_matches = list(HTML_TABLE_RE.finditer(source))
    warnings: list[str] = []
    replacements: list[tuple[int, int, str]] = []
    used: set[int] = set()
    skipped = 0

    if len(html_matches) != len(tables):
        warnings.append(
            f"table count mismatch: content_list_v2.json tables={len(tables)}, full.md HTML tables={len(html_matches)}"
        )
        if strict_count:
            warnings.append("strict count enabled; full.md was not modified")
            return len(html_matches), 0, len(html_matches), warnings

    for html_index, html_match in enumerate(html_matches, start=1):
        caption_match = find_caption_before(source, html_match.start())
        caption = caption_match.group(1).strip() if caption_match else None
        table = choose_table_for_html(html_index, caption, tables, used)
        if table is None:
            skipped += 1
            warnings.append(f"HTML table {html_index}: no matching content_list table")
            continue
        used.add(table.ordinal)
        if table.status == "failed" or not (table.image_path.exists() or dry_run):
            skipped += 1
            warnings.append(f"HTML table {html_index}: table image is not ready for {table.caption!r}")
            continue

        replacement_text = f"![]({markdown_path(md_path, table.image_path)})\n"
        replacements.append((html_match.start(), html_match.end(), replacement_text))

    transformed = source
    for start, end, replacement_text in reversed(replacements):
        transformed = transformed[:start] + replacement_text + transformed[end:]
    transformed = re.sub(r"\n{4,}", "\n\n\n", transformed)

    if not dry_run:
        if in_place:
            md_path.write_text(transformed, encoding="utf-8")
        elif output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(transformed, encoding="utf-8")

    return len(html_matches), len(replacements), skipped, warnings


def process_rawdata(
    input_path: Path,
    *,
    content_list: Path | None = None,
    pdf_path: Path | None = None,
    images_dir: Path | None = None,
    dpi: int = 300,
    image_format: str = "png",
    overwrite: bool = False,
    trim_table_top: bool = True,
    in_place: bool = False,
    output_path: Path | None = None,
    strict_count: bool = False,
    dry_run: bool = False,
) -> ProcessResult:
    paths = resolve_paths(input_path, content_list, pdf_path, images_dir)
    pages = load_pages(paths.content_list)
    tables = collect_tables(pages, paths.images_dir, image_format)
    cropped_count, images_ready, crop_warnings = crop_tables(
        paths, tables, dpi, overwrite, trim_table_top, dry_run
    )
    html_count, replaced_count, skipped, replace_warnings = replace_html_tables(
        paths.full_md, tables, output_path, in_place, strict_count, dry_run
    )
    warnings = crop_warnings + replace_warnings
    for table in tables:
        warnings.extend(f"table {table.ordinal}: {msg}" for msg in table.warnings)
    return ProcessResult(
        rawdata_dir=paths.rawdata_dir,
        full_md=paths.full_md,
        table_count=len(tables),
        html_table_count=html_count,
        count_mismatch=len(tables) != html_count,
        images_ready=images_ready,
        cropped_count=cropped_count,
        replaced_count=replaced_count,
        skipped_replacements=skipped,
        warnings=warnings,
        table_specs=tables,
    )


def report_dict(result: ProcessResult) -> dict[str, Any]:
    return {
        "rawdata_dir": str(result.rawdata_dir),
        "full_md": str(result.full_md),
        "content_list_tables": result.table_count,
        "full_md_html_tables": result.html_table_count,
        "count_mismatch": result.count_mismatch,
        "images_ready": result.images_ready,
        "cropped_count": result.cropped_count,
        "replaced_count": result.replaced_count,
        "skipped_replacements": result.skipped_replacements,
        "warnings": result.warnings,
        "tables": [
            {
                "ordinal": table.ordinal,
                "page": table.page_index,
                "block": table.block_index,
                "caption": table.caption,
                "has_footnote": table.has_footnote,
                "bbox": table.bbox,
                "crop_bbox": table.crop_bbox,
                "image_path": str(table.image_path),
                "status": table.status,
                "warnings": table.warnings,
            }
            for table in result.table_specs
        ],
    }


def print_result(result: ProcessResult) -> None:
    for table in result.table_specs:
        caption = table.caption or "(no caption)"
        print(
            f"[{table.status.upper()}] table {table.ordinal}: page={table.page_index} "
            f"caption={caption} -> {table.image_path.relative_to(result.rawdata_dir)}"
        )
    for warning in result.warnings:
        print(f"[WARN] {warning}", file=sys.stderr)
    print(
        "[INFO] "
        f"content_list tables={result.table_count}; "
        f"full.md HTML tables={result.html_table_count}; "
        f"count mismatch={result.count_mismatch}; "
        f"images ready={result.images_ready}; "
        f"cropped={result.cropped_count}; "
        f"replaced={result.replaced_count}; "
        f"skipped replacements={result.skipped_replacements}"
    )


def main() -> int:
    args = parse_args()
    try:
        result = process_rawdata(
            args.input,
            content_list=args.content_list,
            pdf_path=args.pdf,
            images_dir=args.images_dir,
            dpi=args.dpi,
            image_format=args.image_format,
            overwrite=args.overwrite,
            trim_table_top=not args.no_trim_table_top,
            in_place=args.in_place,
            output_path=args.output,
            strict_count=args.strict_count,
            dry_run=args.dry_run,
        )
    except RawdataError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1

    print_result(result)
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(
            json.dumps(report_dict(result), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    if args.strict_count and result.count_mismatch:
        return 3
    if result.images_ready != result.table_count:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
