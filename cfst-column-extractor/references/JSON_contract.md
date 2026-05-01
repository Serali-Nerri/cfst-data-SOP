# CFST JSON Output Contract

Use `cfst-extraction-schema.json` as the machine-readable schema. This file is
the authoritative human-readable contract for writing CFST extraction JSON.

A JSON file that follows every REQUIRED rule in this document is expected to
pass `scripts/validate_single_output.py --strict-rounding`. The validator is an
execution tool, not an additional policy source. If the validator fails on a rule
not documented here, report a documentation/validator mismatch.

Warnings alone are not validation failure, but agents should avoid documented
warnings when the evidence supports doing so.

## Contents

- Top-Level Shape
- Allowed Keys
- Required Keys And Basic Types
- Valid And Invalid Papers
- Section Groups
- Effective Data And Inheritance
- Required Effective Specimen Data
- Numeric And Rounding Rules
- Section Geometry Rules
- Concrete Strength Type Output
- Material, Loading, And Condition Objects
- Evidence Objects
- Normalized Enumerations
- Quality Flags
- Examples
- Pre-Validation Checklist

## Top-Level Shape

A valid extraction output is one JSON object. Do not add top-level keys outside
`schema_version`, `paper`, and `section_groups`.

```json
{
  "schema_version": "1.0.0",
  "paper": {
    "ref_info": {
      "title": "Paper title",
      "authors": ["Author 1", "Author 2"],
      "journal": "Journal name",
      "year": 2005,
      "doi": null,
      "language": "en"
    },
    "validity": {"is_valid": true, "reason": null},
    "paper_evidence": {
      "source_locations": [
        {"table": null, "figure": null, "section": "Title / abstract", "quote": "Original title and bibliographic text."}
      ],
      "field_evidence": {},
      "description": "Paper-level bibliographic and extraction evidence."
    },
    "paper_shared_defaults": {
      "data": {
        "loading_mode": {"type": "monotonic", "description": null},
        "condition": {"tags": ["normal"], "description": null}
      },
      "evidence": {
        "source_locations": [
          {"table": null, "figure": "Fig. 3", "section": "Test setup", "quote": "Monotonic compression setup."}
        ],
        "field_evidence": {},
        "description": "Loading mode and condition apply to all retained specimens."
      }
    },
    "notes": null
  },
  "section_groups": {
    "square": {"has_data": false, "shared": {}, "specimens": [], "group_notes": null},
    "rectangular": {"has_data": false, "shared": {}, "specimens": [], "group_notes": null},
    "circular": {"has_data": false, "shared": {}, "specimens": [], "group_notes": null},
    "round_ended": {"has_data": false, "shared": {}, "specimens": [], "group_notes": null}
  }
}
```

## Allowed Keys

Objects may contain only the keys listed here. Do not add convenience fields such
as `paper_id`, `xi`, `specimen_count`, `n_calculated`, `source_file`, or `group`
unless they are already one of the allowed keys below.

Top-level object MUST contain exactly:

- `schema_version`
- `paper`
- `section_groups`

`paper` MAY contain only:

- `ref_info`
- `validity`
- `paper_evidence`
- `paper_shared_defaults`
- `notes`

`paper.ref_info` MUST contain exactly:

- `title`
- `authors`
- `journal`
- `year`
- `doi`
- `language`

`paper.validity` MUST contain exactly:

- `is_valid`
- `reason`

`section_groups` MUST contain exactly:

- `square`
- `rectangular`
- `circular`
- `round_ended`

Each section group MAY contain only:

- `has_data`
- `shared`
- `specimens`
- `group_notes`

Each `shared` object MAY contain only:

- `data`
- `evidence`

Each specimen MAY contain only:

- `specimen_id`
- `data`
- `evidence`
- `quality_flags`
- `notes`

Each `data` object MAY contain only:

- `fco_mpa`
- `fc_type`
- `fy_mpa`
- `recycled_aggregate_ratio_percent`
- `geometry`
- `eccentricity`
- `n_exp_kn`
- `material`
- `loading_mode`
- `condition`

`geometry` MAY contain only:

- `b_mm`
- `h_mm`
- `t_mm`
- `r0_mm`
- `l_mm`

`eccentricity` MAY contain only:

- `e1_mm`
- `e2_mm`
- `top_components_mm`
- `bottom_components_mm`

Each eccentricity component object MAY contain only:

- `x`
- `y`

`material` MAY contain only:

- `steel`
- `concrete`

Each material part MAY contain only:

- `type`
- `note`

`loading_mode` MAY contain only:

- `type`
- `description`

`condition` MAY contain only:

- `tags`
- `description`

Evidence objects MAY contain only:

- `source_locations`
- `field_evidence`
- `description`

Each `source_locations[*]` object MAY contain only:

- `page`
- `table`
- `figure`
- `section`
- `quote`

Each `field_evidence.<field>` object MAY contain only:

- `source_locations`
- `basis`
- `derivation`
- `raw_value`
- `normalized_value`

## Required Keys And Basic Types

Top-level object:

- `schema_version` is required and MUST be exactly `"1.0.0"`.
- `paper` is required and MUST be an object.
- `section_groups` is required and MUST be an object.

`paper`:

- `ref_info` is required and MUST be an object.
- `validity` is required and MUST be an object.
- `paper_evidence` is required and MUST be an evidence object.
- `paper_shared_defaults` is optional and MUST be a shared-defaults object when present.
- `notes` is optional and MUST be a string or null when present.

`paper.ref_info`:

- `title`, `journal`, `doi`, and `language` are required and MUST be strings or null.
- `authors` is required and MUST be a list of strings.
- `year` is required and MUST be an integer from 1800 to 2100, or null.

`paper.validity`:

- `is_valid` is required and MUST be boolean.
- `reason` is required and MUST be string or null. When `is_valid=false`, it
  MUST be a non-empty single-line string.

Each section group:

- `has_data` is required and MUST be boolean.
- `shared` is required and MUST be a shared-defaults object, or `{}`.
- `specimens` is required and MUST be a list.
- `group_notes` is optional and MUST be a string or null when present.

Each specimen:

- `specimen_id` is required and MUST be a non-empty single-line string.
- `data` is required and MUST be an extraction data object.
- `evidence` is optional and MUST be an evidence object when present.
- `quality_flags` is optional and MUST be a list of allowed unique strings.
- `notes` is optional and MUST be a string or null when present.

Evidence object:

- `source_locations` is optional and MUST be a list when present.
- `field_evidence` is optional and MUST be an object when present.
- `description` is optional and MUST be a string or null when present.

Each source location:

- `page` is optional and MUST be an integer >= 1 or null when present.
- `table`, `figure`, `section`, and `quote` are optional and MUST be strings or
  null when present.

Each field evidence object:

- `source_locations` is optional and MUST be a list when present.
- `basis` and `derivation` are optional and MUST be strings or null when present.
- `raw_value` and `normalized_value` are optional and MUST be strings, numbers,
  or null when present.

## Valid And Invalid Papers

For valid papers:

- `paper.validity.is_valid` MUST be `true`.
- `paper.validity.reason` SHOULD be `null`.
- At least one specimen MUST be present across all section groups.

For invalid papers:

- Use invalid output only when no in-scope CFST column ultimate-capacity data can
  be recovered under `extraction-rules.md`.
- `paper.validity.is_valid` MUST be `false`.
- `paper.validity.reason` MUST be a non-empty single-line string.
- All four section groups MUST be present.
- Every section group MUST have `has_data=false` and `specimens=[]`.
- Fill `paper.ref_info` where recoverable; otherwise use nulls and an empty
  `authors` list.

## Section Groups

`section_groups` must contain exactly these keys:

- `square`: Group A square sections
- `rectangular`: Group A rectangular sections
- `circular`: Group B circular sections
- `round_ended`: Group C round-ended sections

Each group MUST contain:

- `has_data`: true only when the group has specimen rows
- `shared`: group-level inherited defaults, or `{}`
- `specimens`: list of specimen objects, or `[]`
- `group_notes`: string or null

Group consistency rules:

- If `has_data=true`, `specimens` MUST contain at least one specimen.
- If `has_data=false`, `specimens` MUST be an empty list.
- Empty groups MUST still be present.
- `shared` MUST be `{}` when no shared values or evidence are needed.

## Effective Data And Inheritance

Use shared defaults only when the value is genuinely shared. Prefer
specimen-level `data` when values vary row by row.

For each specimen, effective data is resolved by deep-merging data objects in
this order:

1. `paper.paper_shared_defaults.data`
2. `section_groups.<shape>.shared.data`
3. `section_groups.<shape>.specimens[*].data`

Later objects override earlier objects at the field level. Nested objects are
merged. For example, a specimen may inherit `material.concrete` from paper
defaults while overriding only `geometry`.

The practical lookup priority is:

1. specimen data
2. section-group shared data
3. paper shared defaults

## Required Effective Specimen Data

Every retained specimen must resolve these effective fields after inheritance:

- `fco_mpa`
- `fc_type`
- `fy_mpa`
- `recycled_aggregate_ratio_percent`
- `geometry.b_mm`
- `geometry.h_mm`
- `geometry.t_mm`
- `geometry.r0_mm`
- `geometry.l_mm`
- `eccentricity.e1_mm`
- `eccentricity.e2_mm`
- `n_exp_kn`
- `material.steel.type`
- `material.concrete.type`
- `loading_mode.type`
- `condition.tags`

Use `recycled_aggregate_ratio_percent = 0` when recycled aggregate is not
applicable or not reported.

Each `specimen_id` MUST be a non-empty single-line string and MUST be unique
across all section groups.

## Numeric And Rounding Rules

All extracted numeric fields MUST be JSON numbers, not strings.

Under `--strict-rounding`, extracted numeric values MUST be rounded to no more
than 0.001 precision. Integers and one- or two-decimal values are acceptable
because they are already representable at 0.001 precision. Do not write trailing
zeroes just to show precision; JSON numbers do not preserve them.

Required numeric ranges:

- `fco_mpa`: > 0
- `fy_mpa`: > 0
- `recycled_aggregate_ratio_percent`: 0 to 100 inclusive
- `geometry.b_mm`: > 0
- `geometry.h_mm`: > 0
- `geometry.t_mm`: > 0
- `geometry.r0_mm`: >= 0
- `geometry.l_mm`: > 0
- `eccentricity.e1_mm`: finite number
- `eccentricity.e2_mm`: finite number
- `eccentricity.top_components_mm.x`: finite number or null
- `eccentricity.top_components_mm.y`: finite number or null
- `eccentricity.bottom_components_mm.x`: finite number or null
- `eccentricity.bottom_components_mm.y`: finite number or null
- `n_exp_kn`: > 0

For all geometries, `t_mm` MUST be smaller than
`min(b_mm, h_mm) / 2`.

When both x and y eccentricity components are given, the corresponding
eccentricity SHOULD equal `sqrt(x^2 + y^2)` in magnitude. A mismatch is a
warning, not a failure.

## Section Geometry Rules

Each specimen MUST be placed in exactly one section group.

### `square`

- Group A.
- Requires `b_mm == h_mm`.
- Usually uses `r0_mm = 0`.
- If `r0_mm > 0`, evidence or notes SHOULD explain the rounded corner.

### `rectangular`

- Group A.
- Requires `b_mm >= h_mm`.
- Usually uses `r0_mm = 0`.
- If `r0_mm > 0`, evidence or notes SHOULD explain the rounded corner.

### `circular`

- Group B.
- Requires `b_mm == h_mm`.
- `b_mm` and `h_mm` are both the outer diameter `D`.
- Requires `r0_mm = h_mm / 2`.
- Calculate derived `r0_mm` with `scripts/safe_calc.py` through the sandbox.

### `round_ended`

- Group C.
- Requires `b_mm > h_mm`.
- Requires `r0_mm = h_mm / 2`.
- Calculate derived `r0_mm` with `scripts/safe_calc.py` through the sandbox.

## Concrete Strength Type Output

`fc_type` records the strength basis of the stored `fco_mpa` value. It follows
the reported or converted basis of the stored value, not necessarily the raw
test specimen geometry. Apply `fc-basis-rules.md` before using
`fc_type = "unknown"`.

`fc_type` MUST NOT be a table symbol or design-code symbol. Invalid values
include:

- `fc`
- `f'c`
- `fc'`
- `fcu`
- `fck`
- `fcm`
- `fcd`

Use basis values such as:

- `cube`
- `cube_150`
- `cube_100`
- `cylinder`
- `cylinder_100x200`
- `cylinder_150x300`
- `prism`
- `prism_150x150x300`
- `unknown`

Project-specific basis strings are allowed only when they describe the stored
strength basis and match the schema pattern.

## Material, Loading, And Condition Objects

When `material.steel.type = "other"`, `material.steel.note` MUST be a non-empty
single-line explanation.

When `material.concrete.type = "other"`, `material.concrete.note` MUST be a
non-empty single-line explanation.

When `loading_mode.type = "other"`, `loading_mode.description` MUST be a
non-empty single-line explanation.

When `condition.tags` contains `other`, `condition.description` MUST be a
non-empty single-line explanation.

`condition.tags` MUST contain at least one tag and MUST NOT contain duplicates.
Using `normal` together with other condition tags is allowed but triggers a
warning; avoid that combination unless the paper clearly supports it.

## Evidence Objects

Evidence may be stored at paper, group, or specimen level. Put field-specific
derivations under `field_evidence` using paths such as `fco_mpa`, `fc_type`,
`geometry.l_mm`, `geometry.r0_mm`, `eccentricity.e1_mm`, `n_exp_kn`,
`material`, `loading_mode`, or `condition`.

Evidence source locations SHOULD include at least one non-page locator:

- `table`
- `figure`
- `section`
- `quote`

Page-only evidence is not sufficient extraction evidence and may trigger a
warning. Warnings alone do not fail validation.

Use short quotes, table identifiers, figure identifiers, captions, or section
names. Do not quote long passages.

Preferred patterns:

```json
{"table": "Table 2", "figure": null, "section": "Specimens", "quote": "SC-1 geometry and material row."}
```

```json
{"table": null, "figure": null, "section": "Materials", "quote": "The concrete strength was converted to standard cube compressive strength."}
```

```json
{"table": null, "figure": "Fig. 4", "section": "Test setup", "quote": "Eccentric loading arrangement."}
```

## Normalized Enumerations

`material.steel.type` values:

- `carbon_steel`
- `stainless_steel`
- `other`

`material.concrete.type` values:

- `normal`
- `UHPC`
- `recycled_concrete`
- `other`

`loading_mode.type` values:

- `monotonic`
- `cyclic`
- `sustained`
- `dynamic`
- `thermal`
- `other`

`condition.tags` values:

- `normal`
- `corrosion`
- `freeze_thaw`
- `thermal`
- `long_term`
- `defect`
- `damage`
- `strengthened`
- `other`

## Quality Flags

Allowed `quality_flags` values:

- `reported_group_average`
- `figure_derived`
- `formula_derived`
- `text_derived`
- `table_derived`
- `ambiguous_source`
- `unit_converted`
- `partially_unknown`

`quality_flags` MUST NOT contain duplicates.

Use `reported_group_average` when one reported average `Nexp` is assigned to
explicitly recoverable repeated specimens.

## Examples

### Valid Circular Specimen With Shared Defaults

In this example, `fco_mpa`, `fc_type`, recycled aggregate ratio,
`eccentricity`, `material`, `loading_mode`, and `condition` are inherited from
`paper.paper_shared_defaults.data`. The specimen row supplies values that vary.

```json
{
  "specimen_id": "HSC1-1",
  "data": {
    "fy_mpa": 482.5,
    "geometry": {
      "b_mm": 159.8,
      "h_mm": 159.8,
      "t_mm": 6.3,
      "r0_mm": 79.9,
      "l_mm": 476.0
    },
    "n_exp_kn": 2350.0
  },
  "quality_flags": ["reported_group_average", "table_derived", "formula_derived"],
  "notes": "Table reports group-average measured capacity for explicitly listed repeated specimens."
}
```

### Invalid Paper Output

If no in-scope CFST column ultimate-capacity data can be recovered, write a
schema-valid invalid output:

```json
{
  "schema_version": "1.0.0",
  "paper": {
    "ref_info": {"title": null, "authors": [], "journal": null, "year": null, "doi": null, "language": null},
    "validity": {"is_valid": false, "reason": "No extractable CFST column ultimate-capacity data."},
    "paper_evidence": {"source_locations": [], "field_evidence": {}, "description": null},
    "paper_shared_defaults": {},
    "notes": null
  },
  "section_groups": {
    "square": {"has_data": false, "shared": {}, "specimens": [], "group_notes": null},
    "rectangular": {"has_data": false, "shared": {}, "specimens": [], "group_notes": null},
    "circular": {"has_data": false, "shared": {}, "specimens": [], "group_notes": null},
    "round_ended": {"has_data": false, "shared": {}, "specimens": [], "group_notes": null}
  }
}
```

## Pre-Validation Checklist

Before running the validator, check:

- `schema_version` is `1.0.0`.
- Top-level keys are exactly `schema_version`, `paper`, and `section_groups`.
- All four section groups are present.
- Empty section groups have `has_data=false` and `specimens=[]`.
- Each specimen ID is unique.
- Every specimen resolves all required effective data after inheritance.
- No unsupported extra keys were added.
- All extracted numbers are JSON numbers and rounded to 0.001 precision.
- Circular specimens satisfy `b_mm == h_mm` and `r0_mm == h_mm / 2`.
- Round-ended specimens satisfy `b_mm > h_mm` and `r0_mm == h_mm / 2`.
- `fc_type` is a basis value, not `fc`, `fck`, `fcu`, or `f'c`.
- `other` material, loading, or condition values include note or description.
- Evidence includes table, figure, section, or quote locators, not only page numbers.
