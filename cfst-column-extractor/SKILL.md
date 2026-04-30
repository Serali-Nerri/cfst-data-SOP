---
name: cfst-column-extractor
description: Extract one experimental CFST column paper into schema-v2.3 JSON with Markdown-first rawdata reading, table-image cross-checking, PDF fallback, shared_context, series_definitions, specimen-level ordinary tagging, authoritative ordinary_decisions scratch YAML, and validator-backed normalization. Use when Codex needs to extract, repair, validate, or review a single paper's CFST column data, usually inside a worker launched by `cfst-orchestrator`.
---

# CFST Column Extractor

Use this skill for exactly one paper. Treat the parent-supplied worker brief, this file, `references/extraction-rules.md`, and `references/single-flow.md` as the complete extraction contract. The schema identifier remains `cfst-paper-extractor-v2.3` for compatibility; it is not tied to the parent orchestrator skill name.

## Required Inputs

The worker should receive:

- `paper_id`
- `worktree_path`
- `paper_pdf_path`
- `paper_pdf_relpath`
- `output_dir`
- `output_host_path`
- `temp_json_workspace_path`
- `temp_json_host_path`

The parent may also provide rawdata evidence paths such as `rawdata_dir`, `full_md_path`, or `images_dir`. These are preferred when available but are not required for backward-compatible PDF-only extraction.

## Core Workflow

1. Read `references/extraction-rules.md` and `references/single-flow.md`.
2. Verify the owned PDF exists, then locate the owned rawdata evidence bundle when the parent provides it or it is inferable: `full.md`, referenced `images/`, and optional preprocessing files.
3. If `full.md` is present and readable, use it as the default narrative, table, caption, and image-link index. Do not read `content_list_v2.json` by default; treat it only as a preprocessing, repair, or debugging artifact.
4. For every table used as evidence, read both the HTML table in `full.md` and the corresponding semantic table image placed under or near the table caption. Use the table image or rendered PDF page over OCR/HTML text when they conflict on values, units, symbols, row grouping, merged cells, or footnotes.
5. Open referenced images only when they are relevant to specimens, materials, results, geometry, setup/loading mode, failure mode, or table verification. Do not scan the entire `images/` directory by default.
6. Fall back to the original PDF when `full.md` is missing, unreadable, garbled, cross-article mixed beyond reliable separation, missing critical sections, or when referenced images are absent/cropped/ambiguous. Render PDF pages with `pdf_info` / `pdf_text` / `pdf_pages` / `view_image` for fallback and conflict resolution.
7. Keep only true CFST column specimens. Exclude beam-columns, joints, frames, non-column members, and steel-only controls before ordinary tagging.
8. Build exactly one scratch YAML at `output/tmp/<paper_id>/_scratch/extraction_draft.yaml`, then build exactly one JSON at `temp_json_host_path`.
9. Use `shared_context` only for values truly shared by all kept rows. Use `series_definitions`, `context_overrides`, or direct row fields for mixed evidence.
10. Keep ordinary and non-ordinary kept specimens together in `Group_A` / `Group_B` / `Group_C`; distinguish them with `is_ordinary` and `ordinary_exclusion_reasons`.
11. Use the parent-provided sandbox command to validate the same JSON through `temp_json_workspace_path`. If validation fails for schema, data, or evidence reasons, repair once and rerun the same validator command.

## Use These Resources

- `references/extraction-rules.md`: scope rules, ordinary gate, schema-v2.3 shape, shared-context rules, evidence rules, and numeric constraints
- `references/single-flow.md`: one-paper execution order, required input layout, scratch YAML structure, and validation expectations
- `scripts/safe_calc.py`: sandbox-only arithmetic helper for conversions and derived values
- `scripts/validate_single_output.py`: sandbox-only validator for the final JSON plus authoritative scratch YAML
