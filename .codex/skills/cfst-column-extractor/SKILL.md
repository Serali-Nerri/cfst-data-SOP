---
name: cfst-column-extractor
description: Extract all experimental CFST column ultimate load-capacity data from one paper into standardized schema 2.0.0-draft JSON. Use when Codex needs to extract, repair, validate, or review a single paper's CFST column capacity data from full.md first, referenced images on demand, and PDF fallback using the extraction rules, concrete-strength basis rules, section-shape reference image, JSON contract, and validator.
---

# CFST Column Extractor

Use this skill for exactly one paper. The goal is to extract every recoverable experimental CFST column ultimate load-capacity specimen row from the paper and write one standardized JSON file.

## Authority And Resources

Treat the parent worker brief, this file, and these resources as the complete one-paper contract:

- `references/extraction-rules.md`: extraction scope and field rules for all CFST column ultimate-capacity data
- `references/fc-basis-rules.md`: decision framework for `fco` and `fc_type`
- `references/section_shapes.jpg`: visual reference for `Group_A-D` section groups and `r0`
- `references/JSON_contract.md`: authoritative human-readable JSON authoring contract, including validator-equivalent writing rules
- `scripts/safe_calc.py`: sandbox-only arithmetic helper for conversions and derived values
- `scripts/validate_single_output.py`: sandbox-only execution tool for validating the final JSON

Use `references/JSON_contract.md` to decide how to write JSON. Do not inspect `scripts/validate_single_output.py` to infer JSON authoring rules unless explicitly debugging a validator implementation failure.

## Source Trust And Fallback Priority

Use this fixed trust order for evidence: PDF > referenced table/figure images > `full.md` > `content_list_v2.json`.

- Treat `full.md` as the default work entry point, not the highest-authority source.
- Treat referenced `images/` table and figure files as higher authority than the Markdown/HTML/OCR text in `full.md`.
- Treat `content_list_v2.json` as OCR/parser output only. Use it only to locate parsed blocks, image/table crops, PDF pages, or coordinates; never use it as a field-value source or cross-validation source.
- When lower-trust sources conflict with higher-trust sources, use the higher-trust source.
- When `full.md` has visible OCR noise, layout damage, mojibake, broken tables, missing critical fields, or values contradicted by referenced images, recover the affected fields from images or rendered PDF pages.
- When a field cannot be recovered from `full.md`, fall back to the PDF.

## Required Inputs

The parent should provide:

- `paper_id`
- `worktree_path`
- `paper_pdf_path`: absolute host path to the owned PDF
- `paper_pdf_relpath`: PDF path relative to the worktree root
- `output_dir`
- `output_host_path`
- `temp_json_workspace_path`: sandbox-visible JSON path
- `temp_json_host_path`: host-backed JSON path to write

The parent should also provide or make inferable the owned rawdata bundle:

- `rawdata_dir`: usually `rawdata/[<paper_id>]` or a directory whose basename starts with `[<paper_id>]`
- `full_md_path`: `<rawdata_dir>/full.md`
- `images_dir`: `<rawdata_dir>/images`
- `content_list_path`: `<rawdata_dir>/content_list_v2.json`

If rawdata paths are absent, infer them from `paper_id` by checking `rawdata/[<paper_id>]` first, then a unique `rawdata/` directory whose basename starts with `[<paper_id>]`. If no usable rawdata bundle exists, switch to PDF fallback mode.

## Boundaries

- Process exactly one paper.
- Read the owned `full.md` and referenced `images/` by default, then the owned PDF only as fallback or conflict resolver.
- Read `content_list_v2.json` only for locating parsed/PDF blocks during repair, fallback, or debugging; do not treat it as extraction evidence, a data source, or cross-validation evidence.
- Read only the owned rawdata bundle, owned PDF, this skill, and its references/scripts.
- Write exactly one JSON file to `temp_json_host_path`.
- Write no secondary extraction artifacts.
- Never write directly to final published output.
- Do not inspect prior outputs, unrelated papers, or `runs/` to infer schema or extraction policy.
- Run sandbox-only helpers only through the parent-provided `worker_sandbox.py` command.
- Do not read `scripts/validate_single_output.py` during normal extraction. Run it only as the validator after the JSON is written.

## Workflow

1. Read `references/extraction-rules.md`, `references/fc-basis-rules.md`, and `references/JSON_contract.md`; view `references/section_shapes.jpg` before assigning section groups or `r0`.
2. Locate the owned rawdata bundle for this `paper_id`.
   - Default to `rawdata/[<paper_id>]/full.md` when it exists.
   - Otherwise use the parent-provided `full_md_path`, or the unique rawdata directory whose basename starts with `[<paper_id>]`.
   - Treat `images/` as the original image files referenced by `full.md`.
3. Use `full.md` as the default entry point when it is present, readable, and not visibly garbled.
   - Read narrative text, table HTML/Markdown, captions, footnotes, equations, and image links from `full.md` first.
   - Use `full.md` to identify specimen tables, result tables, material-property tables, section geometry, concrete strength basis, loading mode, condition, and paper-level data sources.
   - Do not start from the PDF when `full.md` is usable.
4. Open only the `images/` files referenced by relevant `full.md` tables, figures, or captions.
   - For experimental table data, first use the table image referenced by `full.md`; if the image is readable, full-page PDF rendering is not required for those table values.
   - Use referenced table images to verify numeric values, symbols, merged cells, units, and footnotes when the Markdown table is suspicious or lower quality than the image.
   - Use referenced setup/geometry figures when they affect loading mode, eccentricity, section group, `r0`, or `L`.
   - Do not scan unrelated images just because they exist.
5. Use the PDF only as fallback or conflict resolver.
   - Fall back to PDF when `full.md` is missing, unreadable, incomplete for critical fields, garbled, contradicted by referenced images, or unable to provide a needed field.
   - For OCR-garbled narrative fields, render the corresponding PDF page and read the field from the page image.
   - For missing or garbled bibliographic fields, render the PDF first page, footer, header, or first-page bottom area as needed.
   - Use PDF text for locating candidate sections/tables only; render target pages or table/figure images before reading disputed values.
   - Use `content_list_v2.json` only to locate parser blocks, image/table crops, or PDF positions during fallback/repair.
6. Identify all in-scope CFST column ultimate-capacity rows under `references/extraction-rules.md` section 1. Exclude non-column and non-CFST controls before JSON assembly.
7. Extract the required A-R parameters from `references/extraction-rules.md` section 2 for each retained specimen row.
8. Resolve `fco` and `fc_type` using `references/fc-basis-rules.md`; `fc_type` follows the basis of the stored `fco` value, not necessarily the raw test specimen geometry.
9. Resolve section group and geometry using `references/section_shapes.jpg` and `references/extraction-rules.md` section 4:
   - `Group_A` is square
   - `Group_B` is rectangular
   - `Group_C` is circular
   - `Group_D` is round-ended
10. Use `scripts/safe_calc.py` for every unit conversion or derived value, including eccentricity resultants, `r0 = h / 2`, and figure/formula-derived dimensions.
11. Record paper-level source summaries and derivation bases in `paper.data_sources`, `paper.default_notes`, and `paper.notes`. Do not write evidence/source blocks, source names, quotes, or derivation bases under groups or specimens; group/specimen notes are only for local exceptions.
12. Normalize material, loading mode, condition, inheritance, allowed JSON keys, numeric precision, notes, and paper-level source summaries according to `references/JSON_contract.md`.
13. Use JSON inheritance only for genuinely shared values:
    - `paper.defaults` plus `paper.default_consistency` for paper-level `fco`, `fc_type`, `loading_mode`, `condition`, and `material`
    - `Group_X.shared` for values shared by that section group, including `r_ratio`, `e1`, and `e2` when appropriate
    - `Group_X.specimens[*]` for row-specific values and overrides
    - never put `r_ratio`, `e1`, or `e2` in `paper.defaults`
14. Write one JSON file to `temp_json_host_path` using schema version `2.0.0-draft`.
15. Validate the same file through `temp_json_workspace_path` with the parent-provided sandbox command.
16. If validation fails for JSON-contract, data, source-summary, or note reasons documented in `references/JSON_contract.md`, repair the same JSON once and rerun validation. If the sandbox fails for path, mount, startup, ownership reasons, or an undocumented validator rule, stop and report that failure.

## Validation Command

Use the parent-provided paths and run:

```bash
python .codex/skills/cfst-orchestrator/scripts/worker_sandbox.py \
  --worktree-path <worktree_path> \
  --paper-dir-relpath <paper_pdf_relpath> \
  --skill-dir-relpath .codex/skills/cfst-column-extractor \
  --output-dir output/tmp/<paper_id> \
  --host-output-dir <output_host_path> \
  --cwd-mode workspace \
  -- \
  python3 .codex/skills/cfst-column-extractor/scripts/validate_single_output.py \
    --json-path output/tmp/<paper_id>/<paper_id>.json \
    --strict-rounding
```

Warnings alone are not validator failure. If you edit the JSON after any validation attempt, rerun the same validator command before returning.
