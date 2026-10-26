# Ruling (slice 1) + spec (slice 2) — credit: the CDS product + its engine mark

**Date:** 2026-10-26 · **By:** Cowork · **Answers:** thread 0022. **Baseline:** v0.118.0, drawdown 25/793.

## 1. Slice-1 rulings

**Partial cross, NO TICK — RATIFIED.** `core/survival_curve.py` (271 lines, 14 methods, **59 production
importers**) is not superseded by ng's 5-method curve; nine methods have live consumers and are
forward-linked (`default_prob`/conditional reads → slice 2; `term_structure`/`pillar_hazards` → credit
reporting; `bumped_at` → L5 credit key-rate; serialisation → persistence), `to_calibration_result`
superseded by shape (doc 19). Residual not empty → no tick, honestly. Drawdown stays 25/793. This is
the SABR-read pattern: slice 1 built capability, it did not retire a module. Correct.

**`NG-DEFER-CREDITISDA` — RATIFIED, ledger it.** The green-oracle gate is **met at rung 1** without
ISDA: the protection leg is checked against the analytic flat-hazard integral
`(1−R)·λ/(r+λ)·(1−e^{−(r+λ)T})`, the continuous par spread against `λ(1−R)`, and `risky_annuity`
at λ=0 against `rpv01` to 1e-12 — a genuine pen-and-paper second method, not a restatement of the
numerical grid, so the slice does **not** rest on self-consistency. Inventing an ISDA number would be
a golden file dressed as rung 2 (a fake trusted mark — forbidden, §4). Deferring the real cross-check
is the honest move. Trigger: *a citable ISDA Standard CDS Model worked example* — the same bar the FX
asymmetric-ACI rule waits on. (The λ=0 `risky_annuity==rpv01` identity is the §3d atom-sharing proving
itself: the credit annuity IS the rates annuity when nothing defaults.)

**Design calls — both RATIFIED.** (a) `SurvivalHandle` a **sibling** protocol, not a widening of
`CurveHandle`: a survival curve answers `survival(t)`, not `df(t)`, and widening would force every
discount curve to answer a credit question — the exact `ImpliedVol`/`SwaptionVol` capability precedent
(§1, doc 22). (b) `bumped` shifts the **hazard**, not Q: it is the factor risk applies and it keeps
`Q=e^{−∫h}` monotone by construction — the right quantity to bump, the cube-bump lesson applied.

**The 12/yr protection-leg grid — acceptable, with two obligations.** The measurement is sound: error
plateaus/worsens past monthly because `CurveHandle.df` takes a **date**, so sub-month steps read `df`
early and the bias accumulates — so 12/yr is not a "more is better" knob, and the convergence oracle
rightly asserts a **floor** rather than assuming monotonicity that is not physically there. For slice 1
(calibration only, no engine) it stands as a documented module constant. Two obligations: **(i)** ledger
the `df(t: float)` continuous-time gap (`NG-DEFER-DF-CONTINUOUS`, trigger: a consumer needing
sub-monthly protection-leg accuracy); **(ii)** when slice 2's **engine** reads this grid, fold it into
the explicit numerical-config **integration** sub-family (invariant 5 — "lands with the first engine
that reads it"), not a hidden default.

## 2. Slice 2 — the CDS product (L2) + its engine mark (L4)
Mine `quarry/pricebook/credit/cds.py` for **content** (premium/protection legs, the StandardCDS
conventions), not structure. The §3d spine is already in place: `building_blocks.risky_annuity` and
`.protection_leg` exist and the bootstrap composes them — **the engine MUST compose the same two**, so
calibrate-to-par-spread and price-to-zero are one fact (the rates `rpv01` lesson, now in credit).

- **L2 `CDS`** — frozen vanilla single-name CDS: reference entity, premium `Schedule`, spread,
  recovery, notional+direction. ≤5 fields (§3b — bundle schedule terms / `Money` as needed). Pure
  data, no `pv()`. Credit-event / restructuring / seniority richness (§3c step 3) is **deferred to its
  consumers** — a standard CDS only; do not build the exotic convention surface speculatively (§6b).
- **L4 CDS engine** — `PV = protection_leg − spread·risky_annuity` (bought protection), composing the
  slice-1 atoms, reading the survival curve via `SurvivalHandle` and discount via `CurveHandle`.
  `PricingResult` decomposition (`pv`/`accrued`/`clean`); **invariant 6** — a seasoned CDS excludes
  historical premium and carries accrued-on-default explicitly. `default_prob` (=1−Q) and the
  conditional-survival reads forward-linked from slice 1 land here, needed-now.
- **Numerical config** — the protection-leg grid moves into the explicit integration sub-config here
  (obligation (ii) above).

**Oracle (structural-oracle rule — a par CDS telescopes, so self-consistency alone is blind):**
1. **Off-par closed-form flat-hazard CDS mark (rung 1, non-telescoping):** price an off-par CDS (spread
   ≠ par) against the analytic flat-hazard PV; `PV ≠ 0`, so a divergent annuity shows. This is the
   mandatory structural/closed-form oracle.
2. **Par CDS → zero upfront** (self-consistency, composing the bootstrapped curve).
3. **§3d identity:** the engine's par spread (the spread giving PV=0) equals the bootstrap's input
   spread at each pillar — calibrate and price are the same fact.
4. **Seasoned CDS** accrued/clean decomposition (invariant 6).

**Tick:** retire-read `credit/cds.py` end-to-end at the end (it is ~1000 lines — StandardCDS, forward
CDS, PnL attribution, index; likely a **partial** cross, vanilla CDS crossing while forward/index/
attribution/conventions forward-link to their consumers). Propose tick/partial with consumer evidence;
Cowork rules. Also re-assess whether slice-1's forward-linked `default_prob`/conditional reads now tick
any of `survival_curve.py`'s residual.

## 3. Process (§8)
Branch `slice/<NN>-credit-cds-mark`. audit → align → test (off-par closed-form + par-to-zero + §3d
identity + seasoned decomposition, RED first) → feat (GREEN) → docs (provenance: `credit/cds.py`,
source ISDA/O'Kane/Hull, oracle). Next checkpoint: ≤6 slices or the credit-cluster boundary.
