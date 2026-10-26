# Audit — swaption vol cube (slice B): the resident is four silent-wrongness sites, not a cube type

**Baseline:** v0.112.0 · **Scope:** `quarry/pricebook/options/swaption_vol_cube.py` (297 lines,
3 classes + 2 module functions) · **Mandate:** the resident half of the slice-25 partial cross —
`quarry_reconciliation.md` names *"the cube's CALIBRATION and node scanner → slice B"*.
**Status:** STOP AND REPORT before building. `CP_implied_vol.md` §6 required a scoping pass for this
cluster rather than an immediate build; this is it.

The smile READ crossed at v0.111.0 (`SABRModel.swaption_vol`). What remains resident is **not a data
structure we are missing** — it is a calibration path and a lookup path, and both are built on
silent failure. Five of the nine findings below are the *same defect family already shed twice*
(slice 23's synthetic smile, slice 25's nearest-strike snap).

---

## 1. Inventory, and where each piece lands

| quarry member | what it is | disposition |
|---|---|---|
| `SABRNode` (8 fields, `.vol`) | per-node params + ATM | **superseded** — ng's `SabrSurface` + `SabrParams` carry this |
| `SABRNode.vol` | Hagan read with an ATM fast-path and a bare fallback | **superseded** by `SABRModel.swaption_vol` (v0.111.0) — but see F3/F4 |
| `SwaptionVolCubeResult` | 4-field report record | **shed** — `CalibrationResult` (doc 19) is the ratified shape |
| `SwaptionVolCube.{vol,vol_by_years,atm_vol,smile}` | read surface | **superseded** by the capability + engine composition |
| `SwaptionVolCube.bumped` | parallel vol shift | **NOT superseded** — ng has no cube bump. **F7 is a live bug**; rebuild, do not port |
| `SwaptionVolCube._interp_atm` | bilinear ATM interp (method) | **crosses, as ONE shared atom with `_lookup_atm`** — see F9 |
| `SwaptionVolCube._nearest_sabr` | nearest-node-by-distance | **shed** (tracker names it) — see F2 |
| `build_swaption_vol_cube` | **the calibration** | **crosses** — the real content of slice B. See F1 |
| `_lookup_atm` | bilinear ATM interp (module fn) | **crosses, merged with `_interp_atm`** — see F9 |

**Net: slice B builds two things** — a node-scanning calibration over a quoted smile grid, and one
shared ATM-interpolation atom. Everything else is superseded or shed.

---

## 2. The findings

**F1 — `build_swaption_vol_cube`: `except Exception: pass` silently drops failed nodes (L235-237).
This is a floor-less filter, and it is the fourth instance of the pattern.**

```python
try:
    params = sabr_calibrate(fwd, strikes, vols, exp_y, beta=beta)
    ...
    sabr_nodes.append(SABRNode(...))
except Exception:
    pass                      # <-- a quoted node vanishes, no signal
```

20 quoted smiles with 5 failed fits yields a 15-node cube and no indication. If **every** fit fails,
`sabr_nodes == []`, the cube still constructs, and `vol_by_years` returns flat ATM at every strike —
a smile-free cube that reprices its own ATM backbone perfectly. **A self-consistency oracle cannot
see this** (§6, structural-oracle rule): it reprices what it built. Only a *count* can.

This is precisely thread entry `0002`'s open question, now with a fourth instance:

| instance | the check | never asserted |
|---|---|---|
| audit #10 | reprice-what-you-stripped | caplet grid = quote grid |
| `--layer 0` | CI test tier | a floor on collected tests (177/366) |
| `provenance` | four header lines present | that the path resolves (17/45 dangle) |
| **F1** | cube builds, ATM reprices | **a floor on nodes surviving the fit** |

**F2 — `_nearest_sabr`: distance in mixed units, with a magic tolerance (L177-189).** Ranks nodes by
`(e - t_exp)² + (t - tenor)²` — adding an expiry-year displacement to a tenor-year displacement as
if commensurable (a 2Y expiry move and a 2Y tenor move are not the same risk). Then `best_dist < 4.0`
is commented *"within ~2Y on each axis"*, which is **false**: `dist < 4` admits 2.0Y on one axis or
1.41Y on both. The node that wins then prices the **requested strike against a different
(expiry, tenor)'s smile**. Tracker already classifies this shed; recording the reason.

**F3 — `SABRNode.vol`: the ATM fast-path makes the smile discontinuous at the money (L43-44).**
`if abs(strike - forward) < 1e-8: return self.atm_vol` returns the **grid-interpolated** ATM, which
has no reason to equal the Hagan expansion at K=F. So σ(F) and σ(F±1e-8) differ by the
interpolation-vs-expansion gap. The in-file `T4-SVC1` note confirms the mechanism — it records that
an off-pillar node's wrong ATM "showed up at the exactly-strike-equals-forward fast-path." The
fast-path is the carrier, not the symptom.

**F4 — `SABRNode.vol`: `except (ValueError, ZeroDivisionError): return self.atm_vol` (L47-49).** A
failed Hagan evaluation returns the ATM vol, so a broken smile is indistinguishable from a flat one.
Same family as F1.

**F5 — `_lookup_atm` returns `0.0` on an empty axis (L261-262).** Zero vol is a plausible-looking
number that yields zero option value rather than an error.

**F6 — both interpolators clamp off-grid queries to the edge, silently.** `i = max(0, min(i, n-2))`
plus weight clamping means a 40Y expiry on a grid ending at 10Y returns the 10Y value with no flag.
The tracker defers *cross-node interpolation* to the first off-pillar consumer — correctly — but the
**silence** is a separate defect from the interpolation choice.

**F7 — `bumped(shift)` adds an absolute vol shift to SABR `alpha`. VERIFIED WRONG, 5.4–6.2×.**
`alpha` is a vol only when β=1; for β≠1 it scales as `vol · F^(1-β)`. Measured against ng's own
`sabr_vol` (F=0.03, β=0.5, ATM=20%, T=5Y, ρ=−0.3, ν=0.4):

| strike | intended | realised | factor |
|---|---|---|---|
| K=F | +1.0 bp | **+5.97 bp** | 5.97× |
| K=1.25F | +1.0 bp | **+5.43 bp** | 5.43× |
| K=0.80F | +1.0 bp | **+6.19 bp** | 6.19× |

Predicted `1/F^(1-β) = 5.77×` — the measurements bracket it. The bump is also **strike-dependent**,
so it *tilts* the smile; the docstring claims it shifts alpha *"for smile consistency"*, which is the
opposite of its effect. ng has no cube bump yet, so **nothing inherits this** — but any rebuild must
bump the vol and re-imply alpha, never bump alpha.

**F8 — `beta: float = 0.5` is a hidden default (L205).** β is a calibration *choice* that shapes the
whole smile. Engine-contract invariant 5: config is explicit, never a hidden default.

**F9 — the ATM-interpolation atom is implemented twice and the copies disagree. VERIFIED.** §3d
("an atom is defined ONCE and every stage COMPOSES it") is violated inside a single file:
`_lookup_atm` carries degenerate-axis branches, `_interp_atm` does not. Replicating both verbatim on
identical inputs — 1 expiry × 2 tenors, grid `[[0.20, 0.30]]`, query (1.0, 3.0):

```
_lookup_atm : 0.25
_interp_atm : IndexError: index 1 is out of bounds for axis 0 with size 1
```

The calibration populates each node's `atm_vol` via `_lookup_atm` while reads go through
`_interp_atm`, so the two paths can disagree *by construction* — the §3d annuity failure mode
(calibrate with one atom, price with another), in miniature.

---

## 3. What this means for slice B's shape

1. **The tick is real but it is not a port.** `swaption_vol_cube.py` goes deletable when ng has the
   calibration + the shared ATM atom. Seven of nine findings are shed or superseded; two (F7, F9)
   are bugs that must not cross.
2. **F1 decides the oracle before it decides the code.** A cube calibration whose oracle is
   "reprice the ATM backbone" is structurally blind, exactly as the cap-vol strip was for three
   slices. The slice needs a **node-count** criterion and a **no-silent-drop** criterion; a failed
   fit must be a `PricingFailure`-shaped value or a raise, never a vanished node.
3. **F9 is the §3d atom to name:** one `interp_surface(expiries, tenors, grid, x, y)` that the
   calibration and the read both call. That is the building block this cluster was missing.

## 4. Blocked on

**Thread entry `0002`'s ruling.** F1 is a fourth instance of the floor-less-filter pattern, so
whether slice B's node-count criterion is *law* (§6 second clause binding the verification
apparatus) or *my judgement* is the same open question — and it now has a consumer waiting on it.
Recommend Cowork rule `0002` and mandate slice B in the same pass.

## 5. Unaffected, ready once ruled

`SABRModel.swaption_vol` and the threaded-forward signature (v0.111.0) are untouched by all nine
findings — the cube's defects live in the calibration and lookup paths, not the smile read. Slice 24's
implied-vol inverter is likewise ready and becomes this slice's first consumer (a cube built from
prices needs it). 366 tests green; drawdown unchanged at 22 / 793 until the tick lands.

**Also recorded (pre-existing, not slice B's):** the quarry no longer imports —
`quarry/pricebook/core/__init__.py` pulls `core.discount_curve`, which was physically parked at the
T1 close. §7c's "nightly quarry regression" is therefore currently impossible. Logged separately;
this audit verified F7/F9 by replicating the arithmetic against ng's `sabr_vol` instead (§7bb).
