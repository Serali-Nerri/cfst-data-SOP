# CFST JSON Output Contract

Warnings alone are not validation failure, but agents should avoid documented
warnings when the paper supports a cleaner value.

Documented validator warnings include:

- `paper.data_sources` is empty for a valid paper.
- A specimen repeats the same value already supplied by its group `shared`
  object.
- A `Group_B` row has `b == h`; verify whether it belongs in `Group_A`.
- `material`, `loading_mode`, or `condition` uses `other` without an applicable
  explanatory note.
- Numeric values are not rounded to 0.001 when validation is run without
  `--strict-rounding`; under `--strict-rounding`, this is an error.

## Contents

- Top-Level Shape
- Allowed Keys
- Required Keys And Basic Types
- Valid And Invalid Papers
- Groups
- Effective Data And Inheritance
- Required Effective Specimen Data
- Numeric And Rounding Rules
- Section Geometry Rules
- Concrete Strength Type Output
- Material, Loading, And Condition Values
- Paper-Level Source Notes
- Normalized Enumerations
- Examples
- Pre-Validation Checklist

## Top-Level Shape

A valid extraction output is one JSON object. Do not add top-level keys outside
`schema_version`, `paper`, `Group_A`, `Group_B`, `Group_C`, and `Group_D`.

The four group keys have fixed meanings:

- `Group_A`: square sections
- `Group_B`: rectangular sections
- `Group_C`: circular sections
- `Group_D`: round-ended sections

Do not repeat these meanings inside JSON with fields such as `shape`,
`shape_description`, `has_data`, or section-rule text. Section rules belong in
this contract and the validator.

```json
{
  "schema_version": "2.0.0-draft",
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
    "data_sources": [
      {
        "source_id": "S1",
        "type": "table",
        "name": "Table 1",
        "description": "Specimen parameters and material properties."
      }
    ],
    "defaults": {
      "fco": 53.4,
      "fc_type": "prism",
      "loading_mode": "monotonic",
      "condition": "normal",
      "material": {"steel": "carbon_steel", "concrete": "normal"}
    },
    "default_consistency": {
      "fco": true,
      "fc_type": true,
      "loading_mode": true,
      "condition": true,
      "material": true
    },
    "default_notes": {
      "fco": "The same concrete strength applies to all retained specimens.",
      "fc_type": "The stored strength basis applies to all retained specimens.",
      "loading_mode": "The same loading mode applies to all retained specimens.",
      "condition": "The same condition applies to all retained specimens.",
      "material": "The same steel and concrete material categories apply to all retained specimens."
    },
    "notes": null
  },
  "Group_A": {"shared": {}, "specimens": [], "note": null},
  "Group_B": {"shared": {}, "specimens": [], "note": null},
  "Group_C": {
    "shared": {"r_ratio": 0, "e1": 0, "e2": 0},
    "specimens": [
      {
        "specimen_label": "C1",
        "fy": 345,
        "b": 150,
        "h": 150,
        "t": 5,
        "r0": 75,
        "L": 450,
        "n_exp": 1200
      }
    ],
    "note": null
  },
  "Group_D": {"shared": {}, "specimens": [], "note": null}
}
```

## Allowed Keys

Objects may contain only the keys listed here. Do not add convenience fields
such as `paper_id`, `xi`, `specimen_count`, `source_file`, `shape`,
`shape_description`, `has_data`, `section_groups`, `paper_evidence`,
`source_locations`, or `field_evidence`.

Top-level object MUST contain exactly:

- `schema_version`
- `paper`
- `Group_A`
- `Group_B`
- `Group_C`
- `Group_D`

`paper` MAY contain only:

- `ref_info`
- `validity`
- `data_sources`
- `defaults`
- `default_consistency`
- `default_notes`
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

Each `paper.data_sources[*]` MUST contain exactly:

- `source_id`
- `type`
- `name`
- `description`

`paper.defaults` MAY contain only:

- `fco`
- `fc_type`
- `loading_mode`
- `condition`
- `material`

Do not put `r_ratio`, `e1`, or `e2` in `paper.defaults`. These fields are
commonly experimental variables and MUST be written in a group `shared` object
or in each specimen.

`paper.default_consistency` MUST contain exactly:

- `fco`
- `fc_type`
- `loading_mode`
- `condition`
- `material`

`paper.default_notes` MUST contain exactly:

- `fco`
- `fc_type`
- `loading_mode`
- `condition`
- `material`

Each group (`Group_A`, `Group_B`, `Group_C`, `Group_D`) MUST contain exactly:

- `shared`
- `specimens`
- `note`

Each group `shared` object MAY contain only extracted data fields:

- `fco`
- `fc_type`
- `fy`
- `r_ratio`
- `b`
- `h`
- `t`
- `r0`
- `L`
- `e1`
- `e2`
- `n_exp`
- `loading_mode`
- `condition`
- `material`

Each specimen MAY contain only:

- `specimen_label`
- `fco`
- `fc_type`
- `fy`
- `r_ratio`
- `b`
- `h`
- `t`
- `r0`
- `L`
- `e1`
- `e2`
- `loading_mode`
- `condition`
- `material`
- `n_exp`
- `note`

`material` MUST contain exactly:

- `steel`
- `concrete`

Do not put evidence, source, source locations, field evidence, or table quotes
under groups or specimens. All source information belongs under `paper`.

## Required Keys And Basic Types

Top-level object:

- `schema_version` is required and MUST be exactly `"2.0.0-draft"`.
- `paper`, `Group_A`, `Group_B`, `Group_C`, and `Group_D` are required objects.

`paper`:

- `ref_info`, `validity`, `data_sources`, `defaults`,
  `default_consistency`, `default_notes`, and `notes` are required.

`paper.ref_info`:

- `title` is required and MUST be a non-empty trimmed single-line string. It
  MUST NOT be null.
- `authors` is required and MUST be a non-empty list of non-empty trimmed
  single-line strings. It MUST NOT be empty.
- `journal` is required and MUST be a non-empty trimmed single-line string. It
  MUST NOT be null.
- `year` is required and MUST be an integer from 1800 to 2100. It MUST NOT be
  null.
- `doi` and `language` are required and MUST be strings or null.

`paper.validity`:

- `is_valid` is required and MUST be boolean.
- `reason` is required and MUST be string or null. When `is_valid=false`, it
  MUST be a non-empty single-line string.

`paper.data_sources`:

- MUST be a list.
- Each item MUST have non-empty `source_id`, `type`, `name`, and `description`
  single-line strings.
- `source_id` values MUST be unique.

`paper.defaults`:

- MUST be an object.
- May be incomplete only when corresponding values vary and are supplied in
  group or specimen fields.
- MUST NOT contain `r_ratio`, `e1`, or `e2`.

`paper.default_consistency`:

- Each value MUST be boolean.
- `true` means the corresponding `paper.defaults` value applies to all retained
  specimens.
- `true` requires the corresponding value to exist in `paper.defaults` for
  valid papers.
- `false` means at least one retained specimen or group differs from the
  default; lower-level fields may override it.

`paper.default_notes`:

- Each value MUST be a string or null.
- Use these notes to summarize the paper-level basis for `fco`, `fc_type`,
  `loading_mode`, `condition`, and `material`. Cite source identifiers from
  `paper.data_sources` in the prose when helpful.

Each group:

- `shared` is required and MUST be an object, or `{}`.
- `specimens` is required and MUST be a list.
- `note` is required and MUST be a string or null.
- Empty groups use `{"shared": {}, "specimens": [], "note": null}`.

Each specimen:

- `specimen_label` is required and MUST be a non-empty single-line string.
- `note` is optional and MUST be a string or null when present.
- Extracted fields are written directly on the specimen object, not inside a
  nested `data` object.

## Valid And Invalid Papers

For valid papers:

- `paper.validity.is_valid` MUST be `true`.
- `paper.validity.reason` SHOULD be `null`.
- At least one specimen MUST be present across the four groups.

For invalid papers:

- Use invalid output only when no in-scope CFST column ultimate-capacity data can
  be recovered under `extraction-rules.md`.
- `paper.validity.is_valid` MUST be `false`.
- `paper.validity.reason` MUST be a non-empty single-line string.
- All four groups MUST be present.
- Every group MUST have `specimens=[]`.
- `paper.ref_info.title`, `paper.ref_info.authors`, `paper.ref_info.journal`,
  and `paper.ref_info.year` MUST still be filled with non-null bibliographic
  values recovered from the paper. If `full.md` is missing or garbled, recover
  them from the rendered PDF first page, header, footer, or first-page bottom
  area. Do not invent placeholder bibliographic values; if these fields remain
  unrecoverable after PDF fallback, stop and report the failure instead of
  writing invalid JSON.

## Groups

Use exactly these group keys:

- `Group_A`: square sections
- `Group_B`: rectangular sections
- `Group_C`: circular sections
- `Group_D`: round-ended sections

No `has_data` flag is used. A group has data when `specimens` is non-empty.

Use `shared` only for values that are genuinely shared by every specimen in that
group. Good uses include:

- `r_ratio: 0` when every specimen in the group uses non-recycled concrete
- `e1: 0` and `e2: 0` when every specimen in the group is axially loaded
- one common `fy`, geometry, or material value when all specimens in the group
  share it

Do not use group `shared` when a value varies row by row. Put varying values on
the specimens.

If all square or rectangular specimens in a group have rounded corners, explain
that once in the group `note` instead of repeating it on every specimen. Do not
put table names, figure names, source identifiers, evidence quotes, or
derivation basis text in the group note.

## Effective Data And Inheritance

Use shared values only when the value is genuinely shared. Prefer specimen-level
fields when values vary row by row.

For each specimen, effective data is resolved by deep-merging data objects in
this order:

1. `paper.defaults`
2. `Group_X.shared`
3. `Group_X.specimens[*]`

Later objects override earlier objects at the field level. Nested `material`
objects are merged.

The practical lookup priority is:

1. specimen field
2. group `shared` field
3. paper default field

If `paper.default_consistency.<field>` is `true`, lower-level fields MUST NOT
override that field. If a lower-level field must override it, set the
corresponding consistency value to `false` and explain the local exception in
the specimen `note` or, for group-wide deviations, the group `note`.

If a specimen writes a field that already exists in its `Group_X.shared`, the
value MUST be identical. A different value contradicts the meaning of `shared`.
An identical repeated value is valid but redundant.

## Required Effective Specimen Data

Every retained specimen must resolve these effective fields after inheritance:

- `fco`
- `fc_type`
- `fy`
- `r_ratio`
- `b`
- `h`
- `t`
- `r0`
- `L`
- `e1`
- `e2`
- `n_exp`
- `loading_mode`
- `condition`
- `material.steel`
- `material.concrete`

Use `r_ratio = 0` when recycled aggregate is not applicable or not reported.

Because eccentricity is a group/specimen experimental variable, write `e1` and
`e2` in group `shared` or specimens, not in `paper.defaults`.

Each `specimen_label` MUST be unique across all groups.

## Numeric And Rounding Rules

All extracted numeric fields MUST be JSON numbers, not strings.

Under `--strict-rounding`, extracted numeric values MUST be rounded to no more
than 0.001 precision. Integers and one- or two-decimal values are acceptable
because they are already representable at 0.001 precision. Do not write trailing
zeroes just to show precision; JSON numbers do not preserve them.

Required numeric ranges:

- `fco`: > 0
- `fy`: > 0
- `r_ratio`: 0 to 100 inclusive
- `b`: > 0
- `h`: > 0
- `t`: > 0
- `r0`: >= 0
- `L`: > 0
- `e1`: finite number
- `e2`: finite number
- `n_exp`: > 0

For all geometries, `t` MUST be smaller than `min(b, h) / 2`.

Use `scripts/safe_calc.py` for every unit conversion or derived value, including
eccentricity resultants, `r0 = h / 2`, and figure/formula-derived dimensions.

## Section Geometry Rules

Each specimen MUST be placed in exactly one group.

### `Group_A`

- Square section.
- Requires `b == h`.
- Non-rounded square sections MUST use `r0 = 0`.
- Rounded-corner square sections MUST use `r0 > 0` and MUST have a group
  `note` or specimen `note` that states the section has rounded corners.
  Use wording such as `rounded-corner`, `corner radius`, or `圆角` so the
  validator can detect it.
- If `r0 > 0`, `r0` MUST be smaller than `h / 2`.

### `Group_B`

- Rectangular section.
- Requires `b >= h`.
- Non-rounded rectangular sections MUST use `r0 = 0`.
- If `b == h`, the validator warns because the row may belong in `Group_A`.
- Rounded-corner rectangular sections MUST use `r0 > 0` and MUST have a group
  `note` or specimen `note` that states the section has rounded corners.
  Use wording such as `rounded-corner`, `corner radius`, or `圆角` so the
  validator can detect it.
- If `r0 > 0`, `r0` MUST be smaller than `h / 2`.

### `Group_C`

- Circular section.
- Requires `b == h`.
- `b` and `h` are both the outer diameter `D`.
- Requires `r0 = h / 2`.

### `Group_D`

- Round-ended section.
- Requires `b > h`.
- Requires `r0 = h / 2`.

## Concrete Strength Type Output

`fc_type` records the strength basis of the stored `fco` value. It follows the
reported or converted basis of the stored value, not necessarily the raw test
specimen geometry. Apply `fc-basis-rules.md` before using `fc_type = "unknown"`.

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
strength basis and match the validator pattern.

## Material, Loading, And Condition Values

`material.steel` values:

- `carbon_steel`
- `stainless_steel`
- `other`

`material.concrete` values:

- `normal`
- `HSC`
- `SCC`
- `EC`
- `LWAC`
- `FRC`
- `UHPC`
- `UHSC`
- `recycled_concrete`
- `other`

When a material value is `other`, explain it using the note placement rule under
Paper-Level Source Notes.

`loading_mode` values:

- `monotonic`
- `cyclic`
- `sustained`
- `dynamic`
- `thermal`
- `other`

When `loading_mode = "other"`, explain it using the note placement rule under
Paper-Level Source Notes.

`condition` values:

- `normal`
- `corrosion`
- `freeze_thaw`
- `thermal`
- `preload`
- `long_term`
- `defect`
- `damage`
- `strengthened`
- `other`

When `condition = "other"`, explain it using the note placement rule under
Paper-Level Source Notes.

## Paper-Level Source Notes

All extraction source information belongs under `paper`.

Use `paper.data_sources` to record only overall source locations such as table
names, figure names, and section names with short descriptions. Do not record
per-specimen source blocks.

Preferred pattern:

```json
{
  "source_id": "S1",
  "type": "table",
  "name": "Table 2",
  "description": "Specimen dimensions, steel yield strength, concrete strength, and ultimate load."
}
```

Use `paper.default_notes` for short field-level explanations of the paper
defaults and their derivation basis:

```json
{
  "fco": "Source S1 reports fcu=76.8 MPa converted to fck=53.4 MPa; stored fco is 53.4 MPa.",
  "fc_type": "The stored value is the converted standard compressive strength, treated as prism.",
  "loading_mode": "Source S2 describes monotonic axial compression.",
  "condition": "No preload, deterioration, thermal exposure, or strengthening is reported.",
  "material": "Source S1 reports carbon-steel tubes and normal concrete."
}
```

Place non-source explanatory notes at the same inheritance level as the value
they explain: `paper.default_notes.<field>` for paper defaults, `Group_X.note`
for group-shared values, and specimen `note` for specimen fields. Use
`paper.notes` only for paper-wide context not tied to one field, group, or
specimen.

Do not quote long passages. Short table or section descriptions are enough.
Group and specimen notes are only for local data exceptions, such as rounded
corners, grouped average capacities, or lower-level overrides. Do not put table
names, figure names, source identifiers, quotes, or derivation basis text in
group or specimen notes. The validator rejects obvious source/derivation wording
in group or specimen notes, including table or figure names, source identifiers,
quotes, and conversion/derivation phrases.

## Normalized Enumerations

`paper.data_sources[*].type` values:

- `table`
- `figure`
- `section`
- `text`
- `other`

`material.steel` values:

- `carbon_steel`
- `stainless_steel`
- `other`

`material.concrete` values:

- `normal`
- `HSC`
- `SCC`
- `EC`
- `LWAC`
- `FRC`
- `UHPC`
- `UHSC`
- `recycled_concrete`
- `other`

`loading_mode` values:

- `monotonic`
- `cyclic`
- `sustained`
- `dynamic`
- `thermal`
- `other`

`condition` values:

- `normal`
- `corrosion`
- `freeze_thaw`
- `thermal`
- `preload`
- `long_term`
- `defect`
- `damage`
- `strengthened`
- `other`

## Examples

### Valid Circular Specimens With Group Shared Defaults

In this example, `fco`, `fc_type`, `material`, `loading_mode`, and `condition`
are inherited from `paper.defaults`; `r_ratio`, `e1`, and `e2` are inherited
from `Group_C.shared`; specimen rows supply values that vary.

```json
{
  "schema_version": "2.0.0-draft",
  "paper": {
    "ref_info": {
      "title": "钢管高强混凝土轴压力学性能的理论分析与试验研究",
      "authors": ["韩林海"],
      "journal": "工业建筑 / Industrial Construction",
      "year": 1997,
      "doi": "10.13204/j.gyjz1997.11.010",
      "language": "zh"
    },
    "validity": {"is_valid": true, "reason": null},
    "data_sources": [
      {"source_id": "S1", "type": "table", "name": "表1", "description": "试件参数表。"},
      {"source_id": "S2", "type": "table", "name": "表2", "description": "实测承载力表。"}
    ],
    "defaults": {
      "fco": 53.4,
      "fc_type": "prism",
      "loading_mode": "monotonic",
      "condition": "normal",
      "material": {"steel": "carbon_steel", "concrete": "HSC"}
    },
    "default_consistency": {"fco": true, "fc_type": true, "loading_mode": true, "condition": true, "material": true},
    "default_notes": {
      "fco": "Source S1 reports one converted concrete strength fck=53.4 MPa.",
      "fc_type": "Stored strength uses the converted standard compressive strength basis.",
      "loading_mode": "Source S2 identifies axial monotonic compression.",
      "condition": "No special deterioration, strengthening, or preload condition is reported.",
      "material": "Source S1 reports steel tubes and high-strength concrete."
    },
    "notes": null
  },
  "Group_A": {"shared": {}, "specimens": [], "note": null},
  "Group_B": {"shared": {}, "specimens": [], "note": null},
  "Group_C": {
    "shared": {"r_ratio": 0, "e1": 0, "e2": 0},
    "specimens": [
      {
        "specimen_label": "HSC1-1",
        "fy": 482.5,
        "b": 159.8,
        "h": 159.8,
        "t": 6.3,
        "r0": 79.9,
        "L": 476,
        "n_exp": 2350
      }
    ],
    "note": null
  },
  "Group_D": {"shared": {}, "specimens": [], "note": null}
}
```

### Rounded-Corner Rectangular Section

```json
{
  "Group_B": {
    "shared": {"r_ratio": 0, "e1": 0, "e2": 0},
    "specimens": [
      {
        "specimen_label": "RHS-RC-1",
        "fy": 345,
        "b": 200,
        "h": 120,
        "t": 5,
        "r0": 12,
        "L": 600,
        "n_exp": 1600,
        "note": "Rounded-corner rectangular steel tube."
      }
    ],
    "note": null
  }
}
```

### Invalid Paper Output

If no in-scope CFST column ultimate-capacity data can be recovered, write a
validator-valid invalid output:

```json
{
  "schema_version": "2.0.0-draft",
  "paper": {
    "ref_info": {
      "title": "Example Paper Without Extractable CFST Column Tests",
      "authors": ["Author Name"],
      "journal": "Journal Name",
      "year": 2005,
      "doi": null,
      "language": "en"
    },
    "validity": {"is_valid": false, "reason": "No extractable CFST column ultimate-capacity data."},
    "data_sources": [],
    "defaults": {},
    "default_consistency": {"fco": false, "fc_type": false, "loading_mode": false, "condition": false, "material": false},
    "default_notes": {"fco": null, "fc_type": null, "loading_mode": null, "condition": null, "material": null},
    "notes": null
  },
  "Group_A": {"shared": {}, "specimens": [], "note": null},
  "Group_B": {"shared": {}, "specimens": [], "note": null},
  "Group_C": {"shared": {}, "specimens": [], "note": null},
  "Group_D": {"shared": {}, "specimens": [], "note": null}
}
```

## Pre-Validation Checklist

- `schema_version` is `2.0.0-draft`.
- Top-level keys are exactly `schema_version`, `paper`, `Group_A`, `Group_B`,
  `Group_C`, and `Group_D`.
- No `section_groups`, `paper_evidence`, `source_locations`, or
  `field_evidence` keys are present.
- `paper.ref_info.title`, `paper.ref_info.authors`, `paper.ref_info.journal`,
  and `paper.ref_info.year` are non-null and recovered from reliable
  bibliographic evidence.
- `paper.data_sources` summarizes the paper-level source tables/figures/sections.
- `paper.data_sources` does not cite `content_list_v2.json` as a data source or
  cross-validation source.
- `paper.default_notes` summarizes paper-level default derivation basis.
- `paper.defaults` does not contain `r_ratio`, `e1`, or `e2`.
- Every group has only `shared`, `specimens`, and `note`.
- Empty groups have `shared={}`, `specimens=[]`, and `note=null`.
- Each specimen has a unique `specimen_label`.
- Effective data after inheritance contains all required specimen fields.
- Square and rectangular rows without a rounded-corner note have `r0=0`; rows
  with a rounded-corner note have `r0>0`.
- Circular and round-ended rows use `r0 = h / 2`.
- Numeric values are JSON numbers rounded to 0.001 precision.
