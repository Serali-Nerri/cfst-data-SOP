# CFST Extraction Rules

Use this file as the extraction rule source of truth for one paper. Workflow
belongs in `../SKILL.md`; JSON shape and required fields belong in
`JSON_contract.md`.

The extraction target is **all CFST column ultimate load-capacity data**
recoverable from the paper. 
Fire, corrosion, freeze-thaw, long-term loading, defects, damage,
strengthening, cyclic loading, dynamic loading, high temperature, stainless
steel, UHPC, recycled concrete, and other special cases are included when the
tested member is a CFST column and an experimental ultimate load capacity is
reported.

Section map:

- `## 1. Target Scope`: include all CFST column ultimate-capacity data and
  exclude non-target tests.
- `## 2. Required Parameters`: define the project fields to extract.
- `## 3. Concrete Strength Rules`: resolve `fco` and `fc_type`.
- `## 4. Section Shape And Geometry Rules`: resolve `Group_A-D`, `b`, `h`,
  `t`, `r0`, and `L`.
- `## 5. Eccentricity Rules`: resolve signed top/bottom eccentricities `e1`
  and `e2`.
- `## 6. Material Rules`: normalize steel and concrete material information.
- `## 7. Loading Mode Rules`: normalize loading mode and loading history.
- `## 8. Condition Rules`: normalize pre-test and in-test conditions.
- `## 9. Source And Numeric Rules`: record paper-level source summaries and
  normalize numbers.
- `## 10. Invalid Or Failed Extraction`: define invalid papers and processing
  failures.

## 1. Target Scope

Extract only experimental **CFST column ultimate load-capacity data**.

A specimen row is in scope when all are true:

- the tested member itself is a concrete-filled steel tube column, stub column,
  short column, slender column, or long column
- the row has an experimental ultimate load capacity, stored as `n_exp`
- the loading is axial compression, eccentric compression, combined compression
  with recoverable axial ultimate load, or another column test whose ultimate
  load capacity can be stored as `n_exp`
- the required geometry, material, loading, condition, eccentricity, recycled
  aggregate ratio, and capacity fields are recoverable through the schema
  inheritance rules

Do **not** exclude a CFST column row because it is non-ordinary, specially
treated, conditioned, damaged, strengthened, high-temperature, post-fire,
cyclic, dynamic, sustained-load, stainless-steel, UHPC, recycled, or otherwise
outside an ordinary dataset. Capture those differences in `material`,
`loading_mode`, `condition`, `r_ratio`, specimen/group notes, and paper-level
source summaries.

Exclude before extraction:

- beams or flexural beam tests
- joints / beam-column joints
- connections and connection tests
- frame or subassembly tests when the column specimen's own ultimate capacity
  cannot be separated
- wall, pier, brace, panel, slab, or other non-column members
- pure bending tests without a recoverable column axial/eccentric ultimate load
  capacity
- hollow steel tube / bare steel tube / empty steel tube / steel-only controls
  without concrete infill
- concrete-only controls, steel-only controls, or other non-CFST comparison rows
- FE-only, theory-only, review-only, or numerical-parametric rows without
  physical specimen capacity data
- papers where CFST columns appear only as background and no separable CFST
  column ultimate-capacity data can be recovered.
-  intentionally hollow-core CFST-type specimens, including double-skin,
    double-tube, or hollow-sandwich CFST columns, even when `n_exp` is reported.


A paper is `is_valid=true` when at least one in-scope CFST column specimen row
can be extracted. A paper is invalid only when no in-scope CFST column
ultimate-capacity data can be recovered.

Grouped average ultimate capacities are usable when the paper explicitly
defines the repeated-specimen group membership, or gives enough specimen-count /
parameter-set mapping to assign the same reported average to each member
specimen row without fabricating group composition. In that case, store the same
`n_exp` on each member row and explain the reported average using the note
placement rule in section 9. If a paper reports only grouped averages but the
member-to-row mapping is not defensibly recoverable, do not fabricate individual
specimen rows.

## 2. Required Parameters

Record only **CFST column ultimate load-capacity data**. Do not include beams,
joints, connections, pure-bending tests, or similar non-target data.

Parameters to extract:

| Col | JSON field       | Unit | Meaning |
| --- | ---------------- | ---- | ------- |
| A   | `paper.ref_info` | -    | Bibliographic metadata identifying the source paper |
| B   | `fco`            | MPa  | Concrete compressive strength represented by the stored value |
| C   | `fc_type`        | -    | Strength basis represented by `fco`; follows the stored value when the paper converts results |
| D   | `specimen_label` | -    | Specimen label or ID exactly as given in the source |
| E   | `fy`             | MPa  | Steel tube yield strength |
| F   | `r_ratio`        | %    | Recycled aggregate replacement ratio; use 0 if not applicable or not reported |
| G   | `b`              | mm   | Section outer width; for circular sections `b = h = D`; use `b >= h` |
| H   | `h`              | mm   | Section outer depth or height |
| I   | `t`              | mm   | Steel tube wall thickness |
| J   | `r0`             | mm   | Outer corner radius; see `section_shapes.jpg` and section 4 |
| K   | `L`              | mm   | Specimen length |
| L   | `e1`             | mm   | Eccentricity at the upper end; 0 for axial loading |
| M   | `e2`             | mm   | Eccentricity at the lower end; 0 for axial loading |
| N   | `n_exp`          | kN   | Experimental ultimate load capacity |
| O   | Group key        | -    | `Group_A` square, `Group_B` rectangular, `Group_C` circular, `Group_D` round-ended |
| P   | `material`       | -    | Steel and concrete material categories |
| Q   | `loading_mode`   | -    | Loading mode and loading history applied to the specimen |
| R   | `condition`      | -    | Conditions applied to the specimen before or during testing |

Use inheritance only for genuinely shared values:

1. `paper.defaults` for `fco`, `fc_type`, `loading_mode`, `condition`, and
   `material` values shared at paper level
2. `Group_X.shared` for values shared by all specimens in one section group,
   including `r_ratio`, `e1`, and `e2` when appropriate
3. specimen fields for row-specific values and overrides

Do not put `r_ratio`, `e1`, or `e2` in `paper.defaults`.

## 3. Concrete Strength Rules

`fco`: the concrete compressive strength value represented by the stored
extraction row, numeric, for example `fco = 43 MPa`.

`fc_type`: the concrete compressive strength type corresponding to `fco`. It is
a string: strength basis (`cube`, `cylinder`, `prism`, `unknown`) plus marked
size when known, for example:

- `cube`
- `cube_150`
- `cube_100`
- `cylinder`
- `cylinder_100x200`
- `cylinder_150x300`
- `prism`
- `prism_150x150x300`
- `unknown`
- `...`

See `references/fc-basis-rules.md`.

When `fco` and `fc_type` are shared by all retained specimens, write them in
`paper.defaults` and set the corresponding `paper.default_consistency` values to
`true`. When they vary, set the corresponding consistency values to `false` and
write the varying values in `Group_X.shared` or specimen fields with local
exception notes.

## 4. Section Shape And Geometry Rules

Section shape parameters: refer to `references/section_shapes.jpg`. `b` is the
longer side, so `b >= h`.

Group meanings:

- `Group_A`: square sections
- `Group_B`: rectangular sections
- `Group_C`: circular sections
- `Group_D`: round-ended sections

Do not write shape labels, shape descriptions, or section-rule strings inside
the JSON. The group key is the shape declaration.

For `Group_A` square sections:

- `b == h`
- non-rounded square sections must use `r0 = 0`
- rounded-corner square sections must use `r0 > 0`
- when a section is rounded-corner, the group or specimen `note` must state that
  local exception
- when `r0 > 0`, `r0 < h / 2`

For `Group_B` rectangular sections:

- `b >= h`
- `b == h` is suspicious and should be checked against `Group_A`
- non-rounded rectangular sections must use `r0 = 0`
- rounded-corner rectangular sections must use `r0 > 0`
- when a section is rounded-corner, the group or specimen `note` must state that
  local exception
- when `r0 > 0`, `r0 < h / 2`

For `Group_C` circular sections:

- `b == h`
- `b` and `h` are both the outer diameter `D`
- `r0 = h / 2`

For `Group_D` round-ended sections:

- `b > h`
- `r0 = h / 2`

`L`:

Determine `L` as the project geometric specimen length in the following priority
order:

1. Explicit specimen length in the paper text / tables / notes
2. Explicit formula or ratio with clear variable meaning
3. Figure-based derivation with clear geometric evidence, including steel-tube
   clear height when the figure makes that geometric relationship clear

If the paper does not directly name `L`, but the specimen / setup figure makes
the steel-tube clear height derivable, use that geometric length and describe
the source and derivation basis only in `paper.data_sources`, `paper.default_notes`,
or `paper.notes`. Do not put source names, figure names, table names, quotes, or
derivation basis text in group or specimen notes.

When the geometric basis is ambiguous, do not populate `L`. Do not infer `L`
from boundary-condition assumptions or effective-length formulas.

## 5. Eccentricity Rules

Upper-end eccentricity, signed: `e1`

Lower-end eccentricity, signed: `e2`

Do not put `e1` or `e2` in `paper.defaults`.

Use `Group_X.shared` when every specimen in a group has the same eccentricity,
for example axial groups:

```json
"shared": {"e1": 0, "e2": 0}
```

Use specimen fields when eccentricity varies row by row.

If `e_x_top` and `e_y_top` are distinguished, then:

```text
e1 = sqrt(e_x_top^2 + e_y_top^2)
```

The lower-end eccentricity follows the same rule.

When the paper reports signed eccentricities, preserve the paper's sign. The
sign records direction: `e1` and `e2` with the same sign act in the same
direction; opposite signs act in opposite directions. If the paper reports only
unsigned eccentricity magnitudes, store non-negative values.

| Eccentricity pattern | `e1` | `e2` | Meaning |
| -------------------- | ---- | ---- | ------- |
| Axial loading | 0 | 0 | Load passes through the section centroid |
| Equal-end eccentric loading | e | e | Upper and lower eccentricities are equal |
| Unequal-end eccentric loading | e1 | e2 | Upper and lower eccentricities are unequal |

## 6. Material Rules

`material` is an object:

```json
{"steel": "carbon_steel", "concrete": "normal"}
```

`material.steel` values:

- `carbon_steel`
- `stainless_steel`
- `other`

`material.concrete` values:

- `normal`
- `UHPC`
- `recycled_concrete`
- `other`

When a material value is `other`, briefly explain it using the note placement
rule in section 9.

When material is shared by all retained specimens, write it in `paper.defaults`
and set `paper.default_consistency.material=true`. If it varies, set
`paper.default_consistency.material=false` and write overrides in
`Group_X.shared` or specimen fields with notes for special cases.

## 7. Loading Mode Rules

`loading_mode` is a coarse category for the primary loading or action regime
associated with the reported ultimate load.

`loading_mode` values:

- `monotonic`: monotonic static loading
- `cyclic`: cyclic / reversed loading
- `sustained`: long-term load / sustained load
- `dynamic`: impact, blast, or dynamic loading
- `thermal`: high temperature, fire, or post-fire residual
- `other`: other loading type

When `loading_mode = "other"`, briefly explain it using the note placement rule
in section 9.

When loading mode is shared by all retained specimens, write it in
`paper.defaults` and set `paper.default_consistency.loading_mode=true`. If it
varies, set `paper.default_consistency.loading_mode=false` and write overrides
in `Group_X.shared` or specimen fields with notes for special cases.

## 8. Condition Rules

`condition` is a coarse category for the specimen's dominant state, treatment,
deterioration, damage, strengthening, or environmental exposure.

`condition` values:

- `normal`: conventional undeteriorated specimen; no corrosion, freeze-thaw,
  high temperature, pre-damage, or obvious defect
- `corrosion`: chloride corrosion, acid-rain corrosion, atmospheric corrosion,
  electrochemical accelerated corrosion, etc.
- `freeze_thaw`: water freeze-thaw, salt freeze-thaw, multiple freeze-thaw
  cycles, etc.
- `thermal`: temperature/fire condition, high-temperature action, fire exposure,
  post-fire residual capacity, etc.
- `long_term`: sustained load, creep, service-load history, etc.
- `defect`: initial or construction defect, debonding, voids, initial gaps,
  local dents, initial geometric imperfections, etc.
- `damage`: pre-damage, preload damage, impact damage, cyclic damage, residual
  capacity after local buckling, etc.
- `strengthened`: strengthening/repair, FRP strengthening, steel-sleeve
  strengthening, concrete/UHPC jacketing, post-corrosion repair, etc.
- `other`: other special condition

For multi-factor cases, choose the dominant category for coarse normalization
and explain secondary factors using the note placement rule in section 9.

When `condition = "other"`, briefly explain it using the note placement rule in
section 9.

When condition is shared by all retained specimens, write it in
`paper.defaults` and set `paper.default_consistency.condition=true`. If it
varies, set `paper.default_consistency.condition=false` and write overrides in
`Group_X.shared` or specimen fields with notes for special cases.

## 9. Source And Numeric Rules

All source information and derivation basis text belongs under
`paper.data_sources`, `paper.default_notes`, and `paper.notes`. Do not write
evidence/source blocks, table names, figure names, source identifiers, quotes,
or derivation basis text under groups or specimens.

`paper.data_sources` should list the table names, figure names, or section names
that support the extraction overall. Keep descriptions short.

Use `paper.default_notes` to describe the paper-level basis for `fco`,
`fc_type`, `loading_mode`, `condition`, and `material`.

Place non-source explanatory notes at the same inheritance level as the value
they explain: `paper.default_notes.<field>` for paper defaults, `Group_X.note`
for group-shared values, and specimen `note` for specimen fields. Use
`paper.notes` only for paper-wide context not tied to one field, group, or
specimen.

Use group or specimen `note` only for local data exceptions, such as
rounded-corner square/rectangular sections, grouped average capacities, or
lower-level overrides of paper defaults. Do not use group or specimen notes for
source or derivation evidence. Obvious table/figure/source identifiers, quotes,
or conversion/derivation phrases in group or specimen notes are validation
errors.

All extracted numeric fields must be JSON numbers, not strings. Under
`--strict-rounding`, numeric values must be rounded to no more than 0.001
precision.

Use `scripts/safe_calc.py` for every unit conversion or derived value, including
eccentricity resultants, `r0 = h / 2`, and figure/formula-derived dimensions.

## 10. Invalid Or Failed Extraction

### 10.1 Invalid Paper

Produce an invalid JSON using `JSON_contract.md` when the paper has no
extractable CFST column ultimate-capacity data, including when it is:

- FE-only
- theory-only or review-only
- a non-column CFST study without separable column-specimen ultimate-load data
- a beam, joint, connection, frame, pure-bending, or non-CFST-control study
  without in-scope CFST column rows
- missing recoverable experimental ultimate load capacity for every potential
  CFST column row

### 10.2 Processing Failure

When evidence is insufficient for a defensible extraction:

- stop with a clear failure reason
- do not fabricate row values
- keep intermediate output outside final published output
