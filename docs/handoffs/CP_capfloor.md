# Checkpoint — Cap/Floor (the ladder becomes an atom; audit #10 discharged)

**Version:** v0.109.0 · **Slice:** `slice/23-capfloor` · **Baseline:** v0.108.0 (SABR multi-law).
**Trigger:** a new product family **+ a new cross-cutting atom (`cap_ladder`) + a module tick** —
three §6 stops. **Mandate:** the Cowork ruling "Cap/Floor retirement: product + pricing + the #10
ladder fix + SABR-cap calibration", executed in full, STEP A and STEP B in one slice.

## 1. The headline — #10 was not a tolerance bug, it was a missing atom

The old strip modelled a cap as **one caplet per quote**: a "2Y cap" was a single caplet fixing at
2Y, not the seven-caplet ladder it is, and `q.maturity` was silently read as that caplet's *fixing*
date rather than the cap's end. Three stages each had their own idea of what a cap is — and only one
of them was written down, inside a calibrator.

`cap_ladder(cap)` is now that idea, written once at L2, composed by the L4 pricer, the vol strip and
the cap-SABR calibration. The §3d claim is asserted, not asserted-in-prose: a test compares the
pillars the strip produces, the ladder the pricer composes, and the expiries the calibration fits.

**What that structurally buys.** `price_capfloor` is `Σ price_caplet` over the ladder and *nothing
else* — so the model's own vol law, the ruling-2 canonical-accrual guard and invariant 6 all apply
per caplet for free. A cap prices at a **negative forward** under the normal law, refuses under the
lognormal one, and refuses a semi-annual schedule on a 3M index, without one line of law- or
convention-aware code in the cap pricer. The quarry instead duck-typed
`hasattr(model, "price_ir_option")` and branched on `t_fix <= 0` per period.

## 2. Why the old oracles could not see #10 (the lesson worth keeping)

The C2 strip shipped with two green oracles: a flat cap-vol curve strips to a flat caplet curve, and
the stripped surface reprices its quotes. **Both are structurally blind to the ladder's shape.** A
flat vol in gives a flat vol out whether the cap is one caplet or twenty; and the reprice oracle
repriced the very one-caplet object it had just stripped — a self-consistency check in the most
literal sense, agreeing with its own mistake.

The fix needed oracles of a different *kind*, not a tighter tolerance:
- a **count** (a 2Y cap is 7 caplets; a 5Y quote set strips 19 pillars),
- a **finer-grid reprice** (4 quotes, 19 caplets, repriced end-to-end through the L4 engine on both
  sides — the one case the old shape could not express),
- and **parity** `cap − floor = Σ df·N·τ·(F − K)`, composed from the `forward`/`df` atoms alone, with
  no option formula in the expected value.

Filed as a general warning for the oracle audit: *a self-consistency oracle cannot see a wrong
decomposition, only a wrong number.* Where a slice's content is a **structure** (a ladder, a grid, a
schedule), at least one oracle must be about the structure.

## 3. Oracle-quality audit

| Oracle | Class | Result |
|---|---|---|
| **2Y 3M cap = 8 periods → 7 caplets, first excluded** | **structural count (#10)** | exact |
| **5Y quote set strips 19 pillars** (not 4) | **structural count (#10)** | exact |
| A longer cap's ladder **extends** a shorter one's | structural prefix | exact |
| **`cap − floor = Σ df·N·τ·(F − K)`** from the `forward`/`df` atoms only | **independent composition** | <1e-9 |
| `cap == Σ price_caplet(cap_ladder)` | by construction | <1e-12 |
| Every ladder caplet == `index.canonical_accrual(start)` | per-caplet F-identity | exact |
| Each cap reprices to its flat quote, **19 caplets under 4 quotes**, through the L4 engine | cross-stage | <1e-10 |
| Flat quote curve → flat caplet curve across the full ladder | closed-form anchor | <1e-10 |
| Engine caplet vs an inline `erf` Black at every one of the **19** ladder expiries | closed-form cross-impl | <1e-12 |
| Normal-law cap prices at a **negative** forward; lognormal-law cap fails | law domain (inherited) | asserted |
| Semi-annual schedule on a 3M index → `PricingFailure` | ruling 2, per caplet | asserted |
| **STEP B:** seed params → SABR caplet vols → cap flat vols **inverted by the test's own Black+Brent** → strip → smile → fit **recovers the seed per expiry** | **known-answer, end-to-end** | <1e-6 |
| The calibrated `SabrSurface` reprices every quoted cap through the engine | cross-stage | <1e-6 rel |
| **One ladder across all three stages** (strip pillars == pricer ladder == fitted expiries) | §3d structural | asserted |
| Contradictory cap smile → `CalibrationFailure` (1bp gate); <3 strikes; ragged grid; off-grid maturity; duplicate maturities; mixed strikes | value-not-raise (6 cases) | asserted |
| 47 single-`Caplet`/swaption paths of slices 1–22 | **byte-identical** | exact |

The STEP B round trip is the strongest oracle in the slice: it runs *seed → vols → quotes → strip →
smile → fit → seed* with the quote-inversion stage implemented independently in the test, and with
the quote grid deliberately set equal to the caplet grid so recovery is **exact** rather than
approximate. The approximate case is tested separately, as a reprice.

## 4. Challenge-me

- **I read one line of the ruling conservatively.** Cowork wrote "each ladder caplet carries its
  *canonical* accrual". I build each caplet from the **contract's own** schedule period (on the
  index's day count), which *equals* the canonical accrual for an unadjusted schedule at the index
  tenor — the only kind in scope — and differs otherwise. Substituting the canonical accrual
  unconditionally would price a *different contract* (different τ, different forward) and silently;
  with the contract's own periods, `cap == Σ its own caplets` is exact and a mismatched schedule trips
  the ruling-2 guard per caplet. **Ruling wanted:** is loud refusal the right trade, or should the
  ladder normalise to canonical accruals?
- **`cap_ladder` excludes the first period unconditionally (`CF-D1`).** Right for every cap in scope
  and for the market convention, wrong for a genuinely forward-starting cap, which loses a caplet.
  Fixing it needs the valuation date *inside* the atom — which is exactly how the three stages were
  free to diverge before. I chose a deferral over a valuation-dependent atom; that is a judgement
  call about which risk is worse.
- **The strip is lognormal-only (`CF-D3`), and I did not generalise it.** `_Leg.pv` composes
  `Lognormal()` and `calibrate_capfloor_sabr` refuses a non-lognormal model. The reason is §6b: the
  only consumer of a flat/term `Surface` is `BlackModel`, whose law is fixed, so a law-generic strip
  would emit vols nothing can read. The cost is that the shifted/normal **cap** market needs a
  law-tagged `Surface` first. Flagged because "the strip is not law-generic" looks like an omission
  next to slice 22's laws, and it is a decision.
- **Six new failure-as-value paths in one slice.** Off-grid maturity, duplicate maturity, mixed
  strikes, ragged grid, <3 strikes, non-lognormal model. Each replaces something the quarry did
  silently, and each is a real market-data error. But six refusals is a lot of surface: if a real
  quote feed trips them routinely, the right answer may be a quote-set *validator* at L1 rather than
  six guards spread across two calibrators.
- **`price_capfloor` returns the FIRST caplet failure as the whole cap's value.** Simple and safe
  (invariant 4: no defensible PV), but it discards which caplet failed and how many did. A
  diagnostics-carrying failure is the obvious next want; deliberately not built (no consumer).

## 5. Smell + debt scan

- `verify.py` acyclic / fields / layers / provenance / version / **debt** all green; `pyright` **0
  errors**; **344 tests** (+24).
- **§3d exception-count: 0.** No `isinstance`/type-switch on a product or model in any pricer or
  calibrator; the pricer's only `isinstance`es are the capability protocols and `PricingFailure` (the
  slice-22 AST guard was widened to allow the failure-as-value check, which the L5 guard already
  allowed — a convention made consistent, not loosened).
- **Atoms shared, not re-derived:** `cap_ladder` (3 stages), `cap_for_quote` (2 stages),
  `canonical_accrual`, `forward`, `df`, `Lognormal().price`. The strip gained **no** private caplet
  formula; it still never imports L4.
- **Field/arg discipline:** `CapFloor` 5 fields, `Caplet` 5, `CapSabrCalibrationSpec` 5,
  `VolCalibrationSpec` 4. `price_capfloor` 2 args, `cap_ladder` 1, `calibrate_capfloor_sabr` 1. No new
  grouping type was needed.
- **No suppressions added** (balance unchanged). Audit **#10 CLOSED**; four deferred-scope rows added
  (`CF-D1`…`CF-D4`), each with a named trigger.
- **Deviation from the ruling's commit order, deliberately:** Cowork listed `feat A → test(RED)`.
  CLAUDE.md §8 makes red-before-green a hard rule whose only carve-out is a pure refactor under a
  green oracle, and STEP A is net-new behaviour. So each step is `test(RED) → feat(GREEN)`; the A/B
  split and every other instruction stand. CLAUDE.md wins by its own §0.

## 6. Drawdown (§4) — 20 → **21 / 793** (+1 TICK)

`options/capfloor.py` is **deletable**: the vanilla cap/floor crosses whole (product, pricing, the
#10-fixed strip, the SABR-cap calibration). Residual = **three deferred capabilities, no deferred
product** — per-caplet greeks (`deferred→L5`), `_cf_from_convention` (`deferred→conventions`, 0
consumers anywhere), serialisation (`deferred→DB-spine`) — each forward-linked on its destination row
in the Topic-1 MANIFEST. Five quarry behaviours are shed as debt with grep evidence (a strip that
never stripped, a **fabricated** SABR smile, a 0.5Y tenor bucketing with averaged forwards, two silent
`except` fallbacks) and the first-period intrinsic-off-the-forward is shed as a **correction**; full
classification in `AUDIT_capfloor.md` §3. Physical `git mv` batches at the next topic close.

## 7. Named next checkpoint

Whichever comes first (§6): **≤6 slices**, or the next capability-cluster boundary.

**Recommended next work — keep retiring, and the swaption/vol-cube cluster is now the cheapest
tick.** `options/swaption.py` and the vol-cube modules are the remaining named residuals
forward-linked to "the SABR/smile slice", and every block they need now exists: the three laws, the
smile calibrator, the cap-surface calibration (a direct precedent for a cube), `SwaptionVol` and the
swaption pricer. The alternative worth weighing is `options/implied_vol.py` (a vol *inversion*
utility — Black and Bachelier both, now that both laws exist), which is small and ticks a module on
its own. Either keeps drawdown moving two slices in a row, which §4 has not seen yet.
