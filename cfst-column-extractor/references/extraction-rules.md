# CFST Extraction Rules

Use this file as the extraction rule source of truth for one paper. Workflow belongs in `../SKILL.md`; JSON shape and required fields belong in `JSON_contract.md`.

The extraction target is **all CFST column ultimate load-capacity data** recoverable from the paper. Do not apply an ordinary-CFST eligibility filter. Fire, corrosion, freeze-thaw, long-term loading, defects, damage, strengthening, cyclic loading, dynamic loading, high temperature, stainless steel, UHPC, recycled concrete, and other special cases are included when the tested member is a CFST column and an experimental ultimate load capacity is reported.

Section map:

- `## 1. Target Scope`: include all CFST column ultimate-capacity data and exclude non-target tests.
- `## 2. Required Parameters`: define the A-R project fields to extract.
- `## 3. Concrete Strength Rules`: resolve `fco` and `fc_type`.
- `## 4. Section Shape And Geometry Rules`: resolve group, `b`, `h`, `t`, `r0`, and `L`.
- `## 5. Eccentricity Rules`: resolve signed top/bottom eccentricities.
- `## 6. Material Rules`: normalize steel and concrete material information.
- `## 7. Loading Mode Rules`: normalize the loading mode and loading history.
- `## 8. Condition Rules`: normalize pre-test and in-test conditions.
- `## 9. Evidence And Numeric Rules`: preserve evidence and numeric normalization.
- `## 10. Invalid Or Failed Extraction`: define invalid papers and processing failures.

## 1. Target Scope

Extract only experimental **CFST column ultimate load-capacity data**.

A specimen row is in scope when all are true:

- the tested member itself is a concrete-filled steel tube column, stub column, short column, slender column, or long column
- the row has an experimental ultimate load capacity, stored as `Nexp (kN)` / `n_exp`
- the loading is axial compression, eccentric compression, combined compression with recoverable axial ultimate load, or another column test whose ultimate load capacity can be stored as `Nexp`
- the required geometry, material, loading, and condition fields are recoverable or explicitly marked by the schema as unknown/null where allowed

Do **not** exclude a CFST column row because it is non-ordinary, specially treated, conditioned, damaged, strengthened, high-temperature, post-fire, cyclic, dynamic, sustained-load, stainless-steel, UHPC, recycled, or otherwise outside an ordinary dataset. Capture those differences in `Material`, `loading mode`, `condition`, notes, and `source_evidence`.

Exclude before extraction:

- beams or flexural beam tests
- joints / beam-column joints
- connections and connection tests
- frame or subassembly tests when the column specimen's own ultimate capacity cannot be separated
- wall, pier, brace, panel, slab, or other non-column members
- pure bending tests without a recoverable column axial/eccentric ultimate load capacity
- hollow steel tube / bare steel tube / empty steel tube / steel-only controls without concrete infill
- concrete-only controls, steel-only controls, or other non-CFST comparison rows
- FE-only, theory-only, review-only, or numerical-parametric rows without physical specimen capacity data
- papers where CFST columns appear only as background and no separable CFST column ultimate-capacity data can be recovered

A paper is `is_valid=true` when at least one in-scope CFST column specimen row can be extracted. A paper is invalid only when no in-scope CFST column ultimate-capacity data can be recovered.

Grouped average ultimate capacities are usable when the paper explicitly defines the repeated-specimen group membership, or gives enough specimen-count / parameter-set mapping to assign the same reported average to each member specimen row without fabricating group composition. In that case, store the same `Nexp` / `n_exp` on each member row, mark each affected row with an appropriate quality flag when the schema supports it, and make `source_evidence` state that the value is a reported group average.

If a paper reports only grouped averages but the member-to-row mapping is not defensibly recoverable, do not fabricate individual specimen rows.

## 2. Required Parameters

Record only **CFST column ultimate load-capacity data**. Do not include beams, joints, connections, pure-bending tests, or similar non-target data.

Parameters to extract:

| Col | Header       | Unit | Meaning                                                                                                                                                   |
| --- | ------------ | ---- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A   | Ref.info.    | —    | Bibliographic string identifying the source paper                                                                                                         |
| B   | fco (MPa)    | MPa  | Concrete compressive strength as directly reported in the paper                                                                                           |
| C   | fc_type      | —    | The strength basis represented by `fco` (usually a specimen geometry, but it follows the stored value's basis when the paper explicitly converts results) |
| D   | Specimen     | —    | Specimen label or ID, exactly as given in the source                                                                                                      |
| E   | fy (MPa)     | MPa  | Steel tube yield strength                                                                                                                                 |
| F   | R (%)        | %    | Recycled aggregate replacement ratio; 0 if not applicable or not reported                                                                                 |
| G   | b (mm)       | mm   | Section outer width (for circular sections: b = h = outer diameter D), b >= h                                                                             |
| H   | h (mm)       | mm   | Section outer depth or height                                                                                                                             |
| I   | t (mm)       | mm   | Steel tube wall thickness                                                                                                                                 |
| J   | r0 (mm)      | mm   | Outer corner radius (see section_shapes.jpg)                                                                                                              |
| K   | L (mm)       | mm   | Specimen length                                                                                                                                           |
| L   | e1 (mm)      | mm   | Eccentricity at the upper end; 0 for axially loaded specimens                                                                                             |
| M   | e2 (mm)      | mm   | Eccentricity at the lower end; 0 for axially loaded specimens                                                                                             |
| N   | Nexp (kN)    | kN   | Experimental ultimate load capacity                                                                                                                       |
| O   | Group        | —    | Section shape group: A, B, or C                                                                                                                           |
| P   | Material     | —    | Steel and concrete material information for CFST columns                                                                                                  |
| Q   | loading mode | —    | Loading mode and loading history applied to the specimen                                                                                                  |
| R   | condition    | —    | Conditions applied to the specimen before or during testing                                                                                                |

ref_info, for example:

```json
"ref_info": {
  "title": "钢管高强混凝土轴压力学性能的理论分析与试验研究",
  "authors": ["韩林海"],
  "journal": "工业建筑",
  "year": 1997,
  "doi": null,
  "language": "zh"
}
```

## 3. Concrete Strength Rules

fco and fc_type:

fco: the concrete compressive strength value reported in the table, numeric, for example: `fco = 43 MPa`

fc_type: the concrete compressive strength type corresponding to the concrete compressive strength value reported in the table. It is a string: strength basis (`cube`, `cylinder`, `prism`, `unknown`) + marked size, for example:

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

## 4. Section Shape And Geometry Rules

Section shape parameters: refer to `references/section_shapes.jpg`. `b` is the longer side, so `b >= h`.

Special cases:

For Group A (square or rectangular sections):

- `r0` is generally `0`, but if the paper states that the square/rectangular section has rounded corners, `r0` may be nonzero.
- When `r0` is nonzero, the reason must be stated in `notes`.

For Group B (circular sections):

- `b == h && r0 = h/2`

For Gruop C (round-ended sections):

- `b > h && r0 = h/2`

`L`:

Determine `L` as the project geometric specimen length in the following priority order:

1. Explicit specimen length in the paper text / tables / notes
2. Explicit formula or ratio with clear variable meaning
3. Figure-based derivation with clear geometric evidence, including steel-tube clear height when the figure makes that geometric relationship clear

If the paper does not directly name `L`, but the specimen / setup figure makes the steel-tube clear height derivable, use that geometric length and record the basis in `source_evidence`.

When the geometric basis is ambiguous, do not populate `L`. Do not infer `L` from boundary-condition assumptions or effective-length formulas.

## 5. Eccentricity Rules

Eccentricity:

Upper-end eccentricity, signed: `e1_mm`

Lower-end eccentricity, signed: `e2_mm`

In particular, if `e_x_top_mm` (top x-direction eccentricity, in mm) and `e_y_top_mm` (top y-direction eccentricity, in mm) are distinguished, then:

$$ e1 = \sqrt(e_{x,top}^2+e_{y,top}^2) $$

The lower-end eccentricity follows the same rule.

| Loading mode | e1_mm | e2_mm | Meaning |
| ------------ | ----- | ----- | ------- |
| Axial loading | 0 | 0 | Load passes through the section centroid |
| Equal-end eccentric loading | e | e | Upper and lower eccentricities are equal |
| Unequal-end eccentric loading | e1 | e2 | Upper and lower eccentricities are unequal |

## 6. Material Rules

Material information: only when `other` is used, `note` is required; in other cases, `note` is optional.

Material.steel:

Includes:

- `carbon_steel`
- `stainless steel`
- `other`

When `other` is used, briefly describe it in `Material.steel.note`.

Material.concrete:

Includes:

- normal (low strength, high strength)
- `UHPC`
- recycled concrete
- `other`

When `other` is used, briefly describe it in `Material.concrete.note`.

## 7. Loading Mode Rules

loading mode: only when `other` is used, `loading mode.description` is required; in other cases, `loading mode.description` is optional.

- `monotonic`: monotonic static loading
- `cyclic`: cyclic / reversed loading
- `sustained`: long-term load / sustained load
- `dynamic`: impact, blast, or dynamic loading
- `thermal`: high temperature, fire, or post-fire residual
- `other`: other type; `loading mode.description` must be filled with a brief description.

## 8. Condition Rules

condition: only when `other` is used, `condition.description` is required; in other cases, `condition.description` is optional.

tags:

- `normal` # conventional undeteriorated specimen; no corrosion, freeze-thaw, high temperature, pre-damage, or obvious defect
- `corrosion` # corrosion condition, such as chloride corrosion, acid-rain corrosion, atmospheric corrosion, electrochemical accelerated corrosion, etc.
- `freeze_thaw` # freeze-thaw condition, such as water freeze-thaw, salt freeze-thaw, multiple freeze-thaw cycles, etc.
- `thermal` # temperature/fire condition, such as high-temperature action, fire exposure, post-fire residual capacity, etc.
- `long_term` # long-term action condition, such as sustained load, creep, service-load history, etc.
- `defect` # initial or construction defect, such as debonding, voids, initial gaps, local dents, initial geometric imperfections, etc.
- `damage` # pre-damage condition, such as preload damage, impact damage, cyclic damage, residual capacity after local buckling, etc.
- `strengthened` # strengthening/repair condition, such as FRP strengthening, steel-sleeve strengthening, concrete/UHPC jacketing, post-corrosion repair, etc.
- `other` # other special condition that cannot be classified into the above categories

`description`: a brief textual description of the condition, used to record the specific situation.

## 9. Evidence And Numeric Rules

## 10. Invalid Or Failed Extraction

### 10.1 Invalid Paper

Produce an invalid JSON using `JSON_contract.md` when the paper has no extractable CFST column ultimate-capacity data, including when it is:

- FE-only
- theory-only or review-only
- a non-column CFST study without separable column-specimen ultimate-load data
- a beam, joint, connection, frame, pure-bending, or non-CFST-control study without in-scope CFST column rows
- missing recoverable experimental ultimate load capacity for every potential CFST column row

### 10.2 Processing Failure

When evidence is insufficient for a defensible extraction:

- stop with a clear failure reason
- do not fabricate row values
- keep intermediate output outside final published output
