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
| K   | `L`              | mm   | Effective length governing stability of `n_exp`; see section 4 for priority and K table |
| L   | `e1`             | mm   | Eccentricity at the upper end; 0 for axial loading |
| M   | `e2`             | mm   | Eccentricity at the lower end; 0 for axial loading |
| N   | `n_exp`          | kN   | Experimental ultimate load capacity |
| O   | Group key        | -    | `Group_A` square, `Group_B` rectangular, `Group_C` circular, `Group_D` round-ended |
| P   | `material`       | -    | Steel and concrete material categories |
| Q   | `loading_mode`   | -    | Primary mechanical loading regime for the reported capacity |
| R   | `condition`      | -    | Condition object: searchable `tags` plus short `notes` |

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

Determine `L` as the **effective (calculation) length** that governs the
stability capacity associated with `n_exp`. `L` is not necessarily the physical
specimen length; when end fittings or boundary conditions modify the equivalent
length, `L` must reflect that correction.

### L extraction priority (top-down, first-match wins)

| Level | Evidence | L value |
| ----- | -------- | ------- |
| L1 | Paper explicitly reports effective / calculation length (`Le`, `L_e`, "有效长度", "计算长度") | Use the reported value directly |
| L2 | Paper provides `Le = K · L0` (or equivalent formula) with both K and L0 recoverable | `L = K × L0`, computed via `scripts/safe_calc.py` |
| L3 | Paper provides an unbraced length plus identifiable end conditions (text statement or test-setup figure) | `L = K × L_unbraced`, with K from the table below |
| L4 | Fallback: no end-fixture correction, no identifiable boundary condition, and no length-related formula | `L = L_geo` (geometric specimen length) |

For L3, the unbraced length is the distance between rotation-restraint points
(pin-to-pin centers, end-plate inner faces, or the steel-tube clear height when
the figure makes that geometry clear).

### Boundary condition → K factor table

Use these theoretical K values unless the paper explicitly states a different
code-modified K. When the paper gives its own K, use the paper's value and
record it in the methodology note.

| End condition | Short form | K |
| ------------- | ---------- | --- |
| Both ends pinned (pin / spherical hinge / freely rotating end) | pin-pin | 1.0 |
| One end fixed, one end pinned | fix-pin | 0.7 |
| Both ends fixed (welded end plates with full rotation restraint) | fix-fix | 0.5 |
| One end fixed, one end free (cantilever) | fix-free | 2.0 |
| Knife edge at both ends (eccentric-load tests, pinned about the loading axis) | knife-edge | 1.0 |
| End plate + stiffening sleeve (semi-rigid) | semi-rigid | 0.7 |
| Asymmetric end combinations | combine from rows above | per pairing |

Evidence priority for end conditions: **paper formula > test-setup figure >
text description > same-group convention** (the last is weak evidence and must
be flagged in the methodology note).

### Reverse derivation and consistency check

When the paper reports slenderness `λ` and radius of gyration `i`, compute
`Le_check = λ × i` and compare with the L3 lookup value. Differences ≤ 5% are
consistent; if the difference exceeds 5%, prefer the paper-derived value.

If the paper reports an L/D ratio, slenderness, or other length-derived
quantity, re-evaluate which level applies according to that quantity's internal
definition; do not apply the K table mechanically.

### Fallback boundary (L4)

`L4` is allowed only when **all** of the following hold:

1. The paper does not report `Le` or `K`.
2. The test-setup figure is missing or cannot identify the end condition.
3. The specimen end is a simple flat bearing plate or has no fixture correction.
4. The fallback is explicitly recorded in the methodology note.

Short / stub columns (L/D ≤ 4) commonly fall here, but must still go through
condition 4 — fallback is never implicit.

### Methodology note (required placement)

Record the L methodology once per scope at the matching level. Notes must be a
single short clause; do not quote sources.

| Scope | Location |
| ----- | -------- |
| One L methodology shared by the whole paper | `paper.notes` |
| Different K per group (e.g. boundary-condition comparison studies) | `Group_X.note` |
| One specimen deviates from its group methodology | specimen `note` |

L methodology phrases are an explicit allowed exception to the "no derivation
phrases in group/specimen note" rule in section 9. Use the templates below.

Recommended templates (one line, no source quotes):

- `L = Le as reported (level L1).`
- `L = K × L0 = 0.7 × 1500 = 1050 mm (level L2).`
- `L = 0.5 × 1200 = 600 mm; fix-fix (level L3).`
- `L = L_geo = 800 mm; no end-fixture correction (level L4 fallback).`

### Non-recoverable

If even the geometric length cannot be recovered, treat the row as not
recoverable under section 10.

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

When inferring eccentricity signs from moment ratios or curvature labels, first
separate moment-sign convention from geometric eccentricity direction.

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

`loading_mode` is a coarse category for the primary mechanical loading regime
associated with the reported ultimate load.

`loading_mode` values:

- `monotonic`: monotonic static loading
- `cyclic`: cyclic / reversed loading
- `sustained`: long-term load / sustained load
- `dynamic`: impact, blast, or dynamic loading
- `other`: other loading type

Do not encode temperature, fire, corrosion, freeze-thaw, preload, sustained-load
history, damage, or repair in `loading_mode`; use `condition.tags` and
`condition.notes` for those.

When `loading_mode = "other"`, briefly explain it using the note placement rule
in section 9.

When loading mode is shared by all retained specimens, write it in
`paper.defaults` and set `paper.default_consistency.loading_mode=true`. If it
varies, set `paper.default_consistency.loading_mode=false` and write overrides
in `Group_X.shared` or specimen fields with notes for special cases.

## 8. Condition Rules

`condition` is an object with exactly `tags` and `notes`. Use it for specimen
state, exposure, prior loading history, damage, or repair conditions. Do not
encode geometry, material strength, dimensions, eccentricity, or ordinary
loading type here.

`condition.tags` allowed templates:

| Family | Templates | Meaning |
|---|---|---|
| normal | `normal` | No special condition; use alone. |
| temperature | `temperature_C`, `temperature_heat`, `temperature_cold` | Specific °C value, unspecified heat/fire, or unspecified cold. |
| corrosion | `corrosion`, `corrosion_P` | Corrosion, with optional reported loss percentage. |
| freeze-thaw | `freeze_thaw`, `freeze_thaw_N` | Freeze-thaw, with optional cycle count. |
| load history | `load_history`, `preload_R`, `sustained_load_R`, `initial_stress_R` | Prior load history, with optional reported ratio. |
| prior damage | `cyclic_damage`, `blast_damage`, `impact_damage` | Prior cyclic, blast, or impact damage. |
| defect/damage | `defect_damage`, `defect_damage_TYPE`, `defect_damage_LEVEL` | Defect or damage, optionally by type or level. |
| strengthening/repair | `strengthening_repair`, `strengthening_repair_TYPE` | Strengthening or repair, optionally by type. |
| other | `other` | Other special condition; explain in `condition.notes`. |

Placeholders: `C` = Celsius value, `P` = percentage, `N` = cycle count, `R` =
ratio. Use the most specific tag available; do not combine broad and specific
tags in the same family. Put procedural details in `condition.notes`.

Use `{"tags": ["normal"], "notes": null}` for ordinary specimens with no
reported special condition. For non-normal tags, write a short source-free
natural-language `condition.notes` description.

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
`fc_type`, `loading_mode`, and `material`. Use `condition.notes` for condition
descriptions.

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

Explicit exception: **L methodology phrases** (the level marker `level L1` /
`L2` / `L3` / `L4`, the K factor `K=<value>`, and the baseline-length reference
such as `L_geo`, `L0`, `Le`) are allowed in group / specimen / paper notes,
because the L methodology is itself a local data exception. See section 4 for
the recommended templates. Source identifiers (table / figure / `S\d+` /
`source` / `表` / `图`) remain disallowed even within an L methodology note.

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
