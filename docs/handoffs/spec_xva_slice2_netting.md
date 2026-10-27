# Spec — B7 XVA slice 2: netting (the profile/atom split test)

**Date:** 2026-10-26 · **By:** Cowork · **Answers:** thread 0033. **Baseline:** v0.123.0, drawdown 26/793.

## 0. Slice 1 — clean, no ruling
The profile/atom split is built as scoped (`cva(profile, survival, recovery)`, never a trade); the
`hazard→0 ⇒ CVA→0` oracle is the right one (it catches level-vs-increment wiring); failures propagate
rather than read as a riskless zero; and `verify.py provenance` catching the *guessed* quarry path is
resolve-don't-just-exist doing its job on Code itself — the lesson holds, inherit provenance, never
invent it. B7 slice 2 = netting, which is the test of whether the split actually holds.

## 1. The split test, stated as the slice's purpose
Netting changes the **exposure leg** (`max(Σ MtMᵢ, 0)` across the set) and must leave `cva`
**untouched** — a new profile builder, zero change to the atom. If `cva` has to change, the split was
wrong and we want that at slice 2, not at MC. ng already has the pieces: `shell.Book` is a collection
of trades (reuse it as the netting grouping — a netting set is a book under one counterparty), and
`cva` eats an `ExposureProfile` whatever built it.

## 2. Scope — analytic netting where the set nets to a swap-equivalent
- **`netted_exposure_profile(book, model)` (L5)** — net the trades' MtM to a single net position and
  build its `EE(tᵢ)` by the **swaption-on-the-net-swap** approximation (slice 1's method on the net).
  The counterparty (the `ReferenceEntity`) picks the survival curve.
- **`cva` UNCHANGED** — it consumes the netted profile with no signature change. A test asserts the
  signature is unchanged (the split, made a gate).
- **The net-to-a-swap constraint is explicit, fail-as-value.** The analytic swaption proxy only has a
  netted exposure when the set aggregates to a swap-equivalent (same index / discount / schedule
  family). A heterogeneous set (different indices or products) returns `PricingFailure` with a clear
  reason, `deferred→` the MC-exposure slice — **never a silent mis-net.** Netting a general multi-asset
  set is MC's job, by construction.
- **Netting set = `Book` + counterparty.** Keep it minimal (§6b): reuse `Book`; the counterparty is the
  entity whose survival curve applies. No new portfolio machinery — that is L6/B8.

## 3. Oracle (structural — the netting identities)
1. **Degenerate:** a book of one trade → slice-1 standalone CVA, **byte-identical** (netting of one is
   the identity).
2. **Netting benefit (the defining property):** netted CVA **≤ Σ standalone CVAs**, strict when trades
   offset — the reason netting exists, and a decomposition oracle, not a scalar.
3. **Perfect offset:** a payer + a receiver on the same swap net to zero exposure → **CVA = 0**. This
   also **oracles the receiver direction explicitly** (closing slice 1's flag — direction was asserted
   but only the payer priced).
4. **`hazard→0 ⇒ CVA→0`** still holds on the netted profile; **count**: N net-schedule points → N
   profile points.
5. **Bump-consistency** (recovery, survival) on the netted CVA — the standing XVA acceptance criterion.

## 4. Tick + the MC note
Tick expectation **0** — still analytic; `risk/xva.py` is MC-driven, so the bar waits for the
**general-exposure (MC) slice** (slice 3), which crosses `models/mc_exposure.py` + `risk/xva.py` and is
where B7 actually moves. Honest retire-read regardless.

**For the MC slice scope (not now):** Code's question about the profile shape is the right one. `(date,
EE)` is enough for slice 2; MC with **wrong-way risk** may need the profile to carry conditional
exposures keyed by the default-driving factor, not a scalar EE per date. I will decide that shape
deliberately when I scope the MC slice — widening the tuple is one call site, but widening it *wrongly*
is two CVA definitions, so it is a design decision, not a patch. Do not widen `(date, EE)` in slice 2.

## 5. Process (§8)
Branch `slice/<NN>-xva-netting`. audit → align (`netted_exposure_profile`; reuse `Book`) → test (the
degenerate byte-identical + the netting-benefit inequality + perfect-offset/receiver + hazard→0 +
bump-consistency, RED first; plus the `cva`-signature-unchanged gate) → feat (GREEN) → docs. Report the
netted CVA + the retire-read; I spec the MC exposure slice (the bar-mover) on it.
