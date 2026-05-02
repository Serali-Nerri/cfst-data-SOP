---
name: cfst-column-extractor
description: Extract all experimental CFST column ultimate load-capacity data from one caller-provided paper package into standardized schema 2.0.0-draft JSON. Use when Codex needs to extract, repair, validate, or review a single paper's CFST column capacity data from prepared full.md first when provided, referenced images on demand, and PDF fallback using the extraction rules, concrete-strength basis rules, section-shape reference image, JSON contract, and caller-provided validation command.
---

# CFST Column Extractor

Use this skill for exactly one paper. The goal is to extract every recoverable experimental CFST column ultimate load-capacity specimen row from caller-provided inputs and write one standardized JSON file.

## Authority And Resources

Treat this file and these resources as the complete one-paper extraction contract. The parent or caller provides input paths, output paths, and sandbox/validation commands; it does not define extraction policy.

- `references/extraction-rules.md`: extraction scope and field rules for all CFST column ultimate-capacity data
- `references/fc-basis-rules.md`: decision framework for `fco` and `fc_type`
- `references/section_shapes.jpg`: visual reference for `Group_A-D` section groups and `r0`
- `references/JSON_contract.md`: authoritative human-readable JSON authoring contract, including validator-equivalent writing rules
- `scripts/safe_calc.py`: sandbox-only arithmetic helper for conversions and derived values
- `scripts/validate_single_output.py`: sandbox-only execution tool for validating the final JSON

Use `references/JSON_contract.md` to decide how to write JSON. Do not inspect `scripts/validate_single_output.py` to infer JSON authoring rules unless explicitly debugging a validator implementation failure.

## Source Handling

Use `full.md` as the work entry point when a usable prepared rawdata bundle is provided. On conflicts, use this evidence authority order: rendered PDF/source page > referenced table/figure images > `full.md` Markdown/HTML/OCR text > `content_list_v2.json` locators.

- Treat `full.md` as the default work entry point, not the highest-authority source.
- Treat referenced `images/` table and figure files as higher authority than the Markdown/HTML/OCR text in `full.md`.
- Treat `content_list_v2.json` as OCR/parser output only. Use it only to locate parsed blocks, image/table crops, PDF pages, or coordinates; never use it as a field-value source or cross-validation source.
- Fall back to images or rendered PDF pages when `full.md` is noisy, incomplete, unreadable, or contradicted by higher-authority evidence.

## Required Inputs

The parent or caller must provide these extraction inputs:

- `paper_id`
- `paper_pdf_path`: path to the owned PDF
- `rawdata_status`: `prepared`, `unavailable`, or `invalid`
- `rawdata_dir`: prepared rawdata directory, or `unavailable`
- `full_md_path`: `<rawdata_dir>/full.md`, or `unavailable`
- `images_dir`: `<rawdata_dir>/images`, or `unavailable`
- `content_list_path`: `<rawdata_dir>/content_list_v2.json`, or `unavailable`
- `temp_json_host_path`: the one JSON file to write

The parent or caller must provide these operational inputs when validation or sandbox-only arithmetic is required:

- `temp_json_workspace_path`: sandbox-visible JSON path for validation
- `sandbox_command_prefix`: command prefix that runs a child-skill script inside the parent-owned sandbox
- `validation_command`: exact validator command to run after writing JSON

Do not search unrelated directories to infer missing rawdata. If `rawdata_status=prepared`, the provided rawdata paths must be usable or this is an `input_contract_failure`. If `rawdata_status=unavailable` or `invalid`, use PDF fallback only when `paper_pdf_path` is usable.

## Boundaries

- Process exactly one paper.
- Read only the caller-provided owned rawdata bundle, owned PDF, and this skill's referenced resources/scripts.
- Read the owned `full.md` and referenced `images/` by default when `rawdata_status=prepared`, then the owned PDF only as fallback or conflict resolver.
- Read `content_list_v2.json` only for locating parsed/PDF blocks during repair, fallback, or debugging; do not treat it as extraction evidence, a data source, or cross-validation evidence.
- Write exactly one JSON file to `temp_json_host_path`.
- Write no secondary extraction artifacts.
- Never write directly to final published output.
- Do not inspect prior outputs, unrelated papers, or `runs/` to infer schema or extraction policy.
- Run sandbox-only helpers only through the parent-provided sandbox command prefix.
- Do not read `scripts/validate_single_output.py` during normal extraction. Run it only as the validator after the JSON is written.

## Workflow

1. Read `references/extraction-rules.md`, `references/fc-basis-rules.md`, and `references/JSON_contract.md`; view `references/section_shapes.jpg` before assigning section groups or `r0`.
2. Verify the caller-provided input contract.
   - If `rawdata_status=prepared`, confirm `full_md_path`, `images_dir`, and `content_list_path` refer to the owned rawdata bundle.
   - If prepared rawdata paths are missing or unusable, stop with `input_contract_failure`.
   - If `rawdata_status=unavailable` or `invalid`, do not search for a replacement rawdata bundle; use PDF fallback only when the owned PDF is usable.
3. Collect evidence using `Source Handling`: start from usable `full.md`, open only relevant referenced images, and use PDF rendering only for fallback or conflict resolution.
4. Apply `references/extraction-rules.md` for target scope, required fields, geometry/eccentricity/material/loading/condition rules, source/numeric rules, and invalid or failed extraction handling.
5. Apply `references/fc-basis-rules.md` when resolving `fco` and `fc_type`.
6. Use `references/section_shapes.jpg` before assigning section groups or `r0`.
7. Use `scripts/safe_calc.py` through `sandbox_command_prefix` for every unit conversion or derived value.
8. Apply `references/JSON_contract.md` for JSON shape, allowed keys, inheritance, notes, numeric precision, normalized values, and validation-equivalent writing rules.
9. Write one JSON file to `temp_json_host_path`, then validate it through `temp_json_workspace_path` with `validation_command`.
10. If validation fails for a documented JSON/data rule, repair the same JSON once and rerun the same validation command. If sandbox execution fails or the validator enforces an undocumented rule, stop with the matching structured status below.

## Validation Command

Run the parent-provided `validation_command` exactly as given. Do not reconstruct worktree paths, mount paths, or validator arguments from memory.

Warnings alone are not validator failure. If you edit the JSON after any validation attempt, rerun the same validator command before returning.

When the parent requests structured status, use:

- `success`: JSON written and validation passed
- `input_contract_failure`: caller-provided paths, rawdata status, output path, sandbox prefix, or validation command are missing or unusable
- `extraction_failure`: the owned sources are readable but insufficient for a defensible extraction
- `validation_failure`: documented child-skill validation/data issues remain after one repair
- `sandbox_failure`: parent-owned sandbox path, mount, startup, or execution failure
- `documentation_validator_mismatch`: validator enforces a rule not documented in `references/JSON_contract.md`
