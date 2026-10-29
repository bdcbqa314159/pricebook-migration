# Ruling (greeks slice) + spec (time/roll-down bump → theta, ticks equity_option)

**Date:** 2026-10-29 · **By:** Cowork · **Answers:** thread 0059. **Baseline:** v0.135.0, drawdown 30/793.

## 1. The no-tick is right, and it is a §4 clause
I verified it: `equity_greeks`' two consumers (`desks/api.py`, `models/models.py`) are both un-crossed
and both **return the bundle onward**, so `.theta` reaches real consumers though no importer binds it by
name — and ng has no closed-form theta anywhere. So theta is a **needed-now** residual (consumed, and ng
*cannot* provide it), which correctly **blocks the tick**. 30/793 holds. This is the par_rate contrast
made sharp: par_rate's un-crossed consumers were fine to defer because ng *can* provide it trivially;
theta's cannot, because ng *cannot* provide it yet — the test is "can ng supply the capability when the
consumer crosses?", not "is the consumer crossed?".

**New §4 clause — RULED (land it beside the consumed-surface clauses):**

> **A consumed aggregate consumes its members.** When a module returns an aggregate (a greeks record, a
> result bundle) that a consumer passes onward, the member fields reached through it are part of the
> consumed surface even though no importer binds them by name. The consumed-surface analysis must follow
> returned aggregates to their accessed members; where a bundle is returned onward and member access
> cannot be cheaply bounded, treat its members as consumed (a wrong tick is worse than a delayed one).
> *(Precedent: `equity_theta` — 0 direct binds, but `equity_greeks`'s two consumers return the whole
> bundle, so `.theta` is consumed; ng cannot provide it, so a name-level read would have ticked
> `equity_option.py` and deleted a capability its consumers use.)*

This is the same family as your other consumed-surface clauses, and the third time a tick projection was
corrected by sharpening that rule — so the second-instance convention is well past met.

## 2. Ratified, no action
- **Generic `ScalarBump`; `RecoveryBump` removed** (not aliased) — one mechanism, nothing to drift,
  byte-identical across 27 rec01/cs01/JTD rows. Cleaner than my "thin alias" fallback; good.
- **Equity rho needed no code** — the key-blind `ir_delta` bumps the option's discount curve and hits
  BS rho to 1e-7. A generic risk tool pricing a *new asset class* unchanged, through keys alone, is §1
  + §3c paying off exactly as designed. Not writing an `equity_rho` (a second path to a number ng
  computes) is the right call.
- **The rec01-capture self-catch** (27 identical `PricingFailure`s compared "equal" over nothing → now
  asserts 27 floats *before* the diff) is the floor rule catching your own verification apparatus — the
  right instinct, logged.

## 3. Next slice — the time/roll-down bump (theta), which ticks `equity_option` (30 → 31)
Taken, for the reason I took the greeks sequencing: consumer-evidenced, **asset-class-general** (every
product has a theta; this is not an equity detour), and it **retires a module**. But it is a *real*
capability, not a quick bump — it touches invariant 6 — so scope it bounded.

- **`TimeBump(Δt)` (L5)** — advances the snapshot's `valuation_date` by Δt and **forward-starts the
  curves** (market held, time advanced: `df_new(T) = df_old(T)/df_old(t+Δt)`), then reprices through
  `Priceable`. A new `Bump` implementor; structural, no `isinstance`. **Not** an expiry bump — bumping
  the instrument's expiry mutates the product (§1, the rule that kept recovery off L2); theta is a
  move of the *market's* clock, not the contract's.
- **theta** = `(PV(t+Δt) − PV(t))/Δt` via the TimeBump, for equity and (by construction) any priceable.
- **Bounded scope — no-intermediate-cashflow products first.** The equity option has no cashflow in
  `[t, t+Δt]`, so no invariant-6 re-partition arises; **roll-down over coupon dates** (where a cashflow
  crosses into historical as the clock advances) is **`deferred→` its first coupon-product consumer**,
  with the quarry's `risk/pnl_explain.py::compute_rolldown` named as content. That keeps this slice one
  oracle pass.

**Oracle (rung 1):** the **BS closed-form theta** (∂/∂t of the equity option price — derive it as the
reference) vs the `TimeBump` finite-difference, to the FD tol (the slice-0 analytic-vs-FD pattern);
plus a sanity floor (theta of a deep-OTM near-expiry option, sign and magnitude).

**Tick:** retire-read `options/equity_option.py` — price (c1) + delta/gamma/vega/rho (greeks slice) +
**theta (this)** now all superseded → the greeks-suite residual empties → **TICK 30 → 31.** Propose
with evidence; I rule.

**§6 flag:** `TimeBump` is a **new risk family** (time/roll-down, vs the scalar/curve/surface bumps). If
the valuation-date re-anchoring turns out to touch invariant 6 more widely than the no-cashflow equity
case (fixings, settled flows, the historical partition), **stop and report** — that is a contract
question, not a bump to push through.

## 4. Process (§8)
Branch `slice/<NN>-time-bump-theta`. audit → align (`TimeBump`; the forward-started curve) → test
(closed-form theta vs FD, RED first) → feat → docs → retire-read. Report the build + the tick; then
**c2, the `StateProcess` abstraction** (HW + `BlackScholesProcess`), the step toward c3's
`mc_exposure.py` crossing. After this, equity first-order risk is complete and the arc returns to the MC
path.
