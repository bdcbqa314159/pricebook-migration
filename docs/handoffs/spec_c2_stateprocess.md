# Ruling (theta/invariant-6) + spec (c2 — the `StateProcess` abstraction)

**Date:** 2026-10-29 · **By:** Cowork · **Answers:** thread 0061. **Baseline:** v0.136.0, drawdown 31/793.

## 1. The invariant-6 / theta contract — RULED
Theta ticked `equity_option` 30→31, total, and the aggregate clause forcing rho+theta is why — good.
Two items ratified, then the contract question.

- **Survival-curve theta REFUSED by role — correct.** `Q` is anchored too; rolling the clock without
  re-anchoring it is a silent wrong CDS theta, so guarding by role (not by inspecting the curve) is the
  capability-model fail-as-value. Keep.
- **The flat-curve self-catch — exactly right, and worth the name.** A test that passed whichever
  construction was implemented (flat makes `df(T)/df(Δ) ≡ df(T−Δ)`) had **no discriminating power** —
  the §1 distinction was untestable as written, and *no amount of green reveals a powerless test*. Same
  family as the cap-strip and ML-D1 findings (a flat input strips flat whatever the shape); the sloped
  fixture + asserted flat-degeneracy is the fix. This is the structural-oracle rule applied to a test's
  *power*, not its number — a good sharpening to carry.

**The contract — (a)-semantics, enforcement deferred to its first violating consumer. (c) rejected.**
- **theta IS pure time decay** — the market clock advances, market held, **no cashflow crosses**.
  Rejecting (c): conflating decay with realized coupon cash destroys the P&L attribution desks need (and
  the quarry *separates* them, `pnl_explain`), so "realized + decay" is not theta — it is roll-down.
- **`roll_down` (realized + decay + slide) is a SEPARATE function, deferred→** its first coupon-product /
  carry consumer, with `quarry/pricebook/risk/pnl_explain.py::compute_rolldown` named as content.
- **The coupon-crossing must be REFUSED, not silently mislabeled** (make-it-unwritable) — but the guard
  is **deferred, not built now**, for two reasons that both hold: (i) **no present consumer can violate
  it** — the only theta consumer is the equity option, which has no coupons, so the wrong call is
  unwritable today; (ii) detecting the crossing needs a signal ng does not cheaply expose
  (`PricingResult` is pv/accrued/basis — no cashflow count), so building a `Priceable` cashflow-dates
  capability now would be a §6b abstraction for a **single not-yet-present** consumer. So I **overturn
  the lean to (b)-now**: ledger **`NG-DEFER-THETA-COUPON-GUARD`** (trigger: the first coupon-product
  theta / the `roll_down` slice), and that slice builds the guard §1-cleanly — a minimal crossed-flow
  signal from the engine's existing invariant-6 partition, or a `Priceable` cashflow capability justified
  then by **two** consumers (the guard + `roll_down`). Today theta documents the precondition and every
  present consumer satisfies it vacuously; the guard lands the moment a consumer could break it.

## 2. c2 — the `StateProcess` abstraction (HW + `BlackScholesProcess`, rule-of-two at birth)
This is the ratified new cross-cutting abstraction the whole (c) arc was predicated on (§6 flags a new
abstraction — this is it, introduced deliberately with its two consumers present, not anticipated).

- **`StateProcess` protocol (L3)** — the generic interface a *simulatable* dynamics exposes for MC:
  an **exact** transition / path sampler (`sample_paths(times, n_paths, seed)` or an `evolve`
  per-step; your shape within §3b). **Two consumers at birth (§6b):** **HW** (refactor its exact
  Gaussian sampler onto `StateProcess`, no behaviour change) and a new **`BlackScholesProcess`** (equity
  GBM, exact lognormal sampling `S_t = S₀·exp((r−q−½σ²)t + σ√t·Z)`), reading spot/vol/dividend from the
  snapshot keyed by `EquityUnderlying`.
- **The generic MC engine consumes `StateProcess`** — the HW-specific MC exposure builder generalises to
  take any `StateProcess`, dispatching on the protocol **structurally, no `isinstance`**. This is what
  c3 then drives across `mc_exposure.py`.
- **§3d:** the sampler is the atom, defined once, composed by the MC engine; HW and BS both implement
  it under one signature — no per-model MC dialect.

**Oracle:**
1. **HW MC byte-identical after the refactor** — the exact HW sampler behind `StateProcess` produces the
   same paths/EE/CVA as the slice-1 HW MC (a behaviour-preserving refactor; assert to the ULP where
   same-process, else tol).
2. **`BlackScholesProcess` exact sampling vs analytic GBM** — `E[S_t] = S₀·e^{(r−q)t}` and `Var` to MC
   error; and a **European equity option by MC over BS paths → the c1 Black-Scholes closed form within
   3·stderr** (c1 is the anchor, as the arc intended).
3. **One engine, two asset classes** — the generic MC engine prices an HW rates exposure and a BS equity
   payoff through the *same* `StateProcess` interface, no `isinstance` (a structural test that the
   abstraction is real, not a two-branch switch).

**Tick:** likely **0** — c2 is the abstraction + the HW refactor + the BS process; `mc_exposure.py`
crosses at **c3** (the generic MC *exposure*), not here. Honest retire-read; do not force one.

**§6:** `StateProcess` is the new vocabulary type — if its shape raises a contract question mid-build
(what exactly the sampler returns for a multi-factor or path-dependent consumer), **stop and report**;
do not widen it speculatively for consumers beyond HW + BS.

## 3. Process (§8)
Branch `slice/<NN>-stateprocess`. audit → align (`StateProcess`; refactor HW onto it) → test (HW MC
byte-identical + BS-vs-closed-form + the one-engine-two-assets structural test, RED first) → feat →
docs. Report the build; then **c3 equity MC exposure** — the `mc_exposure.py` crossing and B7's
bar-mover. Ledger `NG-DEFER-THETA-COUPON-GUARD` in this slice's `OPEN.md` touch or the next; it is a
deferral, not debt-in-code.
