# CFST Extraction Rules

Use this file as the extraction rule source of truth for one paper. Workflow
belongs in `../SKILL.md`; JSON shape and required fields belong in
`JSON_contract.md`.

The extraction target is **all CFST column full-section compression ultimate
load-capacity data** recoverable from the paper.
Fire, corrosion, freeze-thaw, long-term loading, defects, damage,
strengthening, cyclic loading, dynamic loading, high temperature, stainless
steel, UHPC, recycled concrete, and other special cases are included when the
tested member is a CFST column and an experimental ultimate load capacity is
reported.

Section map:

- `## 1. Target Scope`: include all CFST column full-section compression
  ultimate load-capacity data and exclude non-target tests.
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
- `## 10. Processing Failure`: define evidence-insufficient failures.

## 1. Target Scope

Extract experimental CFST column rows whose reported `n_exp` is the
full-section compression ultimate load of a concrete-filled steel tube column.

Include full-section CFST column, stub-column, short-column, slender-column, and
long-column rows under axial, eccentric, combined, or other recoverable
full-section compression. Keep non-ordinary full-section CFST rows; encode
treatments, damage, exposure, loading history, and materials in the normalized
fields and notes.

Exclude:

- non-column members or tests: beams, pure bending without recoverable column
  axial/eccentric capacity, joints, connections, frames/subassemblies without
  separable column capacity, walls, piers, braces, panels, slabs
- non-CFST or component-only rows: hollow/bare/empty steel tubes,
  concrete-only/steel-only controls, rows loaded to failure through only the
  concrete section or only the steel tube
- FE-only, theory-only, review-only, or numerical-parametric rows
- intentionally hollow-core CFST-type specimens: double-skin, double-tube, or
  hollow-sandwich columns

Retain a row only when all required effective fields are recoverable. For
recoverable grouped averages, assign the reported average `n_exp` to each member
row; do not fabricate group composition.

## 2. Required Parameters

Record only **CFST column full-section compression ultimate load-capacity
data**. Do not include beams, joints, connections, pure-bending tests, or
similar non-target data.

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

Upper-end eccentricity: `e1`

Lower-end eccentricity: `e2`

Do not put `e1` or `e2` in `paper.defaults`.

Use `Group_X.shared` when every specimen in a group has the same eccentricity;
otherwise use specimen fields.

For axial loading, use `e1 = 0` and `e2 = 0`.

If end eccentricity direction is recoverable, store `e1` and `e2` as signed
values. Same-side end eccentricities use the same sign; opposite-side end
eccentricities use opposite signs.

If only unsigned magnitudes are reported but the same-side/opposite-side
relationship is recoverable, take `e1` as positive by convention and assign
`e2` only to preserve that relationship. If the relationship is not recoverable,
store non-negative values.

| Eccentricity pattern | `e1` | `e2` |
| -------------------- | ---- | ---- |
| Axial loading | 0 | 0 |
| Same-side equal-end eccentricity | e | e |
| Same-side unequal-end eccentricity | e_top | e_bottom |
| Opposite-side equal-end eccentricity | e | -e |
| Opposite-side unequal-end eccentricity | e_top | -e_bottom |

For biaxial eccentricity (see `biaxial_eccentricity.png`), use the end
resultant:

```text
e1 = sqrt(e1x^2 + e1y^2)
e2 = sqrt(e2x^2 + e2y^2)
```

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
- `HSC`: high-strength concrete
- `SCC`
- `EC`: expansive concrete
- `LWAC`: lightweight aggregate concrete
- `FRC`: fiber-reinforced concrete
- `UHPC`
- `UHSC`
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

- `normal`: conventional undeteriorated specimen; no preload, corrosion,
  freeze-thaw, high temperature, pre-damage, or obvious defect
- `corrosion`: chloride corrosion, acid-rain corrosion, atmospheric corrosion,
  electrochemical accelerated corrosion, etc.
- `freeze_thaw`: water freeze-thaw, salt freeze-thaw, multiple freeze-thaw
  cycles, etc.
- `thermal`: temperature/fire condition, high-temperature action, fire exposure,
  post-fire residual capacity, etc.
- `preload`: preloading or initial stress applied before the final ultimate
  capacity test
- `long_term`: sustained load, creep, service-load history, etc.
- `defect`: initial or construction defect, debonding, voids, initial gaps,
  local dents, initial geometric imperfections, etc.
- `damage`: pre-damage, impact damage, cyclic damage, residual capacity after
  local buckling, etc.
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

## 10. Processing Failure

When evidence is insufficient for a defensible extraction:

- stop with a clear failure reason
- do not fabricate row values
- keep intermediate output outside final published output
