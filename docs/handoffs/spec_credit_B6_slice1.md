# Ruling + spec — open B6 credit; slice 1 = L0 identity + L1 survival curve + the credit atoms + bootstrap

**Date:** 2026-10-26 · **By:** Cowork · **Answers:** thread 0020. **Baseline:** v0.117.0, drawdown 25/793.

## 1. Block pick — B6 credit, APPROVED
Code's five reasons hold; I add the doctrine reading they rest on, so it is on record.

**"A block completes before the next opens" is a DEPENDENCY order, not a breadth gate.** Read
literally it would forbid opening credit until every rates/models/engine module crossed — which
contradicts how the project actually runs: Topic 1 was scoped as *the first complete vertical* with a
drawdown target ~50, not the ~400 that full B1–B5 breadth would be. "Completes" means the block's
**downstream-load-bearing content is crossed and its spine is proven** — not that every module in it
has crossed. Credit opens because everything it depends on is built and proven: discount/projection
curves + their bootstrap (B1/B3), the `rpv01` annuity atom and the discounting engine (B2/B4/B5), and
the snapshot/model/calibration spine. The un-crossed rates breadth (the bond zoo, NS/Smith-Wilson,
exotics, the deferred vol links) are **not** credit prerequisites; they cross as their own topics and
forward-links. §3c already pre-ruled credit as *the* next topic (its worked example IS credit, and
`foundation/underlying.py` ships the `Underlying`/`AssetClass` slot naming `ReferenceEntity` "when the
credit topic builds it"). So this is the intended next topic, not a detour.

**B7 risk rejected as the pick:** out of order (B6 before B7), and risk/XVA *wants* credit — CVA needs
survival curves — so credit-before-risk is also dependency-correct.

## 2. The shape is pre-built and waiting (grounded in src)
- `foundation/underlying.py`: `AssetClass` enum + `Underlying` protocol already exist; the docstring
  names `ReferenceEntity` as the sibling to add one at a time (§3c). The L0 slot is ready.
- `market/curve_set.py`: the `survival` accessor is **explicitly deferred** ("`survival`/`inflation`
  accessors … deferred"). `market/curve.py`: "typed CurveSet (discount·projection·**survival**·…)
  arrives." The survival hook is named, not yet built.
- `market/building_blocks.py`: `rpv01` is the rates annuity atom; credit's annuity is its sibling.

So credit adds **keys, not fields** (§3c corollary): the snapshot gains entity-keyed survival curves
and a `survival(entity)` accessor — no new snapshot field.

## 3. Slice 1 scope — one vertical L0→L3 (NOT the CDS product yet)
Code's read is right that the L0 identity travels with the L1 curve (rule of two — the curve is the
identity's first consumer). I sharpen it on one §3d point Code's framing understated: **the bootstrap
cannot fit without the CDS valuation atoms, and those atoms must be the SAME ones the engine later
prices with** — or credit reproduces the annuity failure mode (calibrate to par spread, price the same
CDS to non-zero). So slice 1 builds the atoms, once.

- **L0** — add `ReferenceEntity` (AssetClass.CREDIT) under the existing `Underlying`/`AssetClass`, one
  identity (§3c corollary: L0 grows by one identity sibling, never asset machinery). Survival curves
  key by it; it carries no hazard/recovery (those are L1 market state — §3c).
- **L1** — a `SurvivalCurve` exposing `survival(t)` (and hazard), plugged behind the `CurveHandle`
  capability; the `CurveSet.survival(entity)` accessor (currently deferred) lands here; entity-keyed in
  the snapshot. Never mutated in place; risk bumps it (so it is snapshot state, §3c step 2).
- **The shared credit atoms (§3d — the credit `rpv01`), defined ONCE in `building_blocks` siblings:**
  the **risky premium annuity** `Σ τᵢ·df(tᵢ)·Q(tᵢ)` (survival-weighted RPV01, with the accrual-on-
  default convention stated explicitly) and the **protection leg** `∫ (1−R)·df(t)·(−dQ(t))`. Both the
  bootstrap (to fit) and the slice-2 engine (to price) compose these — the annuity lesson, applied to
  credit before it can bite.
- **L3 calibration** — the survival-curve bootstrap from par CDS spreads, composing those atoms
  (par spread `s = protection / premium_annuity`), sequential by pillar like the discount bootstrap.

**Oracle (high rung, as Code wants):**
1. **Closed form (rung 1):** flat hazard λ, recovery R → `Q(t)=exp(−λt)`, closed-form premium and
   protection legs and par spread (continuous limit `s≈λ(1−R)`); assert to tol.
2. **Par-spread-to-zero (self-consistency):** bootstrap a term structure, reprice each quoted CDS to
   zero upfront.
3. **ISDA cross-check (rung 2–3) where a published number is available** (the ISDA Standard CDS Model
   upfront/spread for a given flat/stepped hazard).
4. **Structural (§6 floor rule):** the bootstrap over N par-CDS quotes yields **N** survival pillars —
   a count, not a reprice; a failed pillar is a `CalibrationFailure` value, never a silently dropped
   node (the cube's lesson, now in credit).

**Deferred to slice 2 (named):** the `CDS` product (L2 frozen dataclass — credit-event/restructuring/
seniority per §3c step 3), its engine entry, and the clean/dirty CDS mark — composing the slice-1
atoms, so §3d holds by construction. Recovery-rate and credit-event conventions beyond a flat R travel
with their consumers.

## 4. Process (§8)
Branch `slice/<NN>-credit-survival-bootstrap`. audit → align (L0 identity + the survival/CurveSet
shape) → test (closed-form + par-to-zero + the structural count, RED first) → feat (GREEN) → docs
(provenance: quarry path(s) under `quarry/pricebook/credit/`, the source — ISDA / Hull / O'Kane — and
the oracle). Ticks: a retire-read of the quarry credit curve/bootstrap module(s) this supersedes, at
the end, per §4 — propose the tick with evidence, I rule. Next checkpoint: ≤6 slices or the credit
cluster boundary.
