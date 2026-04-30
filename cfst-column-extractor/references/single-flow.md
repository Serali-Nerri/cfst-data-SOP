# Single-Paper Worker Flow V2.3

Use this file as the worker execution contract for one paper.

Section map:

- `## 1-3`: enforce worker scope, required inputs, and execution order.
- `## 4-5`: apply validity and ordinary-CFST gates.
- `## 6-10`: resolve setup figures, apply Markdown/images/PDF evidence order, build shared context, and preserve numeric and evidence traces.
- `## 11-12`: enforce validation expectations and final output goals.

## 1. Worker Contract

- process exactly one paper PDF
- treat the parent-supplied worker brief, `SKILL.md`, this file, and `references/extraction-rules.md` as the complete worker contract
- read the owned evidence bundle using this default order: usable `full.md` first, referenced `images/` on demand, original PDF as fallback and visual authority for conflicts
- for evidence tables, always compare the `full.md` HTML table with the corresponding table image when that image is available; the table image or rendered PDF page overrides OCR/HTML text for values, units, symbols, row grouping, merged cells, and footnotes
- do not read `content_list_v2.json` by default during extraction; use it only for preprocessing/repair tasks such as regenerating crops, fixing Markdown image links, locating blocks, or debugging parser artifacts
- run sandbox-only helpers only through the parent-provided `worker_sandbox.py` command
- `scripts/safe_calc.py` and `scripts/validate_single_output.py` require `CFST_SANDBOX=1`; do not call them directly from the parent shell
- read only the owned paper PDF, owned rawdata files needed for extraction (`full.md` and referenced `images/`), `SKILL.md`, and the two worker references by default
- do not read `runs/`, prior outputs, or `scripts/` to infer schema, validation, or path rules
- when the parent provides both `temp_json_host_path` and `temp_json_workspace_path`, write the JSON on disk to `temp_json_host_path`; the workspace path is the sandbox-visible alias of that same file
- never create or rely on a worktree-local relative `runs/...` JSON path
- before building the final JSON, prepare one structured extraction draft at `output/tmp/<paper_id>/_scratch/extraction_draft.yaml`; do not write a second JSON artifact on disk
- if a concrete runtime blocker remains unresolved after following the documented command, you may inspect the one named helper script involved and report that you did so
- write only to the worker-local temp directory
- never write directly to final published output
- treat repository as non-exclusive runtime; other workers may change unrelated files concurrently
- do not edit, revert, or publish outside declared worker ownership

## 2. Required Input Layout

The worker receives:

- `paper_id`: owned paper id
- `worktree_path`: worker-local worktree root for sandbox execution
- `paper_pdf_path`: absolute path to the PDF file on the host filesystem — use this path when calling `pdf_info`, `pdf_text`, `pdf_montage`, and `pdf_pages` MCP tools
- `paper_pdf_relpath`: relative path to the PDF file under the worktree root — use this path in sandbox commands (`--paper-dir-relpath`)
- `output_dir`: worker-local output directory inside the worktree
- `output_host_path`: host-backed directory bound into `output_dir`
- `temp_json_workspace_path`: sandbox-visible JSON path inside `output_dir`
- `temp_json_host_path`: host-backed JSON path that must be written on disk

The parent may also provide optional evidence paths:

- `rawdata_dir`: directory containing the parsed paper package
- `full_md_path`: explicit path to `full.md`
- `images_dir`: directory containing images referenced by `full.md`

If those optional paths are absent, infer them only from the parent brief or obvious owned-paper rawdata path when available. If no rawdata bundle is available, continue with PDF-only fallback rather than failing solely because `full.md` is absent.

These fields, plus the parent brief, `SKILL.md`, and the two worker references, should be enough to execute the paper without reading extra scripts or repository files for hidden rules.

When `full.md` is usable, it is the default narrative/table/caption/image-link index. Referenced images are opened on demand for table verification, setup/loading figures, geometry, materials, results, and other extraction-critical evidence. The original PDF remains the fallback and conflict resolver. `content_list_v2.json` is not an extraction evidence source by default; use it only when repairing or auditing the parsed rawdata package.

Long paper filenames are allowed and do not need to be renamed.

If the PDF file does not exist at the given path or cannot be read by the MCP tool, fail fast and report the missing or unreadable file.

## 3. Mandatory Execution Order

1. Read `references/extraction-rules.md` and this file.
2. Verify the paper PDF exists at the given path.
3. Locate the owned rawdata bundle when available.
   - prefer parent-supplied `full_md_path`, `images_dir`, and `rawdata_dir`
   - otherwise infer only from the owned paper path or parent brief when the match is unambiguous
   - do not inspect other papers' rawdata directories
4. Decide the evidence path before extraction.
   - use Markdown-first mode when `full.md` is present, readable, and can be separated reliably from unrelated article content
   - use PDF fallback mode when `full.md` is missing, unreadable, garbled, critical sections are absent, or cross-article contamination cannot be separated confidently
   - use `content_list_v2.json` only for rawdata repair/debugging, not as default LLM evidence
5. In Markdown-first mode, read `full.md` before rendering PDF pages.
   - use it to identify title, authors, specimen tables, result tables, materials, notation, setup/loading figures, figure captions, table captions, table footnotes, and image references
   - ignore clearly unrelated appended article sections; if the article boundary is uncertain, switch to PDF fallback for affected evidence
6. Open referenced images only when they are extraction-critical.
   - always open the table image paired with any HTML table used as specimen, material, geometry, or results evidence
   - open setup/loading, geometry, and failure-mode figures when they affect `loading_mode`, boundary condition, specimen dimensions, or ordinary-gate decisions
   - do not scan all files under `images/` just because they exist
7. For each evidence table, perform table dual-reading.
   - read the HTML table in `full.md` for structure and searchable text
   - read the corresponding semantic table image under or near the table caption for visual confirmation
   - preserve table footnotes and notes under the table when they define units, symbols, row groups, averages, concrete-strength basis, or exceptions
   - if HTML and image disagree, use the table image or rendered PDF page and record the conflict in `source_evidence` or scratch notes
8. Render the original PDF when any critical evidence is missing, cropped, ambiguous, or conflicting.
   - call `pdf_info` to get total page metadata when PDF fallback or page localization is needed
   - call `pdf_text` for page navigation and keyword search, not as the final source for table values
   - prefer `include_pages=false` when you only need metadata, `cache_path`, and optional page-hit metadata
   - use `preview_pages` only when you need a small inline preview
   - use `match_query` plus `matched_pages_only=true` only when you intentionally want just the matched pages inline
9. Search `full.md` and, when needed, the PDF text index for target evidence:
   - specimen tables: `Table`, `表`, `Specimen`, `试件`
   - material properties: `Material`, `Concrete`, `材料`, `混凝土`, `C30`-`C80`
   - setup/loading figures: `Fig`, `Figure`, `图`, `loading`, `setup`, `test`, `加载`, `装置`
   - paper metadata: title, authors, abstract on page 1 or first Markdown section
10. Build an internal evidence-anchor checklist before extraction:
   - `design_table_page`
   - `results_table_page`
   - `replicate_average_rule_page`
   - `setup_figure_page`
   - `loading_program_page`
   - `concrete_basis_page`
   - `steel_properties_page`
   - `full_md_table_locator`
   - `table_image_path`
   - `setup_image_path`
11. Build a structured extraction draft before final JSON assembly.
   - write exactly one non-canonical scratch file at `output/tmp/<paper_id>/_scratch/extraction_draft.yaml`
   - do not write a second JSON file on disk
   - required sections:
     - `specimen_universe`: list of all kept CFST column specimens with measured values
     - `controls_policy`: notes on non-CFST rows excluded before ordinary tagging
     - `replicate_policy`: notes on grouped-average expansion decisions
     - `shared_context`: paper-wide defaults proposed for schema-v2.3
     - `series_contexts`: per-series shared defaults proposed for schema-v2.3
     - `materials_map`: concrete type, modifiers, steel, and geometry evidence
     - `results_map`: per-specimen ultimate loads from the source table
     - `setup_trace`: loading mode, boundary, and figure evidence
     - `ordinary_decisions`: one entry per specimen — the authoritative ordinary-classification record

   The `ordinary_decisions` section is authoritative. Write it **before** the JSON and keep the JSON exactly consistent with it.

   Required format per specimen entry:

   ```yaml
   ordinary_decisions:
     - label: A-H0
       section_shape: circular
       steel_type: carbon_steel
       concrete_type: high_strength
       loading_pattern: monotonic
       test_temperature: ambient
       loading_regime: static
       durability_conditioning: []
       member_modifiers: []
       material_modifiers: []
       is_ordinary: true
       exclusion_reasons: []
     - label: PF-C1
       section_shape: circular
       steel_type: carbon_steel
       concrete_type: normal
       loading_pattern: monotonic
       test_temperature: post_fire
       loading_regime: static
       durability_conditioning: [fire_exposure]
       member_modifiers: []
       material_modifiers: []
       is_ordinary: false
       exclusion_reasons: [fire_exposure, non_ambient_temperature]
   ```

   Verify `material_modifiers` against the remaining non-ordinary blacklist in `extraction-rules.md` section 2.2 while filling `ordinary_decisions`. Record the specimen-level ordinary-gate inputs in the same record: `section_shape`, `steel_type`, `concrete_type`, `loading_pattern`, `test_temperature`, `loading_regime`, `durability_conditioning`, `member_modifiers`, and `material_modifiers`.

12. Use `pdf_montage` only when it helps compare already-identified PDF pages side by side.
   - montage is for navigation/comparison only, never for final value reading
   - low DPI broad scanning is optional and conditional; if you need it, prefer roughly `150-200 dpi`
13. Call `pdf_pages(paths_only=true)` on identified target pages when PDF visual evidence is needed.
   - use normal single-page reading at about `300 dpi`
   - if a page has small headers, footnotes, merged cells, or symbol ambiguity, rerender that page at higher DPI before reading values
14. Use `view_image` on each needed rawdata image or rendered PDF page. For numeric table values, merged cells, units, symbols, signs, row boundaries, and footnotes, visual table evidence overrides OCR/HTML text.
15. Identify specimen-bearing tables, setup/loading figures, grouped-average notes, and non-CFST control rows from the combined `full.md`, referenced-image, and PDF evidence.
16. Resolve concrete-strength basis evidence from `Materials`, `Specimens`, `Concrete properties`, notation sections, specimen tables, table images, and table footnotes before assigning `fc_basis`. First search for nearby concrete-strength-grade signals such as `C30`, `C40`, `C50`, `C60`, or `C60/75`, then interpret symbols such as `fck`, `fc`, `f'c`, or `Fc`.
17. Run the validity gate.
18. Build the kept CFST column specimen universe for this paper.
   - keep only CFST **column** specimens in the extraction universe
   - exclude beam-columns, joints, frame subassemblies, and non-CFST controls before ordinary tagging
19. Resolve specimen-level environment and conditioning evidence needed for the ordinary-CFST gate.
20. Resolve the setup/loading figure from referenced image evidence when available, otherwise from rendered PDF page evidence.
21. Extract the kept CFST specimen rows from the best available combined evidence; use table/figure images or rendered PDF pages to settle any conflict with HTML/OCR text.
22. When a paper reports grouped average measured capacity for an explicit repeated-specimen group, expand the reported group label `G` into `G-1 ... G-q`, assign that same average `n_exp` to each defensibly identified member row, and mark `group_average_n_exp`.
23. Normalize units and derived values with `scripts/safe_calc.py`.
24. Run the ordinary-CFST specimen-level evaluation.
    - fill the `ordinary_decisions` section in `extraction_draft.yaml` first
    - judge ambient/static/durability-conditioning status per specimen or per explicitly labeled specimen group
    - apply the remaining non-ordinary modifier blacklist from `extraction-rules.md` section 2.2 before committing any `is_ordinary: true` entry
25. Derive schema-v2.3 context layers.
    - promote only truly universal values into top-level `shared_context`
    - promote subgroup-wide values into `series_definitions[*].shared_context`
    - keep exceptions as direct specimen fields or `context_overrides`
    - use `specimen_note` only when a difference cannot be captured structurally
26. Build all kept specimens as full rows in `Group_A` / `Group_B` / `Group_C`.
    - ordinary rows stay in those groups with `is_ordinary=true`
    - non-ordinary rows also stay in those groups with `is_ordinary=false` and non-empty `ordinary_exclusion_reasons`
    - do not create top-level `excluded_specimens`
27. Derive paper-level `is_ordinary_cfst` and `ordinary_filter` summary from the final kept-row set.
    - `ordinary_filter.special_factors` must be the sorted unique paper-level base-concrete tags derived from `ordinary_decisions`
    - allowed values only: `high_strength_concrete`, `lightweight_concrete`, `recycled_aggregate`, `self_consolidating_concrete`, `alkali_activated_concrete`, `geopolymer_concrete`, `expansive_concrete`
28. Build schema-v2.3 JSON from `output/tmp/<paper_id>/_scratch/extraction_draft.yaml` plus the final evidence anchors.
29. Write that JSON on disk to `temp_json_host_path` from the worker brief. Do not create a worktree-local relative `runs/...` JSON path.
30. Validate that same file through `temp_json_workspace_path` with the parent-provided `worker_sandbox.py` command, and pass `--scratch-yaml-path output/tmp/<paper_id>/_scratch/extraction_draft.yaml`.
31. If validation fails for schema, data, or evidence reasons, repair once, overwrite the same host-backed JSON path, and validate once more.
32. If validation fails for path, mount, sandbox startup, or ownership reasons, stop and report the failure; do not relocate the JSON and do not create a second copy elsewhere.

## 4. Validity Gate

Stop as invalid when the paper is:

- FE-only
- theory-only or review-only
- non-column CFST study without recoverable column-specimen data
- no kept CFST column specimen with usable ultimate experimental load data

Grouped average measured capacities do not make a paper invalid by themselves. If the repeated-specimen group membership is explicit enough to map the same reported average to each member row defensibly, keep the paper valid and mark the affected rows with `group_average_n_exp`.

A paper is also valid whenever at least one kept CFST column specimen can be defensibly extracted, even if every kept specimen is later classified as non-ordinary.
Do not mark a paper invalid merely because `ordinary_filter.include_in_dataset` will be false.

For invalid papers:

- `is_valid=false`
- `is_ordinary_cfst=false`
- `shared_context={}`
- `series_definitions=[]`
- empty specimen groups
- non-empty single-line `reason`

## 5. Ordinary-CFST Gate (Specimen-Level)

Even when `is_valid=true`, evaluate the full kept CFST column specimen universe for ordinary-CFST inclusion using the specimen-level model defined in `references/extraction-rules.md` section 2.

The ordinary gate applies only to the kept CFST column specimen universe. Non-CFST controls and non-column members are excluded before this stage and must not be written into `Group_A`, `Group_B`, or `Group_C`.

### Specimen-Level Environment And Conditioning Screen

Judge environmental and conditioning limits per kept specimen or per explicitly labeled specimen group.

- the specimen itself must be ambient-temperature
- the specimen itself must use a static loading regime
- the specimen itself must not be durability-conditioned by fire, corrosion, freeze-thaw, or similar treatment

Papers may mix ordinary controls with non-ordinary conditioned specimens. Do not reject an ambient static control row solely because the paper theme is post-fire, corrosion, freeze-thaw, or another non-ordinary program.

### Per-Specimen Evaluation

- resolve `section_shape`, `steel_type`, `concrete_type`, `loading_pattern`, `test_temperature`, and `loading_regime` per specimen after applying context inheritance
- keep `material_modifiers` explicit in the resolved specimen context, even when the effective value is `[]`
- tag each kept specimen:
  - `is_ordinary = true` with `ordinary_exclusion_reasons = []` when all conditions pass
  - `is_ordinary = false` with non-empty `ordinary_exclusion_reasons` listing each failing condition
- when `is_ordinary=false`, include material-side failure reasons implied by the normalized concrete family or modifier evidence, for example `uhpc`, `reactive_powder`, `fiber_reinforced`, `rubber_concrete`, `polymer_modified`, or `foamed_concrete` when those conditions are present

### Paper-Level Derivation

After the kept specimen universe is tagged, derive paper-level fields:

- `is_ordinary_cfst = true` when at least one row in `Group_A` / `Group_B` / `Group_C` has `is_ordinary=true`
- `ordinary_filter.include_in_dataset = is_ordinary_cfst`
- `ordinary_filter.ordinary_count = count of rows with is_ordinary=true`
- `ordinary_filter.total_count = total kept specimen count across Group_A / Group_B / Group_C`
- `ordinary_filter.special_factors`: sorted unique paper-level base-concrete tags derived from `ordinary_decisions`
- `ordinary_filter.exclusion_reasons`: paper-level exclusion summaries

## 6. Setup Figure Resolution

- identify the setup/loading figure from `full.md` figure captions and referenced images when Markdown-first mode is usable; otherwise identify it from rendered PDF page images
- look for images or pages containing loading apparatus diagrams, test setup schematics, or captions such as `Fig.`, `Figure`, `图`, `loading device`, `test setup`, `加载装置`
- determine loading mode from visual evidence when possible
- if `full.md` references a setup/loading image, open that image before deciding loading mode
- if the referenced setup/loading image is missing, cropped, unclear, or contradicts text, render the original PDF page for confirmation
- do not decide loading mode from text alone when setup image evidence exists
- note the Markdown figure locator and image path; also note the PDF page number when known or when PDF fallback was used

Store the resolved setup trace in:

- `paper_level.loading_mode`
- `paper_level.setup_figure` (with `image_path` set to the referenced image when available, otherwise `null`; set `page` to the PDF page number when known)
- resolved specimen `loading_mode`

## 7. Evidence Reading Order

The worker reads the paper using a Markdown-first, image-on-demand, PDF-fallback approach:

1. Use `full.md` first when present and readable. It is the default source for narrative context, captions, section order, HTML tables, table notes, and image references.
2. Open referenced `images/` only when needed for specimen tables, material/result tables, geometry, setup/loading figures, failure descriptions, or conflict resolution.
3. For tables, read both the HTML table in `full.md` and the paired table image. Treat the HTML table as a structural/search aid and the table image as the visual check.
4. Use the original PDF when Markdown/images are unavailable, incomplete, garbled, visibly cropped, or contradictory.
5. When PDF evidence is needed, `pdf_info` captures total-page metadata, `pdf_text` supports navigation and keyword search, `pdf_montage` compares already-identified pages, `pdf_pages(paths_only=true)` renders target pages, and `view_image` loads individual page images for visual inspection.

Markdown prose may be used for ordinary narrative statements when it is readable and internally consistent. OCR-derived HTML tables remain provisional until checked against their table image or the PDF page.

`content_list_v2.json` is not part of the default evidence packet for LLM extraction. It may be used only for preprocessing or repair: regenerating table/figure crops, fixing Markdown image links, locating parser blocks, or debugging rawdata artifacts.

When `pdf_text` cannot localize the paper reliably, you may do a low-DPI visual sweep to find candidate pages. Treat that sweep as page discovery only. Re-render any page that supplies specimen values, table headers, footnotes, row boundaries, setup figures, or conflicting evidence at normal or high DPI and confirm those values through single-page `view_image`.

For specimen values, units, symbols, signs, row boundaries, merged cells, and table footnotes, the visual source is authoritative: paired table image first, rendered PDF page when needed. If visual evidence and HTML/OCR text conflict, use the visual evidence and document the conflict.

## 8. Context-Building Rules

- use `shared_context` only when a value is explicitly shared by all kept specimens
- if the paper splits into clear specimen series, create `series_definitions`
- if a row differs from its inherited context, prefer `context_overrides`
- if a difference is structured and repeated, prefer a series over repeating overrides
- if a difference is unusual and cannot be normalized cleanly, store it in `specimen_note` and explain it in `source_evidence`
- do not promote a value to `shared_context` or `series_definitions` when the evidence is incomplete or mixed

## 9. Numeric Rules

- every conversion or derivation must use `scripts/safe_calc.py`
- store published JSON numbers in canonical `MPa / mm / kN / %` units
- round to `0.001`
- keep the `fcy150` key present; it may stay `null` when project-level strength normalization is deferred
- `boundary_condition` may be `unknown` or `null` when the paper does not define it defensibly
- `L` means project geometric specimen length, not effective length
- keep eccentricity signs as source evidence shows them
- do not use the sign pattern of `e1` and `e2` alone to exclude a specimen from the ordinary dataset
- recycled concrete rows must preserve `R%` in `r_ratio`
- when the paper does not define `L`, use steel-tube net height only when the figure evidence makes that geometry explicit, and record the derivation
- never infer `L` from boundary-condition assumptions or effective-length formulas

## 10. Evidence Rules

Every specimen row must contain a concise `source_evidence` string.

`source_evidence` must:

- be a non-empty single-line string
- identify the `full.md` table / figure / text locator(s), referenced image path(s), and PDF page(s) when known for each stored value
- state explicitly when `n_exp` is a reported group average rather than an individually measured value
- explain derivations or notation resolutions inline
- explain any visual-vs-OCR conflict that affected a stored value
- explain any important series-level or row-level exception when a row differs from `shared_context`

## 11. Validation Expectations

Validation outcomes fall into two classes:

- schema/data/evidence failures: repair once, overwrite the same temp JSON, and rerun validation once
- path/mount/sandbox failures such as missing JSON at the declared path: report the failure to the parent and stop; do not move the JSON or invent a second output path

Warnings alone are not validator failure. If the validator exits zero with warnings only, the worker may return success unless a warning reflects a clearly recoverable omission that it is already correcting during an error-driven repair pass.
If the worker edits the JSON or scratch YAML after any validation attempt, it must rerun the same validator command before returning.

Validation must reject:

- missing or blank `specimen_label`
- invalid `fc_basis`
- impossible dimensions or strengths
- `is_valid=false` with non-empty specimen groups
- unknown `ordinary_filter.special_factors` or unsorted/duplicated `special_factors`
- axial rows with nonzero eccentricity
- eccentric rows with both eccentricities zero
- non-null `fcy150` values that are non-numeric or non-positive
- `is_ordinary=true` with shapes outside circular / square / rectangular / round-ended
- `is_ordinary=true` with non-carbon steel
- `is_ordinary=true` with concrete types outside normal / high-strength / recycled / lightweight / self-consolidating / alkali-activated / geopolymer / expansive
- `is_ordinary=true` with remaining non-ordinary `material_modifiers`
- `is_ordinary=true` with `loading_pattern != monotonic`
- missing `shared_context` or `series_definitions`
- unresolved inherited context for any kept row
- missing `ordinary_decisions` in scratch YAML, or any scratch/JSON mismatch in labels, ordinary verdicts, gate-input fields, `material_modifiers`, exclusion reasons, or kept-specimen counts
- `is_ordinary_cfst=true` but no specimen has `is_ordinary=true`
- `is_ordinary_cfst=false` but some specimen has `is_ordinary=true`
- `ordinary_filter.ordinary_count` mismatch with actual count of ordinary rows
- `ordinary_filter.total_count` mismatch with actual kept-row count
- duplicate specimen labels

## 12. Final Output Goal

The single-paper JSON should be:

- traceable
- physically plausible
- ordinary-filter aware
- normalized with shared context where defensible
- canonical for downstream project-specific processing
