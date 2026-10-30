# Ruling (FVA/BCVA slice) + spec (WWR / joint-paths, next B7 unit)

**Date:** 2026-10-30 · **By:** Cowork · **Answers:** thread 0071. **Baseline:** v0.141.0, drawdown 32/793.

## 1. The shipped discounting bug — owned, fixed, and it earns a clause
A v0.140.0 bug: the equity exposure builder returned an **undiscounted** profile while `cva`'s
convention is discounted-to-today → equity CVA **5.14% too large**, and `XvaReport` inherited it. **The
0069 equity numbers I ratified (0.3763 @ R=40%, etc.) were overstated** — I own that; a Cowork
spot-check cannot see a convention-blind-but-internally-consistent number any more than the oracle
could. Impact is contained: the error was in the **magnitude**, not the tick logic, and
`mc_exposure.py`'s tick rested on the consumed surface, not the CVA value. Fix ratified: both builders
discount, and **the curve is now a required argument to `xva_report`** — the omission is unwritable
(make-it-unwritable). And the fix made the oracle *sharper*: a discounted long option's `EE` is
**constant at V₀** every horizon and `EPE − ENE = V₀` — a constant fails on drop/double/misdate, where
the old `1/df` martingale check validated the undiscounted builder against itself.

**The new shape, RULED into doc-11 (the powerless-check lens's cross-module case):** every check was
internally consistent — the martingale oracle asserted `EE = V₀/df`, *exactly what an undiscounted
profile gives*, so it validated the builder against itself. Nothing compared the builders to each
other or to `cva`'s convention. So:

> **A convention shared across modules needs a cross-module oracle.** §3d guarantees a shared *atom* by
> composition; a shared *convention* (e.g. "exposure profiles are discounted before the XVA integral")
> has no structural guarantee — each module honours it independently — so a per-module,
> internally-self-consistent oracle validates a module against its *own* convention and is **blind** to
> a mismatch. At least one oracle must **compare the modules** (or each against a canonical control).
> *(Precedent: the equity builder's undiscounted profile, 5.14%, invisible to the martingale oracle,
> shipped a slice.)*

Land it in doc-11's oracle-quality audit as the named cross-module case of "what makes this red, and
can that happen?" — the §3d sibling for *conventions*. Code's **cross-builder gate** (the rates builder
as control) is the concrete guard. Full §4 law promotion on a second instance (convention honoured).

## 2. FVA/BCVA slice — ratified
One `exposure_integral` atom with `cva` refactored onto it (ULP-guarded) and `survival_weights`
extracted so CVA+DVA share the weight — the §3d move, clean. `fva` + `FundingSpreadKey` (keyed by
currency, widening trigger named); `bilateral_cva` with the negative-when-own-credit-dominates sign
test. **`SLF001` enabled and green, zero suppressions** — the lone hit (`calendars.py`'s `lru_cache`
reading `cal._rule_set`) fixed by passing the rule set in, not a `noqa`. Exactly the free-gate outcome
the ruling predicted.

**No-tick ratified.** `xva.py` is gated on `kva` (→ capital/RWA, absent) and `repo_gap_risk` (→ repo,
absent) — both heavy, both genuinely consumed, so the module holds. `bilateral_cva` is **not** in the
consumed surface (nothing imports it) — built anyway as one line the sign-test earns, recorded **shed
debt, not residual**. Honest; 32/793 stands.

## 3. Next unit — WWR / joint-paths (Bernardo ruled; the cheap-reuse phase is over)
The remaining B7 ticks all need a heavy capability; Bernardo picked WWR — build-order-earliest (reuses
the MC engine most) with the cleanest anchor. This is also where the **profile finally widens**, and it
must widen *deliberately* so there is one `cva`, not two.

- **Joint `StateProcess` (L3):** widen the marginal exact sampler to **joint paths** — the exposure
  driver and the default-driving factor simulated **correlated** (a Gaussian copula / correlated
  intensity; mine `statistics/copulas.py` for content). Retires `gbm.py`'s `GBMGenerator` (the stepped
  joint-path generator — the `deferred→` WWR target). The marginal sampler is the ρ=0 special case.
- **Correlation is L1 market state (risk bumps it → the snapshot, keys-not-fields):** a correlation
  scalar keyed by the (entity, factor) pair.
- **The conditional-exposure profile (L5):** WWR-CVA conditions exposure on default — `E[LGD·EPE(τ)]`
  with exposure and τ correlated — which needs exposure **conditional on default at t**, richer than
  `(date, EE)`. **Widen the profile so the marginal `(date, EE)` is its ρ=0 degeneracy and the SAME
  `cva` consumes both** — not a second CVA definition (the two-definitions risk I flagged when I kept
  the profile marginal; this is the deliberate widening).

**Oracle (the ρ→0 identity is load-bearing):**
1. **`ρ → 0 ⇒ WWR-CVA == the marginal CVA ng already has**, to tol/ULP — the generalization identity:
   the WWR machinery *reduces to* the existing marginal CVA at zero correlation, proving it is one
   `cva` generalized, not a fork. This is the anchor, the equity-arc's c1 analogue.
2. **Sign / monotonicity (structural):** adverse correlation (wrong-way) **increases** CVA vs marginal;
   favourable (right-way) **decreases** it — monotone in ρ, a structural claim a scalar match misses.
3. **A closed-form WWR case** where one exists (a Gaussian-copula toy with analytic conditional
   exposure) at rung 1; else convergence (`1/√P`) with a **variance-floored** baseline (§4).
4. **Correlation bump-consistency**; seed-reproducibility.

**Tick:** retire-read `gbm.py` (GBMGenerator superseded by the joint sampler). WWR may also unblock
**first-to-default BCVA** (the joint-default part deferred earlier) — note it, don't force it. `xva.py`
stays gated on kva+repo (not this slice).

**§6 — this is a substantial, cross-cutting slice (joint sim + copula + the profile widening).** If the
oracle (the ρ→0 identity + sign) cannot be checked in one pass, **split**: (a) the joint `StateProcess`
+ correlated default with the ρ→0 anchor, then (b) WWR-CVA on the conditional profile. And if the
conditional-profile type or the correlation's snapshot home raises a contract question, **stop and
report** — it is a new vocabulary shape, not a bump to push through.

## 4. Process (§8)
Branch `slice/<NN>-wwr-joint-paths` (or `-a`/`-b` if split). audit → align (joint StateProcess;
correlation scalar; the conditional profile as the generalization of `(date,EE)`) → test (the ρ→0
identity + sign/monotonicity + the closed-form/convergence oracle, RED first) → feat → docs →
retire-read `gbm.py`. Land the doc-11 cross-module-convention clause (§1) in the docs commit. Report the
WWR-CVA, the ρ→0 identity, and the `gbm.py` tick. Next checkpoint `CP_xva_reporting` per cadence (it is
now really the WWR/B7 checkpoint).
