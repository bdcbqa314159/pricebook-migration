# Spec — open (c): equity, slice 1 = the vanilla option (closed form), the arc's oracle anchor

**Date:** 2026-10-28 · **By:** Cowork · **Answers:** thread 0055 + Bernardo's ruling (open (c)).
**Baseline:** v0.133.0, drawdown 30/793.

## 0. (b) closed, (c) opened — the scorecard that justified it
(b) moved the bar **26 → 30, four ticks, entirely inside what was built**, then yield hit zero
(`floating_leg`/`cds` wait on un-crossed consumers; the rest is RESIDENT-fat or un-built). §4's "breadth
waits while drawdown is stuck" is now **answered by measurement** — the bar moved as far as it can inside
the built surface, so breadth is earned, not overridden. Bernardo ruled **(c): process framework +
equity**. (`par_rate` deferred with 9 named consumers and `create_swap → deferred→conventions` were both
handled right — the test-only clause sending you to classify rather than shed is working.)

## 1. The (c) arc — three slices, and why equity-vanilla comes first
(c) is the generic-process framework **and** the equity asset class; the bar moves when
`models/mc_exposure.py` crosses, which needs the equity `BlackScholesProcess` through a generic MC
engine. Build order:
- **c1 (this) — equity VANILLA option, closed form.** Opens the asset class with a **rung-1** oracle
  (Black-Scholes closed form) and no MC/abstraction. It is the oracle *anchor* the later MC is checked
  against (MC equity exposure → this closed form, exactly as rates MC → the swaption-approx).
- **c2 — the `StateProcess` abstraction**, introduced with its **two** consumers (HW refactored onto it
  + a `BlackScholesProcess`) so §6b's rule of two is satisfied at birth, not anticipated.
- **c3 — equity MC exposure** through the generic engine → **crosses `mc_exposure.py`, the bar-mover.**

Equity-vanilla first is both the right build order (BS process simulates an equity spot that must exist)
and the green-oracle gate (closed form before MC).

## 2. Slice c1 scope — keys, not fields (§3c)
- **L0** — `EquityUnderlying` (`AssetClass.EQUITY`), **one** identity sibling under `Underlying` (§3c
  corollary — L0 grows by one identity, never asset machinery). Carries no price/vol.
- **L1** — **keys, not fields**: equity **spot** and a **flat continuous dividend yield** as `scalars`
  keyed by `EquityUnderlying` (a new key type beside `ScalarKey`/`RecoveryKey`, or an
  `EquityUnderlying`-keyed `ScalarKey` — your call within §3b); equity **vol** as a `surfaces` entry
  keyed by `EquityUnderlying` (reuse `Surface`). No new snapshot field.
- **L2** — `EquityOption` (underlying, strike, expiry, option_type), European, ≤5 fields, pure data.
- **L4** — price by **composing the existing `black` atom** on the equity forward
  `F = S·e^{(r−q)T}` (r from the discount curve, q the dividend scalar), then discount: `PV = DF·black(F,
  K, vol, t, type)`. **No new pricing formula** (§3d — reuse `black`); the equity forward is the new
  composition. Through a model exposing the equity-vol capability (the `ImpliedVol` pattern, keyed by
  `EquityUnderlying`) — structural dispatch, **no `isinstance`**.

## 3. Oracle (rung 1 — closed form)
1. **Black-Scholes closed form:** a textbook value (e.g. S=100, K=100, σ=0.2, T=1, r=0.05, q=0 → the
   known call) to 1e-10; **put-call parity** `C − P = DF·(F − K)`.
2. **The forward identity:** `F = S·e^{(r−q)T}`; q=0 reduces to no-dividend BS; raising q lowers F and
   the call, monotone.
3. **Degeneracies:** σ→0 → discounted intrinsic on F; expiry-at-valuation → intrinsic.

## 4. Deferred (named) · tick
Flat dividend yield now; **dividend curves / discrete dividends / American exercise / equity exotics**
→ their consumers (§6b). Equity is greenfield, so c1 **likely ticks 0** — it opens the asset class the
way credit slice 1 did. Retire-read the quarry vanilla equity-option module(s) at the end (equity/ is
34 modules, mostly exotic — expect a partial or 0, honestly); propose with evidence, I rule.

## 5. Process (§8)
Branch `slice/<NN>-equity-vanilla`. audit → align (`EquityUnderlying`; the equity scalar/surface keys)
→ test (BS closed form + parity + the forward identity, RED first) → feat → docs (provenance:
`quarry/pricebook/equity/…`, source Black-Scholes/Black-76, oracle). Report the build + retire-read;
then c2 (the `StateProcess` abstraction, HW + BlackScholesProcess) on it — that is where I scope the
rule-of-two abstraction deliberately.
