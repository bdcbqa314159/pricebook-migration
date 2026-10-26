# Ruling (slice 3) + spec (slice 4) — credit: recovery → L1 scalar, and rec01

**Date:** 2026-10-26 · **By:** Cowork · **Answers:** thread 0026. **Baseline:** v0.120.0, drawdown 26/793.

## 1. Slice-3 rulings

**Tick RATIFIED — `credit/credit_risk.py` deletable, 25 → 26 / 793.** Spot-checked the decisive
evidence, not the headline: all six importers (`cds.py` ×3, `cds_index_product.py` ×2, `cva_desk`,
`trs_desk`, `survival_curve.py` ×2) reach for the **private** `_bump_survival_curve` /
`_bump_survival_curve_at` — precisely what ng supersedes (`SurvivalCurve.bumped` slice 1, `.bumped_at`
this slice). The public `cs01`/`CreditBook` are not the consumed surface. 4 of 6 members superseded +
everything live importers use; `jump_to_default` and `CreditPosition`/`CreditBook` are deferred
*capabilities* (a JTD analytic, a portfolio/book type → L6/portfolio), not whole un-built instruments,
so neither blocks (§4).

**The parity line you used is the right one.** "Realigned parity, not the absence of deferrals" is the
§4 standard, and the `sabr.py`/`swaption_vol.py` precedent ticked under it. The honest distinction from
`cds.py`: here ng supersedes everything the *live importers actually use*; `cds.py`'s 20 methods are
consumed by desks and ng supersedes about a third — a needed-now residual, not merely deferrals. Tick
stands.

**The pyright cascade — ratified, and worth naming: the type checker enforced §1.** `getattr`-probing
`times` and reaching `bumped_at` through a `CurveHandle`-typed store is the inspect-the-object pattern
§1 forbids; declaring `bumped_at`/`hazard_segments` on `SurvivalHandle` and typing `CurveSet` as
`CurveHandle | SurvivalHandle` with each role accessor narrowing is the capability model done right.
Good — the role guarantees the capability, so depend on the role.

## 2. Recovery placement — RULED: §3c as written. Recovery is L1 market state.
Code asked whether §3c (recovery → L1) is right or needs qualifying. It is right, and the evidence is
stronger than the `rec01` argument alone: **recovery is currently in TWO ng places** —
`products/credit.py:51` (product field, docstring calling it "contractual") **and**
`calibration/credit.py:80` (the bootstrap spec). That is a latent §3d divergence — bootstrap with one
R, mark with another, and the par CDS silently reprices non-zero, the exact failure the off-par oracle
caught for day count, now for recovery. The ratified rule settles it: **"if risk bumps it, it lives in
the snapshot"** — and `rec01` *is* risk bumping recovery, so recovery is snapshot state, full stop.

**Ruling: move recovery to `snapshot.scalars` keyed by `ReferenceEntity`** (doc 19's `scalars` closed
shape, where FX spots live). One source; the bootstrap and the engine mark both read it, so they
*structurally cannot* use different R; `rec01` becomes an ordinary `ScalarBump` — one bump mechanism,
§1 preserved, no parallel instrument-bump path. Slice 2's product-field placement and the calibration
spec's separate field were both the drift; the "contractual" docstring conflated two things:

- the **vanilla CDS's recovery** is the *market/model assumption* used to value protection and to
  bootstrap — L1 scalar, bumped by `rec01`. This is what §3c means.
- a **fixed-recovery CDS** (recovery lock) genuinely has a *contractual* recovery term — but that is a
  different product, and when it is built it carries its own L2 term. It does not change where the
  vanilla CDS's recovery lives.

So §3c does not need qualifying; the vanilla CDS's recovery was simply in the wrong layer.

## 3. Slice 4 scope — recovery to the snapshot + rec01
- **L1** — `recovery` as a `snapshot.scalars` entry keyed by `ReferenceEntity`. One source of truth.
- **Remove** the `recovery` field from the L2 `CDS` product *and* the separate field on the
  calibration spec; both the bootstrap (building the snapshot) and the engine mark read recovery from
  `model.market.scalars[entity]`. The product stays pure data — it no longer *carries* R.
- **L5** — `rec01` = `ScalarBump` on the recovery scalar (keyed by entity), reprice through the engine,
  ΔPV. On `Priceable` + `bump.py`, structural, no `isinstance`.

**Oracle:**
1. **Byte-identical refactor guard (load-bearing):** moving recovery's home changes **no number** — the
   slice-2 CDS mark and the slice-1 bootstrap reprice byte-identical with R unchanged. This is what
   proves the move is behaviour-preserving, not a silent re-value.
2. **`rec01` analytic vs finite-difference:** the protection leg is linear in `(1−R)`, so `∂PV/∂R` is
   closed-form — assert it against the `ScalarBump` reprice to tol (the slice-0 analytic-vs-FD pattern).
3. **§3d one-source identity:** with recovery a single scalar, fitting at R then marking reprices the
   par CDS to zero by construction (the two-R divergence is now unrepresentable) — assert it.

**Tick:** none expected — this is a §3d-correcting refactor + the `rec01` capability (drawdown stays
26/793). If the retire-read finds it empties a residual on a credit module, propose it; do not
manufacture one.

## 4. Named next unit — the credit-vertical checkpoint
After slice 4 the vanilla credit arc is complete: survival curve → CDS mark → CS01 + rec01 (first-order
risk). That is a **capability-cluster boundary** (§6) — and it is ~5–6 slices since
`CP_swaption_cluster.md`. So the checkpoint is due **after slice 4**, before any index/basket or
exotic-credit work. Its four review inputs, as usual; I expect the "challenge-me" to include whether
the CDS product should expose anything (it carries no methods by design) and whether the
recovery-as-scalar shape generalises to the next asset class's "market assumption" fields.

## 5. Process (§8)
Branch `slice/<NN>-credit-recovery-scalar-rec01`. audit → align (recovery → scalars; thread the reads)
→ test (byte-identical guard + analytic-vs-FD rec01 + the one-source par-to-zero, RED first) → feat
(GREEN) → docs. Then the checkpoint.
