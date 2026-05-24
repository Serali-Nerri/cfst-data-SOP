# CFST Effective Length (L) Rules

## Definition

`L` is the **effective length governing the stability behavior associated
with `n_exp`** — the equivalent unbraced length that, paired with the
section properties, drives the column's actual ultimate capacity. `L` is
rarely the bare steel-tube length; it reflects how the real column actually
buckles under its real end devices and loading.

## What `L` carries, what it does not

`L` carries the **end-state** effects on equivalent length:

- the rotational restraint of the column ends (pin / fix / cantilever, 刀铰
  / 球铰 / 销轴 / knife edge / spherical hinge / etc.)
- the geometric extension or retraction of the unbraced segment caused by
  end plates, end sleeves, loading platens, knife-edge bodies, and similar
  end devices

`L` does **not** carry the **moment / eccentricity distribution pattern**
along the length:

- end moment ratio β = M₁ / M₂
- single curvature vs. double curvature
- equivalent uniform-moment factors (Cm, β_M)

Those are already encoded by the signed eccentricities `e1` and `e2`. If a
paper introduces a coefficient that converts a "non-standard moment
distribution" into an "equivalent standard column" with a shorter equivalent
length (a moment-distribution k, not a boundary-condition K), **do not fold
that coefficient into `L`** — doing so double-counts what `e1` and `e2`
already carry.

## Notes to weigh before assigning `L`

- A paper often contains more than one length: bare steel-tube length,
  pin-to-pin distance with end fittings, "等效长度 / Le / 计算长度", an FEM
  effective length, a code-formula effective length. Identify which one
  enters the paper's own stability analysis (its λ formula, its capacity
  formula, its FEM boundary), and what physical effect it absorbs.
- Treat the paper's own usage as the strongest evidence: which length does
  the paper put into its λ, its φ(λ), its design / FEM check against the
  experimental `n_exp`? Follow that convention when it is clear.
- "等效长度 / Le / 计算长度" in Chinese papers do not always mean our `L`.
  A paper may use that term for moment-distribution conversion, cross-section
  equivalence, or other corrections. Read what the multiplier actually
  modifies before adopting the value.
- End loading plates, knife-edge bodies, and end sleeves go into `L` when
  the paper treats them as part of the unbraced segment (e.g. it explicitly
  extends L₀ to include device lengthening, or its λ formula uses the
  pin-to-pin distance). They stay out of `L` when the paper treats them as
  rigid load-transfer devices (e.g. its FEM boundary is applied at the
  specimen cover plate, or its λ formula uses the specimen length directly).
- Stub / short-column tests with simple plate ends often have `L = L_geo`.
  Do not introduce a restraint correction the paper does not justify.
- Welded fixed-end tests shorten the equivalent length; cantilever tests
  lengthen it. Read setup figures, test photos, and any explicit length
  expressions before committing.
- Same paper, multiple groups with different end conditions: assign `L` per
  group and record the difference in `Group_X.note`.
- When in doubt and the paper offers no defensible modification, the
  geometric specimen length is an acceptable fallback. Flag it.

## Physical background (intuition, not lookup)

Idealised end restraint produces well-known effective-length ratios — pinned
ends behave as the full unbraced length, fixed ends as roughly half, fix-pin
somewhere between, cantilever roughly double. Real tests rarely sit cleanly
on these idealised values, and a paper's own treatment of its setup usually
already encodes its judgement about where it falls. Use these intuitions to
sanity-check your choice; do not treat them as a formula to plug into.

## Fallback

If no end-fixture modification is present, the boundary cannot be defensibly
characterised, and no length-related formula is available, the geometric
specimen length is an acceptable fallback. Mark it explicitly in the
methodology note.

## Non-recoverable

If even the geometric length cannot be recovered, treat the row as not
recoverable under `extraction-rules.md` section 10.

## Methodology note (required)

Document how `L` was determined for the paper in one short sentence. Place
it at the scope where the choice is shared:

- one rule for the whole paper → `paper.notes`
- different rule per group (e.g. boundary-condition comparison tests) →
  `Group_X.note`
- one specimen deviates → specimen `note`

Phrase the note in natural language that names the **end-condition family**
and the **chosen length source**. Examples (illustrative, not literal
templates):

- `L taken as the reported effective length; pin-pin setup with knife-edge hinges.`
- `L = pin-to-pin distance per the paper's λ formula; includes loading-device lengthening.`
- `L = paper's specimen length; loading plates and knife-edge bodies treated as rigid load-transfer devices per the paper's FEM boundary.`
- `L = clear height between welded end-plate restraint points; fix-fix configuration.`
- `L = geometric specimen length used as fallback; end conditions not defensibly identifiable.`

L methodology phrases are an explicit allowed exception to the "no derivation
phrases in group / specimen note" rule in `extraction-rules.md` section 9.
Source identifiers (table / figure / `S\d+` / 表 / 图) remain disallowed even
within an L methodology note.
