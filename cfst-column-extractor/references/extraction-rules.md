# CFST Extraction Rules V2.3

Use this file as the extraction source of truth for one paper.

Section map:

- `## 1. Target Scope`: decide whether the paper is usable and whether a specimen is in scope at all.
- `## 2. Ordinary-CFST Gate`: tag each kept CFST column specimen as ordinary or non-ordinary.
- `## 3-7`: build the schema-v2.3 JSON shape, shared context, series context, and specimen rows.
- `## 8-12`: apply evidence, loading, numeric, length, and invalid-output rules.

## 1. Target Scope

This workflow is for experimental CFST **column** papers that can support a unified dataset for ultimate axial or eccentric compression resistance.

Keep a specimen only when the tested member itself is a CFST column specimen, including stub columns, short columns, slender columns, and long columns.

Exclude before extraction:

- beam-columns
- beam specimens
- joints / beam-column joints
- frame or subassembly tests
- connection tests
- wall, pier, or non-column members
- papers where CFST columns appear only as surrounding context and no separable column-specimen data can be recovered
- hollow steel tube / bare steel tube / empty steel tube / steel-only controls without concrete infill

A paper is `is_valid=true` when the workflow can keep at least one extractable CFST column specimen and all are true:

- the research object includes CFST columns or stub columns
- the paper contains physical specimen test evidence
- at least one kept CFST column specimen has usable specimen-level experimental capacity data
- the kept specimen universe is axial compression, eccentric compression, or a clearly separable mixture of those two modes

A paper may remain `is_valid=true` even when every kept CFST column specimen is non-ordinary. Ordinary-dataset inclusion is decided later at the specimen level and must not be used to invalidate an otherwise extractable paper.

Grouped average measured capacities are still usable specimen-level experimental capacity data when the paper explicitly defines the repeated-specimen group membership, or gives enough specimen-count / parameter-set mapping to assign the same reported average to each member specimen row without fabricating group composition.
In that case, store the same `n_exp` on each member row, mark each affected specimen with `quality_flags += ["group_average_n_exp"]`, and make `source_evidence` state clearly that the value is a group average rather than an individually measured row value.
If a paper reports only grouped averages but the member-to-row mapping is not defensibly recoverable, those loads are not usable specimen-level capacity data.

### 1.1 Repeated-Specimen Group-Average Expansion

When a design/specimen table states that a reported group has `quantity = q`, but the results table reports only one average capacity row for that same group:

- treat the paper's printed identifier as the reported group label, not yet as the final unique specimen label
- expand the group into `q` specimen rows
- use the canonical naming rule `G-1`, `G-2`, ..., `G-q` where `G` is the paper's reported group label
- when available in the schema, set `reported_group_label = G` and `replicate_index = 1..q` on the expanded rows
- copy the shared design/material fields to each member row
- assign the same reported average `n_exp` to each member row
- mark every expanded row with `quality_flags += ["group_average_n_exp"]`
- make `source_evidence` explicitly say that the stored `n_exp` is a reported group average and cite both the member-count source and the result-table source
- compute `paper_level.expected_specimen_count` from the expanded member count, not from the number of reported result-table rows

Do not improvise alternative suffix styles such as `a/b`, `#1/#2`, or repeated identical labels. If defensible group membership still cannot be recovered, fail extraction instead of fabricating member rows.

## 2. Ordinary-CFST Gate

The ordinary gate uses specimen-level evaluation over the kept CFST column specimen universe. Evaluate every kept specimen individually as ordinary or non-ordinary before final JSON assembly.

In schema-v2.3, **all kept CFST column specimens remain as full rows** in `Group_A`, `Group_B`, or `Group_C`. Use `is_ordinary` plus `ordinary_exclusion_reasons` to distinguish ordinary and non-ordinary rows. There is no top-level `excluded_specimens` field in v2.3.

The paper-level `is_ordinary_cfst` is derived: `true` when the paper contains at least one ordinary specimen row kept in `Group_A` / `Group_B` / `Group_C`, `false` otherwise.

### 2.1 Specimen-Level Environment And Conditioning Screen

Environmental and conditioning limits are judged per kept specimen, not by whole-paper theme.

A specimen may be `is_ordinary=true` only when its own row/group evidence shows all of:

- ambient-temperature testing for that specimen
- static loading regime for that specimen
- no durability conditioning applied to that specimen (fire exposure, corrosion conditioning, freeze-thaw, or similar)

Papers may mix ordinary control specimens with non-ordinary treated specimens. Do not reject an ambient static control row solely because the paper also studies post-fire, corrosion, freeze-thaw, or other non-ordinary companion specimens.

### 2.2 Per-Specimen Evaluation

Use two separate fields to classify concrete:

- `concrete_type`: primary concrete family — `normal`, `high_strength`, `recycled`, `lightweight`, `self_consolidating`, `alkali_activated`, `geopolymer`, `expansive`, `uhpc`, `other`, `unknown`
- `material_modifiers`: additional subtype tags, secondary refinements, admixture-driven functions, or remaining non-ordinary material systems as a list of strings; use `[]` for plain concrete

Examples:

- Fly-ash geopolymer concrete: `concrete_type=geopolymer` + `material_modifiers=["fly_ash_geopolymer"]`
- Slag-based alkali-activated concrete: `concrete_type=alkali_activated` + `material_modifiers=["alkali_activated_slag"]`
- High-strength expansive concrete: `concrete_type=high_strength` + `material_modifiers=["expansive_concrete", "type_k_expansive"]`
- Recycled rubber concrete: `concrete_type=recycled` + `material_modifiers=["rubber_concrete"]`
- Plain high-strength concrete: `concrete_type=high_strength` + `material_modifiers=[]`

After the specimen-level environment and conditioning screen passes for that specimen, a specimen is `is_ordinary=true` only when all hold:

- `section_shape` is one of `circular`, `square`, `rectangular`, `round-ended`
- `steel_type = carbon_steel`
- `concrete_type` is one of `normal`, `high_strength`, `recycled`, `lightweight`, `self_consolidating`, `alkali_activated`, `geopolymer`, `expansive`
- `material_modifiers` is empty or contains no remaining non-ordinary modifier
- `loading_pattern = monotonic`
- compression mode is axial or eccentric
- no strengthening, no added confinement device, no stiffener that changes the basic member system
- recycled aggregate concrete has explicit `R%` recorded in `r_ratio`

Remaining non-ordinary `material_modifiers` — any of these makes the specimen non-ordinary regardless of `concrete_type`:

- `rubber_concrete`
- `reactive_powder`
- `fiber_reinforced`
- `polymer_modified`
- `foamed_concrete`
- `other_modified_concrete`

Ordinary-compatible family tags may appear in `material_modifiers` without disqualifying the row, provided the other ordinary-gate conditions pass. Normalize them as follows:

- alkali-activated family tags: `alkali_activated`, `alkali_activated_slag`, `alkali_activated_fly_ash`, `alkali_activated_metakaolin`, `alkali_activated_calcined_clay`, `alkali_activated_natural_pozzolan`, `alkali_activated_blend`, `alkali_activated_hybrid`
- geopolymer family tags: `geopolymer`, `fly_ash_geopolymer`, `slag_geopolymer`, `metakaolin_geopolymer`, `calcined_clay_geopolymer`, `natural_pozzolan_geopolymer`, `blended_geopolymer`
- expansive family tags: `expansive_concrete`, `shrinkage_compensating_concrete`, `self_stressing_concrete`, `type_k_expansive`, `type_m_expansive`, `type_s_expansive`, `calcium_sulfoaluminate_expansive`, `cao_expansive`, `mgo_expansive`, `composite_expansive`

High-risk non-ordinary aliases must be normalized aggressively even when the paper does not use the canonical tag form. At minimum:

- RPC / reactive powder / reactive powder concrete / UHRPC → `reactive_powder`
- steel fiber / steel fibre / SFRC / fiber-reinforced / fibre-reinforced → `fiber_reinforced`
- crumb rubber / rubberized / rubberised concrete → `rubber_concrete`
- polymer-modified / latex-modified / epoxy-modified concrete → `polymer_modified`
- foamed / foam concrete → `foamed_concrete`

When the paper explicitly identifies geopolymer or alkali-activated concrete as the primary reported family, prefer `concrete_type=geopolymer` or `concrete_type=alkali_activated` instead of encoding the whole family only as a modifier. Use `material_modifiers` to preserve precursor, binder, or expansive-agent subtype detail.

Do not infer ordinary status from `concrete_type=high_strength`, `concrete_type=recycled`, `concrete_type=lightweight`, `concrete_type=self_consolidating`, `concrete_type=alkali_activated`, `concrete_type=geopolymer`, or `concrete_type=expansive` alone. Always separately scan for remaining non-ordinary modifier evidence.

### 2.2.1 Control Specimens And Strengthening Mapping

Before building `Group_A`, `Group_B`, or `Group_C`, first partition the paper's tested specimens into:

- CFST column specimens that belong in the extraction output
- non-CFST controls that must be excluded from specimen output entirely

Exclude non-CFST controls before ordinary tagging. Typical exclusions:

- hollow steel tube
- bare steel tube
- empty steel tube
- plain steel control
- steel-only comparison specimens without concrete infill

For the kept CFST column specimens, use these ordinary-exclusion mappings:

- external jackets, welded cover plates, bonded reinforcement, section-enlarging plates, and internal or welded stiffeners that materially change the member system: `strengthened_section`
- rings, clamps, ties, hoops, or other added confinement devices whose primary role is extra confinement rather than restoring the base CFST section: `confinement_device`
- internal U-shaped stiffeners, 拉结件, 加劲肋, or similar added steel details that materially alter the wall-restraint mechanism: default to `strengthened_section` unless the paper clearly defines them as a separate confinement device

When the paper's wording is ambiguous, prefer a conservative non-ordinary classification over silently treating the specimen as ordinary, and explain the decision in `source_evidence`.

### 2.2.2 Concrete Classification Priority

When classifying concrete for `concrete_type` and `material_modifiers`, follow this priority:

1. Determine the primary concrete family (`normal` / `high_strength` / `recycled` / `lightweight` / `self_consolidating` / `alkali_activated` / `geopolymer` / `expansive` / `uhpc` / `other`).
2. Separately scan for family and subtype evidence: 碱激发 / alkali-activated / slag-activated / fly-ash-activated / metakaolin-activated / calcined-clay-activated / 地聚物 / geopolymer / fly ash geopolymer / slag geopolymer / 膨胀混凝土 / expansive / 补偿收缩 / shrinkage-compensating / 自应力 / self-stressing / Type K / Type M / Type S / CSA / CaO / MgO / 橡胶颗粒 / RPC / 纤维 / 聚合物改性 / 泡沫混凝土 / etc.
3. If the paper explicitly treats alkali-activated concrete, geopolymer concrete, or expansive concrete as the primary reported family for that row, prefer the corresponding `concrete_type`.
4. Record normalized subtype and secondary family detail in `material_modifiers`.
5. Only the remaining non-ordinary modifiers listed in section 2.2 disqualify an otherwise ordinary specimen.
6. For mixed papers, classify specimen by specimen, not at paper level.

### 2.2.3 Zero-Dosage Control Specimen Exception

If a paper contains modified mixes plus an explicit plain-control mix with zero modifier dosage, the control row may be ordinary provided its own row carries no active modifier in that row. Set `material_modifiers=[]` and `is_ordinary=true` for that control row, and explain the zero-dosage decision in `source_evidence`.

### 2.3 Specimen Exclusion Tagging

When a kept CFST column specimen fails the specimen-level ordinary screen, keep it in the output and record each failing condition in `ordinary_exclusion_reasons`. Common reasons:

- `stainless_steel`
- `uhpc`
- `cyclic_loading`
- `repeated_loading`
- `non_ambient_temperature`
- `non_static_loading_regime`
- `fire_exposure`
- `corrosion_conditioning`
- `freeze_thaw_conditioning`
- `non_ordinary_shape`
- `confinement_device`
- `strengthened_section`
- `rubber_concrete`
- `reactive_powder`
- `fiber_reinforced`
- `polymer_modified`
- `foamed_concrete`
- `other_modified_concrete`

### 2.4 Paper-Level Derivation

After the kept CFST column specimen universe is tagged:

- `is_ordinary_cfst = any(specimen.is_ordinary for specimen in all_group_rows)`
- `ordinary_filter.include_in_dataset = is_ordinary_cfst`
- `ordinary_filter.ordinary_count = count of rows with is_ordinary=true`
- `ordinary_filter.total_count = total kept CFST column specimen count across Group_A / Group_B / Group_C`
- `ordinary_filter.special_factors`: sorted unique paper-level base-concrete tags derived from the kept specimen universe. Allowed values only:
  - `high_strength_concrete`
  - `lightweight_concrete`
  - `recycled_aggregate`
  - `self_consolidating_concrete`
  - `alkali_activated_concrete`
  - `geopolymer_concrete`
  - `expansive_concrete`
  Collapse specimen-level subtype tags such as `alkali_activated_slag`, `fly_ash_geopolymer`, or `type_k_expansive` to these supported paper-level family tags rather than copying subtype strings directly into `special_factors`.
- `ordinary_filter.exclusion_reasons`: paper-level exclusion summaries

## 3. Top-Level JSON Shape

Required top-level keys:

- `schema_version`
- `paper_id`
- `is_valid`
- `is_ordinary_cfst`
- `reason`
- `ordinary_filter`
- `ref_info`
- `paper_level`
- `shared_context`
- `series_definitions`
- `Group_A`
- `Group_B`
- `Group_C`

Recommended `schema_version` value:

- `cfst-paper-extractor-v2.3`

Keep this identifier stable for schema compatibility. It is a dataset/schema version string, not the parent skill name.

Published `output/<paper_id>.json` files are the canonical dataset artifact. Any downstream tabular conversion is project-specific and outside this skill's canonical schema.

Use the schema description below as the worker's example source of truth. Do not inspect `runs/`, prior outputs, or unrelated papers to infer JSON shape.

### 3.1 Canonical Skeleton

```json
{
  "schema_version": "cfst-paper-extractor-v2.3",
  "paper_id": "A1-1",
  "is_valid": true,
  "is_ordinary_cfst": true,
  "reason": "One-line paper usability summary.",
  "ordinary_filter": {
    "include_in_dataset": true,
    "ordinary_count": 1,
    "total_count": 2,
    "special_factors": [],
    "exclusion_reasons": ["cyclic_loading"]
  },
  "ref_info": {
    "title": "Paper title",
    "authors": ["Author 1", "Author 2"],
    "journal": "Journal name",
    "year": 2005,
    "citation_tag": "[A1-1]",
    "doi": null,
    "language": "zh"
  },
  "paper_level": {
    "loading_mode": "axial",
    "boundary_condition": "unknown",
    "test_temperature": "ambient",
    "loading_regime": "static",
    "loading_pattern": "monotonic",
    "setup_figure": {
      "figure_id": null,
      "image_path": null,
      "page": null
    },
    "expected_specimen_count": 2,
    "notes": []
  },
  "shared_context": {
    "section_shape": "circular",
    "loading_mode": "axial",
    "loading_pattern": "monotonic",
    "boundary_condition": "unknown",
    "fc_type": "Cube 150",
    "fc_basis": "cube",
    "steel_type": "carbon_steel",
    "concrete_type": "normal",
    "material_modifiers": []
  },
  "series_definitions": [
    {
      "series_id": "S-cyclic",
      "description": "Cyclic loading subgroup.",
      "shared_context": {
        "loading_pattern": "cyclic"
      },
      "notes": []
    }
  ],
  "Group_A": [],
  "Group_B": [
    {
      "ref_no": "",
      "specimen_label": "SC-1",
      "reported_group_label": null,
      "replicate_index": null,
      "series_id": null,
      "context_overrides": {},
      "is_ordinary": true,
      "ordinary_exclusion_reasons": [],
      "fc_value": 30.5,
      "fy": 345.0,
      "fcy150": null,
      "r_ratio": 0.0,
      "b": 165.0,
      "h": 165.0,
      "t": 4.0,
      "r0": 82.5,
      "L": 495.0,
      "e1": 0.0,
      "e2": 0.0,
      "n_exp": 1650.0,
      "source_evidence": "Page 9 Table 3 row SC-1 gives axial peak load 1650 kN; Page 4 Table 2 gives CHS165×4 geometry; Page 3 Table 1 gives 30.5 MPa cube strength; Page 5 Fig. 5 gives axial setup."
    },
    {
      "ref_no": "",
      "specimen_label": "SC-C1",
      "series_id": "S-cyclic",
      "context_overrides": {},
      "is_ordinary": false,
      "ordinary_exclusion_reasons": ["cyclic_loading"],
      "fc_value": 30.5,
      "fy": 345.0,
      "fcy150": null,
      "r_ratio": 0.0,
      "b": 165.0,
      "h": 165.0,
      "t": 4.0,
      "r0": 82.5,
      "L": 495.0,
      "e1": 0.0,
      "e2": 0.0,
      "n_exp": 1490.0,
      "source_evidence": "Page 9 Table 3 row SC-C1 gives cyclic peak load 1490 kN; Page 6 Fig. 6 and Page 7 loading program define cyclic loading for this subgroup."
    }
  ],
  "Group_C": []
}
```

## 4. Context Normalization

Schema-v2.3 reduces repeated categorical fields by using three levels of context.

### 4.1 Context Resolution Order

Resolve inherit-able specimen context in this order:

1. direct specimen field
2. `context_overrides` on the specimen row
3. `series_definitions[*].shared_context` referenced by `series_id`
4. top-level `shared_context`
5. `paper_level` fallback, but only for `loading_mode`, `loading_pattern`, `boundary_condition`, `test_temperature`, and `loading_regime`

For `section_shape`, `Group_B` may default to `circular` when no more specific value is needed.

### 4.2 When To Use Each Layer

- Use top-level `shared_context` only when the value applies to **all kept CFST column specimens** in the paper.
- Use `series_definitions` when a subset of specimens shares a different context.
- Use direct specimen fields or `context_overrides` only for exceptions.
- Prefer structured overrides over free-text notes.
- Use `specimen_note` only when the difference cannot be captured cleanly with structured keys.

### 4.3 Supported Shared/Override Context Keys

These keys may appear in `shared_context`, `series_definitions[*].shared_context`, or `context_overrides`:

- `section_shape`
- `loading_mode`
- `loading_pattern`
- `boundary_condition`
- `fc_type`
- `fc_basis`
- `steel_type`
- `concrete_type`
- `material_modifiers`
- `test_temperature`
- `loading_regime`

## 5. Group Mapping

- `Group_A`: square / rectangular
  - `b`: outer width
  - `h`: outer depth
- `Group_B`: circular
  - `b = h = D`
  - `r0 = h / 2`
- `Group_C`: elliptical / round-ended / obround
  - `b`: major axis
  - `h`: minor axis
  - `b >= h`
  - `r0 = h / 2`

Unlike v1, `Group_A.r0` is not forced to zero. Keep a nonzero corner radius when the paper provides it or when the section is clearly rounded-corner rectangular.

## 6. Required Top-Level Objects

### 6.1 `ordinary_filter`

Required keys:

- `include_in_dataset`: boolean (true when at least one specimen is ordinary)
- `ordinary_count`: integer (count of specimens with `is_ordinary=true`)
- `total_count`: integer (total kept CFST column specimen count across Group_A / Group_B / Group_C)
- `special_factors`: sorted unique list drawn only from `high_strength_concrete`, `lightweight_concrete`, `recycled_aggregate`, `self_consolidating_concrete`, `alkali_activated_concrete`, `geopolymer_concrete`, and `expansive_concrete`
- `exclusion_reasons`: list of strings

### 6.2 `ref_info`

Required keys:

- `title`
- `authors`
- `journal`
- `year`
- `citation_tag`

Optional:

- `doi`
- `language`

### 6.3 `paper_level`

Required keys:

- `loading_mode`
- `boundary_condition`
- `test_temperature`
- `loading_regime`
- `loading_pattern`
- `setup_figure`
- `expected_specimen_count`
- `notes`

`paper_level.expected_specimen_count` must count the full kept CFST column specimen universe represented in the final JSON.

`loading_mode` allowed values:

- `axial`
- `eccentric`
- `mixed`
- `unknown`

`test_temperature` allowed values:

- `ambient`
- `elevated`
- `post_fire`
- `unknown`

`loading_regime` allowed values:

- `static`
- `dynamic`
- `impact`
- `unknown`

`loading_pattern` allowed values at paper level:

- `monotonic`
- `cyclic`
- `repeated`
- `mixed`
- `unknown`

### 6.4 `shared_context`

`shared_context` is required and must be an object, but it may be empty when the paper is invalid or when no defensible all-specimen default exists.

Use it for paper-wide defaults that would otherwise repeat on every row.

### 6.5 `series_definitions`

`series_definitions` is required and must be a list.

Each series object may contain:

- `series_id` (required, unique)
- `shared_context` (required object)
- `description` (optional string)
- `notes` (optional string list)

## 7. Required Output Row Fields

Every kept specimen row in `Group_A`, `Group_B`, or `Group_C` must contain these core keys:

- `ref_no`
- `specimen_label`
- `is_ordinary`
- `ordinary_exclusion_reasons`
- `fc_value`
- `fy`
- `fcy150`
- `r_ratio`
- `b`
- `h`
- `t`
- `r0`
- `L`
- `e1`
- `e2`
- `n_exp`
- `source_evidence`

Optional trace and normalization keys:

- `reported_group_label`
- `replicate_index`
- `quality_flags`
- `series_id`
- `context_overrides`
- `specimen_note`

Optional direct context keys, allowed when the row does **not** inherit them cleanly:

- `section_shape`
- `loading_mode`
- `loading_pattern`
- `boundary_condition`
- `fc_type`
- `fc_basis`
- `steel_type`
- `concrete_type`
- `material_modifiers`

Even when a row omits those direct context keys, the **effective** values must still be resolvable after applying the inheritance order in section 4.

### 7.1 Row Field Semantics

- `ref_no`: fixed empty string `""`
- `specimen_label`: unique, non-empty specimen ID; when expanding a repeated-specimen group average, use the canonical form `reported_group_label-1 ... reported_group_label-q`
- `reported_group_label`: optional original paper label for a repeated-specimen group or original paper row label
- `replicate_index`: optional positive integer replicate index used when one reported group label expands into multiple specimen rows
- `series_id`: optional reference into `series_definitions`
- `context_overrides`: optional object that overrides inherited shared context for this row only
- `specimen_note`: optional last-resort free-text note for distinctions that do not fit the structured schema
- `boundary_condition`: trace metadata for the specimen support/end condition; may be `null` or `unknown`
- `fc_value`: source concrete strength value in MPa
- `fc_type`: source concrete specimen description, for example `Cube 150`, `Cylinder 100x200`, or `Prism 150x150x300`
- `fc_basis`: basis category of `fc_value`; use `prism` for prism / axial-compression concrete-strength systems, not for CFST member loading mode
- `fy`: steel yield strength in MPa
- `fcy150`: normalized 150 mm cylinder compressive strength in MPa; keep the key present, but `null` is allowed during extraction when project-level conversion is deferred
- `material_modifiers`: list of additional concrete subtype / modification tags; use empty list `[]` for plain ordinary concrete; never `null`
- `r_ratio`: recycled aggregate ratio in percent; use `0` for non-recycled concrete
- `b`, `h`, `t`, `r0`, `L`, `e1`, `e2`: numbers stored in mm
- `L`: project geometric specimen length in mm; do not reinterpret it as effective length
- `n_exp`: experimental ultimate load in kN
- `source_evidence`: concise human-readable trace string
- `loading_pattern`: the loading pattern for this specific specimen row (`monotonic`, `cyclic`, `repeated`, or `unknown`) after context resolution
- `is_ordinary`: boolean indicating whether this kept row qualifies for the ordinary CFST dataset
- `ordinary_exclusion_reasons`: empty when `is_ordinary=true`; non-empty when `is_ordinary=false`
- `quality_flags`: optional list of extraction-risk flags such as `group_average_n_exp`, `derived_L`, `unit_converted`, `context_inferred_fc_basis`; omit when empty

For recycled aggregate concrete, `r_ratio` must record the recycled aggregate replacement ratio `R%`.

### 7.2 Effective Context Validation Rules

After inheritance, every row must resolve:

- `section_shape`
- `loading_mode`
- `loading_pattern`
- `boundary_condition`
- `fc_type`
- `fc_basis`
- `steel_type`
- `concrete_type`
- `material_modifiers`
- `test_temperature`
- `loading_regime`

Validator rules apply to the **resolved** values, not only to direct row keys.

## 8. Concrete-Strength Basis Rules

Resolve `fc_basis` using this priority order:

1. explicit statements in `Materials`, `Specimens`, `Concrete properties`, notation sections, specimen tables, and table footnotes
2. explicit specimen/test descriptions such as `150 mm cube`, `100x200 cylinder`, `ASTM C39 cylinder`, `JIS A 1108`, `JIS A 1132`, or prism / axial-compression concrete-strength wording
3. cited design-code or test-standard context, including code-defined grade notation such as Chinese GB/T 50010 `C30` / `C40` / `C50` / `C60` and Eurocode / EN 206 `C60/75`
4. shorthand strength symbols such as `f'c`, `Fc`, `fck`, `fc`, or bare notation whose governing code context is still unresolved

Apply these rules:

- before relying on symbols such as `fck`, `fc`, `f'c`, or `Fc`, first search the same sentence, paragraph, table header, and table footnote for nearby concrete-strength-grade signals such as `C30`, `C40`, `C50`, `C60`, or `C60/75`
- if the source explicitly says `cube`, `150 mm cube`, or equivalent standard cube wording, use `fc_basis = cube`
- if the source explicitly says `cylinder`, gives cylinder dimensions, or cites cylinder-based test standards, use `fc_basis = cylinder`
- if the source explicitly says prism strength, axial compressive strength, or uses the Chinese GB/T 50010 `fck` / `fc` axial-compression system, use `fc_basis = prism`
- in Chinese GB/T 50010-type context, a nearby single-grade `C30` / `C40` / `C50` / `C60`-style notation is a code-defined cube-strength cue and outranks nearby bare `fck` / `fc` symbol usage when the two conflict
- in the same Chinese context, when a reported measured strength value is numerically consistent with the nearby cube-grade system and clearly inconsistent with the prism/axial reading of a nearby `fck` / `fc` symbol, you may resolve `fc_basis = cube`; explain the local notation mismatch explicitly in `source_evidence`
- when both cube and cylinder strengths are reported, store the basis/value that the paper explicitly uses in material parameters, constitutive calculations, or specimen-property tables; cite that decision in `source_evidence`
- if the basis remains unresolved after checking the paper text, cited standards, and table notes, set `fc_basis = unknown`
- when `fc_basis = unknown`, keep `fcy150 = null` unless the paper itself provides a defensible normalized cylinder value
- for context-inferred decisions, make `source_evidence` cite the specific section/table/note and the standard or notation that justified the choice

## 9. Evidence Contract

Each specimen row requires a concise `source_evidence` string.

`source_evidence` must:

- be a non-empty single-line string
- identify the PDF page(s) and table / figure / text locator(s) for each stored value
- state explicitly when `n_exp` is a reported group average rather than an individually measured row value
- explain derivations or notation resolutions inline (for example, unit conversion, `r0 = D/2`, `fck` notation resolved to cube basis)
- explain any important inherited exception when `context_overrides`, `series_id`, or `specimen_note` is needed

Accepted page/locator wording may be English or Chinese. `Page`, `页`, `Table`, `Fig.`, `Figure`, `text`, `section`, `表`, `图`, `正文`, and explicit section forms such as `第2.3节` are all valid locator styles.

When page localization cannot be determined, state the best available locator rather than inventing a page number.

## 10. Loading-Mode Rules

- determine paper-level loading mode from setup-figure evidence when available
- preserve specimen-level loading mode after context resolution in every row
- if specimen `loading_mode = axial`, enforce `e1 = 0` and `e2 = 0`
- if specimen `loading_mode = eccentric`, at least one of `e1`, `e2` must be nonzero
- preserve the original signs of `e1` and `e2`
- `e1` and `e2` may have the same sign or opposite signs; sign alone must not be used to exclude an otherwise ordinary specimen
- mixed papers must still resolve each specimen row to its own loading mode even if `paper_level.loading_mode = mixed`

## 11. Numerical Rules

- use `scripts/safe_calc.py` for every conversion and derived value
- convert stored values to canonical units before writing JSON
- round numeric outputs to `0.001`
- enforce:
  - `fc_value > 0`
  - `fy > 0`
  - `fcy150 > 0` when `fcy150` is populated
  - `b > 0`
  - `h > 0`
  - `t > 0`
  - `L > 0`
  - `n_exp > 0`
  - `0 <= r_ratio <= 100`
- `t` must be strictly smaller than `min(b, h) / 2`
- keep `fcy150 = null` when the project defers strength-basis conversion; do not fabricate it during extraction

A specimen with `is_ordinary=true` must satisfy all of:

- `section_shape in {square, rectangular, circular, round-ended}`
- `steel_type = carbon_steel`
- `concrete_type in {normal, high_strength, recycled, lightweight, self_consolidating, alkali_activated, geopolymer, expansive}`
- `material_modifiers` contains no remaining non-ordinary modifier
- `loading_pattern = monotonic`
- the specimen itself is ambient-temperature, static, and not durability-conditioned

## 12. Length And Invalid Outputs

### 12.1 Length Rule

Determine `L` as the project geometric specimen length with this priority:

1. explicit specimen length in paper text/table/note
2. explicit formula or ratio with clear variable meaning
3. figure-based derivation with explicit geometry evidence, including steel-tube net height when the figure makes that geometry unambiguous

If the paper does not name `L` directly but the specimen/setup figure makes the steel-tube net height derivable, use that geometric length and record the basis in `source_evidence`.

Do not populate `L` when the geometry basis is ambiguous. Do not infer `L` from boundary-condition assumptions or effective-length formulas.

### 12.2 Invalid Paper

If the paper is outside the experimental CFST-column scope, or no extractable kept CFST column specimens remain:

- `is_valid=false`
- `is_ordinary_cfst=false`
- `ordinary_filter.include_in_dataset=false`
- `ref_info` may still contain bibliographic metadata when available
- `shared_context={}`
- `series_definitions=[]`
- `Group_A=[]`, `Group_B=[]`, `Group_C=[]`

### 12.3 Processing Failure

When evidence is insufficient for a defensible extraction:

- stop with a clear failure reason
- do not fabricate row values
- keep intermediate output outside final published output
