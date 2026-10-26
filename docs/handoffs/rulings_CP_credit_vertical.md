# Ruling — the credit-vertical checkpoint (`CP_credit_vertical.md`)

**Date:** 2026-10-26 · **By:** Cowork · **Rules:** `CP_credit_vertical.md` (thread 0028). **Baseline:**
v0.121.0, drawdown 26/793. **Verdict: checkpoint RULED, vanilla credit arc sound.** One correction (O1),
one new oracle shape named.

## 1. Oracle-quality audit — ACCEPTED, with O1 reopened as closable-now
Four independent closed forms + the `risky_annuity==rpv01` at λ=0 cross-identity carry the vertical at
rung 1 — strong. The three divergences caught (day-count, two-R, `bumped_at` typing) are logged
honestly, including that one was review-caught (§5 below answers that).

**O1 — I reject the vendor-reference deferral; it is closable NOW.** `survival_curve.py:98` interpolates
**log-linear in Q, which IS piecewise-constant hazard**. So a non-flat stepped-hazard curve has an
*analytic* intermediate value: for `λ₁` on `(0,t₁]`, `λ₂` on `(t₁,t₂]`, the exact
`Q(t) = exp(−(λ₁t₁ + λ₂(t−t₁)))` for `t₁<t<t₂`. Build that curve, assert `survival(t)` at an
intermediate, non-pillar `t` on a **non-flat** curve (λ₁≠λ₂) equals the analytic value to 1e-12 — a
rung-1 oracle testing the interpolation *structure*, needing **no vendor reference**. A wrong scheme
(linear-in-Q, or log-linear in another variable) fails it. The ISDA deferral is for the full Standard
Model (conventions, accrual-on-default, upfront) and genuinely needs a published number; the
*interpolation alone* does not. **Close O1 in the next slice; do NOT ledger `NG-DEFER-SURVIVALINTERP`.**
`NG-DEFER-CREDITISDA` stands for the full-model cross-check.

## 2. Drawdown — ACCEPTED (26/793), and the ~370 projection is a front-loaded-phase extrapolation
The steering rule is sound and important: **ticks come from modules whose consumed surface is narrow**
(`credit_risk.py` ticked because its six importers all used two private bump helpers), not from
"mostly covered" fat modules. But the "~370 slices for `credit/`" linear extrapolation overstates:
this vertical paid the *foundation* cost once (new L0 identity, L1 curve, the credit atoms, the engine,
the first risk) — exactly as the rates vertical did before breadth accelerated. Later credit reuses all
of it. And many of `credit/`'s 94 are exotic/fat modules (CDO/CLN/CLO/bespoke/hybrid) that will
supersede-by-not-cloning or defer, not cross one-for-one. The projection is a useful alarm, not a
forecast — and it is the argument against grinding credit breadth now (§5).

## 3. Challenge-me — ruled
1. **`PremiumLeg` vs `FixedLeg` — keep separate.** DRY is about knowledge: a fixed coupon pays
   unconditionally; a CDS premium is survival-contingent with accrual-on-default. They coincide only in
   the no-default limit (why `risky_annuity→rpv01` at λ=0). The *shared computation* is already one
   atom (`risky_annuity` = the annuity loop with a survival weight); the leg *types* staying distinct
   is correct. Do **not** merge into `AccrualLeg` — it would hide that the premium is risky.
2. **`protection_leg`'s `Accrual` parameter — change it, make the wrong call unwritable.** Divergence ①
   happened *because* the signature invited an accrual day_count that can differ from the curve's
   measure. Take `(start, end)` and read the time basis from the curve/survival `measure` instead — the
   structural-prevention principle (stronger than a test). Fold into the next slice.
3. **Flat `recovery` scalar vs term-structured recovery — scalar is right and future-proof.** §6b: do
   not build term recovery now. When it arrives it is a **`curves` entry** keyed by the same
   `ReferenceEntity` (doc 19: a term structure lives in `curves`, a scalar in `scalars`) — a *different
   field, same key*, so the scalar shape does not break. Closed-shapes×open-keys working as designed.
4. **`IntegrationConfig` arity-dispatch — keep it; numerics on the model is wrong.** The model carries
   *market* (invariant 5 separates reproducibility knobs from the calibrated model); putting numerics
   on it conflates the two. The arity-dispatch meets a *present* need — 8 closed-form pricers that must
   not carry the arg, 1 that must — so it is not speculative generality. One localized mechanism;
   revisit only if it grows hairy.
5. **`jump_to_default` — build it, do not defer.** A one-liner on existing atoms (`(1−R)·N − accrued`),
   rung-1 oracle, and the *defining* credit risk — it completes the first-order triple (CS01, rec01,
   JTD). Deferring the cheapest real gap in the vertical is the wrong call. Into the next slice.
6. **Credit book — defer, correctly.** `CreditBook`/`CreditPosition`/`cs01_by_name` are the general L6
   book pattern applied to credit, not credit-specific machinery; they travel with the L6/portfolio
   topic (B8). Vanilla single-name credit closes *without* it. Consistent with the `credit_risk` tick's
   `CreditBook` deferral.

## 4. The gate shape for divergence ② — the single-source (bump-consistency) oracle
Code could not find a gate for "the same quantity in two places" and said finding one is worth more
than the fix. Here it is. The two-R bug was a violation of a rule already in the law — *"if risk bumps
it, it lives in the snapshot"* and *market is reached through the model* — that no existing gate
checked. The gate that checks it: **for any market input a model both calibrates to and prices with,
bumping it at its snapshot home must preserve reprice-to-par.** A value with a second home fails,
because its second home does not see the bump — recovery on the product would not move when
`scalars[RecoveryKey]` is bumped, so the par CDS breaks. This is a **third structural-oracle face**
beside *count* and *finer-grid/parity*: **bump-consistency** — a shared input, bumped at its one home,
moves every stage; a duplicate home is a reprice-to-par-under-bump failure. It turns ② from
review-caught into gate-catchable, and it is a sibling of the floor rule (assert the property, not a
proxy). **Ruling:** add it to doc 11's per-checkpoint oracle-quality audit as a standing question —
*"for each market input a model both fits and prices with, is there a bump-consistency check that it
has exactly one home?"* — and promote it into §6's structural-oracle rule if a second instance arrives
(rule of two for the law text).

## 5. Next work
**Immediate slice — "complete vanilla credit":** `jump_to_default` (challenge 5) + the `protection_leg`
signature fix (challenge 2) + close O1 with the stepped-hazard interpolation oracle (§1). All cheap,
all on existing atoms, each with a rung-1 oracle. This finishes the vanilla single-name credit arc.

**Then the credit vanilla vertical CLOSES.** Not more credit product: the ~370 alarm + the
consumer-narrow steering rule both say grinding index/basket/exotic credit now is the wrong move; they
defer to a later pass. The credit book is B8/L6.

**The block after — RULED BY BERNARDO (2026-10-26): open B7 risk/XVA.** Dependency-correct now that
survival curves exist (CVA/DVA reuse credit + the rates exposure engine), the natural next block and
breadth-on-proven-spine. (The alternatives weighed and not taken: a consumer-narrow harvest to move
the bar; a different asset class for breadth.) So the sequence is: the vanilla-credit-complete slice →
credit vanilla closes → **open B7 risk/XVA**. XVA's first slice gets its own scope when the
vanilla-credit slice lands; the natural opener is single-netting-set CVA/DVA on a CDS-and-swap book
reusing the rates exposure engine + the survival curve, oracled against an independent closed-form
expected-exposure where one exists.

## 6. Ledger
- **Do NOT add `NG-DEFER-SURVIVALINTERP`** (O1 closable now, §1). The 5 existing items stand.
- The bump-consistency oracle → doc 11 oracle-audit question (§4).
