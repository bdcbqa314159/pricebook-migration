# Spec — Hull-White 1F (B4 model), the prerequisite MC exposure was blocked on

**Date:** 2026-10-27 · **By:** Cowork · **Answers:** thread 0035 + Bernardo's ruling (build HW next).
**Baseline:** v0.124.0, drawdown 26/793.

## 0. Why this slice, and the §1 debt I owe
MC exposure (the B7 bar-mover) needs a **simulatable dynamics model**, and ng has none — `models/` is
all static/analytic (black, bachelier, sabr, discounting). The analytic CVA slices never needed one;
MC does. Bernardo ruled: build HW-1F now, MC on top after. (Also: my slice-2 spec told Code to import
`shell.Book` at L5 — an upward import and a real cycle, since `shell` imports `risk`. Code fixed it
correctly, netting set stays L6 and `book_cva` delegates down from the shell. My error; the layering
instinct was right, the import direction was backwards. Recorded so I do not repeat it.)

## 1. Scope — the STATIC, calibrated HW. Simulation is deferred to its consumer (MC).
Build HW-1F as a complete analytic model now; add the path simulation in the MC slice that consumes it
(§6b — simulation's first consumer is MC, so it arrives with MC, not speculatively here). A calibrated
closed-form HW is complete and oracle-able on its own; it is not a half-built abstraction.

- **L3 `HullWhite` (a `CalibratedModel` carrying its `MarketSnapshot`).** Short rate
  `dr = (θ(t) − a·r)dt + σ dW`, with **θ(t) fitted to the snapshot's discount curve so HW reprices the
  curve exactly by construction** (`P_HW(0,T) == curve DF`). Closed forms: `B(t,T)=(1−e^{−a(T−t)})/a`,
  `A(t,T)` from the curve + (a,σ), the discount bond `P(t,T)=A·e^{−B·r}`, the zero-bond option, and the
  **European swaption via Jamshidian** (swaption = portfolio of zero-bond options). Constant `a`, `σ`
  for this slice — term-structure `σ(t)` is deferred (§6b; the quarry started constant too).
- **Calibration (L3)** — fit `(a, σ)` to the **swaption cube** the cluster just built (co-terminal or
  diagonal swaptions), through the unified `calibrate` front. HW consumes the cube; the cluster's work
  feeds it.
- **§3d — the forward swap rate is the SAME `S`.** HW prices the *same* swaption the Black/SABR cube
  does, under different dynamics; its underlying `S = float_leg_pv/rpv01` must be the shared atom, not a
  re-derivation. HW's swaption pricing goes through the engine's capability path (structural dispatch,
  no `isinstance`) where it fits — Code works the exact protocol wiring; the invariant is that HW is
  *another model satisfying the pricing capability*, like `SABRModel`/`BlackModel`, not a special case.

## 2. Oracle (rung 1 — closed form, the whole point of doing HW before MC)
1. **Term-structure fit:** `P_HW(0,T) == curve DF(T)` to 1e-12 for all pillars — HW reprices the curve
   by construction; a θ(t) error shows here.
2. **Closed-form swaption agreement (the §3d cross-model check):** a swaption HW is calibrated to
   reprices, in HW's Jamshidian closed form, to the **same price the Black/SABR cube gives** for that
   vol — calibrate-to-vol / price-to-same, the annuity lesson across two models.
3. **Zero-bond option** closed form vs a published/hand value; `B`, `A` analytic identities.
4. **Limits:** `σ→0 ⇒` deterministic rates, swaption → intrinsic; `a→0 ⇒` the Ho-Lee limit of `B`.
5. **Structural:** calibrating to N swaptions solves for the parameters with a residual per quote (the
   count/floor shape), an unfittable set a `CalibrationFailure`, never a silent partial.

## 3. Deferred (named triggers)
Path **simulation** → the **MC-exposure slice** (its first and immediate consumer — next). `σ(t)` term
structure → first term-vol consumer. G2++/2-factor, per-currency HW → their own slices. These are
capabilities, not products, so they do not block HW's tick.

## 4. Tick
Retire-read `quarry/pricebook/models/hull_white.py` (+ `hw_calibration.py`, `short_rate_models.py`)
end-to-end. Likely a **partial** cross — ng's analytic+calibrated core supersedes the static HW, while
simulation, term-σ, and exotic pricing forward-link to their consumers; tick only if the consumed
surface is genuinely superseded (the consumer-narrow rule). Propose with evidence; Cowork rules. The
bar may move here if `hull_white.py`'s consumed surface is narrow; do not assume it.

## 5. Process (§8)
Branch `slice/<NN>-hull-white-1f`. audit → align → test (curve-reprice + the closed-form swaption
agreement + limits, RED first) → feat (GREEN) → docs (provenance: `models/hull_white.py`, source
Hull-White 1990 / Brigo-Mercurio, oracle). Then the **MC-exposure slice**: simulate HW paths, build the
netted path-wise exposure, oracled by **agreement with the analytic swaption-approximation EE where
both apply** (Code's input 2) + convergence; and — deciding Code's input 1 now — the **profile stays
`(date, EE)` for the first MC slice**: path-wise `max(ΣMtM,0)` is netted *inside* the builder before
averaging to EE, so `cva` is still untouched. The profile widens only for **wrong-way risk** (a later
slice, conditional exposures keyed by the default factor) — not for MC netting. That keeps the split
intact through MC and confines the two-CVA-definitions risk to the WWR slice alone.
