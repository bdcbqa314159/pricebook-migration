# Spec — equity greeks + the generic `ScalarBump` (sequenced between c1 and c2; a bar-mover)

**Date:** 2026-10-28 · **By:** Cowork · **Answers:** thread 0057. **Baseline:** v0.134.0, drawdown 30/793.

## 0. c1 ratified, and the three calls confirmed
Equity c1 is clean (0 ticks, greenfield; `EquityUnderlying` the whole L0 footprint; spot/dividend/vol
as keys, no new field; `EquityVol` additive on `BlackModel`; L4 composes `equity_forward` + the existing
`black`). All three of your §3b calls are right — each is the single-source / make-it-unwritable
discipline:
1. **forward takes `df`, not `r`** — `df` owns `e^{−rt}`; a separate `r` would re-derive it and let them
   disagree. Correct.
2. **spot and dividend are two keys** — independently bumped; one key would make a dividend bump
   indistinguishable from a spot bump (and this slice is exactly why that must be distinguishable).
3. **`currency` a field on `EquityOption`, not derived** — deriving it silently marks a EUR option off
   the USD curve in a two-currency book. Field, at the 5-limit, correct.

## 1. Take the sequencing — this slice goes before c2
Your retire-read is right: `options/equity_option.py`'s price is superseded, its **greeks suite** is the
residual (4 live importers), and the structural block is that **ng has no spot bump**. `bump.py` already
anticipates the generic `ScalarBump` "with its first consumer" — this is it. The slice is cheap,
consumer-evidenced, builds a foundation piece FX/commodity will reuse, and **retires a module** — so it
gives (c) a tick *before* the larger MC arc. Revised arc: **c1 vanilla → (this) equity greeks +
`ScalarBump` → c2 `StateProcess` → c3 equity MC exposure (crosses `mc_exposure.py`).**

## 2. Scope
- **`ScalarBump(scalar_key, shift)` (L5)** — bumps `snapshot.scalars[key]`, on the `Bump`/`Priceable`
  machinery, structural (no `isinstance`). **Two consumers now justify the generic (§6b rule of two):**
  equity spot/dividend *and* recovery — so **refactor `RecoveryBump` onto `ScalarBump(RecoveryKey)`**
  rather than leave two scalar-bump paths (the §3d divergence smell). If the refactor risks rec01, keep
  `RecoveryBump` as a thin alias of `ScalarBump(RecoveryKey)` — but one bump mechanism, not two.
- **Equity greeks (L5)** — delta (`ScalarBump` on spot), vega (`SurfaceBump` on the equity vol — exists),
  dividend sensitivity (`ScalarBump` on dividend), theta — by bump-and-reprice through the c1 equity
  option pricer + `Priceable`. Cover the four importers' suite.

## 3. Oracle (rung 1 — analytic vs finite-difference, the slice-0 pattern)
1. **Closed-form BS greeks vs the bump:** delta against the BS closed form (`N(d₁)` adjusted for
   dividend/discount — derive it as the reference), vega against the existing **`black_vega`**, each vs
   the `ScalarBump`/`SurfaceBump` finite-difference to the FD tol. (ng has `black_vega` already — that is
   the vega reference; delta's closed form is the one to add as a test reference, not a pricer path.)
2. **`rec01` byte-identical** after the `RecoveryBump → ScalarBump(RecoveryKey)` refactor — the credit
   rec01 oracle stays green to the ULP (the refactor moves the home, not the number).
3. **Put-call parity on the greeks** (delta_call − delta_put = DF·∂F/∂S) as a structural cross-check.

## 4. Tick
Retire-read `options/equity_option.py`: price superseded (c1) + greeks superseded (this) → the residual
empties → **TICK 30 → 31.** Consumer-evidenced (the 4 greeks importers), not feature-diffed. Propose
with evidence; I spot-check and rule. (Any remaining equity_option omissions classify dead/deferred→named
under the clauses.)

## 5. Process (§8)
Branch `slice/<NN>-equity-greeks-scalarbump`. audit → align (`ScalarBump`; refactor `RecoveryBump`) →
test (analytic-vs-FD delta/vega + rec01 byte-identical + parity, RED first) → feat → docs → retire-read.
Report the build + the tick; then I scope **c2, the `StateProcess` abstraction** (HW refactored on + a
`BlackScholesProcess`, rule-of-two at birth) — the step toward c3's `mc_exposure.py` crossing.
