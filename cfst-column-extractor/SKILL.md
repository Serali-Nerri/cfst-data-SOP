---
name: cfst-column-extractor
description: Extract all experimental CFST column ultimate load-capacity data from one paper into standardized schema 1.0.0 JSON. Use when Codex needs to extract, repair, validate, or review a single paper's CFST column capacity data from rawdata/full.md first, referenced images on demand, and PDF fallback using the extraction rules, concrete-strength basis rules, section-shape reference image, and JSON schema.
---

# CFST Column Extractor

Use this skill for exactly one paper. The goal is to extract every recoverable experimental CFST column ultimate load-capacity specimen row from the paper and write one standardized JSON file.

## Authority And Resources

Treat the parent worker brief, this file, and these resources as the complete one-paper contract:

- `references/extraction-rules.md`: extraction scope and field rules for all CFST column ultimate-capacity data
- `references/fc-basis-rules.md`: decision framework for `fco_mpa` and `fc_type`
- `references/section_shapes.jpg`: visual reference for section groups and `r0_mm`
- `references/cfst-extraction-schema.json`: machine-readable JSON schema
- `references/JSON_contract.md`: authoritative human-readable JSON authoring contract, including validator-equivalent writing rules
- `scripts/safe_calc.py`: sandbox-only arithmetic helper for conversions and derived values
- `scripts/validate_single_output.py`: sandbox-only execution tool for validating the final JSON

Do not apply an ordinary-CFST filter. Include non-ordinary CFST column rows when they satisfy `references/extraction-rules.md`.

Use `references/JSON_contract.md` to decide how to write JSON. Do not inspect `scripts/validate_single_output.py` to infer JSON authoring rules unless explicitly debugging a validator implementation failure. If validation fails because of a rule not documented in `JSON_contract.md`, report the documentation/validator mismatch instead of treating the validator source as extraction policy.

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
- Read `content_list_v2.json` only for locating parsed/PDF blocks during repair, fallback, or debugging; do not treat it as primary extraction evidence.
- Read only the owned rawdata bundle, owned PDF, this skill, and its references/scripts.
- Write exactly one JSON file to `temp_json_host_path`.
- Write no secondary extraction artifacts.
- Never write directly to final published output.
- Do not inspect prior outputs, unrelated papers, or `runs/` to infer schema or extraction policy.
- Run sandbox-only helpers only through the parent-provided `worker_sandbox.py` command.
- Do not read `scripts/validate_single_output.py` during normal extraction. Run it only as the validator after the JSON is written.

## Workflow

1. Read `references/extraction-rules.md`, `references/fc-basis-rules.md`, and `references/JSON_contract.md`; view `references/section_shapes.jpg` before assigning section groups or `r0_mm`.
2. Locate the owned rawdata bundle for this `paper_id`.
   - Default to `rawdata/[<paper_id>]/full.md` when it exists.
   - Otherwise use the parent-provided `full_md_path`, or the unique rawdata directory whose basename starts with `[<paper_id>]`.
   - Treat `images/` as the original image files referenced by `full.md`.
3. Use `full.md` as the default extraction source when it is present, readable, and not visibly garbled.
   - Read narrative text, table HTML/Markdown, captions, footnotes, equations, and image links from `full.md` first.
   - Use `full.md` to identify specimen tables, result tables, material-property tables, section geometry, concrete strength basis, loading mode, and condition evidence.
   - Do not start from the PDF when `full.md` is usable.
4. Open only the `images/` files referenced by relevant `full.md` tables, figures, or captions.
   - Use referenced table images to verify numeric values, symbols, merged cells, units, and footnotes when the Markdown table is suspicious.
   - Use referenced setup/geometry figures when they affect loading mode, eccentricity, section shape, `r0_mm`, or `l_mm`.
   - Do not scan unrelated images just because they exist.
5. Use the PDF only as fallback or conflict resolver.
   - Fall back to PDF when `full.md` is missing, unreadable, incomplete for critical fields, garbled, or contradicted by referenced images.
   - Use PDF text for locating candidate sections/tables only; render target pages or table/figure images before reading disputed values.
   - Use `content_list_v2.json` only to locate parser blocks, image/table crops, or PDF positions during fallback/repair.
6. Identify all in-scope CFST column ultimate-capacity rows under `references/extraction-rules.md` section 1. Exclude non-column and non-CFST controls before JSON assembly.
7. Extract the required A-R parameters from `references/extraction-rules.md` section 2 for each retained specimen row.
8. Resolve `fco_mpa` and `fc_type` using `references/fc-basis-rules.md`; `fc_type` follows the basis of the stored `fco_mpa` value, not necessarily the raw test specimen geometry.
9. Resolve section group and geometry using `references/section_shapes.jpg` and `references/extraction-rules.md` section 4:
   - `square` / `rectangular` represent Group A
   - `circular` represents Group B
   - `round_ended` represents Group C
10. Use `scripts/safe_calc.py` for every unit conversion or derived value, including eccentricity resultants, `r0_mm = h_mm / 2`, and figure/formula-derived dimensions.
11. Record evidence with table identifiers, figure identifiers when figure-derived, and/or original source text quotes. Page numbers are not required and must not be the only evidence locator.
12. Normalize material, loading mode, condition tags, quality flags, inheritance, allowed JSON keys, numeric precision, and evidence blocks according to `references/JSON_contract.md`.
13. Use JSON inheritance only for genuinely shared values:
    - `paper.paper_shared_defaults` for values shared by all extracted rows
    - `section_groups.<shape>.shared` for values shared by that section-shape group
    - `specimens[*].data` for row-specific values and overrides
14. Write one JSON file to `temp_json_host_path` using schema version `1.0.0`.
15. Validate the same file through `temp_json_workspace_path` with the parent-provided sandbox command.
16. If validation fails for schema, data, or evidence reasons documented in `references/JSON_contract.md`, repair the same JSON once and rerun validation. If the sandbox fails for path, mount, startup, ownership reasons, or an undocumented validator rule, stop and report that failure.

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
