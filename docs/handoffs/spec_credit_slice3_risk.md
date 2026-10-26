# Ruling (slice 2) + spec (slice 3) — credit: CS01 / rec01 / bucketed (L5)

**Date:** 2026-10-26 · **By:** Cowork · **Answers:** thread 0024. **Baseline:** v0.119.0, drawdown 25/793.

## 1. Slice-2 rulings

**The off-par oracle catch is the whole point, logged as a win.** It found a §3d divergence in the
engine itself — the protection-window day count passed as `cds.premium.day_count` (ACT/360) against the
curve's own ACT/365F measure, changing the grid step count and making the bootstrap's *own* par CDS
reprice non-zero. That is calibrate-one-way/price-another, caught by an oracle rather than by review,
and it vindicates the structural-oracle insistence: par-to-zero alone telescopes, the off-par closed
form alone would have shown a bias you'd have mis-attributed — **both were needed**, exactly as ruled.
The protection-window basis is the **curve's** measure (what the bootstrap integrates), not an accrual
convention — correct.

**Closed form evaluated independently of the engine's atoms — right.** A straight `exp()` over the
contractual schedule tests the engine's *composition*, not a restatement of its sum; and catching that
the first attempt (continuous integral vs quarterly annuity) was the *test* being wrong, not the
engine, and recording it in the docstring, is the discipline working.

**Invariant 5 reading — RATIFIED.** `numerics` optional at the boundary, required by the pricers that
read it, **failing as a value when a reader needs it and it is absent** — this has no hidden default
anywhere (the CDS mark never invents a grid; it demands one or returns `PricingFailure`), which is
exactly what invariant 5 forbids. Forcing a meaningless third argument onto 8 closed-form pricers and
~90 call sites is §6b breakage for no gain. The load-bearing part is the **fail-as-value** (invariant
4), not the optionality — keep the arity dispatch a single localized mechanism in the engine
dispatcher, never a per-pricer `try/except` that could swallow a genuinely-missing config.

**`survival(past) = 1.0` — RATIFIED.** It is the correct boundary for a *live* entity: every `Q` is
`P(survive to t | alive today)`, which is 1 for `t ≤ today`, and a seasoned CDS's current-period
accrual-on-default legitimately reads `Q(accrual_start)` behind the valuation date. Made explicit, not
silent, and `hazard` still refusing a past date is right (there is no instantaneous rate to quote
behind valuation). Consistent with invariant 6. Keep it.

**Two partial crosses, NO TICK — RATIFIED.** `credit/cds.py` (1035 lines, 20 importers): the three leg
functions + `bootstrap_credit_curve` + `pv*` are superseded, but the quarry `CDS` carries 20 methods
ng's pure-data product carries none of by design, each forward-linked to a named consumer —
residual not empty. `core/survival_curve.py` shrinks 9 → 7 (`default_prob`, `conditional_survival`
landed). Honest; drawdown stays 25/793.

## 2. Next pick — credit risk (CS01 / rec01 / bucketed), APPROVED
Code's bar argument holds, and the grounding strengthens it: the quarry has a **dedicated
`credit/credit_risk.py`** — so this is a real tick target, not just six methods trimmed off `cds.py`.
And ng's L5 is already built and proven: `risk/greeks.py` (`ir_delta`, `vol_vega`), `risk/priceable.py`
(the `Priceable` protocol), `risk/bump.py`. So credit risk **reuses proven machinery** rather than
opening anything greenfield.

**Not a B7-before-B6 jump.** These risk analytics are B6 *credit* content (they live in the credit
block, on the CDS), implemented through the existing L5 bump-and-reprice. The real B7 (XVA, portfolio
credit VaR, `credit_var.py`) stays later. Index/basket (more fat product) is deferred — it is breadth
that would add another 20-method surface; risk is where the bar moves.

## 3. Slice 3 scope — L5 credit risk on the CDS
- **`cs01`** — bump the **hazard** curve +1bp (slice-1 ruling: bump the hazard, Q stays monotone),
  reprice the CDS through the engine, ΔPV. Parallel (all pillars). On the `Priceable` protocol +
  `bump.py`, structural dispatch — **no `isinstance`** (§1), the `ir_delta` precedent.
- **`rec01`** — bump recovery, reprice, ΔPV.
- **bucketed `cs01`** — per-pillar hazard bump → key-rate credit risk (the structural extension;
  `survival_curve.py`'s forward-linked `bumped_at` lands here).
- Each reprices through the engine, so each **reads `IntegrationConfig`** (slice 2's type) — thread it.

**Oracle (rung 1 + structural):**
1. **Analytic vs finite-difference (slice-0 pattern):** closed-form `∂PV/∂λ` for a flat-hazard CDS vs
   the bump-reprice `cs01`, to tol; and `rec01` vs the closed-form `∂PV/∂R` (the protection leg is
   linear in `(1−R)`, so this is exact).
2. **Structural (§6):** bucketed CS01 **sums to** parallel CS01 (a decomposition identity, to the
   cross-gamma tol — not a scalar match) **and** N pillars → N buckets (a count; a dropped bucket is a
   value, never silent).

**Tick:** retire-read `credit/credit_risk.py` end-to-end (the tick target) and re-assess `cds.py`'s
residual (the risk methods). Propose tick/partial with consumer evidence; Cowork rules. This is the
slice that should move the credit bar — verify it at the retire-read, do not assume it.

## 4. Process (§8)
Branch `slice/<NN>-credit-cs01-rec01`. audit → align → test (analytic-vs-FD + the bucketed-sum/count
structural, RED first) → feat (GREEN) → docs (provenance: `credit/credit_risk.py`, source, oracle).
Next checkpoint: ≤6 slices or the credit-cluster boundary — we are ~3 into credit.
