---
name: cfst-l-reviewer
description: Use only when explicitly specified by the user; review one paper's pre-extracted CSV L values against the effective-length definition and write a review.md.
---

# CFST L Reviewer

Use this skill for exactly one paper. The goal is to judge whether each `L`
value in a previously extracted CSV still stands under the current
effective-length definition, and to produce a `review.md` (and, when needed, a
companion `<paper_id>_recommended.csv`) documenting the per-specimen verdict.

This skill does **not** re-extract any other field. It only reviews `L`.

## Authority And Resources

Treat this file and these resources as the complete one-paper L-review
contract. The parent or caller provides package paths, output paths, and the
validation command; it does not define review policy.

- `references/effective-length-rules.md`: decision framework for `L`

## Source Handling

Use `full.md` as the work entry point when a usable prepared package is
provided. On conflicts, use this evidence authority order: rendered/source PDF
page > referenced table/figure images > `full.md` Markdown/HTML/OCR text >
`content_list_v2.json` locators.

- Treat `full.md` as the default work entry point, not the highest-authority source.
- Treat referenced `images/` table and figure files as higher authority than the text in `full.md`.
- Treat `content_list_v2.json` as OCR/parser output for locating blocks only; never use it as evidence.
- Fall back to images or rendered PDF pages when `full.md` is noisy, incomplete, or contradicted by higher-authority evidence.

## Required Inputs

The parent or caller must provide:

- `paper_id`
- `package_dir`: prepared package containing `full.md`, `images/`, `content_list_v2.json`, and `<paper_id>.csv`
- `owned_pdf_path`: the package-owned fallback PDF
- `extracted_csv_path`: the previously extracted `<paper_id>.csv`
- `output_review_path`: where `review.md` is written
- `recommended_csv_path`: where `<paper_id>_recommended.csv` is written (only if any specimen is `CHANGE`)
- `validation_command`: exact validator command to run after writing

Use only caller-provided paths. If any required input is missing or unusable,
return `input_contract_failure`.

## Core Principle

- **Anchor every verdict in the paper's own usage.** A verdict must be
  defensible by pointing at what the paper itself does — which length its λ
  formula plugs in, where its FEM boundary is applied, how its setup figure
  defines the unbraced segment, whether a coefficient it gives is a
  boundary-condition K or a moment-distribution k. If no such evidence is
  available, the verdict is `UNDETERMINED`.

## Verdict Definitions

- **OK** — Original `L` matches the value you can defend from the paper's
  evidence under the new definition; or it differs only by inconsequential
  precision / rounding.
- **CHANGE** — Original `L` conflicts with the new definition at the level of
  *which physical length was chosen*, and the evidence is sufficient to name
  the error and propose a corrected `recommended L (mm)`.
- **UNDETERMINED** — Evidence is insufficient to decisively defend either
  `OK` or `CHANGE`. Do not default to either.

## Workflow

1. Read `references/effective-length-rules.md`.
2. Verify the caller-provided input contract.
   - Confirm `package_dir` contains `full.md`, `images/`, `content_list_v2.json`, and `<paper_id>.csv`.
   - Confirm `owned_pdf_path` and `extracted_csv_path` are readable.
   - If any required input is missing or unusable, stop with `input_contract_failure`.
3. Read `extracted_csv_path`; list specimen identifiers, original `L`, and
   relevant geometry fields (b/h/t/r0/e1/e2).
4. Collect evidence using `Source Handling`: start from `<package_dir>/full.md`,
   open only relevant images under `<package_dir>/images/`, and use the PDF for
   fallback or conflict resolution.
5. Determine the **L methodology for this paper**: end-condition family, the
   length source the paper itself uses, and any non-`L` coefficients that must
   be explicitly excluded. Split by group if methodology differs across groups.
6. Apply that methodology to each specimen and assign a verdict; for `CHANGE`,
   record the recommended `L (mm)`.
7. Write `review.md` to `output_review_path` following `Output Format` below.
8. If any specimen verdict is `CHANGE`, also write `recommended_csv_path` with
   the same header as the original CSV and only the `CHANGE` rows (with updated
   `L` values).
9. Run the parent-provided `validation_command`. If validation fails for a
   documented structural rule, repair the same review once and rerun the same
   command.

## Output Format

Write `review.md` in **Chinese**. The five level-2 headers, verdict tokens
(`OK` / `CHANGE` / `UNDETERMINED`), and the summary keys (`reviewed`, `OK`,
`CHANGE`, `UNDETERMINED`) must stay in the exact English form shown below —
they are the validator's structural anchors. All surrounding narrative,
reasons, methodology paragraphs, and table cell prose should be in Chinese.

`review.md` must contain exactly these five level-2 headers, in this order,
with these exact titles:

```
## 1. Source identification
## 2. L methodology for this paper
## 3. Per-specimen review
## 4. Summary
## 5. Recommended replacement
```

Within each section, presentation (table / list / paragraph) is up to you.
Minimum content per section:

- **1. Source identification** — `paper_id`; citation (author / title / journal / year); original CSV filename; specimen count.
- **2. L methodology for this paper** — natural-language paragraph(s) stating end-condition family, the length source the paper itself uses, and any coefficients explicitly excluded from `L`. Split per group if methodology differs.
- **3. Per-specimen review** — covers **every** specimen in the CSV. Each specimen has a verdict from `{OK, CHANGE, UNDETERMINED}` (uppercase) and a short reason. `CHANGE` rows must include a `recommended L (mm)` numeric value.
- **4. Summary** — at least four numeric values: `reviewed`, `OK`, `CHANGE`, `UNDETERMINED`. The three verdicts must sum to `reviewed`. Place each count on the same line as its key (e.g. `reviewed: 27`, `| OK | 22 |`, `- CHANGE = 5`).
- **5. Recommended replacement** — if any `CHANGE` row exists, list affected specimens with `original L` and `recommended L`. If none, write a single line such as `No specimens require change.` The companion CSV at `recommended_csv_path` carries the same rows in machine-readable form.

## Boundaries

- Read only the caller-provided package, owned PDF, and this skill's `references/`.
- Write only `output_review_path` (and `recommended_csv_path` when any verdict is `CHANGE`).
- Intermediate scratch files may be written under the workspace `tmp/` directory.
- Do not modify the input CSV. Do not re-extract any other field.
- Do not inspect prior outputs, unrelated papers, or sibling packages.

## Validation Command

Run the parent-provided `validation_command` exactly as given. Do not
reconstruct paths or arguments from memory.

Warnings alone are not validator failure. If you edit the review after any
validation attempt, rerun the same validator command before returning.

When the parent requests structured status, use:

- `success`: review written and validation passed
- `input_contract_failure`: caller-provided paths or validation command are missing or unusable
- `review_failure`: sources are readable but insufficient to produce any defensible verdict
- `validation_failure`: documented validator issues remain after one repair
- `documentation_validator_mismatch`: validator enforces a rule not documented in this SKILL.md
