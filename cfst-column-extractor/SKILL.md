---
name: cfst-column-extractor
description: Extract one experimental CFST column paper into schema-v2.3 JSON with image-first PDF reading, shared_context, series_definitions, specimen-level ordinary tagging, authoritative ordinary_decisions scratch YAML, and validator-backed normalization. Use when Codex needs to extract, repair, validate, or review a single paper's CFST column data, usually inside a worker launched by `cfst-orchestrator`.
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

## Core Workflow

1. Read `references/extraction-rules.md` and `references/single-flow.md`.
2. Verify the owned PDF exists.
3. Read the paper through `pdf_info` → `pdf_text` → optional `pdf_montage` → `pdf_pages(paths_only=true)` → `view_image`.
4. Use the text layer only for page discovery. Read specimen values only from rendered page images.
5. Keep only true CFST column specimens. Exclude beam-columns, joints, frames, non-column members, and steel-only controls before ordinary tagging.
6. Build exactly one scratch YAML at `output/tmp/<paper_id>/_scratch/extraction_draft.yaml`, then build exactly one JSON at `temp_json_host_path`.
7. Use `shared_context` only for values truly shared by all kept rows. Use `series_definitions`, `context_overrides`, or direct row fields for mixed evidence.
8. Keep ordinary and non-ordinary kept specimens together in `Group_A` / `Group_B` / `Group_C`; distinguish them with `is_ordinary` and `ordinary_exclusion_reasons`.
9. Use the parent-provided sandbox command to validate the same JSON through `temp_json_workspace_path`. If validation fails for schema, data, or evidence reasons, repair once and rerun the same validator command.

## Use These Resources

- `references/extraction-rules.md`: scope rules, ordinary gate, schema-v2.3 shape, shared-context rules, evidence rules, and numeric constraints
- `references/single-flow.md`: one-paper execution order, required input layout, scratch YAML structure, and validation expectations
- `scripts/safe_calc.py`: sandbox-only arithmetic helper for conversions and derived values
- `scripts/validate_single_output.py`: sandbox-only validator for the final JSON plus authoritative scratch YAML
