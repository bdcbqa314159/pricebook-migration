# Checkpoint — SABR cluster (the vol smile: price + calibrate)

**Version:** v0.107.0 · **Slices:** `slice/20-sabr-caplet` (read, v0.106.0) + `slice/21-sabr-calibrate`
(v0.107.0) · **Baseline:** v0.105.0 (v0.98 audit close, 20/20).

The first **volatility smile** in the new tree, and the first calibration **family** beyond curves + the
flat-vol strip. Two slices form one capability cluster — SABR pricing (`sabr_vol` + `SABRModel`) and its
smile calibration (`calibrate_sabr_smile`). A capability-cluster boundary → checkpoint (§6).

## 1. The headline — a smile with no signature change (rule-of-two on `BlackVol`)
`SABRModel` is the **second `BlackVol` implementer** (after `BlackModel`) and the **first that reads
`strike`**. The caplet grew a full strike-dependent smile with **zero change** to the `BlackVol`
signature (`black_vol(index, expiry, strike)`), the engine (`price_caplet` byte-identical), or the
snapshot shape (`surfaces` widened to `Surface | SabrSurface` — a new *representation*, not a new field).
This is the payoff doc 22 Q1 predicted: the capability protocol absorbed a materially richer model as a
drop-in. The calibrator then closed the **read→calibrate** arc, composing the *same* `sabr_vol` atom the
model reads — so calibrate-to-quote and price-to-smile are one fact by construction (§3d).

## 2. §3d F-identity — verified byte-identical, not asserted
The load-bearing constraint across both slices: `SABRModel.black_vol` and `calibrate_sabr_smile` both
derive the forward from the model's **own** projection curve via the **same** canonical accrual
(`Accrual(expiry, expiry + index.id.tenor, index.accrual.day_count)`) and the **same** `forward` atom the
L4 caplet composes. Confirmed `F_model == F_engine` **to the bit** for the standard caplet. Consequence:
fitted params → `SabrSurface` → `SABRModel` reproduce the calibrated smile at exactly the F priced at —
the ATM strike lands on the smile minimum by construction, no cross-stage forward drift.

## 3. Oracle-quality audit
| Oracle | Class | Result |
|---|---|---|
| `sabr_vol` vs independent inline Hagan (2.17a), 6 strikes | **closed-form cross-impl** | <1e-14 |
| ATM (F=K) branch vs published eq 2.18 | closed-form anchor | <1e-14 |
| β=1, ν=0 → σ_B ≡ α at every strike (degenerate lognormal) | closed-form anchor | <1e-14 |
| F=K seam continuity (z/χ→1 removable limit) | limit check | <1e-4 across the seam |
| ρ<0 skew orientation (low-strike vol > high-strike vol) | qualitative sign | asserted |
| Caplet reprices to Black-76 at the SABR vol through the unchanged engine | closed-form cross-engine | <1e-10 |
| **Calibration round-trip:** recover a known seed `SabrParams` from its own smile | **known-answer** | α/ρ/ν <1e-6; max resid ~8e-11 |
| **Reprice identity:** `SABRModel.black_vol` reproduces every target vol post-fit | closed-form cross-stage | <1e-6 |
| Degenerate smile (non-positive strike → lognormal undefined) → `CalibrationFailure` | value-not-raise | asserted |
| `SmileQuote` shape (ascending, len-match, ≥3 pts) → `ValueError` | input validation | asserted |

The round-trip is the load-bearing anchor: the seed is a *known answer* (not just fit-converges), and
recovering it **also proves the F-identity** — the fit's forward must equal the generating forward or the
seed would not come back. The reprice identity closes the loop back through the pricing path.

## 4. Challenge-me
- **`converged` reads the solver's success flag, not a residual-acceptance gate.** A converged-but-poor
  fit returns a `CalibrationResult` with large residuals (reported), *not* a `CalibrationFailure` — because
  scipy TRF genuinely converges on a contradictory smile (it finds the best fit). So the failure oracle keys
  on a real lognormal degeneracy (non-positive strike), not "residuals too big." **Open question for Cowork:**
  is that the right contract, or should calibration reject a converged fit whose max vol-residual exceeds a
  tolerance? Deferred: the round-trip/reprice oracles need exact fits, so no acceptance gate is *exercised*
  yet; the first noisy-market-smile consumer forces the decision (and it's a ≤3-line addition, `SolveConfig`
  already carries a `tolerance`).
- **The F-identity rests on a *canonical-accrual assumption*, documented but not enforced.** F matches the
  engine byte-identically **for a standard caplet** whose accrual is `[expiry, expiry+tenor]` on the index
  day-count. A non-canonical **stub** caplet (odd end date / different day-count) would make `black_vol`'s
  reconstructed F silently diverge from the caplet's own F — the smile evaluated at the wrong forward. In
  scope nothing books such a caplet; the coupling is a code comment, not a guard. **Re-open trigger:** the
  first stub/non-standard optionlet consumer — at which point the honest fix is to thread the accrual, which
  *does* touch the `BlackVol` signature (the one change this cluster avoided).
- **Drawdown did not move — 19/793, and both slices are `tick 0`.** SABR is real, tested capability that
  retires **nothing** (`options/sabr.py` stays resident: shifted/normal variants + DB-persistence artefact
  block the tick). Stated plainly: we are building smile capability *ahead* of emptying the quarry. Justified
  as ratified forward progress after the audit, but the §4 "breadth waits while drawdown is stuck" spirit says
  the next slices should bias toward **retiring** — either the SABR variants that finish `options/sabr.py`, or
  back to the linear/multicurve backlog that actually ticks modules.
- **β is fixed, never fitted.** The 3-parameter fit (α, ρ, ν) is the market-standard treatment (β chosen a
  priori, not identifiable from a single smile). β-calibration is deferred to its consumer — flagged so it is
  a *decision*, not an omission.

## 5. Smell + debt scan
- `verify.py` acyclic/fields/layers/provenance/version/**debt** all green; pyright 0 errors; 291 tests.
- **Field/arg discipline:** `SabrParams` 4 fields, `SabrSurface` 1, `SmileQuote` 3, `SabrCalibrationSpec`
  5 — all ≤5. `sabr_vol` 4 args, `calibrate_sabr_smile` 1, `least_squares`/`root_nd` 5 (bounds added). No
  suppressions added → debt balance unchanged (suppressions − ledger = 0).
- **§3d exception-count: 0 type-switches** in the pricing/calibration path — the surface-union narrowing
  (`vol_surface.flat_surface`) lives in the market value module, keeping the `Surface | SabrSurface`
  `isinstance` **out of `risk/`** (the §1 no-isinstance guard test stays green). One composition path each.
- **acyclic** confirms `calibration/sabr_calibrate.py` composes L1 (`forward`, `SmileQuote`) + L3
  (`sabr_vol`, `SabrParams`) + L0 (`root_nd`) with **no L4 import** (L3 ⊥ L4).
- Provenance drift fixed: the v0.106.0 header pointed at a non-existent `models/sabr.py` → `options/sabr.py`.
- New shared infra, both exercised (rule-of-two satisfied in-slice): `solvers` **bounds** pass-through
  (LM→TRF; first consumer = the SABR fit, a real box not a penalty) and `SmileQuote` (consumer = the fit).

## Drawdown (§4) — 19/793, tick 0 (PARTIAL crosses)
`options/sabr.py`: `sabr_implied_vol`/`sabr_price` (slice 20) + `sabr_calibrate`/`calibrate_sabr_smile`
(slice 21) cross to ng. **Resident, blocking full retire:** `shifted_sabr_implied_vol`/`shifted_sabr_price`
(negative-rate → shifted-SABR slice), `sabr_normal_vol` (Bachelier → normal-SABR slice), and the
`SABRCalibrationResult`/`CanonicalCalibrationResult` DB-persistence artefact (→ DB-spine crossing). Both
slices recorded in `quarry_reconciliation.md`. Numerator unchanged — no tick.

## Named next checkpoint
Whichever comes first (§6): **≤6 slices**, or the **next capability-cluster boundary**. Given the §4
drawdown-bias note (challenge #3), the recommended next work is a **retiring** slice — SABR variants that
finish `options/sabr.py` (shifted/normal), or a return to the multicurve/linear backlog that ticks modules
— rather than more net-new smile surface. Ruling deferred to Cowork.
