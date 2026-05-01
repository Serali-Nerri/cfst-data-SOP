# Concrete Strength Basis Rules

When auditing `fco` and `type`, the central question is:
**What strength basis does the stored `fco` value represent?**

That is not always identical to the raw specimen size that was physically tested.

This document provides a decision framework for answering concrete strength basis.

---

## Separate two concepts first

Before deciding `type`, distinguish:

1. **Raw test specimen geometry** — what the authors actually cast/tested
2. **Reported strength basis** — what basis the final numeric value is on when it is paired with
   the specimen rows in the paper

`type` must follow **(2)**, the basis of the stored `fco` value.

This matters whenever the paper converts one basis to another. For example:
- raw `100×100×100 mm` cube tests converted to **standard cube strength** → store as `Cube 150`
- raw cube tests converted to **axial/prismatic strength `fc`** → store as `Prism`
- raw `100×200 mm` cylinder tests reported directly with no conversion → store as `Cylinder 100x200`

---

## Priority order

Work through these levels top-down. Stop at the first level that gives a clear answer.

1. **Explicit statement of the reported basis or conversion target** — the paper says the value
   used is, for example, "standard cube compressive strength", "`fc = 0.76fcu`", or
   "converted cylinder strength". This is definitive for `type`.

2. **Explicit raw test description** — the materials or experimental section says something like
   "three 150mm cube specimens were cast" or "100×200mm concrete cylinders were tested."
   This is definitive only when the paper does not later convert the reported value to another basis.

3. **Table header or footnote** — the specimen data table labels the column as `fcu (N/mm²)`,
   `f'c (MPa)`, `Fc (N/mm²)`, or similar, with or without a footnote explaining the symbol.
   Combined with regional context this is usually sufficient.

4. **Referenced standard or test code** — the paper cites a standard like ASTM C39, GB/T 50081,
   BS 1881, JIS A 1108. Each has a default specimen geometry (see table below).

5. **Symbol and regional convention** — least reliable. Use only when 1–4 are absent.
   See the regional rules below.

---

## By standard / regional context

### China (GB/T 50010, GB 50017, JGJ 138, etc.)

| Symbol | Meaning | Default specimen |
|---|---|---|
| `fcu` | Cube compressive strength | 150mm cube (GB/T 50081) |
| `fck` | Characteristic strength (design code value) | Not directly a test value |
| `fc` | Axial compressive strength (设计值 or 轴心抗压强度) | 150×150×300mm prism, OR derived from cube via `fc = 0.76×fcu` or `fc = 0.67×fcu` |
| `Cxx` grade | Concrete grade (e.g. C40) | 150mm cube implied |

**Important nuance:** In Chinese practice, `fc` in a paper may be:
- Directly measured with a prism → `type = Prism`
- Derived from cube test results via a stated conversion → `type = Prism` is still defensible
  (the value represents axial/prismatic strength regardless of how it was obtained)

Another important nuance:
- If the paper says `100 mm` cubes were tested, but the reported value is the **standard cube
  compressive strength** after conversion, then `type = Cube 150`
- Use `Cube 100` only when the stored value itself remains on the `100 mm` cube basis

If the paper explicitly writes something like `fc = 0.73fcu` or `fc = 0.76fcu` in the
nomenclature, that tells you the measurement was actually on cubes, but the stored value
represents prismatic strength. In this case, keeping `type = Prism` is correct because
the `fco` value IS the prismatic/axial strength.

If the paper reports `fcu` directly as the primary variable, use `Cube 150` (or `Cube 100`
if the paper explicitly keeps the reported value on the 100 mm cube basis).

### United Kingdom (BS 1881)

| Symbol | Meaning | Default specimen |
|---|---|---|
| `fcu` | Cube strength | 150mm cube (BS 1881 Part 116) |
| `fck` | Characteristic cylinder strength (Eurocode context) | 150×300mm cylinder |

### Europe (EN 206, Eurocode 2)

| Symbol | Meaning |
|---|---|
| `Cx/y` (e.g. C30/37) | x = cylinder strength, y = cube strength |
| `fck` | Characteristic cylinder compressive strength (150×300mm) |
| `fcu` | Cube strength (150mm) |

When `fck` appears without a `Cx/y` grade, the default is cylinder. When a `Cx/y` grade
is present, x is the cylinder value.

### USA (ACI 318, ASTM C39)

| Symbol | Meaning | Default specimen |
|---|---|---|
| `f'c` | Specified compressive strength | Cylinder, 150×300mm (ASTM C39) |
| | | Sometimes 100×200mm for high-strength |

If the paper cites ASTM C39 or mentions "standard cylinder", use `Cylinder 150x300`.
If it mentions "4×8 in." cylinders, that is 100×200mm → `Cylinder 100x200`.

### Japan (JIS A 1108)

| Symbol | Meaning | Default specimen |
|---|---|---|
| `Fc` | Concrete compressive strength (圧縮強度) | Cylinder, 100×200mm (JIS A 1108) |
| `f'c` | Similar usage | 100×200mm cylinder |

---

## When the paper uses a non-standard specimen size

If the paper explicitly states a different size (e.g. "70.7mm cubes", "150×300mm cylinders"),
first ask whether the stored value remains on that raw basis.

- If the paper reports the **raw** non-standard result directly, record the actual size in `type`:
  `Cube 70`, `Cylinder 150x300`, etc.
- If the paper converts that raw result to a **standard** basis before reporting the value used
  in the specimen rows, record the **standard basis** in `type` instead.

---

## When evidence is insufficient

If you've read the relevant sections (nomenclature, materials, specimen table, test procedure)
and still cannot determine the specimen type:

- Set confidence to `Insufficient`
- Set verdict to `UNVERIFIED`
- Do not modify the sub-table
- Flag for manual review

**Do not guess** based on the numeric value alone (e.g. "28 MPa sounds like a cube strength").
Strength values overlap across specimen types.

---

## Common confusion points

**"The paper uses `fc` but the sub-table says `Cube 150`"**
Read more carefully — is `fc` the axial strength derived from cube tests, or measured directly?
Check the nomenclature for any conversion formula. If the paper says `fc = 0.67fcu` and the
stored `fco` is the cube value `fcu`, then `Cube 150` is correct. If the stored `fco` is the
derived `fc`, then `Prism` is more appropriate.

**"The paper says 100×100×100 mm cubes were tested, so `type` must be `Cube 100`"**
Not necessarily. Check whether the paper then converts the result to **standard cube strength**
before reporting the value used in the specimen table.

Example:
- Paper: `制作100 mm × 100 mm × 100 mm的立方体试块……换算后得到混凝土立方体标准抗压强度为33.6 MPa`
- Correct storage: `fco = 33.6`, `type = Cube 150`

Use `Cube 100` only when the stored numeric value itself is still on the 100 mm cube basis.

**"The paper doesn't mention specimen type at all"**
Check for: (a) a referenced standard in the experimental section, (b) the mix design table
which sometimes lists the target grade, (c) the figure caption for any test setup photo.
