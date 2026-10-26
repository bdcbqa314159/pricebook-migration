# Spec — swaption-cluster slice B: the cube calibration (retires `swaption_vol_cube.py`)

**Date:** 2026-10-26 · **By:** Cowork · **Baseline:** v0.113.0 · **Answers:** thread 0004 + 0005.
**Scoping input:** `AUDIT_swaption_vol_cube.md` (nine findings; §1 disposition, §3 shape). Read that
for the resident inventory — this spec references its findings by id, it does not restate them.

Slice B builds **two things** (audit §1): a node-scanning SABR calibration over a quoted smile grid,
and the at-pillar cube read. It is the **first ng consumer of slice 24's implied-vol inverter**. It
**ticks `swaption_vol_cube.py` deletable** (22 → 23 / 793) once the retire-read confirms the residual
is all deferred-*capability*, no deferred-*product* (§4).

---

## The two rulings Code asked for (0005)

### Ruling B1 — F1's surviving-node criterion is an acceptance criterion, and it is LAW, not judgement.
Code's reading is correct and now has a name. The cube calibration's content IS a grid (a structure),
so §6's structural-oracle rule binds it on **both** faces:
- **first clause (test the structure):** the oracle is a **count**, not an ATM reprice. A cube that
  calibrates N quoted smiles must yield N calibrated nodes.
- **second clause (floor-on-population):** a filtered/collected population asserts a floor on
  survivors. `except Exception: pass` is the floor-less filter in its purest form — forbidden.

So two criteria, both law-governed (not Code's discretion): **no silent drop** (a failed fit is a
value, never a vanished node — see B2) and a **node-count floor** (`calibrated == quoted`, asserted;
a partial cube is only ever a *visible, counted* partial). F1 is the fourth instance of the pattern
§6's second clause now governs; this is that clause applied one level down, to the slice's own grid.

### Ruling B2 — a failed node fit is a VALUE recorded in a `CalibrationResult`, never a raise, never a drop.
Of Code's three options (PricingFailure-shaped value / raise / recorded partial `CalibrationResult`),
the answer is the third, and it subsumes the first at the calibration layer. ng already has the
shape: single-smile `calibrate_sabr_smile` returns a `CalibrationFailure` carrying residuals on a
converged-but-unacceptable fit (the 1bp gate), and F2's contract is
`calibrate(quotes, spec) → (output, CalibrationResult)`. The cube follows it:
**Mechanism (corrected against the repo per thread 0007 — adopted, it is sharper than the original
draft).** `CalibrationResult` is `(residuals, converged, jacobian)` — curve-shaped, no counts, no
keying. So the cube does **not** return a count-bearing record. It returns

```
Mapping[SwaptionSurfaceKey, tuple[SabrParams, CalibrationResult] | CalibrationFailure]
```

keyed by **every quoted node**, the value *exactly* `calibrate_sabr_smile`'s own return type — the
cube's per-node outcome IS the single-smile calibrator's outcome, composed, **no new type** (§3d; the
rule of two is not tripped). The `SwaptionSurfaceKey → SabrSurface` map is **derived** from the
successes. `SwaptionVolCubeResult` (the quarry's 4-field record) is **shed**.

- A dropped node is **impossible by construction**, not merely detected: the map is keyed by the
  quoted grid, so a vanished node cannot be represented. Oracle 1 still asserts it, now testing a
  property the type guarantees — the stronger position.
- **Counts are derived, never stored:** `calibrated = len(successes)`, `quoted = len(outcomes)`. A
  *stored* count is itself a proxy that can drift from the collection it summarises — the exact defect
  §6's second clause forbids — so deriving it is the floor rule applied to itself. Do not add count
  fields even where there is room.
- A node that fails is **present as its `CalibrationFailure`** (residuals carried), absent from the
  derived SabrSurface. Never swallowed, never raised — raising is what `except: pass` hid from; silent
  drop is F1.

### Ruling B3 (consequence, so Code does not build deferred infra) — F9's `interp_surface` atom is DEFERRED, not a slice-B criterion.
Code offered F9's single shared atom as an acceptance criterion. Refined: slice B is **at-pillar**
(exact `SwaptionSurfaceKey` + `SabrSurface.at_expiry` pillar lookup, as slice A ratified). All ATM /
off-grid interpolation is **off-pillar / cross-node machinery**, which the tracker already defers to
its first off-pillar consumer (audit F6). §6b forbids building a deferred capability ahead of its
consumer. So:
- **Do not build `interp_surface` in slice B.** An off-pillar cube query is a `PricingFailure` (or a
  raise at a non-engine boundary), never a silently clamped edge value (F6's silence is the defect,
  separate from the deferral).
- F9's criterion is therefore **negative**, exactly like F7: the double-implemented, mutually
  disagreeing ATM atom **must not cross** — neither copy. When the off-pillar consumer arrives, the
  atom is built **once**, §3d, in `foundation/interpolation` (bilinear is finance-free → L0),
  composed by both the calibration and the read. Forward-link it on that consumer's row.
- This keeps the tick honest: off-pillar interpolation is a deferred *capability* (a method on the
  cube), not a deferred *product*, so it never blocks the tick (§4).

### Ruling B4 — the forward must thread through the FIT, not just the read (thread 0008; ML-D1's fit-side close).
Code's §6 stop is correct and the fix is ratified. Slice A threaded the forward through the **read**
(`SABRModel.swaption_vol` takes it); `calibrate_sabr_smile` still reconstructs its own forward from
`index.canonical_accrual(smile.expiry)` (`sabr_calibrate.py:81`) — the single-period *caplet*
forward. That is correct for a caplet (its forward IS that single-period forward, which is why
`calibrate_capfloor_sabr` composes it cleanly) but **wrong for a swaption node**, whose forward is the
swap rate `S = float_leg_pv/rpv01`. Composing it unchanged would re-open ML-D1 per node — the 48.8bp
gap — one slice after the read side closed it. It cannot be patched inside the fit: `SabrCalibrationSpec`
is already at §3b's 5-field ceiling, and the limit never rises.

**Ratified — option 1: `SmileQuote` gains a required `forward` (3 → 4 fields, ≤5).** A market vol
smile *is* quoted at a forward; without it the vols are uninterpretable, so the forward is intrinsic
market data that must travel **with** the smile — the same argument (and the same docstring) that puts
`law` on `SabrSurface`. This is §3b's "fold into the ratified type," not bloat. `calibrate_sabr_smile`
then fits at `smile.forward` and the `canonical_accrual` reconstruction is **deleted** — so each
consumer supplies the forward its *own* product defines: the swaption cube passes the node's
`S = float_leg_pv/rpv01` (equal, by construction, to the forward the engine marks on the read side),
and `calibrate_capfloor_sabr` passes the caplet's single-period `forward(projection, canonical_accrual)`
it reconstructs today — **byte-identical** for the caplet, now explicit at the call site. The fit and
the read compose the **same S by construction**, which is what ruling A established and what §3d
requires; no guard. **ML-D1's fit-side instance closes here** — slice A's close (v0.111.0) covered the
read only; record that honestly rather than leaving a surviving instance under a "closed" label.

Rejected (Code's alternatives, correctly): a `SwaptionSmileQuote` sibling duplicates the smile atom at
one consumer (§3d, rule of two); an optional `forward=None` canonical fallback reinstates the exact
hidden default slice A deleted, silently wrong precisely on the non-canonical underlyings where it
matters.

---

## Build

**L3 calibration — `build_swaption_vol_cube` (the real content).** For each quoted node
(expiry × swap_tenor) in the grid: take the node's quoted smile, compose `calibrate_sabr_smile` over
the shared `sabr_vol` atom (the slice-21 fit, bounded LS, 1bp gate), at the node's forward carried on
the `SmileQuote` (B4) — the node's `S = float_leg_pv/rpv01`, equal by construction to the forward the
engine marks on the read side. Emit the outcome per node into the keyed map (B2); derive the
`SwaptionSurfaceKey → SabrSurface` from the successes. β is an **explicit** calibration input, never a
hidden default (audit F8, invariant 5).

**The inverter consumer (first in ng).** Quotes may arrive as **prices** (premiums) or as vols. When
prices: invert via slice 24's law-generic `implied_vol(law, call_price, forward, strike, t)` to market
vols **before** the SABR fit. This is why B is the inverter's first consumer; compose it, do not
re-derive an inversion (§3d).

**L3/L4 read — unchanged from slice A.** `SABRModel.swaption_vol` already reads the surface and prices
through the engine at the threaded forward (v0.111.0, untouched by all nine findings). Slice B only
*populates* the surface the read already consumes; at-pillar, exact key.

**Do not port:** F7 (`bumped` — adds an absolute shift to `alpha`; wrong by 5.4–6.2×; ng has no cube
bump, so nothing inherits it — a cube bump, when built for L5 risk, bumps the vol and re-implies
alpha); F2 (`_nearest_sabr` nearest-node snap — tracker-shed); F3/F4/F5 (ATM fast-path + bare
fallbacks returning grid-ATM / 0.0 — the silent-failure family); F9 (the double atom, per B3).

---

## Oracles (§6; B1 makes the structural one mandatory, RED before GREEN per §8)

1. **STRUCTURAL — node count / no silent drop (B1, the floor rule on this slice's own grid).**
   Calibrating N quoted smiles yields N nodes. A test feeds a **deliberately unfittable node** and
   asserts it surfaces in the `CalibrationResult` as a counted failure — never vanishes, never raises.
   Assert `calibrated_count == quoted_count` on a clean grid; assert the failure is present and
   counted on the poisoned grid. This is the oracle a reprice-the-ATM-backbone test is blind to.
2. **S-identity per node, on a NON-CANONICAL underlying (carries slice A across the grid; vacuity
   closed).** Each calibrated node's ATM payer, priced at the engine's marked S, lands at that node's
   SABR smile minimum. **The test grid's underlying MUST be non-canonical** (semi-annual / ACT-360,
   not annual / ACT-365F) with the quoted `SmileQuote.forward` set equal to the engine's marked S:
   Code confirmed (0008) that a canonical underlying makes `S == index.canonical_accrual`'s forward,
   so the oracle passes with every node mis-fit and the defect fully latent. Only a non-canonical
   underlying makes `canonical_accrual`'s forward *wrong*, so the test bites — this is why slice A's
   RED test carries that name, and B4's deletion of the reconstruction is what it proves per node.
3. **Round-trip per node (self-consistency, non-vacuous because oracle 1 supplies the floor).**
   Calibrate a node from synthetic SABR-generated vols; recover params within the 1bp gate.
4. **Inverter parity (proves the slice-24 consumer composes).** A node quoted in **prices** inverts to
   the same vols — hence the same fitted params — as the identical node quoted directly in those vols.
5. **β explicit (F8).** No hidden default; a build with an unstated β is a contract error, not a 0.5.

Tolerances, not `==`, on transcendental results (§7c).

---

## Deferred (forward-linked, each a capability not a product — none blocks the tick, §4)
- off-pillar / cross-node interpolation **and** the `interp_surface` L0 atom (B3) → first off-pillar
  consumer (audit F6).
- cube vol bump → L5 risk (rebuilt correctly: bump vol, re-imply alpha — never port F7).
- arb-free SABR (Hagan-2002 wing arb is a known limit) → its own slice.

## Tick / retire-read (§4 deletable-bar rigor — do at the end, before ticking)
Read `swaption_vol_cube.py` end-to-end; confirm every omission is `shed`/`superseded`/`deferred→X`
with evidence (the audit already classifies seven of nine). The tick stands iff the genuine residual
is empty and every deferral is a capability, not a whole product. Then 22 → 23 / 793 in
`quarry_reconciliation.md`; version + CHANGELOG; one `chore(release):` commit (Code owns it, §7/§8).

## Process (§8)
Branch `slice/<NN>-swaption-cube-calibration`. Commits: audit → align → **test (oracles 1–5 RED)** →
feat (GREEN) → docs (provenance + retire-read + this spec referenced). Red-before-green is per step;
oracle 1 (the structural count) is net-new behaviour, so it is RED first, not a refactor carve-out.
Merge gate: oracles green + `verify.py` (incl. the new `TEST_FLOOR`, raised if this slice adds a tier)
+ both OSes.
