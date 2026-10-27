# Changelog

All notable changes to the new tree (`pricebook_ng`) are recorded here, in
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format. `0.x` = migration
in progress; `1.0.0` is reached exactly when the quarry (`python/pricebook/`) is empty.

> **Paths in entries before `0.112.0` refer to the pre-restart layout** (artifact 23). They are left
> as written — a changelog records what was true when it was written. The mapping is
> `src/pricebook_ng/`→`src/pricebook/` · `tests_ng/`→`tests/` · `redesign/`→`docs/` ·
> `python/`→`quarry/` · `ng_parked/`→`quarry/parked/ng/`.

## [Unreleased]

## [0.130.0] - 2026-10-27

### Changed
- **Three `CLAUDE.md` §4 clauses, ruled out of the consumer-narrow sweep**
  (`docs/handoffs/rulings_consumer_narrow_sweep.md`):
  - **A test-only omission never blocks a tick, and is never silently shed.** Test-only is **not
    `dead`** — a quarry test is a consumer by §4's own definition — and it is not a verdict but a
    **prompt to classify**: each name resolves to `dead` (evidenced) or `deferred→<named consumer /
    slice>`. A `deferred→` with no nameable consumer collapses to `dead` or `needed-now`. §4 defined
    `dead` and `deferred→X` and was silent on what the sweep showed to be the **majority** case.
  - **The evidence protocol guards false POSITIVES as well as false negatives.** The bare-name grep
    catches too-narrow searches; on a *common* name it over-reports instead, because sibling modules
    define the same name. A hit is not a consumer until it **resolves to the candidate module**. The
    instrument is an **AST importer graph**, not grep. Measured: `cs01` 155 quarry hits, `roll_pnl`
    32 — every one another module's own definition, all resolving to zero against the candidate.
  - **Net the candidate pool against the deletable set before counting.** A park is a tracker state,
    not a `git mv`, so every ticked module is still physically on disk and a tree-walking sweep
    re-discovers it. This is §6's floor rule applied to a sweep's own population.

### Migration
- **Consumer-narrow sweep corrected — the yield is 3, not 6** (`RETIRE_consumer_narrow_sweep.md`
  Part 2; Part 1 left as written, since a sweep record states what it found when it found it).
  Cowork's spot-check caught 3 of the 6 proposed TICK-now as **already deletable**; netting against
  the reconciled deletable set found **a fourth that the spot-check missed** —
  **`options/sabr.py`** (T1 slice-22), which was filed PARTIAL-cheap, so the partial backlog is
  **3, not 4**. `curves/bootstrap.py` was likewise already deletable, not RESIDENT.
  **Cause:** Part 1 netted against a hardcoded 7-module list scraped with a narrow regex and never
  asserted it was the real deletable set — the **floor rule violated by the sweep meant to apply
  it**. The population now reconciles exactly to the tracker's 26 / 793.
  **The decision is unchanged:** 3 ticks + 3 partials is a real backlog ⇒ **(b) continues, equity
  waits.**
- **Test-only re-classification for the 3 net-new modules** (proposals — no tick applied, tracker
  unchanged until ruled):
  - `options/vol_surface.py` → **TICK** proposed. `VolTermStructure` is **superseded, not shed** —
    ng's `Surface` *is* a term structure (total variance linear in `T`); Part 1 had mis-filed it.
    Arbitrage checks → `deferred→` the arb-free-SABR slice, whose row already names a live consumer.
    `VolSurfaceArbitrageResult` → `dead` (0 source, 0 test refs).
  - `options/swaption.py` → **TICK** proposed. The SABR-HW blender is **`dead` on a stronger ground
    than "unconsumed"**: it needs HW to quote a Black vol, and `HullWhite.swaption_vol` was deleted
    in v0.129.0 precisely because reconstructing an underlying for it was wrong by 381bp. Porting it
    would re-introduce the defect just made unwritable — and its `deferred→SABR slice` link is
    confirmed stale. `pv_ctx` superseded architecturally (the engine has no `ctx`).
  - `credit/cds_market.py` → **TICK** proposed. Upfront↔spread family → `deferred→` the ng
    credit-desk / CDS quote-conversion slice (a real ISDA capability, sharing a trigger with
    `NG-DEFER-CREDITISDA`). `reprice_spreads`/`mark_to_market` superseded; `LadderRung` `dead`.
- **Proposed drawdown 26 → 29 / 793** if the three ticks are ruled.

## [0.129.0] - 2026-10-27

### Changed
- **`SwaptionPrice` — Hull-White prices the contract it is given, and the 381bp becomes unwritable.**
  `models/protocols.py` gains `SwaptionPrice.swaption_price(swap, expiry, kind)`, a sibling of
  `SwaptionVol` rather than a variant of it. `SwaptionVol`'s key is `(index, expiry, swap_tenor,
  strike)` — exactly right for a model that reads a surface, and structurally insufficient for one
  that prices a contract: Jamshidian needs the underlying's whole coupon flow set, which the key
  cannot carry. Forced through it, `HullWhite` had to *reconstruct* an underlying, and the
  reconstruction was wrong by **381bp relative** on a semi-annual swap
  (`docs/handoffs/AUDIT_hull_white_capability.md`, now **closed**). The capability takes the real
  swap, so there is nothing left to guess.
- **`HullWhite` now satisfies `SwaptionPrice` and NOT `SwaptionVol`.** `swaption_vol`,
  `_pending_swap` and `_S_IDENTITY_TOL` are **deleted** — the reconstruction, the threaded-forward
  guard that detected it, and the Black-vol inversion all leave together. A guard is only needed
  while the defect is writable.
- **The engine prefers the price capability, falling back to vol + law**, by protocol membership —
  no `isinstance` on a concrete model. `test_pricer_has_no_law_switch` allowlists `SwaptionPrice`
  as a capability, so §1's no-concrete-type-ladder law still binds the dispatch.

### Oracles
- `test_the_SEMI_ANNUAL_underlying_that_cost_381bp_now_prices_EXACTLY` — **the inversion of the
  slice's STOP.** This test previously asserted a *refusal*; it now asserts the engine agrees with
  HW's own closed form to **1e-9** on the very contract that used to fail. Rung 1 (closed form).
- `tests/L3/test_swaption_price_capability.py` — the 381bp case exact, the reconstruction machinery
  **absent** (asserted structurally, not by grepping for the word — the module still explains why it
  was removed), HW satisfies `SwaptionPrice` and not `SwaptionVol`, the engine source names neither
  concrete model, and payer/receiver parity holds through the engine.
- **Black/SABR byte-identical** across all 32 captured price points (annual/semi-annual ×
  4 strikes × call/put × 2 models). The fallback path is untouched, not merely "still passing".

### Fixed
- **`SwaptionVol` had silently lost `@runtime_checkable`.** Inserting the new protocol between the
  decorator and `class SwaptionVol` stole it. The runtime probe was *misleading* —
  `getattr(SwaptionVol, "_is_runtime_protocol")` still returned `True` because the flag is
  **inherited** from `CalibratedModel` — while pyright correctly flagged the `isinstance`. Caught by
  the pinned static gate, not by the suite; the first dispatch against a non-runtime protocol raises
  `TypeError`, so this was a production fault, not a type-checker nit.

### Debt
- **`NG-WATCH-CLOCK`** (`OPEN.md`) — test wall-clock is ungated. `TEST_FLOOR` holds the *count*,
  nothing holds the *time*; the MC exposure draft ran 73s before vectorisation took it to 0.45s, and
  that was caught by eye. One instance ⇒ **watch, not gate** (a ceiling fitted to one sample is a
  guessed number). Trigger: a second ballooning slice. Ruled by Cowork, `rulings_CP_xva_mc.md` §4.

### Migration
- **Retire read `quarry/pricebook/models/hull_white.py` — 0 ticks, PARTIAL, 26 / 793 unchanged**
  (unchanged verdict; this slice changes the protocol, not the quarry surface ng covers). Residual
  is the **trinomial tree** (`build_tree_alphas`, `tree_european_swaption`,
  `_evolve_state_prices`), and it is **consumer-backed rather than feature-diffed**: 3 live
  quarry-source consumers (`options/bermudan_swaption.py`, `desks/callable_bond_desk.py`, the
  callable-floater / bermudan-capfloor pair). `deferred→` the lattice slice, forward-linked onto
  that row. Note ng is *ahead* on what it does cover — Jamshidian closed form and
  `zero_bond_option`, neither of which the quarry has.
- `TEST_FLOOR` 510 → **518**.

## [0.128.0] - 2026-10-27

**XVA / MC-exposure checkpoint (§6 hard stop at a capability-cluster boundary), and the
consumer-narrow rule promoted into the law.** Report: `docs/handoffs/CP_xva_mc.md`, four review
inputs plus the named next checkpoint. No pricing logic touched; drawdown unchanged at 26 / 793.

### Changed — CLAUDE.md §4 gains a tick rule, on its second instance
> **The consumed surface decides the tick — and steers the targeting.** A module ticks when the names
> its importers actually use are superseded, never when the file "looks mostly covered".

Promoted by §6's second-instance convention (the same bar the floor rule cleared). Both instances were
tick *expectations overturned by evidence*: `vol_arbitrage_scanner` (ng had no arb machinery and its
consumer was live) and `models/mc_exposure.py` (consumed as a generic process framework over a
`BlackScholesProcess`, not as rates netting — `ExposureResult` had **0** consumers anywhere). The
second clause is the new capability: it gives a way to *target* ticks deliberately rather than
discovering after the fact that a fat file will not move.

### Added — `docs/handoffs/CP_xva_mc.md`
**Oracle-quality audit** naming three shapes this arc added: the **forward-measure sampler oracle**
(checks the sampler's own mean/variance against `f(0,t)` — catches the dropped-drift `σ²B²/2` bias
that a convergence test is blind to, since a biased sampler still converges); **convergence as a
rate** rather than a tolerance (twice the right assertion — Ho-Lee's `O(a·dt²)`, MC's `1/√P`); and the
**`cva` signature gate**, which has now survived three exposure methods.

**Finding O1** — the `cva` atom's composition is never checked against a *published* CVA. Every link
in the chain is rung-1, but the whole has no external reference, so a shared misconception in the CVA
definition would pass everything. `NG-DEFER-CREDITISDA`'s trigger closes it too; recorded there rather
than as a new entry.

**Drawdown:** B7 at **five slices, zero ticks**, stated plainly with the reason — the bar moves on a
generic process abstraction, which *is* the equity gateway, so §4's "breadth waits while drawdown is
stuck" is in tension with the bar-mover being new breadth. A milestone fork, surfaced to Bernardo
rather than settled in the thread.

**Smell+debt:** 5 live ledger items, unchanged. `SwaptionPrice` recorded as **pending ruling, not
debt** — ruled in 0038, deferred by 0040, HW's guard holding until it lands. Plus a noted non-gate:
**the clock**. MC's first implementation took 73s for one test file and was caught by noticing, not by
a check; `TEST_FLOOR` counts tests, not seconds.

### Six challenge-me items
Including two I think are genuinely open: whether `_pending_swap` should be **deleted and asserted
absent** when `SwaptionPrice` lands (the `ProtectionWindow` make-it-unwritable pattern), and whether
the profile type should *carry* that its draws are marginals so a WWR slice cannot silently consume
them as joint paths.

## [0.127.0] - 2026-10-27

**MC netting — and the heterogeneous set that analytic cannot price.** Spec:
`docs/handoffs/spec_mc_slice2_netting.md` (Cowork, thread 0040). **510 tests** (was 494). Drawdown
unchanged at 26 / 793 — **the tick was expected here and the evidence says no**; see below, it is the
useful finding of the slice.

### Added — netting inside the path dimension
`mc_netted_exposure_profile(swaps, model, numerics)` (L5):
`EE(tᵢ) = P(0,tᵢ)·mean( max( Σ_trades PV_trade(tᵢ, r), 0 ) )`. The max is **outside** the sum, which
is the whole content of netting — offsetting trades cancel before the floor rather than after.
`book_mc_cva` (L6 shell) delegates down; **`Book` is not imported into L5**, the §1 error the acyclic
gate caught in the analytic netting slice.

**No sampler change.** Marginal-per-date draws suffice because netting is across *trades at one
date*. Wrong-way risk conditions on the default time and does need joint paths — a later slice.

### The point of the slice: MC has no net-to-one-swap constraint
The analytic netted profile must aggregate a set into a **single** underlying, because the swaption
proxy prices one swap — so a multi-index or mixed-schedule set `PricingFailure`s there, correctly
rather than mis-netting. MC revalues each trade on the *same* simulated `r(tᵢ)` with its **own**
flows and adds, so heterogeneity costs nothing. Both facts are asserted **together**: the same set
that fails analytically succeeds under MC, and the mixed-set CVA is oracled by convergence (no closed
form exists for it) — the seed-to-seed scatter tightens by >2× for 16× the paths.

### `cva` untouched for the third time
MC netting is the third exposure method; `cva`'s signature has changed for none of them, and the gate
asserting that now covers all three.

### The netting identities, which a sum would also satisfy
`max(Σ,0) ≤ Σ max(·,0)` holds for a sum-of-exposures implementation too, so the inequality alone
proves nothing. The discriminating pair: same-direction trades show **no** benefit (within 1%) and
offsetting ones a real one (>10%); a perfectly offsetting set is **exactly** zero on every path,
because the cancellation happens inside the path rather than in the average.

### Retired: none — and the reason is the planning finding
`models/mc_exposure.py`: ng supersedes the exposure+netting **content** (and improves it — exact
sampling, path-wise heterogeneity). But its **consumed surface is a generic multi-asset process
framework**, not rates netting:

- `ExposureResult` — **0 consumers** anywhere, source or the 952 test files ⇒ `dead`.
- `ExposureEngine` — exactly **one** production consumer, `models/mc_instrument_adapters.py`, using
  it for *"Equity exposure + CVA/DVA/FVA"* over a **`BlackScholesProcess`**, through the engine's
  `ProcessSpec` + `revalue`-callback generality.

ng's MC exposure is deliberately HW-specific (§6b), so the surface actually consumed has no ng
counterpart. **B7's bar therefore does not move on rates netting** — `mc_exposure.py` crosses with a
**generic process abstraction**, i.e. the equity-MC / `mc_*` framework slice. Forward-linked there.
This is the second time the consumer-narrow rule from `CP_credit_vertical.md` §2 has overturned a
tick expectation (`vol_arbitrage_scanner` was the first), and both times by asking *which* names the
importers use rather than how much of the file looks covered.

`TEST_FLOOR` 494 → 510.

## [0.126.0] - 2026-10-27

**MC exposure — ng's first simulation, anchored to the closed form.** Spec:
`docs/handoffs/spec_mc_exposure_slice.md` (Cowork, thread 0038). **494 tests** (was 482). Drawdown
unchanged at 26 / 793 — the bar moves at MC slice 2 (netting), as the spec said.

### Added — exact sampling, so MC's only error is statistical
Under the `tᵢ`-forward measure HW's short rate is **exactly** Gaussian:
`r(tᵢ) ~ N( f(0,tᵢ), σ²(1 − e^{−2a·tᵢ})/(2a) )`. The mean being the *instantaneous forward* is an
identity, not an approximation — the `α(t)` shift that fits the curve and the forward-measure drift
cancel because `(1 − e^{−aT}) − (1 − e^{−2aT})/2 ≡ (1 − e^{−aT})²/2` (verified to 1e-17). So exposure
dates are sampled **directly**: no time stepping, no Euler bias, and therefore the oracle can be
*agreement with the closed form* rather than mere convergence.

Dropping the drift adjustment is the classic error here and would bias every exposure by
`σ²B(0,t)²/2`; a test checks the sampled mean and variance against `f(0,t)` **directly on the
sampler**, not inferred from a price.

### The agreement numbers
Against HW's own Jamshidian price (the right anchor — MC simulates HW, so comparing to the Black cube
would be comparing two models), 5Y annual swap at 3%, 200k paths:

| exposure date | MC | exact | relative |
|---|---|---|---|
| 2027-01-15 | 139,032.62 | 139,616.05 | 41.8 bp |
| 2028-01-15 | 144,095.42 | 143,149.79 | 66.1 bp |
| 2029-01-15 | 113,532.84 | 114,129.97 | 52.3 bp |
| 2030-01-15 | 64,431.47 | 64,638.58 | 32.0 bp |
| **CVA** | **5,350.25** | **5,355.32** | **9.5 bp** |

Convergence, fixed seed: 268 bp at 2k paths → 130 → 71 → 24 → **12 bp at 512k**, i.e. ~2× per 4× of
paths. The oracle asserts that **rate**, not a tolerance — a fixed tolerance at one path count cannot
distinguish a converging sampler from a biased-but-noisy one.

### Added — the `monte_carlo` numerical family
`MonteCarloConfig(paths, seed)`, **neither defaulted**. The seed is the sharper of the two: without it
a run cannot be repeated, so a defaulted seed breaches invariant 1 (identical inputs ⇒ identical
output) and not merely invariant 5. **No time grid** — the transition is exact, so a grid would be a
knob that cannot change the answer; a model whose transition is *not* exact brings one with it (§6b).
This is the second of §3b's four families to land, beside `IntegrationConfig`; `lattice` and `solver`
still have no consumer.

### `cva` still untouched
The profile stays `(date, EE)`, so MC changed the exposure method and nothing else — the same result
netting produced, and the signature gate from slice 2 still holds. **Marginals, deliberately:** each
date is drawn under its own forward measure, which is sufficient for `EE(tᵢ)` and for path-wise
netting across *trades at one date*; wrong-way risk conditions on the default time and needs joint
paths, so those arrive with WWR — named, not assumed.

### Performance — 73s → 0.45s
The first implementation called `HullWhite.bond` once per path per flow (200k × 6 Python calls),
taking ~73s for this file alone. `P(t,T;r) = exp(logA − B·r)` and neither `logA` nor `B` depends on
`r`, so each maturity's curve-dependent part is now computed **once** and the path dimension stays in
numpy — same formula, two call shapes (§3d). Full suite back to 1.16s.

`TEST_FLOOR` 482 → 494.

## [0.125.0] - 2026-10-27

**Hull-White 1F — the first dynamics model, static and calibrated.** Spec:
`docs/handoffs/spec_hull_white_slice.md` (Cowork, thread 0036; the MC slice was blocked on ng having
no simulatable dynamics). **482 tests** (was 467). Drawdown unchanged at 26 / 793.

### Added — `models/hull_white.py` (L3)
`dr = (θ(t) − a·r)dt + σ dW` with **θ(t) pinned by the discount curve**, so HW reprices that curve by
*construction* — the term-structure oracle is an exact 1e-12 identity at every pillar and every
(a, σ), not a fit quality. Closed forms: `B(t,T)`, `ln A(t,T)`, the discount bond, the zero-bond
option, and the **European swaption by Jamshidian** (one zero-bond option per coupon flow, struck at
the `r*` where the coupon bond is worth par — an option on a sum becomes a sum of options, exactly).

**Simulation is deliberately absent** (§6b): its first consumer is the MC-exposure slice, so it
arrives with MC. A calibrated closed-form HW is complete and oracle-able on its own.

### Oracles — 15, all rung-1 closed form
Exact curve reprice · `B` identities and its **Ho-Lee convergence rate** (`a→0 ⇒ B→T−t` is a *limit*,
error `O(a·dt²)`, so the oracle asserts the rate — a fixed tolerance would either pass vacuously or
fail on correct maths) · numerical stability below the series threshold · zero-bond **call/put
parity** · swaption **payer/receiver parity against the linear atoms** (model-independent, so it
checks Jamshidian against something other than itself) · σ→0 → intrinsic · and the §3d cross-model
identity: the engine reproduces HW's own Jamshidian price at HW's implied vol to 1e-9.

### STOP, measured and guarded — ML-D1 again at 381bp
**A short-rate model cannot satisfy `SwaptionVol` as keyed.** `swaption_vol(index, expiry,
swap_tenor, strike, forward)` gives surface coordinates; Jamshidian needs the underlying's whole
**coupon flow set** — frequency, day counts, schedule — none of which the key carries. Measured on a
2Y5Y at 3%:

| underlying | disagreement (HW's own price vs the engine at HW's vol) |
|---|---|
| annual (what the reconstruction guesses) | **0.0 bp** |
| semi-annual (the actual contract) | **381 bp relative** |

ML-D1 again, an order of magnitude past slice A's 48.8bp forward gap. The first draft's docstring
claimed "the guess cancels"; the semi-annual oracle in the same slice disproved it, and the claim was
mine — recorded rather than quietly fixed.

**Guarded, not shipped broken.** Slice A's threaded forward is what makes the defect *detectable*:
the engine passes the contract's true `S`, HW computes the `S` of its reconstruction, and refuses
beyond 0.1bp — the `PricingFailure` carrying the measured gap. The unsound case is a failure value,
never a wrong vol. Options and a recommendation (a second `SwaptionPrice` capability, so HW receives
the contract and the wrong call becomes *unwritable*) are in
`docs/handoffs/AUDIT_hull_white_capability.md`, for ruling. MC is unaffected — it consumes HW's
dynamics, not this wiring.

### Changed — `CurveHandle` declares its time measure
A model that *fits* against a curve (HW's θ, any integral over it) needs the curve's own `date → t`
map; reaching for it with `getattr` is the inspect-the-object pattern §1 forbids. Now on the
capability, symmetric with `SurvivalHandle.time_basis` (added for the same reason last slice).

### Retired: none — partial cross
`models/hull_white.py` (299 lines): ng supersedes the **analytics** (A/B, the bond, the swaption, now
by closed form where the quarry used a tree) and not the **numerics** — `_evolve_state_prices`,
`tree_zcb`, `build_tree_alphas`, `tree_european_swaption` are the trinomial tree, which is the bulk of
the module and whose consumers (American/Bermudan exercise, path dependence) are its own slice.

`TEST_FLOOR` 467 → 482.

## [0.124.0] - 2026-10-26

**XVA slice 2 — netting, and it was the test of slice 1's split.** Spec:
`docs/handoffs/spec_xva_slice2_netting.md` (Cowork, thread 0034). **467 tests** (was 454). Drawdown
unchanged at 26 / 793 — the spec expected 0 ticks; the bar moves at the MC-exposure slice.

### The split held — and the claim is now a gate
Netting changed the **exposure method** and required **zero** change to `cva`.
`test_cva_signature_is_UNCHANGED_by_netting` asserts `cva`'s signature literally, so a future slice
cannot quietly move netting logic into the atom and end up with two CVA definitions. The design
decision became a check.

### Added — netting where the set nets to a swap-equivalent
- **L5 `netted_exposure_profile(swaps, model)`** — nets the positions **first**, then takes the
  exposure on the net. That order *is* netting: `EE(max(Σ MtM, 0)) ≤ Σ EE(max(MtM, 0))`, because
  exposure is convex in the position and offsetting trades cancel *before* the floor at zero rather
  than after. Summing exposures would lose exactly the benefit netting exists to capture.
- The net swap adds signed notionals and takes the **notional-weighted** fixed rate, so its single
  fixed leg pays what the set's legs pay.
- **L6 `shell.book_cva(book, model, entity)`** — unwraps the netting set and delegates.

### Fixed — a §1 layering violation in the spec's own instruction
The spec said to reuse `shell.Book` as the netting grouping. **`Book` is L6 and risk is L5**, so the
first implementation was an upward import, and `verify.py acyclic` named it immediately:
`risk/exposure.py: risk(L5) imports shell(L6) — upward import`. It was a genuine cycle, not a
stylistic point — `shell/portfolio.py` already imports `risk`.

Resolved by putting the layers where the concepts are: **L5 takes positions** (`swaps`), the
**netting set stays L6** (a `Book` of `Trade`s), and `book_cva` lives in the shell beside `mark`,
which already follows the same unwrap-and-delegate division (§0: the shell never computes).

### Oracles — 13 new, the netting identities
**Degenerate:** a book of one trade gives the slice-1 profile and charge **byte-identically** —
netting of one is the identity. **Netting benefit:** netted CVA ≤ Σ standalone across three sets,
with same-direction trades showing *no* benefit (within 1e-6) and offsetting ones a **strict** one
(>10%) — so the test distinguishes real netting from a sum. **Perfect offset:** a payer plus an
identical receiver nets to zero exposure and zero CVA, *and* each leg standalone is non-zero, so the
zero is cancellation rather than two zeros — this also prices the **receiver direction** that slice 1
derived but never exercised, closing that flag. Plus `hazard → 0 ⇒ CVA → 0` on the netted profile,
the count, and bump-consistency (recovery moves it by exactly the LGD ratio).

**A heterogeneous set is a `PricingFailure` naming which two indices and where it defers**, never a
silent mis-net: netting incompatible positions into a plausible number is the worst outcome
available, and the analytic proxy genuinely cannot do it.

`TEST_FLOOR` 454 → 467.

## [0.123.0] - 2026-10-26

**B7 opens — unilateral CVA of one swap, swaption-approximation exposure.** Spec:
`docs/handoffs/spec_xva_B7_slice1.md` (Cowork, thread 0032). **454 tests** (was 441). Drawdown
unchanged at 26 / 793 — the spec expected 0 ticks for the opener and said not to manufacture one.

### Added — the split that keeps one CVA definition
- **`risk/exposure.py`** — `swaption_exposure_profile(swap, model)` returns `((date, EE), ...)`. The
  standard physical-exposure result: the expected positive exposure of a swap at `tᵢ` **is** a
  physical swaption expiring `tᵢ` on the remaining leg, so `EE` is the pricer the swaption cluster
  already oracled, composed rather than re-derived.
- **`risk/xva.py`** — `cva(profile, survival, recovery) = LGD·Σ EE(tᵢ)·(Q(tᵢ₋₁) − Q(tᵢ))`.
- **The exposure method is pluggable; the CVA atom is not** (§3d). `cva` takes a *profile*, not a
  trade, so the MC exposure engine (a later slice) feeds the identical definition — the two cannot
  become two CVAs that happen to agree. The vol-law and forward-threading precedent, applied before
  it can bite rather than after.
- **Direction is derived, never a knob.** `VanillaSwap`'s PV is the fixed-payer's, so a positive
  notional is a payer and its exposure is a payer swaption (CALL); negative is a receiver (PUT). The
  sub-swap uses `abs(notional)` so the option PV *is* the exposure.

### Oracles — 13 new
**The composition, against an independent re-summation** over the same schedule from direct pricer
calls and `exp()` survivals — testing that the atom composes what it claims rather than restating its
sum. **Limits:** `hazard → 0 ⇒ CVA → 0` (the limit that catches a default leg wired to the survival
*level* instead of its *increment* — the classic error, since levels do not vanish there); monotone in
hazard; **exactly proportional to `(1−R)`**; zero for a swap with no remaining life. **Count:** one
profile point per schedule interval, dates matching the schedule, and **the last point is exactly
0.0** — a profile carrying full exposure to maturity would overstate every XVA built on it.
**Bump-consistency as an XVA acceptance criterion** (doc 11's third face, per Cowork's ruling):
recovery bumped at its snapshot home moves the charge by exactly the LGD ratio; the survival curve
bumped at its home widens it.

**Failure propagation is the sharp one here:** an exposure point that cannot be priced **propagates**
rather than counting as zero exposure. A zero CVA is a *plausible* number — it reads as "this
counterparty is riskless" — so a silently smaller charge is the worst available outcome.

### Retired: none — honestly
`risk/xva.py` is 783 lines with **9 production importers** and 13 functions; ng supersedes **1**
(`cva`, and partially — the quarry's is MC-driven). Everything else is forward-linked: the exposure
family + WWR → the **general-exposure (MC) slice** (which also crosses `models/mc_exposure.py` and is
what will actually move B7's bar); `dva`/`bilateral_cva` → slice 3; `fva`/`mva`/`kva` → their own
slices; `XVAResult` → the consolidated XVA report. The consumer-narrow steering rule from
`CP_credit_vertical.md` §2 agrees: those 9 importers consume the MC exposure surface, not `cva`.

### Noted — the provenance gate caught a guessed path
I wrote `quarry: quarry/pricebook/risk/exposure.py` in the new module's header; no such file exists
(the quarry's exposure lives in `models/mc_exposure.py` and inside `risk/xva.py`). `verify.py
provenance` went RED immediately — the resolve-don't-just-exist face, earning its keep for the third
time.

`TEST_FLOOR` 441 → 454.

## [0.122.0] - 2026-10-26

**Vanilla credit COMPLETE — jump-to-default, the `protection_leg` signature fix, and Cowork's
bump-consistency gate.** Ruling: `docs/handoffs/rulings_CP_credit_vertical.md` §5 (thread 0029/0030).
**441 tests** (was 430). Drawdown unchanged at 26 / 793.

### Added — `jump_to_default`, the defining credit risk
`JTD = (1−R)·N − accrued_owed − PV`. **Not a derivative** — default is a discrete event, so there is
no bump and no finite difference. The `accrued` the mark already reports is the owed amount (negative
for bought protection, invariant 6), which is why it adds. A book can be CS01-flat while carrying a
large jump, which is why CS01 alone was never the whole credit risk.

Oracled on the identity itself at three spreads, on the **relationship** (a CDS already marked up has
less left to jump — `j0 < j1 < j2` as `pv0 > pv1 > pv2`, with the differences equal), on monotonicity
in recovery, on sign-flip with the notional, and on the seasoned case where the accrued subtracts.

### Fixed — divergence ① is now unwritable, not merely guarded
**`protection_leg` takes a `ProtectionWindow(start, end)`**, not an `Accrual`. An `Accrual` carries a
`day_count`, and for this leg a day count was never an accrual convention — only the basis the
integral discretises on. Passing the premium's ACT/360 where the curve's ACT/365F belonged changed the
step count and made the bootstrap's own par CDS mark non-zero (slice 2). The basis now comes from the
curve being integrated against, via a new `SurvivalHandle.time_basis`: **the caller cannot choose
wrongly because it no longer chooses.** A test asserts the signature carries no day count at all.

### Added — doc 11 gains the bump-consistency gate (a third structural face)
> For any market input a model both fits and prices with, **bumping it at its snapshot home must
> preserve reprice-to-par.**

Cowork derived this from the two-R bug, and it is the gate shape I had looked for and failed to find.
A second copy of a shared input fails it by construction: the bump moves the snapshot's copy, the
pricer reads the other, par breaks. It is neither a count nor a finer-grid check — "the same quantity
in two places" has no population to floor — which is why no existing gate could see a defect that
cost ≈96bp on a par quote. Asserted here for **both** shared credit inputs (recovery across five
shifts, and the hazard curve). CLAUDE.md §6 promotion on a second instance.

### Corrected — checkpoint finding O1 was wrong
`CP_credit_vertical.md` §1 claimed the survival curve had no interpolation oracle. **It has had one
since slice 1:** `test_piecewise_constant_hazard_between_pillars_is_log_linear_in_Q` builds a
non-flat two-segment curve and checks an analytic intermediate `Q` strictly inside a segment. It
discriminates against the wrong scheme by **1.66e-3** at a 1e-10 tolerance, so it is a genuine rung-1
oracle, not a tautology. The finding came from under-auditing the test file while writing the
checkpoint — recorded rather than quietly dropped, since an audit that invents findings is as costly
as one that misses them. `NG-DEFER-SURVIVALINTERP` is therefore **not** ledgered.

Two genuine (modest) strengthenings did land: the first segment is now covered as well as the second,
and a **three**-segment curve is probed in its middle segment, where a whole-curve interpolation
would differ — asserted to differ, so the test cannot pass vacuously.

### Challenge-me rulings applied
`PremiumLeg`/`FixedLeg` stay separate (DRY is about knowledge; the shared loop is already the
`risky_annuity` atom) · flat `RecoveryKey → float` stays (term recovery arrives as a `curves` entry
under the same key, no break) · the `IntegrationConfig` arity dispatch stays (numerics on the model
would violate invariant 5) · the credit book defers to B8/L6 (a general book pattern, not
credit-specific).

`TEST_FLOOR` 430 → 441.

## [0.121.0] - 2026-10-26

**B6 credit slice 4 — recovery becomes L1 market state; `rec01`.** Spec:
`docs/handoffs/spec_credit_slice4_recovery.md` (Cowork, thread 0027). **430 tests** (was 421).
Drawdown unchanged at 26 / 793 — a §3d-correcting refactor plus one capability, no tick expected.

### Fixed — recovery had TWO homes, and they could silently disagree
Slices 2–3 carried `recovery` on the L2 `CDS` **and** on the bootstrap spec. §3c places it at L1
("risk bumps them"), and the two-home shape was a latent §3d divergence, not untidiness. **Measured:**
with the curve bootstrapped at R=0.40 and the CDS marked at R=0.30, a **par** quote priced to
**+96,431 on 10mm notional** (≈96bp) — silently, on a quote that had just calibrated to zero. The
day-count divergence's twin, found by Cowork's review of the slice-3 report.

- **`snapshot.scalars[RecoveryKey(entity)]` is now the single source**, read by the bootstrap and by
  the mark. `RecoveryKey` is a **sibling** of `ScalarKey`, not a field on it — a new asset class adds
  keys, not fields (§3c), mirroring `surfaces`' `SurfaceKey | SwaptionSurfaceKey`.
- `CDS.recovery` and `CreditBootstrapSpec.recovery` are **removed**. The divergence is no longer
  merely untested; it cannot be written down.
- An absent recovery is a **failure value**, never an assumed 0.40 — that convention is precisely
  why a silent default would be dangerous: it would look right in every standard case.
- The validation moved with the field: recovery is checked at the snapshot boundary.

### Added — `rec01`, and it is an ordinary snapshot bump
`RecoveryBump` + `risk.rec01`, through the same `Priceable` + `central_diff` path as `cs01`. This is
only possible *because* recovery is now L1: as a product field it would have required a second,
instrument-mutating bump mechanism beside the snapshot one and a type-switch to choose between them
— which is what §1 forbids. One home, one mechanism.

### Oracles
**Byte-identical refactor guard** — full-precision `repr` of 5 CDS PVs, the seasoned pv+accrued,
`cs01`, all 5 CS01 buckets and all 6 bootstrapped survivals, captured before the move and compared
after: **not one ULP moved**. **Analytic ∂PV/∂R vs FD** — the protection leg is linear in `(1−R)` and
the premium leg has no R, so `∂PV/∂R = −protection/(1−R)` exactly. **rec01 is independent of the
spread** — a structural fact, not a number: if it varied with the spread, R would be leaking into the
annuity. **One-source par-to-zero** at R ∈ {0.20, 0.40, 0.60}: every quoted pillar marks to zero at
every recovery, because one R feeds both stages.

### Also
`CreditBootstrapSpec` is now `(entity, currency, quotes, market, solve)` — it takes the snapshot
rather than a bare discount curve, since that is where both the curve and the recovery live.
`TEST_FLOOR` 421 → 430.

## [0.120.0] - 2026-10-26

**B6 credit slice 3 — CS01 and bucketed CS01 at L5. `credit/credit_risk.py` RETIRED: drawdown
25 → 26 / 793, the credit bar moves.** Spec: `docs/handoffs/spec_credit_slice3_risk.md` (Cowork,
thread 0025). **421 tests** (was 412).

### Added — L5 credit risk, on the existing machinery
- **`risk/credit.py`** — `cs01` (parallel hazard bump, reprice, ΔPV) and `bucketed_cs01` (one CS01
  per hazard segment). Both go through `Priceable` + `central_diff` + a `Bump`, so there is **no
  `isinstance` on the instrument** (§1): a CDS, a credit-linked note or a basket all route through
  the same code because they all satisfy `Priceable`.
- **`risk/bump.py`** — `SurvivalBump` (parallel) and `SurvivalPillarBump` (one segment). The bump is
  on the **hazard**, not on Q: Q has no units and a Q shift does not stay monotone (slice-1 ruling).
- **`SurvivalCurve.bumped_at(pillar, shift)`** — the single-segment bump slice 1 forward-linked as
  `deferred→ L5 credit key-rate risk`. Only that segment's hazard moves, so every Q after it shifts
  and every Q before it is untouched — which is what makes the per-pillar bumps a genuine partition.
- **`priceable(instrument, model_ctor, numerics)`** — threads the integration config, because a
  bumped reprice must use the **same grid** as the base or the finite difference measures the grid
  change as well as the market move.

### Oracles — 9 new
**Analytic ∂PV/∂λ vs the bump-reprice (rung 1).** The flat-hazard CDS PV is closed form, so the
derivative is differentiated analytically — `∂protection/∂λ = (1−R)[(1−e^{−kT})r/k² + λTe^{−kT}/k]`,
`∂annuity/∂λ = −(1−e^{−kT})/k² + Te^{−kT}/k` — and compared with `cs01`. An FD-only test would only
prove the bump is self-consistent with itself.

**Structural (§6): bucketed CS01 is a decomposition, not a vector.** The per-pillar bumps partition
the hazard segments, so they **sum to** the parallel CS01 (asserted to 1e-4 relative); **N segments →
N buckets** (a count); and the buckets **beyond the instrument's maturity are zero** — risk smeared
past maturity would be wrong and a parallel CS01 could not reveal it. Plus a sign/antisymmetry check
(bought vs sold protection), and failure propagation for a missing curve or absent numerics.

### Retired (+1) — and the reason is non-obvious
`credit/credit_risk.py` (294 lines, 6 production importers). **Every one of those importers uses the
module's *private* `_bump_survival_curve` / `_bump_survival_curve_at` helpers, not its public API** —
and those two are exactly what ng supersedes (`SurvivalCurve.bumped`, `.bumped_at`). 4 of 6 members
cross: `cs01` → ng `cs01`, `spread_dv01` → ng `bucketed_cs01` (which additionally asserts the
decomposition identity the quarry never checked), and the two bump helpers.
`deferred→`: `jump_to_default` → first JTD consumer; `CreditPosition`/`CreditBook` → the L6 credit
book. Both are **capabilities, not products**, so neither blocks the tick (§4) — the same standard
`options/sabr.py` and `options/swaption_vol.py` ticked under.

### `credit/cds.py` re-assessed — still partial
Three more of its 20 methods are superseded (`cs01`, `bucket_cs01`, and its `_bump_survival_curve`
imports). Residual ~15: quote conversions, `rec01`, duration/convexity/theta, carry/roll-down,
amortising notional, P&L attribution, forward CDS, `StandardCDS`. Bar not empty, so no tick.

### NOT delivered — `rec01`, deliberately, with the reason
The spec scoped `rec01` into this slice. It is **withheld pending a ruling**, because building it
exposes drift: **CLAUDE.md §3c places recovery at L1** — *"Hazard/survival curve and recovery → L1
(risk bumps them)"* — while slice 2 put `recovery` on the L2 product. `rec01` is the consumer that
makes the difference real: as a product field it cannot be reached by a `Bump` (which perturbs the
snapshot), so it would need a second, parallel bump mechanism at L5 — and `isinstance`-free structural
dispatch is the thing §1 protects. The snapshot already has the right home (`scalars`, doc 19's
closed shape, where FX spots live). Recorded in the thread for Cowork; everything not depending on
that answer shipped.

`TEST_FLOOR` 412 → 421.

## [0.119.0] - 2026-10-26

**B6 credit slice 2 — the CDS product (L2) and its engine mark (L4), plus the numerical config
invariant 5 deferred to its first engine.** Spec: `docs/handoffs/spec_credit_slice2.md` (Cowork,
thread 0023). **412 tests** (was 399). Drawdown unchanged at 25 / 793 — two partial crosses, below.

### Added — L2 product, L4 mark
- **`products/credit.py`** — `CDS` (4 fields) + `PremiumLeg` (schedule, day_count, spread), mirroring
  `FixedLeg`. Pure data, no `pv()`. `notional` is **signed**: positive = bought protection.
  Credit-event / restructuring / seniority richness is **deferred to its consumers** (§3c places it
  at L2, §6b forbids building the convention surface before one needs it).
- **`engine/credit.py`** — `PV = N·(protection_leg − spread·risky_annuity)`, composing **the same two
  atoms the slice-1 bootstrap fitted with** (§3d). Invariant 6: only future premium periods are
  discounted, the in-progress period is reported as `accrued` (negative — the buyer owes it) and
  `clean = pv − accrued`.

### Added — the numerical config (invariant 5's deferred type lands)
- **`foundation/numerics.py`** — `IntegrationConfig(steps_per_year)`, **no default**. Invariant 5
  records that the concrete type "lands with the first engine that reads it"; the CDS protection leg
  is that engine. Only the `integration` family exists, because only it has a consumer: §3b names the
  eventual `(monte_carlo, lattice, integration, solver)` decomposition and §6b forbids building the
  other three — or an aggregate wrapping one of four — ahead of them.
- **`price(instrument, model, numerics)`** — threaded through the registry, **optional at the
  boundary and required by the pricers that read it**. A closed-form pricer keeps its two-argument
  signature (the dispatcher inspects arity), while the CDS mark returns a `PricingFailure` when the
  config is absent. Invariant 5 forbids a *hidden default*, not an optional parameter. All 8 existing
  pricers are untouched.

### Oracles — 13 new, led by the mandatory non-telescoping one
**Off-par flat-hazard CDS mark against closed form.** A *par* CDS is worth zero, so a par-only oracle
telescopes and a divergent annuity is invisible — the audit-#10 lesson. Off par, `PV ≠ 0` and the
annuity carries full weight. The closed form is evaluated **independently of the engine's atoms**
(straight `exp()` over the same contractual quarterly ACT/360 schedule), so it tests the engine's
*composition* — log-linear df, log-linear Q, `Accrual`, the generated schedule — rather than
restating it. Plus: every bootstrapped pillar marks to zero (the §3d identity) · the discrete par
spread solved from the closed form prices to zero · the seasoned accrued/clean decomposition · a
missing survival curve is a failure, not a risk-free mark · the grid is observably live.

### Fixed — a §3d divergence in the new engine, caught by its own par-to-zero oracle
The protection window's day count is the **time basis of the integration grid**, not an accrual
convention, so it must be the survival curve's own measure — which is what the bootstrap integrates
over. The first draft passed `cds.premium.day_count` (ACT/360 against the curve's ACT/365F), which
changed the step count and made the bootstrap's own par CDS mark non-zero. Exactly the
calibrate-one-way/price-another failure this slice's atom-sharing exists to prevent, found by the
oracle rather than by review.

### Changed — `SurvivalCurve`
- `survival(d)` for a **past** date returns `1.0` rather than raising: the boundary condition
  `Q(t)=1 for t≤0`. We are pricing a live entity, so by construction it did not default before today
  — and a seasoned CDS needs it, since the in-progress period's accrual-on-default term reads
  `Q(accrual_start)` with that start behind the valuation date. `hazard` still refuses a past date.
- **`default_prob`** and **`conditional_survival`** land — two of the nine methods slice 1
  forward-linked as needed-by-slice-2.

### Added — `OPEN.md`, both ratified by Cowork
`NG-DEFER-CREDITISDA` (no ISDA cross-check; the gate is met at rung 1 without it, and an invented
number would be a golden file dressed as rung 2 — trigger: a citable ISDA worked example) ·
`NG-DEFER-DF-CONTINUOUS` (`df` takes a `date`, so time-integrals carry a day-granularity floor;
trigger: the first consumer needing sub-day accuracy, which is a protocol widening and so a ruled
decision).

### Retired: none — two partial crosses, honestly
`credit/cds.py` (1035 lines, **20 production importers**): the three leg functions, the bootstrap and
the pricing methods are superseded, but the quarry `CDS` carries **20 methods** and ng's product
carries none by design — so quote-convention conversions, CS01/rec01/duration/convexity/theta,
carry/roll-down, amortising notional, P&L attribution, forward CDS and `StandardCDS` are all
forward-linked to named consumers. `core/survival_curve.py`'s residual shrinks from nine methods to
**seven**. Neither bar is empty, so neither ticks.

`TEST_FLOOR` 399 → 412.

## [0.118.0] - 2026-10-26

**B6 credit opens — slice 1: the L0 identity, the L1 survival curve, the shared credit atoms, and the
survival bootstrap.** Spec + rulings: `docs/handoffs/spec_credit_B6_slice1.md` (Cowork, thread
0021). **Drawdown unchanged at 25 / 793** — the quarry survival curve is a *partial* cross, see below.
399 tests (was 375).

### Added — L0: one identity, and only one
- **`foundation/reference_entity.py`** — `ReferenceEntity(name)`, `AssetClass.CREDIT`, satisfying the
  existing `Underlying` protocol. §3c's corollary: an asset class adds roughly *one* L0 object, its
  identity. It carries **no** hazard or recovery (L1 market state that risk bumps) and **no**
  seniority or credit-event definitions (L2 contract description). `underlying.py` had recorded that
  the speculative sibling was cut in Phase 4 to "return with *validated* fields when its asset class
  actually ships" — this is that return.

### Added — L1: the survival curve, as a distinct capability
- **`market/survival_curve.py`** — `SurvivalCurve` stores Q at pillars and interpolates log-linearly,
  which *is* piecewise-constant hazard, so one representation answers both `survival` and `hazard`.
  `bumped(shift)` shifts the **hazard**, not Q: a hazard shift is the credit-spread bump risk applies
  and it keeps Q monotone by construction. Guards reject Q outside (0,1] and **rising** Q (a negative
  hazard — the entity un-defaulting).
- **`SurvivalHandle` is a sibling protocol to `CurveHandle`, not a widening of it.** A survival curve
  has no `df` and a discount curve has no `survival`; widening one protocol would force every discount
  curve to answer a credit question. Same reasoning as `ImpliedVol`/`SwaptionVol` being two model
  capabilities.
- **`CurveSet.survival(entity)` lands** — the accessor `curve_set.py` had explicitly deferred "with
  its asset class". `CurveRole.SURVIVAL`, `CurveKey.id` accepts `ReferenceEntity`: credit adds
  **keys, not fields** (§3c). An unknown entity **raises** rather than defaulting to risk-free — a
  silently risk-free credit curve prices every CDS to zero protection.

### Added — the shared credit atoms (§3d), defined ONCE
- **`risky_annuity(schedule, day_count, discount, survival)`** — the credit sibling of `rpv01`:
  `Σ τ·df(pay)·Q(pay)` plus the **accrual-on-default** term `Σ (τ/2)·df(mid)·(Q₁−Q₂)`. The
  half-period convention is **stated explicitly**, as the spec required, with its deferral (finer
  within-period integration → its first short-stub consumer).
- **`protection_leg(accrual, recovery, discount, survival, steps_per_year)`** —
  `(1−R)·Σ df(mid)·(Q₁−Q₂)`. The increments sum to `Q(0)−Q(T)` by construction whatever the grid, so
  the only approximation is *when* within a step, never *whether*. `recovery` is explicit, never
  defaulted: a guessed R silently rescales every credit number.
- **Why once:** the bootstrap fits with these and the slice-2 engine will price with these. Had the
  fit rolled its own credit annuity, the calibrator would make each CDS par while the engine marked it
  non-zero — and par-spread-to-zero could not see it, because it telescopes exactly as par swaps do.
  The annuity lesson, applied to credit before it could bite.

### Added — L3: the bootstrap
- **`calibration/credit.py`** — one survival pillar per par CDS quote, ascending, each a 1-D monotone
  solve on the segment hazard through the shared `invert_increasing` (the Jacobian is triangular: a
  CDS maturing at tᵢ has no cashflow beyond it). Returns `(curve, CalibrationResult)` with **one
  residual per quote**, or a `CalibrationFailure` **naming the pillar** — never a silently shortened
  curve (§6 floor rule, the swaption-cube lesson).

### Oracles — 24 new, rung 1 where it matters
Flat hazard ⇒ `Q(t)=exp(−λt)` to **1e-12** and hazard reads back λ · the protection leg against the
**analytic integral** `(1−R)·λ/(r+λ)·(1−e^{−(r+λ)T})` — a second method, not a restatement · the
continuous par spread → **λ(1−R)** · `risky_annuity` at λ=0 **is** `rpv01` to 1e-12 · par-spread-to-zero
on every quote through the same atoms · **N quotes → N pillars** with one residual each · an unfittable
pillar as a counted `CalibrationFailure` · monotone-Q and recovery-domain guards.

### Found by measurement — the protection leg's day-granularity floor
`steps_per_year` defaults to **12**, chosen on measurement rather than convention. Error against the
analytic integral: n=1 → 1.6e-5, **n=12 → 2.1e-6**, n=52 → 4.9e-6, n=365 → 5.1e-6. Refining past
monthly makes it *worse*, then plateaus: `CurveHandle.df` takes a **date**, so at daily steps the
midpoint of a one-day step floors to that step's start and `df` is read half a day early at every
step — a systematic bias refinement accumulates rather than removes. The midpoint rule's quadratic
convergence wins until it meets that floor, at roughly monthly steps. The quarry defaulted to 12 too;
the measurement says it was right. A sub-day-accurate leg needs a `df(t: float)` capability, deferred.

### Retired: none — the quarry survival curve is a PARTIAL cross
`core/survival_curve.py` (271 lines, 14 methods, **59 production importers**) crosses partially. Nine
methods are unmatched and each has a named destination: `default_prob` + `forward_hazard` /
`forward_survival` / `marginal_default_density` → slice 2 and the first conditional-survival consumer;
`term_structure` / `pillar_hazards` → credit reporting/risk; `bumped_at` (single-pillar) → L5 credit
key-rate risk; serialisation → `deferred→persistence`. `to_calibration_result` is superseded by shape
(doc 19: the result sits beside the curve, never on it). The deletable bar is an *empty* residual, not
"looks covered" (§4) — so no tick, honestly.

### Also
`TEST_FLOOR` 375 → 399, raised in the counting commit. One suppression was **removed rather than
ledgered**: a frozenness test needed a type-checker ignore, so it uses `setattr` instead — a
frozenness assertion should not owe debt (§5).

## [0.117.0] - 2026-10-26

**Swaption-cluster tail retire-sweep — 2 ticks. Drawdown 23 → 25 / 793. The swaption / vol cluster
closes whole.** Evidence + Cowork's spot-check ruling:
`docs/handoffs/RETIRE_swaption_cluster_tail.md` (thread 0017–0019). No ng code: both ticks are
supersede-with-evidence against paths already built and oracled, which is why this stayed a sweep
rather than becoming two slices.

### Retired (+2)
- **`options/swaption_vol.py`** — exports exactly `SwaptionVolSurface` (a 2D ATM `vol(expiry, tenor)`
  grid), 1 production importer. The container is superseded by
  `{SwaptionSurfaceKey(index, swap_tenor): Surface}`: ng types
  `surfaces: Mapping[SurfaceKey | SwaptionSurfaceKey, Surface | SabrSurface]`, so one 2D grid
  decomposes into keys × term structures (doc 19, closed-shapes×open-keys). **Oracle verified** at
  `tests/L4/test_swaption_sabr.py:254`. `.bumped` → `risk/greeks.py::vol_vega` — and it is
  dimensionally *correct*, unlike the cube's `bumped` (slice B F7, 5.4–6.2× wrong): a `Surface`'s
  entries are vols, whereas `alpha` is a vol only at β=1.
- **`options/swaption_conventions.py`** — all five public names have **0 production consumers**.
  Superseded *by design*: slice A established a swaption's conventions are the **swap's**, which
  `RateIndex` cannot carry, so a per-currency lookup registry is the shape ng deliberately lacks.
  Precedent: retire-#2's `Deposit` with zero production instantiations.

### Left resident, with evidence (4 of the 6 swept)
`vol_arbitrage_scanner.py` (ng has **zero** arb machinery; `vol_calibration.py:112` imports
`scan_surface` live — a tick would be a paper tick) · `vol_surface_strike.py` + `vol_smile.py`
(**general** strike-axis machinery consumed by **equity and FX**; ng's only strike-dependent object is
the *fitted* `SabrSurface`, not an interpolating container) · `synthetic_swaption_data.py` (live
consumer `models/hw_per_currency.py:114`).

### Forward-links written onto their destination rows (§4)
off-pillar consumer (the 2D grid interpolation joins the cube's `interp_surface` atom) ·
`desks/swaption_desk.py` (re-point to the keyed `Surface`) · first currency-defaulting consumer (mine
the convention content) · the arb-free-SABR slice · the general vol-surface topic (equity/FX) ·
the HW/per-currency topic.

### Method note
The dynamic-reachability sweep returned exactly one hit and it was a **false positive** —
`market_data/_types.py` holds `SWAPTION_VOL = "swaption_vol"`, a `QuoteKind` enum *value* sharing the
module's text. Recorded because retire-#1's false negative was this family. `vol_arb.py`'s apparent
`enforce_no_arb` use is likewise a **docstring** cross-reference, not a consumer. Cowork's own first
grep over-claimed for the same substring reason and its precise re-check confirmed the read.

### Cluster closed
Six modules retired across the swaption / vol cluster: `options/{sabr, capfloor, implied_vol,
swaption_vol_cube, swaption_vol, swaption_conventions}.py` — smile read (slice A) → forward-threaded
fit (B4) → cube calibration (slice B) → tail sweep.

## [0.116.0] - 2026-10-26

**The park model: a park is a tracker state, not a physical move. `NG-DEFER-QUARRYIMPORT`
DISCHARGED — the quarry imports again (792 modules, 0 failing).** Ruling:
`docs/handoffs/rulings_quarry_park_model.md` (option A). Apparatus slice: law + quarry packaging + a
gate; ticks nothing, exempt from §4's cross-cutting-ticks-≥1. Drawdown unchanged at **23 / 793**.

### Fixed — the quarry is importable for the first time since v0.74.0
- **The 19 physically parked modules are restored** to their original quarry paths (15 → `core/`,
  4 → `curves/`). `import pricebook` across the tree: **318 → 792 importable, 265 → 0 failing.**
- The Topic-0 (v0.74.0) and Topic-1 (v0.98.0) `git mv` parks removed modules that **294 live quarry
  modules import directly** (`discount_curve` by 223, `day_count` by 221, `serialisable` by 92,
  `schedule` by 79). §7c's "quarry regression nightly" was therefore **unachievable for ~40
  versions** — a stated guarantee that never ran.

### Changed — the law
- **CLAUDE.md §4** gains the park-model clause: a crossed module is ticked deletable in the tracker
  and recorded on its MANIFEST row; **its file stays in `quarry/`** until the tree is deleted once at
  v1.0. *"Quarry empty = v1.0"* is clarified, not changed — the physical emptying moves from per-park
  to once; drawdown (/793) unchanged.
- **doc 13 §7** (new) records why the physical move yielded: of the three commitments in tension —
  physical parking, the read-only quarry, §7c's running regression — it was the youngest and the only
  one with no semantic weight. The tick and MANIFEST row already carry the park's meaning.
- **CLAUDE.md §7c** notes the nightly quarry regression is achievable again, asserted per-commit.

### Added — the real import gate (replacing a proxy, before it ever shipped)
- **`verify.py quarry`** walks the quarry package tree and asserts the importable count against
  `QUARRY_IMPORT_FLOOR = 792`, RED on any drop or any failing module. Wired into CI.
- **It is deliberately not `import pricebook`.** That check was the first prescription and was
  rejected *after measurement*: it **passes while the quarry is broken**, because the top package's
  `__init__` does not eagerly import its sub-packages. Asserting a name resolves is not asserting the
  property (§6, floor rule).
- **It asserts it measured the right package.** Since the restart both trees are named `pricebook`
  (`src/pricebook`, `quarry/pricebook`), so the walk runs rooted at `quarry/` *and* checks the
  imported `__file__` lies under it — measuring ng would be a proxy that passes on a broken quarry.
- **Proven to bite three ways:** re-parking one module (`core/day_count.py`) drops the count to 318
  and fails — the v0.74.0 breakage reproduced and caught; a floor one above the true count fails; and
  the wrong-package guard is asserted.

### Added — `OPEN.md`, carried from the cluster checkpoint ruling
`NG-DEFER-CUBEBETA` (one β for the whole cube; trigger: first per-node-β consumer) ·
`NG-DEFER-CUBEORACLE` (the cube round-trip is rung 4; trigger: a citable vendor/textbook cube node) ·
`NG-WATCH-TIERFLOOR` (`TEST_FLOOR` is global, not per-tier; trigger: the first tier rebalance).

### Noted — the provenance gate immediately caught this slice's own consequence
Restoring the 19 modules made 12 `quarry:` provenance headers dangle (they pointed at
`quarry/parked/topic-*/…`, repointed there by the floor-rule slice). **`verify.py provenance` went RED
on the next run** and the headers were repointed to the restored paths. The gate added one slice
earlier caught the side effect of a law change the same hour — which is the whole argument for
asserting resolution rather than presence.

### Withdrawn before landing
The earlier *atomic-park* clause (prune the `__init__` re-exports a park orphans) — measured
insufficient: pruning all 8 dangling re-exports moved importable 318 → 329 only, since the failing
path is direct imports, not re-exports. Audit: `docs/handoffs/AUDIT_quarry_import.md`.

## [0.115.0] - 2026-10-26

**Swaption / vol-cube cluster checkpoint (§6 hard stop at a capability-cluster boundary).** Report:
`docs/handoffs/CP_swaption_cluster.md`, carrying the four review inputs plus the named next
checkpoint. No pricing logic touched. Drawdown unchanged at **23 / 793** (Cowork ratified the
slice-B tick, thread 0011).

### Added
- `docs/handoffs/CP_swaption_cluster.md` — the cluster's checkpoint: **oracle-quality audit run
  against the AMENDED §6** (the first one under the floor rule and doc 11's new standing question),
  drawdown reconciliation, a 6-item challenge-me list, and the smell+debt scan with
  **NG-DEFER-QUARRYIMPORT's four options** ranked, per thread 0011's fold-it-in ruling.

### Fixed — finding O1 from that audit, closed in the same commit
- **`calibrate_sabr_smile` was the one cluster gate with an unasserted population.** It builds one
  residual per quoted strike and accepts/rejects on `max(abs(r) for r in residuals)`; nothing
  asserted `len(residuals) == len(strikes)`, so a short list would have passed the 1bp gate on a
  subset while the remaining strikes went unfitted. It cannot happen today — `SmileQuote`'s own
  invariant guarantees the length — so the gap was *guaranteed by an invariant and never asserted*,
  the opposite posture to the cube (where the type makes a drop unrepresentable **and** the oracle
  asserts it anyway). New test closes it; `TEST_FLOOR` 374 → 375.

### Audit result, for the record
Five of the cluster's nine oracle files carry a genuine structural/count oracle — the 2Y cap's
**7** caplets, the strip building the ladder (not one caplet per quote), the cube's node count and
poisoned-node floor, the non-canonical S-identity, and `sorted(surface.params) == expected_expiries`.
Three are scalar inversions/reprices with no population to floor, which the report states rather
than assumes. Only O1 was a real gap.

## [0.114.0] - 2026-10-26

**Swaption vol-cube calibration (T1 slice B) — `options/swaption_vol_cube.py` retired. Drawdown
22 → 23 / 793.** Spec + rulings: `docs/handoffs/spec_slice_B_swaption_cube.md` (Cowork, B1–B4).

### Added — `calibration/swaption_cube.py`
- **`build_swaption_vol_cube`** fits a SABR smile at every quoted node by composing the SAME
  `calibrate_sabr_smile` (slice 21's bounded LS + 1bp gate) — no new fitting machinery. It returns
  the outcome for **every quoted node**, keyed `(SwaptionSurfaceKey, expiry)`: successes as
  `(SabrParams, CalibrationResult)`, failures as that node's `CalibrationFailure` carrying residuals.
- **The silent drop is structurally impossible, not merely tested against.** The quarry wrapped each
  node's fit in `except Exception: pass`, so a quoted node that failed to calibrate vanished — and an
  all-failing grid produced an empty-smile cube that repriced its own ATM backbone perfectly, which
  no self-consistency oracle can see. The map is keyed by the quoted grid, so a vanished node cannot
  be represented (ruling B1 — §6's floor rule on this slice's own grid).
- **Counts derived, never stored.** `calibrated_count()` reads the map; a stored count is itself the
  proxy §6's second clause forbids, since it can drift from the collection it summarises.
- An **empty** quote grid is a `CalibrationFailure`, not an empty cube (floor-on-population).
- `swaption_cube()` derives `{SwaptionSurfaceKey → SabrSurface}` — the shape `SABRModel.swaption_vol`
  already reads — from the successes. β is an explicit input with **no default** (invariant 5).

### Changed — ML-D1's FIT-side instance closes (ruling B4)
- **`SmileQuote` gains a required `forward`** (3 → 4 fields). Slice A threaded the forward through the
  **read**; `calibrate_sabr_smile` still reconstructed its own from `index.canonical_accrual` — the
  single-period *caplet* forward, correct for a caplet and **wrong for a swaption node**, whose
  forward is `S = float_leg_pv/rpv01`. Composing it unchanged would have reintroduced ML-D1 per node,
  in a grid, one slice after the read side closed it. A smile *is* quoted at a forward, so it travels
  **with** the smile for the same reason `law` travels with `SabrSurface.params`.
- **The `canonical_accrual` reconstruction is DELETED.** Each consumer supplies its own product's
  forward: the cube passes the node's marked S, `calibrate_capfloor_sabr` passes the caplet forward it
  reconstructed before — **byte-identical, verified exactly** (full-precision `repr` of α/β/ρ/ν across
  all four expiries and all 20 residuals: not one ULP moved).
- **`SabrCalibrationSpec.index` removed** (5 → 4 fields). It existed only to reconstruct the forward;
  once B4 moved that onto the quote it became accepted-and-ignored, which is worse than absent — a
  caller could pass the wrong index and nothing would complain.
- **`verify.py TEST_FLOOR` 366 → 374**, raised in the same commit as the tests it counts. A floor that
  lags lets shrinkage above the stale value pass unseen.

### Oracles (5, RED before GREEN)
Node count / no-silent-drop on a **poisoned** grid (a deliberately unfittable node must surface as a
counted failure) · **S-identity per node on a NON-CANONICAL (semi-annual) underlying** · round-trip ·
inverter parity (slice 24's law-generic `implied_vol` is composed, not re-derived — its first ng
consumer) · β explicit. **Oracle 2's non-vacuity is itself verified**: on this grid the engine's S and
the canonical forward differ by **+6.37 to +6.38bp**, and re-injecting the deleted reconstruction turns
the oracle RED. On a canonical underlying the two coincide and it would have passed with every node
mis-fit — which is why the grid is semi-annual.

### Not ported, with evidence
`bumped()` — added an absolute vol shift to SABR `alpha`, a vol only at β=1; measured **5.43–6.19×**
over-bump against ng's own `sabr_vol`, strike-dependent, so it tilted the smile its docstring claimed
to preserve · `_nearest_sabr` (mixed-unit distance, magic tolerance, priced a different node's smile)
· the ATM fast-path (discontinuous at the money) · the bare fallbacks returning grid-ATM / `0.0` ·
the ATM-interpolation atom implemented **twice in one file**, the copies returning `0.25` and
`IndexError` on identical inputs (§3d; rebuilt once in L0 at its first off-pillar consumer, ruling B3).


## [0.113.0] - 2026-10-26

**The floor rule — §6's second clause now binds the verification apparatus** (Cowork ruling:
`docs/handoffs/rulings_floor_rule.md`, answering thread 0001+0002). Apparatus only; no pricing logic
and no oracle expected value touched. Drawdown unchanged at 22 / 793.

### Changed — the law
- **CLAUDE.md §6, structural-oracle rule, second clause replaced.** *A gate's green is evidence only
  if the gate also asserts a floor on what it examined; green over an unknown, empty, or truncated
  population is not green.* Two faces: **floor-on-population** (any check that filters, collects or
  iterates asserts a minimum count of survivors — a count, not "green") and
  **resolve-don't-just-exist** (a presence check must dereference what it names). Ruled an
  **amendment**, not an application already implied: three instances passed through ratification and
  none was read as covered, so "already implied" would be revisionism.
- Precedent recorded as three instances of one shape — audit #10 (caplet grid ≠ quote grid),
  `--layer 0` (177 of 366 tests for six slices), `provenance` (17 of 45 paths dangling, two wrong
  since written).

### Added — the gates that enforce it
- **`verify.py TEST_FLOOR = 366`**, asserted by `verify.py tests` on the un-truncated run; CI **RED**
  below it. Verified to bite: floor at 367 → exit 1; at 366 → exit 0; and `--layer 0` collects 177,
  so the assertion would have caught the original defect. A slice adding a tier raises it in the same
  commit.
- **`verify.py provenance` now dereferences every `quarry:` path** (file or directory), and RED-fails
  if it examines an empty population. `quarry: —` is the explicit no-ancestor form.
- **`docs/11`** oracle-quality audit gains: *confirm every gate asserts a floor on what it collected
  or resolved, not merely that it ran green.* Docs **09** and **10** carry the per-gate obligations.

### Fixed — `OPEN.md` NG-DEFER-PROV DISCHARGED
17 unresolvable provenance paths, all three failure modes: **10** repointed under
`quarry/parked/topic-*/` (physically parked at a topic close — doc 13 parking is a `git mv`); **2**
wrong sub-directories (`pricing/registry.py`→`registry.py`,
`models/vol_surface.py`→`options/vol_surface.py`); **2** naming a file that never existed
(`fixed_income/interest_rate_swap.py`→`fixed_income/swap.py`); and `risk/priceable.py` has **no**
quarry ancestor — `Priceable` is an ng design construct (§1) — now `quarry: —`.

### Added — records
- `docs/handoffs/record_window_20_25_cleared.md` — the slices-20–25 window **cleared by execution**:
  three CI runs × two OSes, **366 passed** each. The ruling could not clear it; only running it could.
- `docs/handoffs/AUDIT_swaption_vol_cube.md` — slice B's scoping pass (9 findings; `bumped()` verified
  5.43–6.19× over-bump, the ATM-interpolation atom duplicated with one copy raising `IndexError`).
- `OPEN.md` **NG-DEFER-QUARRYIMPORT** — the quarry no longer imports (parking orphaned
  `core/__init__`'s re-exports), so §7c's nightly quarry regression is currently unachievable.

### Re-anchored
`docs/23_repo_restart.md` A3 and `OPEN.md` NG-DEFER-PROV now derive from the ruling rather than from
Code's judgement — the criteria are unchanged, their authority moved from judgement to law.


## [0.112.0] - 2026-10-25

**Repo restart (artifact 23) — the tree is restructured and the test gate is closed.** No pricing
logic changed; no oracle expected value moved. Drawdown unchanged at 22 / 793.

### Changed — layout
- `src/pricebook_ng/` → **`src/pricebook/`**, `tests_ng/` → **`tests/`**, `redesign/` → **`docs/`**,
  `documents/` → **`notes/`**, `python/` → **`quarry/`**; `parked/` and `ng_parked/` fold under
  `quarry/parked/`. 644 path references rewritten across 113 files. The `_ng` suffix was migration
  scar tissue; 59 modules is the cheapest the rename will ever be.
- Root cleared of quarry-era docs. `REFERENCES.md` and `RELEASE_NOTES.md` do not cross (§7 — the
  frozen quarry release log); their `.gitignore` allowlist entries are removed so a stray file of
  either name is not silently tracked again.
- `quarry/parked/ng/` is **deliberately untouched** — its package genuinely is `pricebook_ng` and it
  is a frozen record (728 references left as written). `CHANGELOG` history is likewise not rewritten:
  a changelog records what was true when written. A mapping note stands at the top instead.

### Fixed — the merge gate was checking 48% of the suite
- **CI ran `verify.py tests --layer 0`: 177 of 366 tests.** 189 tests — every oracle from slices
  20–25 included — were gated by nothing for six slices, while each report read "gates green".
  `ci.yml` even carried the comment *"Bump --layer as topics add tiers"*; it was never bumped.
- **`--layer` is now optional and discovers `tests/L*`.** The bug was the hardcoded ceiling, not the
  value `0`: a filter with no floor (CLAUDE.md §6, second clause), the same shape as audit #10.
  `--layer N` is kept for the per-tier local run §7b describes. CI now collects 366 across 6 dirs.

### Fixed — stale index
- `docs/README.md` claimed drawdown `13 / 768` (tracker: `22 / 793`) and called artifact 22
  "awaiting adversarial review" when it has been **ratified rev 3** since 2026-07-29.

### Added
- `docs/23_repo_restart.md` — the ratified artifact, 8 criteria, all pass.
- `OPEN.md` **NG-DEFER-PROV** — 17 unresolvable `quarry:` provenance paths, none caused by this
  restart; `verify.py provenance` never checked that a path resolves.

### History
- Re-founded at `v0.111.0`. Versions 0.0.1–0.111.0 (151 PRs, each with its own `RED → GREEN` commit
  sequence) live in **bdcbqa314159/pricebook-legacy**, archived read-only, reachable on
  `refs/pull/<N>/head`.


## [0.111.0] - 2026-10-24

**Swaption SABR smile, read-not-solved (T1 slice 25) — and the vol capabilities take the forward as
an INPUT (Cowork ruling A). `OPEN.md` ML-D1 CLOSED.** Drawdown unchanged at 22 / 793 (the
`swaption_vol_cube.py` tick lands with slice B).

### Changed — the capability amendment (ruling A)
- **`ImpliedVol.implied_vol(index, expiry, strike, forward)`** and
  **`SwaptionVol.swaption_vol(index, expiry, swap_tenor, strike, forward)`**: the forward is now an
  **input**, never reconstructed inside the capability. A smile is `σ(F, K)`; the engine computes F
  (over the contract's own accrual) and `S = float_leg_pv/rpv01` with the shared atoms and **passes
  it**, so the price formula and the smile compose the SAME forward by construction — the §3d
  identity cannot be false rather than being enforced by a guard.
- **Why it was forced:** a swaption's underlying has a fixed-leg frequency and day counts that the
  contract chooses and `RateIndex` cannot carry, so `swaption_vol` could not reconstruct the engine's
  S. Measured across the four underlying conventions this tree itself uses (annual/semi/quarterly ×
  ACT/365F/ACT/360): **S spans 48.8 basis points**, 1.4% relative. Collateral, seasoning and notional
  shape are three further vectors the reconstruction could not see. All four close at once.
- **`models/sabr_model.py` — the canonical-accrual F reconstruction is DELETED.** `SABRModel` anchors
  its Hagan expansion at the passed forward, via one shared `_params` read used by both capabilities.
- **`BlackModel` ignores the new argument** (`del forward`) — a flat/term `Surface` has no smile axis,
  which is what keeps every Black number byte-identical across the amendment.
- `redesign/22_model_calibrator_foundation.md` carries the amendment and the rejected alternatives.

### Added
- **`SABRModel.swaption_vol`** (L3): reads `SwaptionSurfaceKey(index, swap_tenor)` → `SabrSurface` →
  `at_expiry(expiry)` → `SabrParams`, and returns `law.sabr_vol(S, strike, t, params)` at the engine's
  marked S. `SABRModel` now satisfies **two** opt-in capabilities — `ImpliedVol` *and* `SwaptionVol`
  (doc 22 Q1) — with no fat base class and no type ladder. Read-not-solved: params on the snapshot,
  calibration is slice B.
- **The cube is a key and a method, not a type.** `{SwaptionSurfaceKey(index, swap_tenor) →
  SabrSurface}` is the whole cube; the quarry's `SwaptionVolCube` is **not ported**, and with it go its
  **nearest-node strike hack** (snapping a requested strike to the nearest quoted node — silently
  pricing a different strike) and its **silent calibration fallback**.

### Fixed
- **ML-D1 closed, and the refused class is now delivered.** The slice-23 guard that refused a stub /
  odd-day-count optionlet existed *only* to protect the F reconstruction. With the forward threaded it
  is gone: a short-stub caplet and an odd-day-count caplet now **price correctly at their own
  forwards** (asserted against independent compositions), and a semi-annual cap on a 3M index prices
  as the exact sum of its own ladder.

### Oracles (all green — 366 tests, +10)
- **The structural oracle (the teeth, per the newly ratified §6 rule).** Under ruling A, "do the two
  S match?" is *trivially* true — the engine passes its own S — so that question would be **vacuous**.
  Instead: an ATM payer on a **NON-CANONICAL** (semi-annual on a 3M index) underlying, struck at the
  engine's marked S, must mark at `annuity · black(S, S, σ_SABR(S, S))` — the ATM branch at the
  *engine's* S — to **<1e-12**, with the reconstruct-S failure mode asserted explicitly at both the
  vol (>1e-4) and the PV (>0.1% relative) level.
  **Proven non-vacuous:** re-implementing `swaption_vol` to reconstruct S from the canonical annual
  underlying reds exactly this test and nothing else.
- Hagan reference across four strikes vs an independent inline eq-2.17a (<1e-12).
- **Payer − receiver parity** = `annuity·(S − K)` composed from the atoms alone, no option formula
  (<1e-12).
- A **negative** forward swap rate prices under the normal law (<1e-12 vs inline Bachelier) and is
  refused under the lognormal one.
- Structural reads as values: a flat `Surface` under a SABR swaption, and a model-law/cube-tag
  mismatch. `SABRModel` asserted to satisfy `CalibratedModel`, `ImpliedVol` and `SwaptionVol`.
- **Byte-identical:** all 47 legacy pricing paths (BlackModel caplet + BlackModel swaption + SABR
  caplet) and the caplet-vol strip's stripped vols — so threading the argument moved no in-scope
  number and BlackModel's swaption path is untouched.

### Notes
- The mandate phrased the structural oracle as "lands on the smile minimum". With ρ = −0.3 and β = 0.5
  the ATM point is **not** the minimum — a SABR smile with a CEV backbone is a skew — so the oracle
  asserts the ATM *branch* at the marked S, which is the discriminating content and strictly stronger.
- **`CLAUDE.md` §6 gains the ratified structural-oracle rule** (a self-consistency oracle cannot see a
  wrong decomposition; a filtered grid needs a survivor floor), and `redesign/11`'s oracle-quality
  audit gains the matching checkpoint bullet.
- Ratified without code change: ML-D2 (β=0 as THE normal law), ML-D3 (the 1bp constant), CF-D1 (the
  unconditional first-period exclusion), and slice 23's contract-own-period ladder reading.

## [0.110.0] - 2026-10-24

**Implied-vol inversion (T1 slice 24) — two quarry functions become one law-generic inverter, a
duplicated search becomes an L0 atom, and `options/implied_vol.py` ticks DELETABLE
(drawdown 21 → 22 / 793).** The retiring slice recommended in `CP_capfloor.md` §7.

### Added
- **`models/implied_vol.py` — `implied_vol(law, call_price, forward, strike, t)`** (L3): the vol, in
  the law's own units, that reproduces an UNDISCOUNTED call price. **One function, every law** —
  because a law is a value with its own `price` (slice 22), the inversion is law-generic: lognormal,
  shifted-lognormal and normal are the same code, and `law.defined` decides the domain. The quarry
  needed one inverter per law and never had one for the shifted law. §3d holds by construction: the
  inverse composes the very function it inverts, so a price and its implied vol cannot drift.
- **`models/implied_vol.py` — `call_price_from_put(put_price, forward, strike)`**: put-call parity
  `C = P + (F − K)` as a named atom, exact and identical in every law here. It replaces the quarry's
  `option_type` parameter — the implied vol of a put IS its call's, which is the whole content of
  parity, so the solver carries no option-type branch.
- **`foundation/solvers.py` — `invert_increasing(f, target, lo, hi, cap)`** (L0): the inverse of a
  monotonically increasing function, with an upper bracket **doubled** from `hi` until it straddles
  the target or passes `cap`. Unattainable targets raise, naming which end failed; it never returns a
  mid-bracket consolation value. Promoted because the search was already duplicated — the caplet-vol
  strip's marginal solve and the implied-vol inversion are the same problem.

### Changed
- **`vol_strip._solve_vol` composes `invert_increasing`**, its hand-rolled bracket loop deleted (two
  real in-slice consumers for the new atom, §6b rule of two satisfied by existing code). **Stripped
  vols are byte-identical.** The only visible change is the failure *message*, which is now accurate:
  an infeasible marginal whose target sits **below the intrinsic** used to be reported as "not
  bracketable below 500%", blaming the vol cap for a low-end failure.
- **A price at its intrinsic to machine precision now RAISES.** `law.price(…, vol=0, …)` is the
  intrinsic (every law's degenerate branch), so the bound needs no law-specific arithmetic. A deep
  in-the-money quote is flat in the vol — vega has underflowed — and any answer fits it equally well;
  the quarry returned whatever its solver landed on, a confident ~1e-9 for an option whose true vol
  was 5%.

### Oracles (all green — 356 tests, +12)
- **Round-trip per law** across a strike × vol × expiry grid (`Lognormal`, `ShiftedLognormal(0.03)`
  at positive **and negative** forwards, `Normal` at both): `vol → price → vol` recovers the input vol
  to **<1e-10** and its price to **<1e-14**. Known-answer at both ends, not a self-consistency loop.
  The grid filters quotes whose time value has underflowed and asserts a floor on how many cases
  survive, so the filter cannot quietly eat the suite.
- **PUT prices invert through the parity atom** to the same vol as their calls (<1e-10) — the
  content of the parameter the quarry carried, reproduced as an identity.
- **An independent bisection on an inline `erf`-Black** agrees with the production inverter (<1e-9):
  a different solver on a different price implementation.
- **Negative forwards invert** under `Normal` and `ShiftedLognormal` — the case whose quarry bracket
  (`hi = forward * 5.0`) was broken — and are refused by `Lognormal.defined`.
- **Failure, never a silent number:** at/below intrinsic, above the vol cap, `t ≤ 0`, outside the
  law's domain, and both bracket ends of the L0 atom — each raises, each named.
- **Conditioning stated, not hidden:** a near-intrinsic price reconstructed through parity (how a real
  quote arrives, carrying its own rounding) recovers the vol to ~1e-6 rather than 1e-10 — pinned as a
  documented property, with the well-conditioned path asserted at <1e-12 beside it (§7c).
- **Byte-identical:** the strip's stripped vols, and all 47 legacy pricing paths.

### Drawdown (§4)
**21 → 22 / 793.** `options/implied_vol.py` ticks **deletable** with an **empty residual** — no
deferred capability, no deferred product. Consumer evidence: `implied_vol_black76` has **7**
production consumers in the quarry (`options/sabr_mc`, `desks/api`, `models/hw_calibration`,
`models/rough_equity`, `models/jump_calibration`, `models/g2pp_calibration`,
`equity/joint_calibration`), all un-crossed — a load-bearing capability ng must have for those
modules to cross; `implied_vol_bachelier` has **0** and is absorbed at zero cost by the generic
inverter. **ng consumers today: zero** — this lands because it retires a module (§4), as one concrete
function rather than an abstraction. Physical `git mv` batches at the next topic close (doc 18 §9).
Evidence: `redesign/handoffs/AUDIT_implied_vol.md`, `quarry_reconciliation.md`.

### Debt
No new ledger rows — the residual is empty and nothing was deferred. **No suppressions added.**

## [0.109.0] - 2026-10-24

**Cap/floor retirement (T1 slice 23) — the ladder becomes an atom, audit #10 is discharged, and
`options/capfloor.py` ticks DELETABLE (drawdown 20 → 21 / 793).**

### Added
- **`products/option.py` — `CapFloor(index, schedule, strike, notional, option_type)` + `cap_ladder`**
  (L2): a cap (CALL) / floor (PUT) as pure data — it holds its schedule and **no caplet list**, so
  `cap_ladder(cap)` is the single definition of which caplets a cap IS, composed by the L4 pricer, the
  caplet-vol strip and the cap-SABR calibration alike (§3d). The first period is excluded (its rate is
  set at the cap's start; caps are quoted excluding it — Brigo–Mercurio §1.6), which is also what makes
  a spot-starting cap priceable at all, since the engine refuses a seasoned optionlet as a value.
  Validates a positive notional and ≥2 periods (a one-period schedule has an empty ladder).
- **`engine/vanilla_option.py` — `price_capfloor`** (L4): Σ `price_caplet` over the ladder, returning
  the first failure as the cap's value (invariant 4). Composing the optionlet pricer means the model's
  own **vol law**, the **ruling-2 canonical-accrual guard** and invariant 6 all apply per caplet for
  free — a cap is law-polymorphic without a line of law-aware code, where the quarry duck-typed
  `hasattr(model, "price_ir_option")`.
- **`calibration/sabr_calibrate.py` — `calibrate_capfloor_sabr(spec)` + `CapSabrCalibrationSpec`**
  (L3): cap flat vols → per-strike ladder strip → a `SmileQuote` per expiry → the slice-21 bounded fit,
  returning a `SabrSurface` ready for `SABRModel.for_index`. **Pure composition** — no new fitting
  machinery, so the 1bp acceptance gate (ruling 1) and the F-identity arrive already paid for. Ragged
  grids, <3 strikes, and a non-lognormal model are refused as values.
- **`calibration/vol_strip.py` — `cap_for_quote(quote, spec)`**: the cap a quote describes (valuation
  date → maturity, stepping at the index tenor, anchored forward so each maturity's ladder extends the
  previous one's). Exposed because the cap-SABR calibration builds the same caps — one definition.

### Fixed
- **Audit #10 — `vol_strip` no longer assumes the caplet grid is the quote grid.** It built **one
  caplet per quote**: a "2Y cap" was a single caplet fixing at 2Y rather than the 7-caplet ladder it
  is, and `q.maturity` was silently read as that caplet's *fixing* date. The strip now builds each
  quote's full `cap_ladder` and solves ONE marginal vol per quote *interval*, shared by every new
  caplet in it (piecewise-constant marginal, the standard strip). A 5Y quote set strips **19** pillars,
  not 4. Its trigger — "a real cap with intra-tenor caplets" — is this slice's own product.
  **Why the old oracles were blind:** a flat cap-vol curve strips flat whatever the ladder's shape, and
  the reprice oracle repriced the same one-caplet object it had stripped. The fix needed a **count**
  oracle and a **finer-grid** reprice, not a tighter tolerance.
- **Three silent-wrong paths in the strip now fail as values:** an **off-grid** quote maturity (a 13M
  cap on a 3M index ends in a 1-month stub whose accrual is not canonical — the L4 pricer would refuse
  that caplet, so stripping vols for it produced a surface nothing could price), **duplicate**
  maturities (two quotes claiming the same marginal — the quarry skipped the second silently), and
  **mixed-strike** quote sets (a `Surface` has no strike axis, so blending smiles into one is the same
  class of error as #10).

### Changed
- **`Caplet` gains `option_type`** (default CALL) — the floorlet its own docstring promised would
  "arrive with its consumer"; the floor is that consumer. `price_caplet` reads it, so the CALL default
  keeps every earlier path byte-identical.
- The strip composes **`Lognormal().price`** rather than a bare `black` call — the same composition the
  L4 pricer performs (§3d). The strip stays lognormal-only *by design*: the only model that reads a
  flat/term `Surface` is `BlackModel`, whose law is a fixed `Lognormal`, so stripping in another law
  would produce vols nothing can consume (`OPEN.md` CF-D3).

### Oracles (all green — 344 tests, +24)
- **The ladder count (audit #10):** a 2Y 3M-EURIBOR cap is **8 periods → 7 caplets**, first excluded;
  a 5Y quote set strips **19** pillars; a longer cap's ladder **extends** a shorter one's (what makes
  the sequential strip well-posed).
- **Put-call parity:** `cap − floor = Σ df·N·τ·(F − K)` over the ladder, composed from the `forward`
  and `df` atoms **alone** — no option formula in the expected value — to <1e-9.
- `cap == Σ cap_ladder(cap)` priced caplet-by-caplet (<1e-12); every ladder caplet carries the index's
  canonical accrual (the per-caplet F-identity, by construction); a floor's ladder is PUT optionlets.
- **Each cap reprices to its own flat quote on a finer caplet grid** (4 quotes, 19 caplets), end-to-end
  through the L4 engine on both sides, <1e-10; a flat quote curve still strips flat across the full
  ladder (<1e-10); the engine-vs-inline-Black backstop now runs at all **19** ladder expiries.
- **Multi-law (inherited):** a normal-law cap prices at a **negative** forward; the same cap under the
  lognormal law fails as a value; a semi-annual schedule on a 3M index → `PricingFailure` (ruling 2).
- **STEP B end-to-end known answer:** seed `SabrParams` → SABR caplet vols → **cap flat vols inverted
  by the test's own inline Black + Brent** → the ladder strip → a smile per expiry → the fit recovers
  the seed per expiry to <1e-6. The quote grid is set equal to the caplet grid, so the recovery is
  exact rather than approximate; the calibrated surface then reprices every cap (<1e-6 relative).
- **§3d one-ladder:** the strip's pillars, the pricer's ladder and the calibration's fitted expiries
  are asserted to be the same set. **Byte-identical:** the 47 single-`Caplet`/swaption paths of slices
  1–22 unchanged.
- **Failure as a value:** a contradictory cap smile → `CalibrationFailure` (the 1bp gate); <3 strikes;
  a ragged strike×maturity grid.

### Drawdown (§4)
**20 → 21 / 793.** `options/capfloor.py` ticks **deletable** — the vanilla cap/floor crosses whole.
Residual = three deferred *capabilities*, no deferred product: per-caplet greeks
(`deferred→L5`), `_cf_from_convention` (`deferred→conventions`, 0 consumers anywhere), and
serialisation (`deferred→DB-spine`) — all forward-linked on their destination rows in the Topic-1
MANIFEST. Physical `git mv` batches at the next topic close (doc 18 §9). Evidence:
`redesign/handoffs/AUDIT_capfloor.md`, `quarry_reconciliation.md`, `CP_capfloor.md`.

### Debt
Audit **#10 CLOSED**. Four deferred-scope rows added (`CF-D1`…`CF-D4`): forward-starting caps, the
per-caplet greeks breakdown, the lognormal-only strip, and cap schedules with their own day
count/calendar. **No suppressions added** — `verify.py debt` balance unchanged.

## [0.108.0] - 2026-10-24

**SABR multi-law (T1 slice 22) — the vol LAW becomes a value; shifted + normal SABR land; `options/sabr.py`
ticks DELETABLE (drawdown 19 → 20 / 793).** Executes the Cowork ruling on the SABR-cluster checkpoint.

### Added
- **`models/vol_law.py` — the `VolLaw` protocol + `Lognormal` · `ShiftedLognormal(shift)` · `Normal`**
  (L3): the value that binds a law's three inseparable parts — its option formula, its SABR expansion,
  and its **domain** (`defined`) — plus the α **scale** of its expansion (`seed_alpha`). `vol_law_for(kind,
  shift)` is the ONE tag→law mapping, called at model construction only, so no pricer, calibrator or risk
  bump ever branches on the law (CLAUDE.md §1). Rule of two satisfied three times over, in-slice.
- **`models/bachelier.py` — `bachelier(F, K, vol, t, type)`** (L3): the undiscounted normal-model
  optionlet, the sibling of `black`. Defined for **either sign** of `F` and `K`. Quarry:
  `models/black76.py (bachelier_price)`.
- **`models/sabr.py` — `sabr_normal_vol`**: the **β=0 Hagan normal expansion**,
  `σ_N = α · z/χ(z) · (1 + (2−3ρ²)ν²t/24)` with `z = (ν/α)(F − K)` — **no log-moneyness**, so the smile
  survives through zero. This SUPERSEDES the quarry's `σ_B·√(FK)` conversion (its own docstring called it
  an approximation "for moderate moneyness"); a general-β CEV quoted in normal-vol units is a law
  conversion and now RAISES rather than being approximated (`OPEN.md` ML-D2).
- **`market/vol_surface.py` — `VolLawKind` + `SabrSurface.law`/`.shift`** (L1, **data only**): which law
  the params are quoted in travels WITH them — α is an absolute rate vol under the normal law and a
  relative one under the lognormal, so params read in the wrong law are wrong by a factor of F. Validated
  at the data boundary (a shift only under the shifted law; β=0 under the normal law).
- **`models/sabr_model.py` — `SABRModel.for_index(market, index)`**: the sanctioned constructor, building
  the model with the law its own surface is tagged with. `implied_vol` additionally refuses a
  model-law/surface-tag mismatch (compared as VALUES through the same factory — no reverse mapping).
- **`foundation/rate_index.py` — `RateIndex.canonical_accrual(start)`**: the ONE definition of "the period
  this index's rate is quoted over" (§3c rule 5), composed by the model, the calibrator and the engine.

### Changed
- **`BlackVol` → `ImpliedVol`** (`black_vol` → `implied_vol`, + a `vol_law` member): once the law became
  data, a method called `black_vol` returning a *normal* vol was actively misleading. The capability now
  carries the law it is quoted in — a MATCHED PAIR, since `vol_law.price(F, K, implied_vol(…), t, type)` is
  the only sanctioned composition. The **signature is unchanged**. `ImpliedVol`/`SwaptionVol` now extend
  `CalibratedModel` (a vol is only meaningful bound to the market it was read from).
- **`engine/vanilla_option.py`** composes `model.vol_law.price(...)` instead of calling `black` directly,
  and the hard-coded lognormal `F ≤ 0` guard (audit #15) becomes the law's own `defined(F, K)` — so a
  negative forward is a failure under `Lognormal` and ordinary under `Normal`/`ShiftedLognormal`, with **no
  law branch in the pricer** (asserted structurally over the module's AST).
- **`calibration/sabr_calibrate.py`** composes `model.vol_law.sabr_vol` and `seed_alpha`, so ONE code path
  fits every law in its own units (the lognormal seed `σ_ATM·F^{1−β}` is not even real for a negative
  forward — asking the law fixes it). `SabrCalibrationSpec.model` is now typed `ImpliedVol`.
- **`CalibrationFailure` gains `residuals`** (default empty): carried when the solve RAN and was rejected
  on fit quality, empty when it never started.
- **`models/sabr.py` splits**: the expansions stay; `SABRModel` moves to `models/sabr_model.py` (the
  `black.py`/`black_model.py` precedent), which is what lets `vol_law.py` compose the expansions without an
  intra-layer cycle.

### Fixed
- **Ruling 1 — the acceptance gate.** `converged` is the SOLVER's verdict, not the fit's: bounded TRF
  genuinely converges on a smile no SABR can fit. A converged fit whose worst vol residual exceeds
  `_MAX_VOL_RESIDUAL` (1bp — the quarry's own `max_rmse_bp` default) now returns `CalibrationFailure`
  CARRYING its residuals, instead of a result the caller must remember to inspect (invariant 4). The gate
  is deliberately NOT `SolveConfig.tolerance` — that is the solver's xtol (1e-12), a different quantity;
  gating on it would reject a round-trip fit exact to 8e-11 (`OPEN.md` ML-D3).
- **Ruling 2 — the F-identity guard.** A vol capability is handed only `(index, expiry, strike)`, so it can
  reconstruct the forward only from the index's canonical accrual. `price_caplet` now refuses any caplet
  whose accrual differs (a stub, an odd day count) as a `PricingFailure`, instead of silently reading the
  smile at the WRONG forward. The slice-21 "documented, not enforced" assumption is now enforced, and its
  re-open trigger self-fires (`OPEN.md` ML-D1).
- **Audit #15 discharged.** A NEGATIVE-forward caplet, which the lognormal-only engine could only refuse,
  now prices under the shifted and normal laws (and still fails under the lognormal one).

### Oracles (all green — 320 tests, +29)
- **Byte-identicality of the promotion:** 47 lognormal pricing paths (Black caplet × strikes/vols, SABR
  caplet × params/strikes, Black swaption × rates/vols/parities) dumped as exact float reprs before and
  after — **identical**, so moving the engine onto `law.price` moved no number (§8 refactor carve-out).
- `bachelier` vs an independent inline normal formula (<1e-15); **exact put-call parity `C − P = F − K`**
  for either sign of F and K; σ→0 / t→0 intrinsic.
- `sabr_normal_vol` vs its **ρ=0 `asinh` closed form** (`χ(z) = asinh(z)`, a genuinely different function)
  <1e-15; **ν=0 ⇒ σ_N ≡ α at every strike including negative ones** (<1e-16); the F=K removable-singularity
  branch; ρ<0 skew orientation; β≠0 raises.
- **Cross-law price check:** ONE β=0 SABR dynamics priced through `black`@σ_B and `bachelier`@σ_N agrees to
  ~1e-4 relative (asserted <5e-4) — the quarry's conversion misses by ~3e-3, so the oracle discriminates.
- `ShiftedLognormal(0)` ≡ `Lognormal` at every strike; `ShiftedLognormal(s)` ≡ the lognormal law on the
  shifted pair; every law's domain; `vol_law_for` maps every tag.
- **Per-law known-answer round-trips** through the engine's own forward: NORMAL recovers its seed to <1e-8
  (reprice identity <1e-8), SHIFTED recovers its seed at a **negative** forward to <1e-6 (reprice <1e-6),
  and the same negative smile FAILS under the lognormal law.
- **Ruling 1:** a contradictory (alternating) smile → `CalibrationFailure` with residuals > 1bp; a real
  SABR smile passes the same gate (no false positive). **Ruling 2:** a short-stub caplet and an
  odd-day-count caplet → `PricingFailure`; the canonical caplet is the positive control.
- **Structural:** the pricer imports no law module, names no law, and `isinstance`s only the capability
  protocols — asserted over the module's **AST**, so prose in the docstring cannot pass or fail it.

### Drawdown (§4)
**19 → 20 / 793.** `options/sabr.py` ticks **deletable**: slices 20–22 cross its whole pricing/vol/
calibration content. Genuine residual = the `SABRCalibrationResult`/`CanonicalCalibrationResult`
persistence artefact → **`deferred→DB-spine`** (a deferred *capability*, not a product, so it does not
block the tick, §4); grep-confirmed 0 ng consumers, forward-linked on the DB-spine row of the Topic-1
MANIFEST. Physical `git mv` batches at the next topic close (doc 18 §9). Evidence:
`redesign/handoffs/AUDIT_sabr_multilaw.md`, `quarry_reconciliation.md`, `CP_sabr_multilaw.md`.

### Debt
Four deferred-scope rows added to `OPEN.md` (`ML-D1`…`ML-D4`), each failing LOUD today rather than
approximating: stub optionlets (the `ImpliedVol` signature change, deliberately unpaid), the general-β
normal conversion, the acceptance threshold as a constant, and one law per surface. **No suppressions
added** — `verify.py debt` balance unchanged.

## [0.107.0] - 2026-09-06

**SABR smile calibration (T1 slice 21) — the read→calibrate arc closes; first SABR drawdown movement.**

### Added
- **`calibration/sabr_calibrate.py` — `calibrate_sabr_smile(spec)`** (L3, beside `vol_strip.py`): fit
  (α, ρ, ν) — **β fixed** — to a single-expiry `SmileQuote` by **bounded least-squares** over the
  per-strike lognormal-vol residual, composing the SAME `sabr_vol` atom the model/engine read (§3d).
  Returns `(SabrParams, CalibrationResult) | CalibrationFailure` (invariant 4). ATM seed adapted from
  the quarry; the quarry's SSE/Nelder-Mead + `1e10` penalty is **shed** for a real box.
- **`market/quotes.py` — `SmileQuote(expiry, strikes, vols)`** (L1): a quoted vol smile at one expiry;
  `__post_init__` guards equal lengths, strictly-ascending strikes, and the ≥3 points a 3-parameter fit needs.
- **`foundation/solvers.py` — `least_squares`/`root_nd` gain an optional `bounds=(lower, upper)`**:
  bounded fits switch from Levenberg-Marquardt to Trust Region Reflective (LM cannot take bounds). One
  swap point (§7bb); the SABR calibrator is its first consumer — a real box, never a penalty term.

### Notes
- **§3d F-identity (verified by construction):** the calibrator derives the forward from the model's own
  projection curve via the SAME canonical accrual `SABRModel.black_vol` uses — so fitted params → a
  `SabrSurface` → `SABRModel` reproduce the calibrated smile at exactly the F priced at. The round-trip
  oracle recovers a known seed `SabrParams` to <1e-6 (max residual ~8e-11); the reprice oracle confirms
  `SABRModel.black_vol` reproduces every target vol to <1e-6 — calibrate-to-quote == price-to-smile, one fact.
- Failure-as-value: a degenerate smile (non-positive forward/strike — lognormal SABR undefined, cf. the
  caplet #15 guard) or a non-converged solve returns `CalibrationFailure`, never a raise or a silent bad fit.
- Also fixes the v0.106.0 SABR provenance header (`quarry:` pointed at a non-existent `models/sabr.py` →
  corrected to `options/sabr.py`).
- **Drawdown:** `options/sabr.py` partial-cross advances (calibration half crosses); `shifted_*`/`sabr_normal_vol`
  + the DB-persistence artefact remain resident → **tick 0, 19/793** (recorded in `quarry_reconciliation.md`).

## [0.106.0] - 2026-09-04

**SABR caplet — the vol smile (T1 slice 20). Forward progress after the audit close.**

### Added
- **`models/sabr.py` — SABR lognormal implied vol (Hagan et al. 2002, eq 2.17a/2.18)** at L3 (analytic
  block of a dynamics, the `models/black.py` precedent). `sabr_vol(forward, strike, t, params)` — df OUT,
  the engine still multiplies `df·N·τ·black(...)`. The z/χ(z) removable singularity at F=K takes the ATM
  branch (eq 2.18); ν→0 takes the z→0 limit (z/χ→1).
- **`SABRModel`** — the SECOND `BlackVol` implementer (after `BlackModel`) and the FIRST that USES `strike`,
  so a caplet grows a full smile with **NO change to the `BlackVol` signature** (Q1 rule-of-two on the
  capability). READ, not solved: `SabrParams` carried on the snapshot; calibration is a later slice.
- **`SabrParams(alpha, beta, rho, nu)` + `SabrSurface`** value types (L1); `MarketSnapshot.surfaces`
  widened to `Surface | SabrSurface` (closed shapes × open keys — a new representation, not a new field).

### Notes
- **§3d F-identity (verified byte-identical):** `SABRModel.black_vol` derives the forward from its own
  curves using the SAME `forward` atom and the index's canonical accrual the L4 caplet composes, so the
  smile is evaluated at exactly the F the engine prices at — no cross-stage forward drift.
- Oracle: `sabr_vol` reprices to an independent inline Hagan (different code path); β=1/ν=0 collapses to
  flat α; ATM branch matches eq 2.18; the caplet reprices to Black-76 at the SABR-implied vol through the
  unchanged engine. A flat `Surface` under a `SABRModel` (or a `SabrSurface` under a `BlackModel`) is a
  config error surfaced as a `PricingFailure` value, narrowed once in `vol_surface.flat_surface` (keeps
  the union type-switch out of `risk/`, §1).

## [0.105.0] - 2026-08-31

**Audit Batch E — #19 calendar content. CLOSES the v0.98 audit (20/20 findings addressed).**

### Fixed
- **US_GOVERNMENT_SECURITIES (SIFMA, the USD/SOFR calendar):** `Observance.US_SIFMA` — a Saturday holiday
  shifts to the preceding Friday, EXCEPT never back across a year boundary (New-Year-on-Sat stays open). Plus
  **Juneteenth `since=2022`** (SIFMA's first observance; 2021 was short notice → markets open Fri 2021-06-18).
  Four green-oracle anchors: 2020-07-03 closed, 2021-12-31 open, 2021-06-18 open, 2022-06-20 closed. The
  flip-enumeration (2000–2035) confirmed all 17 flips are legitimate Sat-holiday→Friday closes
  (Veterans/Christmas/July-4/Juneteenth-post-2022), none unverified. SOFR windows spanning these dates now correct.
- **TEL_AVIV:** dropped the stale fixed-Gregorian lunisolar entries → weekend-only (Fri/Sat) + SECULAR_ONLY
  (they positively asserted wrong dates — worse than absent).

### Deferred (documented, named triggers)
TEL_AVIV per-year Hebrew-calendar table → first ILS/equity-IL consumer; RIYADH pre-2013 Thu/Fri weekend
(`Weekend.THU_FRI` + `WeekendSchedule`) → first pre-2013-SAR consumer (post-2013 FRI_SAT approximation used).

**🎯 The v0.98 third-party audit is CLOSED — all 20 findings fixed or deferred-with-trigger.** Nothing remains
as hidden wrongness. Drawdown 19/793 (tick 0). Suite 279.

## [0.104.0] - 2026-08-28

**Audit Batch F — accrued/clean-dirty + #3b (current-period pricing). CLOSES the v0.98 audit.** The last
HIGH: a seasoned trade can now be marked on a **mid-period** valuation date, and the reporting split
`total = realized + mark`, `dirty = clean + accrued` is real. Red→green.

### Added / Changed
- **`MarketSnapshot.fixings: FixingSource`** (the "series" shape, doc 19 §2) — fixings are market state on
  the snapshot (one source, A1). **`BookedTrade.fixings` retired**; `realized(booked, model)`/`total`
  re-source from `model.market.fixings` (values byte-identical, re-sourced).
- **The engine prices the current in-progress period (#3b):** `split_current_period` separates it from the
  strictly-future periods (which still price through the UNCHANGED `float_leg_pv`/`rpv01` atoms — spot/
  boundary byte-identical, §3d). `current_period_float_rate` splices the past fixing: IBOR = the single reset
  fixing; RFR = realized-compounded × forward stub. `price_swap` populates **`PricingResult.accrued`** =
  `N·yearfrac(period_start, vd)·(rate − K)`; `clean = pv − accrued`.
- A missing current-period fixing → `current_period_failure` (invariant 4 preserved).

### Oracle
- Seasoned mid-period swap **prices** (repro_P; was the honest failure) — mark hand-checked; `accrued`
  hand-checked; `clean = pv − accrued`; **boundary/spot degenerate** → `accrued=None`, pv identical (slices
  1–N unchanged); **§3d** spot identity (splice never fires, engine == calibrator); missing fixing → failure.

### Deferred (named triggers; a seasoned instrument still fails HONESTLY)
Current-period splice is on `price_swap`; **cash/xccy/swaption keep the `#3a` honest-failure guard** →
their consumers. Option accrued, book-level clean/dirty reporting, RFR lockout/lookback edges → their consumers.

**The v0.98 third-party audit is CLOSED** — all HIGH/MED/LOW findings fixed; #19/#9/#10/#14/base-ccy
deferred-with-trigger (not hidden wrongness). Drawdown 19/793 (tick 0). Suite 272.

## [0.103.0] - 2026-08-25

**Audit Batch D — five LOW guards** (#11/#12/#13/#17/#18), each ported repro → red → green. No-silent-
fallback + invariant 4/5. Unaffected paths byte-identical (suite 267).

### Fixed
- **#11** `spot_lag` keys `_SPOT_LAGS` on the `frozenset` of the two codes (direction-independent) — a pair
  declared `CADUSD` gets the same T+1 as `USDCAD`.
- **#12** `interpolate` rejects non-ascending `xs` with a clear `ValueError` (was silent-wrong via `bisect`).
- **#13** `_solve_pillar_df` expands the bracket **downward** too (DFs ≪ 1e-9 for very-long-dated or
  hyperinflationary high-rate pillars — ARS in scope), floored; a truly unbracketable pillar → `ValueError`
  → `CalibrationFailure` (invariant 4).
- **#17** `_solve_pillar_df` takes the `SolveConfig` and threads `tolerance`/`max_iterations` into the Brent
  call — the sequential knob is now live (invariant 5); was dead. `_solve_pillar_df` stays ≤5 args (bundled).
- **#18** `build_schedule` raises when `payment.lag != 0` and no calendar resolves (a lag counts business
  days — undefined without one), instead of silently paying on the accrual end.

Drawdown 19/793 (bug-fix slice, tick 0). Audit: only the calendar-content batch (#19) and the
accrued/clean-dirty slice (#3b) remain.

## [0.102.0] - 2026-08-24

**Audit Batch C — three MED correctness fixes** (#4/#5/#6), each ported repro → red → green.

### Fixed
- **#4 [MED]** `Surface.at` interpolates **total variance** `w = σ²·T` linear in `T` (arb-free — `w` cannot
  decrease between pillars → no calendar arbitrage), rooted `σ = √(w/T)`. One canonical `vol_time_measure`
  (ACT/365F) is composed by **both** the surface `T`-axis and the pricer's expiry-`t` — one source (§3d).
  Non-LINEAR interpolation is now rejected (arb-free non-linear deferred to a smile/cube consumer).
  **Discharges the C2 σ²·T deferral** flagged in slice 3.
- **#5 [MED]** `underlying_tenor(swap)` gives the **exact** swaption tenor (period count × the schedule's
  coupon step, whole-years → YEAR), replacing `_swap_tenor`'s `round(days/365)` — a 6M underlying keys 6M,
  18M keys 18M (was silently 1Y), 5Y still keys 5Y.
- **#6 [MED]** `HAGAN_WEST` + `SEQUENTIAL` is **rejected at spec validation** → `CalibrationFailure` naming
  `SIMULTANEOUS` (was a `converged=False` tuple). Sequential-HW (terminal-interval convention) stays deferred.

### Note
`Surface.at` gains a `time_measure` argument; `black_vol`/`swaption_vol` thread the canonical clock.
Flat surfaces, whole-year swaptions, and non-HW calibration are byte-identical. Suite 261.

Drawdown 19/793 (bug-fix slice, tick 0). Audit: all HIGH + MED findings now closed.

## [0.101.0] - 2026-08-23

**Audit Batch B — #1 [HIGH]: `CurveBump` by curve identity.** The last HIGH. IR delta was wrong for
every OIS-indexed trade (~750×, wrong sign) because the OIS discount curve is aliased under two keys
`(DISCOUNT, ccy)` and `(PROJECTION, ois_index)`, and the single-key bump shifted only one role.

### Changed
- **`ir_delta`/`book_dv01` now bump by curve IDENTITY** (`CurveIdentityBump`): resolve the target curve,
  bump it ONCE, and replace every `CurveSet` entry whose value `is` it — so an aliased OIS curve moves in
  BOTH roles at once (bump-once-share). This is the documented parallel DV01.
- **`CurveBump` renamed `CurveBasisBump`** — the single-key partial, now reached via the new
  **`ir_basis_delta`** (a genuine dual-curve basis move; the per-key partials sum to `ir_delta`).
- `central_diff` is UNCHANGED and key-blind — identity resolution lives inside `CurveIdentityBump.apply`,
  never the FD core (no isinstance/type branch).

### Oracle
- OIS 5Y `ir_delta(DISCOUNT, EUR)` == the true parallel DV01 (independent reprice); the discount/projection
  basis partials sum to it (to second-order FD noise); the alias is preserved post-bump; `book_dv01` is
  correct for OIS trades (repro_N); the float leg participates (identity ≠ fixed-only basis).

Drawdown 19/793 (bug-fix slice, tick 0). All three HIGH audit findings now closed.

## [0.100.0] - 2026-08-23

**Audit Batch A — invariant-4/6 boundary hardening.** Six findings from the v0.98.0 audit
(`~/work/analysis/AUDIT_FINDINGS.md`), each ported repro → red → green: failure is a value, uniformly.

### Fixed
- **#2 [HIGH]** the shell returns **`Mapping[Currency, Money]`** (`mark`/`mark_book`/`realized`/`total`) —
  a mixed-currency book is a per-currency map, not an escaped `TypeError`; single-currency = the
  degenerate 1-entry map. `book_priceable` fails-as-value on multi-currency (base-ccy FX conversion
  deferred → reporting consumer).
- **#3a [HIGH]** `future_periods` is now applied uniformly across xccy/cash/caplet; a seasoned
  **mid-period** trade fails with a NAMED message (`current_period_failure`), not a raw L0 date error.
  *(The real fix — pricing the current period from fixings — is #3b, Batch F.)*
- **#8 [MED]** `ir_delta`/`vol_vega` on an absent key → `PricingFailure` (was `KeyError`).
- **#15 [MED]** negative-forward options → `PricingFailure` (lognormal Black undefined; normal/shifted
  deferred), not a silent zero-time-value price.
- **#16 [LOW]** `ZeroDivisionError` added to the cash + caplet + swaption catch sets.
- **#20 [LOW]** expired swaption → PV 0 (mirrors the caplet); `Surface.__post_init__` validates vols vs expiries.

### Note
`mark`/`realized`/`total` change return type `Money → Mapping[Currency, Money]` (single-ccy = 1-entry).
Slice-11/12 oracles adapted. Audit backlog mirrored into `OPEN.md`; #3b → Batch F, defer/document
#9/#10/#14 recorded with triggers.

Drawdown 19/793 (bug-fix slice, tick 0).

## [0.99.0] - 2026-08-22

**Audit #7 — ACT/ACT ICMA + BUS/252 leg pricing (self-describing Schedule).** Both strict conventions
used to RAISE when a leg priced (repro C: ICMA needs the coupon frequency, BUS/252 the calendar); the
atoms now read that context from the schedule. Red→green; the BRL/CDI book is unblocked.

### Changed
- **`Schedule` carries its `ScheduleTerms`** (3→4 fields) — self-describing, so a day count needing
  convention context reads the frequency/calendar from the schedule alone. §3d holds *by construction*:
  the context travels with the schedule, so the calibrator and engine can't price it under mismatched
  conventions. `build_schedule`/`future_periods` populate it; atoms unchanged where inert.
- **`rpv01`/`float_leg_pv` thread the context** (`_coupon_context` reads `schedule.terms`): ICMA builds
  a `CouponPeriod` per period (its consumer for **`is_stub`** — front stubs anchor at the regular
  boundary); BUS/252 passes the calendar; `forward()` gains optional `coupon_period`/`calendar`. INERT for
  ACT/360, 30/360, etc. → **non-ICMA/BUS252 legs byte-identical** (suite 239; prior 234 unchanged).

### Added
- **`Frequency.per_year()`** — coupons/year for integer month/year steps, raises for BULLET/daily/weekly/
  28-day (those take BUS/252, never ICMA). Discharges **AC-T4.15** (implemented with its fixed-leg consumer).
- **`icma_coupon_period()`** — builds the ICMA `CouponPeriod` from schedule boundaries + `is_stub` + frequency.

### Oracle
- Regular semi ICMA coupon = 0.5 exactly; BUS/252 `rpv01` == `Σ business_days/252·df`; both swaps price
  (repro C green); the **§3d identity** — the par rate from the atoms makes the engine price an ICMA swap
  to zero (calibrator == engine, no drift); a non-ICMA leg is byte-identical.

Drawdown 19/793 (capability slice — no whole module superseded, tick 0).

## [0.98.0] - 2026-08-22

**L6 stateful slice — BookedTrade + benefit table + realized P&L. CLOSES C3 and TOPIC 1.** The first
complete instrument vertical, proven end-to-end L0→L6. Realizes `Total = realized + mark` (§2) and
exercises invariant 6 (the last unexercised engine invariant). Red→green.

### Added
- **`future_periods(schedule, valuation_date)`** (L0) — the future sub-schedule (payments strictly after
  the valuation date). **The engine now excludes historical cashflows from the mark (invariant 6):**
  `price_swap`/`price_swaption` pre-filter both legs ABOVE the atoms (`rpv01`/`float_leg_pv` UNCHANGED —
  §3d preserved); `price_caplet` returns 0 for a paid optionlet. A spot trade loses no period → **slices
  1–11 byte-identical.** This closes the seasoned-trade silent misprice (past pay date → `df>1`).
- **`BookedTrade(trade, fixings)`** (L6) + **`realized`** (the benefit table: Σ past undiscounted cash, float
  via the shared `accrued_rate` atom, fixed via the coupon) + **`total`** (= realized + mark). Benefit
  dispatch is a type registry (`register_benefit`) mirroring the engine — the shell stays isinstance-free.

### Oracle
- Seasoned swap: `realized` == a hand-computed benefit table (<1e-9); the future-only `mark` prices correctly
  (closes the silent misprice); `total` == realized + mark; **spot degenerate** → `realized == 0`, `total ==
  mark` (1–11 byte-identical); realized is undiscounted; a missing historical fixing → `PricingFailure`.

### Migration — TOPIC 1 CLOSED
The 6 accumulated Topic-1 deletables were **physically parked** (one `git-mv` into
`parked/topic-01-yield-curve/`): `bootstrap`, `discount_curve`, `ncurve_solver`, `global_solver`,
`multicurve_solver`, `forward_interpolation`. **Drawdown 19/793 — now all physically parked** (13 Topic-0 +
6 Topic-1). ng is unaffected (never imports the quarry). The booking cluster (`core/trade`/`core/book`/
`core/fixings`) stays partial (serialisation/desks/limits/lifecycle + live consumers resident, tick 0).

### Deferred (named triggers)
Accrued + clean/dirty + fixings-on-snapshot (paired follow-up) · lifecycle events · booking persistence ·
daily P&L / attribution · cross-currency benefit table · caplet/swaption realized · resident booking breadth.

## [0.97.0] - 2026-08-21

**L6 opening — the imperative shell (frozen Trade/Book + marking + portfolio risk).** The LAST spine
layer: **all seven layers L0–L6 are now live.** The frozen half of "functional core, imperative shell";
the stateful half (BookedTrade + benefit table) is the next slice. Red→green; ticks 0.

### Added
- **L6 `shell/` package** (new layer, imported by nothing — `acyclic` confirms it's the top leaf).
  **`Trade(products, start_date)`** and **`Book(trades, name)`** — frozen pure data, **no `pv()`** (the
  quarry's `Trade.pv(ctx)` self-pricing is realigned into the shell).
- **`mark`/`mark_book`** — shell FUNCTIONS that sum `engine.price(product, model).pv`: the shell CALLS the
  core, adds nothing. Type-blind via the registry — one `BlackModel` (curves + surfaces) marks a MIXED
  swap+caplet book in one pass, no isinstance on a product. A failing product propagates `PricingFailure`.
- **`book_priceable`** adapts a `Book` to the L5 `Priceable` protocol, so every greek works on a whole
  portfolio; **`book_dv01`** = `ir_delta` of the book (== Σ per-product DV01 by linearity), reusing L5.

### Oracle
- Trade-of-1 == engine PV (exact); book mark == Σ trade marks (<1e-12); portfolio DV01 == Σ per-product
  `ir_delta` (<1e-12); Trade/Book frozen, marking mutates nothing; failure-as-value; **mixed book under one
  model** (single-model ≠ homogeneous).

### Deferred (named triggers)
`BookedTrade` + benefit table + realized P&L (stateful half → next L6 slice) · accrued/realized/clean-dirty
reporting · per-product model resolution / multi-market books · lifecycle events · cross-currency aggregation ·
netting/limits/desks · keyless total-parallel `book_dv01` · Trade/Book serialisation.

### Note
`book_dv01` takes an explicit `key: CurveKey` (which curve to bump) — the ratified `book_dv01(book, model)`
couldn't say which; same shape as L5 `ir_delta(p, market, key)`.

Drawdown 19/793 (partial cross of `core/trade.py`/`core/book.py` — concept crosses, serialisation/desks/
limits/netting + un-crossed desk consumers resident; tick 0).

## [0.96.0] - 2026-08-20

**C3 opening — the risk layer (L5).** Closes the C2 cluster and opens risk: generic bump-and-reprice
greeks (DV01 + vega) on a `Priceable` protocol. New layer + new protocol. Red→green; ticks 0.

### Added
- **L5 `risk/` package** (new layer). **`Priceable`** protocol (`snapshot → PV`) — risk depends DOWN on the
  engine + snapshot and **never inspects an instrument's type** (the registry dispatches). `priceable(instrument,
  model_ctor)` reprices a bumped market. **`central_diff`** is the KEY-TYPE-BLIND finite-difference core;
  **`CurveBump`/`SurfaceBump`** (a `Bump` strategy per shape) are the ONLY shape-aware part — no isinstance,
  no key-type switch in the core (§1/§3d). **`ir_delta`** (DV01) and **`vol_vega`** — the two present key kinds
  (curve, surface) that earn the generic core (rule of two). Sticky-model market delta; recalibration deferred.
  A failed reprice propagates as `PricingFailure` (invariant 4).
- **L1 immutable bump transforms** (additive, no meaning change): `CurveHandle.bumped(shift)` +
  `DiscountCurve.bumped` (`df·exp(−shift·t)`), `Surface.bumped` (`vols+shift`), `CurveSet.with_curve` — all
  return NEW frozen values (invariant 3). **L3 `black_vega`** = `F·φ(d₁)·√t` (the FD-vega oracle target).

### Oracle
- DV01: `ir_delta` (central FD) vs analytic `−Σ N·τ·(F−K)·t·DF` to **<1e-6**.
- Vega: `vol_vega` (central FD) vs `df·N·τ·black_vega` (closed form) to **<1e-6**.
- Generic-over-keys (one core, two `Bump` strategies), isinstance-free (source-structural), immutability +
  failure-as-value. `acyclic` confirms nothing at L≤4 imports L5.

### Deferred (named triggers)
Recalibration / par delta · key-rate / bucketed DV01 · analytic/AAD greeks · gamma / 2nd-order · scalar
(FX-spot) delta (3rd key kind, `ScalarBump`) · greek aggregate (`Greeks`) · XVA/RWA · L6 Trade/Book/portfolio.

Drawdown 19/793 (partial crosses of the quarry risk suite — parallel greek mechanism delivered, gamma/
key-rate/AAD/Jacobian resident; tick 0).

## [0.95.0] - 2026-08-20

**C2 slice 3 — caplet-vol stripping (the first solved surface).** The first calibrated volatility object,
and `SolveConfig`'s rule-of-two second consumer (the first beyond curves). Structurally the curve bootstrap
in a new family; the (A) fork exercised on a non-curve target. Red→green; ticks 0.

### Changed
- **`Surface` grows to a term structure** over expiry (`vols`, `expiries`, `interpolation`) — `at(expiry,
  strike)` interpolates σ² linearly over expiry (exact at pillars, no valuation origin needed) and roots;
  RAISE outside the pillar range; `strike` ignored until the smile axis lands. `Surface.flat(v)` is the
  degenerate 1-pillar case (slices 1–2 migrated, stayed green — refactor under green).

### Added
- **`CapQuote(maturity, strike, flat_vol)`** (L1) — a flat quoted cap vol, the strip's pillar.
- **`VolCalibrationSpec` + `strip_caplet_vols`** (L3) — a per-family calibration entry (a `Surface` is a
  different target than a `CurveSet`): a sequential 1-D Brent strip that composes `black()`/`forward`/`df`
  (the SAME atoms the L4 caplet engine composes — never a private formula, never the L4 engine, L3 ⊥ L4),
  reusing `SolveConfig` verbatim. An infeasible marginal returns `CalibrationFailure` (invariant 4).

### Oracle
- **Flat round-trip** (closed-form anchor): a flat cap strips to a flat caplet-vol curve to **<1e-12**.
- **§3d backstop**: a caplet priced through the L4 engine off the stripped surface matches an independent
  Black to <1e-12 (strip and engine share the atoms). Reprice-to-quote <1e-9. Infeasible → `CalibrationFailure`.

### Deferred (named triggers)
Strike-smile / 2nd surface axis · swaption-cube fitting · SABR/parametric vols (B4) · SIMULTANEOUS vol solve ·
caplet-stripping convention variants · vol-surface serialisation · total-variance (σ²·t) term interpolation
(first off-pillar consumer) · denser cap-caplet schedule via `frequency`.

Drawdown 19/793 (partial crosses of `capfloor.py` strip path + the IR portion of `vol_calibration.py`, tick 0).

## [0.94.0] - 2026-08-18

**C2 slice 2 — Black European swaption (annuity numeraire).** The clean §3d payoff: numeraire = the
annuity `rpv01`, underlying = the forward swap rate `S = float_leg_pv/rpv01` — the SAME shared atoms the
swap calibrator/engine compose. `black()` reused verbatim; only the vol's meaning changes. Second capability
on one model — the capability-model rule-of-two now has its multi-capability case. Red→green; ticks 0.

### Added
- **`SwaptionVol`** capability (L3) — a SIBLING of `BlackVol` (not a reuse) with its Q3′(a) contract: the
  lognormal vol of the forward SWAP RATE under the **annuity (swap) measure** (numeraire `rpv01`), distinct
  from `BlackVol`'s index-forward/T-forward measure. `BlackModel` now satisfies `CalibratedModel` + `BlackVol`
  + `SwaptionVol` — **`BlackVol`/`BlackModel` meaning unchanged** (additive, doc 22 Q1 opt-in capabilities).
- **`SwaptionSurfaceKey(index, swap_tenor)`** (L1) — keyed by index AND swap tenor, never colliding with the
  optionlet `SurfaceKey(index)`. Reuses the flat-minimal `Surface`; `MarketSnapshot.surfaces` key type widened
  to `SurfaceKey | SwaptionSurfaceKey` (a union over one shape, not a new field).
- **`Swaption(swap, expiry, option_type)`** (L2) — reuses `VanillaSwap` (strike = its fixed rate; payer=CALL,
  receiver=PUT). **`price_swaption`** (L4) composes the shared `rpv01`/`float_leg_pv` atoms + `black()`,
  validates `SwaptionVol` structurally, and **never touches the calibrator's private `_par_rate`**.

### Oracle
- Reprices to `N·rpv01·black(S,K,vol,t)` vs an independent inline Black to **<1e-12**; payer−receiver parity
  `N·rpv01·(S−K)`; vol→0 intrinsic; and the **§3d identity** — swaption(payer−receiver) equals the swap
  engine's PV of the same swap (<1e-9), proving engine and calibrator share the `S`/annuity composition.

### Deferred (named triggers)
Cash-settled/IRR swaptions · swaption vol cube + 2D smile · vol calibration/stripping · Bermudan ((A)-fork) ·
SABR/HW swaption vols (B4) · midcurve swaptions · swaption greeks (C3).

Drawdown 19/793 (partial cross of `options/swaption.py`, tick 0).

## [0.93.0] - 2026-08-14

**C2 slice 1 — Black-76 European caplet (opens the models & calibration cluster).** The first dynamics
model, the first capability beyond `Discounting`, the first `surfaces` snapshot shape — the first real
rule-of-two test of doc 22's capability model. Red→green; ticks 0 quarry modules (partial crosses).

### Changed
- **Engine rebased onto the `CalibratedModel` protocol** (refactor under green). `CalibratedModel` + `BlackVol`
  were designed in doc 22 but code-deferred to the second model; they land now. The registry and every pricer
  depend on the capability (`model.market`), not concrete `DiscountingModel` — no `isinstance`, no change to
  any ratified type's meaning. The slice-1..6c linear suite stayed green through the rebase.
- **`MarketSnapshot` gains the `surfaces` shape** (`SurfaceKey`/`Surface`, keyed by index — doc 19 §2, first
  vol consumer). Flat-minimal surface; grid + 2D smile interpolation deferred.

### Added
- **`BlackModel`** (L3) — second `CalibratedModel`, built-not-solved (reads vol from `market.surfaces`); adds
  the **`BlackVol`** capability with its Q3′(a) semantic contract (lognormal, T-forward measure, annualized).
- **`black()`** (L3) — undiscounted Black-76 closed form (df kept out, ≤5 args; at L3 not L0 per the
  `black.py` precedent; uses the `norm_cdf` foundation adapter).
- **`Caplet`** + **`OptionType`** (L2) and **`price_caplet`** (L4) — `PV = df(pay)·N·τ·black(F,K,vol,t,CALL)`;
  the model's `BlackVol` capability is validated structurally (runtime-checkable protocol), never `isinstance`
  on a concrete type.

### Oracle
- Caplet reprices to an **independent** Black-76 evaluation (inline `erf`, distinct from the scipy adapter) to
  **<1e-12**; put-call parity `caplet − floorlet = df·N·τ·(F−K)` to <1e-12; vol→0 = discounted intrinsic.

### Deferred (named triggers)
Bachelier/normal vol (2nd vol consumer) · vol calibration / surface stripping · swaption + annuity numeraire
(B5) · 2D smile interpolation · engine numerics-config (invariant 5 — name it distinctly from `SolveConfig`) ·
Bermudan ((A)-fork trigger) · SABR/HW (B4). Doc fix: rename doc 22's `SolverConfig` → `SolveConfig`.

Drawdown 19/793 (partial crosses of `black76.py` / `capfloor.py`, tick 0).

## [0.92.2] - 2026-08-12

**Slice 6d — audit response.** Fixes all 8 findings from a third-party audit of v0.92.0
(`analysis/AUDIT_FINDINGS.md`). The numerical core was verified clean; exposure was at input/range
boundaries (oracles had tested positive-rate / in-range / well-formed inputs only). Each fix is
red→green (the oracle that exposes the finding, then the fix). Ticks 0 quarry modules.

### Fixed — correctness (crash/hang/wrong)
- **#1 [HIGH] Negative-rate sequential calibration.** `_bootstrap`/`_bootstrap_xccy` used a fixed
  `[1e-6, 1.0]` bracket that baked in positive rates (a negative-rate pillar has DF > 1) and let
  `brentq`'s "different signs" `ValueError` escape. New `_solve_pillar_df` expands the upper bound
  until the residual changes sign (capped); a non-bracketable/failed solve returns
  **`CalibrationFailure`**, never raises — **invariant 4 restored** across the sequential path.
- **#2 [MED] Hagan–West extrapolation.** `MonotoneConvex.value`/`integral` now guard their domain
  `[knots[0], knots[-1]]`; the curve's HAGAN_WEST `df()` **raises** past the last pillar, consistent
  with the log-linear RAISE policy (was a silent flat DF).
- **#3 [MED] ICMA frequency guard.** `_act_act_icma` now requires `1 ≤ frequency ≤ 12 and 12 % f == 0`
  — closes a `frequency > 12` **infinite loop** and a non-divisor silently-wrong DCF.
- **#4 [MED] RegularPeriod anchors.** `_unadjusted` validates `first_regular < last_regular` up front —
  coincident/reversed anchors raise a clear schedule error instead of a silent zero-length period.

### Fixed — robustness (mispriced/degraded quietly)
- **#5 [LOW]** RegularPeriod's short final period now reports `is_stub=True` (non-dividing tenor).
- **#6 [LOW]** `WeekendSchedule` sorts its transitions in `__post_init__` — `on(year)` is order-independent.
- **#7 [LOW]** Convergence is graded at `spec.solve.tolerance`, not a literal `1e-10`.
- **#8 [LOW/perf]** The Hagan–West reconstruction is a `cached_property` — a full-curve reval is O(n)
  not O(n²); the frozen curve makes the cache honest (`cached == uncached`).

### Tests
- Boundary oracles added at L0/L1/L3 (`tests_ng/L*/test_audit_response_l*.py`). Full suite green (207).

## [0.92.1] - 2026-08-09

**Docs/tracker reconciliation — honest baseline before the audit-fix slice.** No `src` behaviour change.

### Migration tracker
- **`multicurve_solver.py` full-cross ruled (Cowork):** the slice-4 spot-check is resolved — §4 grep found
  0 production/dynamic consumers of `multicurve_newton`/`validate_curve`/`curve_analytical_jacobian` (only
  quarry-internal tests, which retire with the quarry). 3 ticks stand. `validate_curve`/`curve_analytical_jacobian`
  forward-linked → C3 risk.
- **`forward_interpolation.py` retire-read done → full cross (+1 → 19/793):** `MONOTONE_CONVEX` → ng
  `HAGAN_WEST`, `PIECEWISE_CONSTANT` → ng `LOG_LINEAR`, `PIECEWISE_LINEAR` → shed (`deferred→` future
  interp-method consumer); architecture superseded by ng's DF-interp + `forward()` atom. **Drawdown now
  19/793** (13 Topic-0 parked + 6 Topic-1 crossed).

### Design artifacts
- 12 design docs flipped **Draft → Ratified** (redesign/01,02,05,06,07,08,09,10,11,12,13,20); stale
  "(pending ratification)" cleared at 05.

### Ledger (`OPEN.md`, §5)
- Added the Topic-1/C1 carried-debt section (5 non-balance entries, each with a named re-open trigger):
  `forward()` subtract-first hardening; collateral→L6 relocation; simultaneous xccy solve; FX triangulation;
  analytic/AAD Jacobian.
- **AC-3.6b** updated: the FX pair-conventions registry **landed** at v0.90.0 (slice 6a); only the
  asymmetric-ACI intermediate-day settlement rule remains deferred.

### Pointers
- C1 checkpoint next-step: an **audit-fix slice lands before C2 opens**. Fixed 768→793 (doc 11) and the
  moved `redesign/archive/16_topic0_foundation.md` link (topic-00 MANIFEST).

## [0.92.0] - 2026-08-08

**Topic 1, slice 6c (C1 CLOSE) — xccy basis curve via the unified calibration front.** Two steps:
a refactor-under-green to a multi-currency `CalibrationSpec`, then the xccy basis curve on top.
Closes cluster C1 (single-curve → dual-curve → cash → global solve → Hagan–West → CSA/xccy).

### Changed
- **`CalibrationSpec` reshaped to the unified multi-currency front** (§8 refactor-under-green):
  `(valuation_date, curves: tuple[CurrencyCurves], solve, xccy, fx)` — 5 fields. `single_currency()`
  classmethod + `.currency`/`.discount`/`.projection` accessors keep slices 1–5 unchanged (1-tuple =
  degenerate). `calibrate()` loops currencies into ONE `CurveSet` on ONE model. No new behaviour; the
  full existing oracle set stayed green through the new shape.

### Added
- **`XccyBasisSwap`** (L2) — constant-notional cross-currency basis swap: domestic OIS-flat leg vs a
  foreign leg + basis, notional exchanged at spot, under a `collateral` CSA.
- **`XccyBasisQuote`/`XccyBuild`** and **`XccyBasisInstrument`** — the foreign-collateral (xccy-basis)
  curve is bootstrapped as a SEQUENTIAL post-step (domestic OIS → foreign OIS → foreign-in-collateral
  last), keyed `(DISCOUNT, foreign, collateral)`. The instrument and the new **`price_xccy`** engine
  pricer compose the SAME `float_leg_pv`/`rpv01` atoms (§3d).
- `test_collateral`'s foreign case now uses a **real calibration**, not a manual curve injection.

### Oracle
- **Reprice-to-zero:** every calibrating xccy basis swap prices to ~0 through the L4 engine (zero and
  10bp basis).
- **CIP closed-form anchor:** at zero basis the curve reproduces `df_foreign` (foreign OIS), so the FX
  forward `F = S·df_foreign^coll/df_domestic` equals the textbook `S·df_foreign/df_domestic` to **1e-10**;
  a real basis moves the curve below CIP.

### Note (design finding)
The constant-notional both-OIS-flat xccy basis swap has the **FX spot and USD discount cancel out of the
reprice-to-zero condition** (the domestic leg telescopes to par; `N_foreign = N_domestic/S`). They enter
only the CIP FX-forward oracle, not the bootstrap — the curve is pinned by `df_foreign` + the basis alone.

### Deferred (named triggers)
Simultaneous/joint xccy solve (xccy pillars in the global state vector) → 2nd xccy consumer; consequently
the sequential==simultaneous degeneracy does **not** cover xccy. Triangulation/3rd ccy, FX vol/options,
tenor-basis, MtM-notional resets, NDFs, collateral optionality → their asset topics. Collateral/CSA
relocates from the L2 product to the L6 trade layer when L6 lands.

Drawdown unchanged (18/793): the quarry xccy/CSA/FX suite is full FX/XVA breadth, not superseded by a
minimal foreign-collateral curve — it retires with the FX/XVA topics (0 ticks, ratified).

## [0.91.0] - 2026-08-08

**Topic 1, slice 6b (C1 close, 2/3) — CSA collateral-keyed discounting.** Activates the
`discount(ccy, collateral)` hook stubbed since slice 2. Red→green.

### Changed
- **`CurveKey` grows `collateral: Currency | None`** (3 fields) — the discount curve is now keyed by
  currency AND CSA collateral. Existing keys default `collateral=None`, so slices 1–5 are unchanged.
- **`CurveSet.discount(ccy, collateral)`** normalizes own-currency collateral (`None` or `== ccy`) to the
  domestic OIS curve; a foreign collateral selects its keyed curve (the xccy curve lands in 6c).
- **`VanillaSwap.collateral: Currency | None`** (5 fields). The engine resolves `discount(ccy, collateral)`
  through `model.market` (A1) and records **`PricingResult.basis`** (`None` for own-currency, the
  collateral currency otherwise). *(Relocation trigger recorded: collateral/CSA moves to the L6 trade
  layer when L6 lands.)*

### Oracle
- **Degeneracy:** a EUR swap collateralized in EUR prices identically to `collateral=None` (domestic OIS)
  to 1e-12; `basis` is `None` for both. All slices 1–5 reprice unchanged through the new key path.
- A foreign-collateral (USD) swap resolves its keyed curve, records `basis == USD`, and differs from the
  domestic price.

Drawdown unchanged (18/793).

## [0.90.0] - 2026-08-05

**Topic 1, slice 6a (C1 close, 1/3) — FX spot in the snapshot.** First step of CSA/xccy: the directional
FX spot. Red→green.

### Added
- **`MarketSnapshot.scalars`** — the first non-curve shape (doc 19 closed-shapes × open-keys), keyed by
  `ScalarKey(pair)`; FX spots stored in the declared canonical quote order. Existing snapshots default
  `scalars` empty (slices 1–5 unaffected); `MarketSnapshot` stays 3 fields.
- **`MarketSnapshot.fx_rate(base, quote)`** — resolves the declared canonical pair, reads the spot,
  inverts on the reverse direction; **raises on an undeclared cross** — never a bare pair-scalar (doc 19
  §2.1, fail loud).
- **`foundation.register_fx_pair` / `fx_pair`** — the FX pair-conventions registry (EUR/USD declared, EUR
  base). Completes **AC-3.6b's registry half**; the asymmetric-ACI FX-date rule stays deferred.

### Oracle
- `fx_rate(A,B)·fx_rate(B,A) == 1` to 1e-15; canonical direction returns the stored value, the reverse
  its reciprocal; an undeclared cross (GBP/JPY) raises; duplicate / same-currency registration raise.

Drawdown unchanged (18/793) — FX-conventions plumbing, no quarry module crossed (the FX suite is
reassigned to the FX/XVA topic).

## [0.89.0] - 2026-08-05

**Topic 1, slice 5 — Hagan–West monotone-convex forward interpolation.** Owns what scipy lacks
(§7bb); the first EXTERNAL-oracle slice in the topic (the paper's equations, since it publishes the
example only as figures). Red→green throughout.

### Added
- **`foundation/hagan_west.py` (L0, finance-free)** — the monotone-convex reconstruction from
  interval averages (Hagan & West AMF 2006): knot estimates eq 30–32, four-region construction eq
  47/49–56, optional positivity clamp eq 60–62. Parameters are `knots` + `averages` + a `positive`
  flag — **no forwards/DFs/rates/curves** (the falsification gate held: pure math). It is a distinct
  primitive, not a mode of the point-based `interpolate()`. `monotone_convex(...)` → `MonotoneConvex`
  with `value(x)` and `integral(x)`.
- **`Interpolation.HAGAN_WEST`** — a MODE TAG; the point-based `interpolate()` raises
  `NotImplementedError` on it (it reconstructs from interval integrals, not point values).

### Changed
- **`DiscountCurve.df` dispatches `HAGAN_WEST`** to the forward path: discrete forwards from the
  pillar DFs → the L0 primitive → `df(t) = exp(−∫₀ᵗ f)`, reproducing the pillar DFs exactly. HW is
  **non-local**, so its home is the SIMULTANEOUS solve (slice 4); sequential-HW is deferred (the
  paper's terminal-interval convention) with a named trigger.

### Oracle (equation-anchored — the paper has no value table)
- **eq-33 interval-average reproduction to 1e-14** (the method's defining invariant).
- **Per-region pointwise checks (regions i–iv)** vs values hand-derived from eq 47/49–56 (independent
  of the code) to 1e-12 — catches a wrong-region transcription; boundary conditions `g(0)=g₀,g(1)=g₁`.
- Positivity clamps knots ≥ 0 and keeps interpolated forwards ≥ 0; eq-33 still holds under it.
- **Reprice-to-par** through the L4 engine on HW curves (via the simultaneous solve), worst |PV|
  1.4e-16; **degeneracy** HW == log-linear on constant forwards (df diff 0.0).

### Drawdown — premise correction, ticks 0 (partial-cross candidate flagged)
The tasking said HW was "missing from both trees" — **incorrect**: the quarry has it in
`core/forward_interpolation.py::monotone_convex_forwards` and `curves/curve_advanced.py::
smooth_forward_curve`. ng's HW supersedes the monotone-convex forward *construction*, but
`forward_interpolation.py` is a **multi-method** module (a `ForwardInterpolationMethod` enum), so this
is at most a **partial** cross — not ticked without a full retire-read. Recorded as a candidate for the
next align/Cowork spot-check; drawdown stays 18/793.

### Drawdown — retire read (docs/tracker only, no code)
The slice-3 checkpoint's named next action is done: the end-to-end retire read of `curves/bootstrap.py`
(713 LOC) + `core/discount_curve.py` (300 LOC). **Both cross → deletable 13 → 15 / 793 (first Topic-1
tick).** Evidence: convention/calendar is *imported* from already-parked Topic-0 modules (not resident);
the only `bootstrap.py`-resident deferred bits are futures convexity (`:151-158`) and turn-of-year
(`:161-162`); `discount_curve.py` residents are curve analytics (`zero_rate`/`bumped`/`roll_down`/… ) —
`forward_rate` already crossed by ng's `forward()` atom. 0 ng consumers of any deferred capability (bare-
name grep across src + tests). Forward-links filed on destination rows (models ← convexity, seasonality
← turn-of-year, C3-risk ← curve analytics, persistence ← curve serialisation); per-leg conventions
recorded as an ng-side note (convention code already parked — nothing to migrate). Tracker
(`quarry_reconciliation.md`) + Topic-1 MANIFEST carry the full record. Deletable = *superseded*; physical
park at Topic-1 close.

### Drawdown — slice-4 reconciliation (docs/tracker only, no code)
Closes the slice-4 (v0.88.0) deferred tick: the three quarry global solvers — `curves/ncurve_solver.py`,
`curves/global_solver.py`, `curves/multicurve_solver.py` — cross, superseded by ng's simultaneous solve.
**Deletable 15 → 18 / 793** (Topic-1: 2 → 5). Hand-rolled damped Newton + FD Jacobian §7bb-shed (scipy);
analytic Jacobian → `deferred→C3/AAD`; N-curve > 2 → `deferred→3rd-projection-curve`; 0 ng consumers.
`multicurve_solver` **flagged for Cowork spot-check** (read found 3 crossings, task expected 2). Evidence:
`CP_slice4_global_solve.md`; tracker + MANIFEST updated.

## [0.88.0] - 2026-08-03

**Topic 1, slice 4 — the simultaneous (global) calibration orchestration + par→zero Jacobian.** The
second orchestration (doc 22 Q4): one `CalibrationSpec`, one residual definition, two orchestrations —
the existing sequential bootstrap and a new global N-D solve of the whole `CurveSet` at once, proven
equal on the degenerate case. Red→green throughout.

### Added
- **`CalibrationMethod` {SEQUENTIAL, SIMULTANEOUS}** — earned now (the second orchestration, rule of two).
- **`SolveConfig`** — bundles `method` + solver knobs (tolerance, max_iterations) so `CalibrationSpec`
  stays **5 fields** (§3b); the first tuned-knob consumer earns the numerics config (invariant 5).
- **`Jacobian`** value type — `∂residualᵢ/∂dfⱼ` + pillar/instrument labels; the SIMULTANEOUS solve
  populates `CalibrationResult.jacobian`, the SEQUENTIAL path leaves it `None` (resolving doc 22 Q4's
  deferred branch — the sequential post-hoc Jacobian arrives with its C3-risk consumer).
- **`foundation/solvers.root_nd`** — the N-D root-find (scipy Levenberg-Marquardt) returning
  `(solution, jacobian, converged)`; `least_squares` now delegates to it. §7bb: scipy wrapped behind
  the foundation adapter, no hand-rolled damped Newton, never called from `calibrate`.
- **`CalibrationFailure`** — non-convergence as a value (invariant 4); `calibrate` returns it instead
  of a silent bad curve.
- **`curve_set_residuals(spec, curves)`** — the residual vector both orchestrations drive to zero.

### Changed
- **`calibrate(spec)` forks on `spec.solve.method`** — sequential (unchanged) or the global solve.
  Both compose the SAME `CalibrationInstrument` residuals (§3d); only the orchestration + Jacobian
  provenance differ. The global path assembles one flat state vector of all pillar DFs across both
  curves and solves them jointly (seed: flat 3% DFs, the `ncurve_solver` default).

### Oracle
- **sequential == simultaneous degenerate** (doc 18 §8): pillar DFs match to **~1e-15** (discount
  5.6e-16, projection 1.8e-15).
- Every calibrating instrument reprices to zero NPV through the L4 engine under the globally-solved
  curves (worst |PV| ~3.5e-16).
- **Jacobian validated vs finite-difference** (tangent prediction) to < 1e-6.
- Non-convergence (`max_iterations=1`) → `CalibrationFailure`; global reprice byte-identical.

### Drawdown
Retire-read of the quarry global solvers (see the slice checkpoint): `curves/ncurve_solver.py`,
`curves/global_solver.py`, `curves/multicurve_solver.py` are all superseded by ng's simultaneous solve
(hand-rolled damped Newton + FD Jacobian are §7bb-shed → scipy; analytic Jacobian → `deferred→C3/AAD`;
N-curve > 2 → `deferred→3rd-curve`; 0 ng consumers of any shed bit). **Tick pending #119 merge** (the
bootstrap/discount retire tick is not yet on main — the tracker count reconciles once it lands).

## [0.87.0] - 2026-07-31

**Topic 1, slice 3 — cash instruments: deposits + FRAs + IMM futures on both curves.** Completes the
"cash front" of the dual-curve build and lands two ratified dispatch abstractions, machinery-first as a
green-guarded refactor (Step A) then the instruments (Step B). Red→green throughout.

### Added (Step A — machinery, pure refactor)
- **Engine registry inside L4** (`engine/registry.py`) — structural product→pricer dispatch, no
  `isinstance` (CLAUDE.md §1). The `VanillaSwap` pricer moved behind it unchanged; `price` is the
  registry `dispatch`.
- **`CalibrationInstrument` protocol (L3)** — `residual(discount, projection)`, 0 at solution;
  `SwapInstrument` wraps the existing `_par_rate`. `_bootstrap` now Brent-solves each pillar via the
  instrument's residual. `calibrate` still imports no L4.

### Added (Step B — instruments)
- **L1 quotes** (`market/quotes.py`): `DepositQuote` · `FRAQuote` (spot-anchored when `start=None`) ·
  `FutureQuote` (price; forward = `1 − price`) · `ParSwapQuote` (moved from L3).
- **L2 products** (`products/cash.py`): `Deposit` · `FRA` · `Future` (IMM-dated).
- **`deposit_df` atom** (`1/(1+r·τ)`) composed by BOTH the L3 `DepositInstrument` and the L4 deposit
  pricer (§3d); FRA/Future compose the existing `forward()`. Engine pricers registered per type.
- **Heterogeneous bootstrap**: `CurveBuild.quotes` is now the deposit/FRA/future/swap union; discount
  (ESTR) = OIS deposits + swaps, projection (EURIBOR_3M) = spot-anchored FRAs + IMM futures + par
  swaps, chained from spot (an unpinned `df(start)` surfaces as `PricingFailure`).

### Oracle
- Every calibrating instrument reprices to **zero NPV through the L4 engine**: discount curve worst
  |PV| = 6.7e-16; projection curve worst |PV| = 2.0e-15 (15 instruments, converged).
- **Future reproduces `1 − price` at its IMM segment** (worst |Δ| = 5.4e-16) — the forward
  approximation is *applied* correctly (doc 18 §2), not a claim the futures price is right.
- Regression: slice-1/2 par swaps still price to zero through the registry-dispatched engine.

### Deferred (named triggers)
Futures **convexity** (`forward = futures_rate − convexity(a,σ,t)`, models topic) · Hagan–West ·
global/simultaneous solve + Jacobian · basis/xccy · full G10 conventions.

### Drawdown
Ticks 0 (13/793). §4 consumer analysis (align commit): the "full G10 conventions" gate has 0 ng
consumers (`deferred→G10`), and `discount_curve.py`'s `zero_rate`/`bump`/`roll_down` are consumed only
by uncrossed quarry modules (`deferred→risk/construction`) — no needed-now blocker, but a tick requires
the formal end-to-end retire read of `bootstrap.py`/`discount_curve.py`, named as the immediate next
step at this slice's checkpoint.

### Docs — factual-counter correction (denominator pinned)
The drawdown denominator had two conventions in flight — `/768` (CLAUDE.md §4/§6 + slices 1–2) vs
`/793` (the live tracker). Verified by direct count: **793 = every `.py` in the original quarry**
(`python/pricebook/` remaining, 780, + `parked/`, 13); `768 = 793 − 25 __init__.py` markers — the same
universe, a different convention, not an error. **Pinned to 793**, and `redesign/handoffs/
quarry_reconciliation.md` is now the single source (its convention stated there). CLAUDE.md §4/§6 no
longer hardcode a literal — they point to the tracker, so the count can't re-drift. The tracker's frozen
`PRE-REPLAN RECORD` (`7 / 768`) is left untouched as history. No ruling reopened.

## [0.86.0] - 2026-07-30

**Topic 1, slice 2 — dual-curve: a EURIBOR swap prices to ZERO off ESTR discounting.** The first
genuine second curve: a swap projects off EURIBOR_3M and discounts off ESTR. Proves the multicurve
machinery and that single-curve is its degenerate case. Drawdown unchanged (0 quarry modules ticked;
the align commit records the named C1 slices where `bootstrap.py`/`discount_curve.py` actually cross).
Red→green throughout.

### Added
- **`market/curve_set.py` (L1)** — `CurveSet` with typed accessors `discount(currency, collateral=None)`
  and `projection(index)` over one `CurveKey`-keyed store (doc 19 §2-§3, closed shapes × open keys).
  Ratified signature lands now; `collateral` non-None raises (CSA/xccy deferred); `survival`/`inflation`
  and a multi-projection map arrive with their consumers.
- **`forward()` projection atom (L1, §3d)** — the single definition of the projection forward rate
  `(df(start)/df(end) − 1)/τ`, which `float_leg_pv` now **composes** (it never inlines the df ratio).

### Changed
- **`float_leg_pv` generalised in place** to dual-curve `Σ df_disc·τ·forward(proj, ·)` — the slice-1
  telescoping `df(start₀) − df(endₙ)` is now its degenerate case (`projection is discount`), not a
  separate code path. `rpv01` unchanged (discount only).
- **`FloatLeg` gained `index: RateIndex`** (→3 fields); it selects the projection curve.
- **`MarketSnapshot.discount_curve` → `curves: CurveSet`.**
- **`calibrate(spec)`** — one entry, still sequential; `CalibrationSpec` now a curve-**set** spec
  (`discount` + `projection` builds) bootstrapped in dependency order (discount self-discounting →
  projection discounted on it). `SingleCurveSpec` replaced by `CurveBuild`; `single_curve_swap` →
  `par_swap`. No `method`/`numerics`/Jacobian (rule of two).

### Oracle
- **Dual-curve EURIBOR par swap → zero NPV: worst |PV| = 1.9e-15** (unit notional).
- **OIS degeneracy (slice-1 par swap through the generalised path): worst |PV| = 6.7e-16** — slice 1
  survives.
- **Degeneracy Δ (general float leg vs telescoping identity): 2.8e-17, rel 2.0e-16** (tight tolerance,
  not bit-identity — the df ratio is not bit-exact).
- DV01 analytic vs finite-difference to 1e-6; repricing byte-identical; beyond-curve → `PricingFailure`.

## [0.85.0] - 2026-07-29

**Topic 1, slice 1 — the first pricing vertical: a par swap prices to ZERO NPV, L0→L4.** First
consumer of F1 (redesign/19) and F2 (redesign/22 rev 3), proving both foundations by pricing a real
swap. Drawdown is unchanged (0 quarry modules ticked deletable yet — parking is one event at Topic-1
close; this slice builds the ng counterparts the tick will later require). Red→green throughout.

### Added
- **`TimeMeasure` (L0)** — the one sanctioned `date → year-fraction` map (anchor + day count, ruling
  A1); nothing re-derives it.
- **`market/` (L1)** — `DiscountCurve` (log-linear discount factors, exact `exp(-r·t)` on a flat
  curve) behind the `CurveHandle` capability; `MarketSnapshot` (valuation date + discount curve,
  frozen, A1); and the **shared `rpv01` / `float_leg_pv` building-block atoms (CLAUDE.md §3d)** the
  calibrator and the engine both compose — one annuity definition, no drift.
- **`products/swap.py` (L2)** — `VanillaSwap` = `FixedLeg` + `FloatLeg`, pure data (≤5 fields each).
- **`models/discounting_model.py` (L3)** — `DiscountingModel`, the degenerate model built (not solved)
  from a curve, carrying its `MarketSnapshot` (A1).
- **`calibration/calibrate.py` (L3)** — `calibrate(spec) → (model, result)`, the sequential
  single-curve bootstrap; the model is the output, the residual is formed through the L1 building
  blocks (never L4, doc 22 Q2). `CalibrationSpec`/`CalibrationResult`/`ParSwapQuote`/`SingleCurveSpec`.
- **`engine/linear.py` (L4)** — `price(swap, model)`, stateless, reaching the market only through
  `model.market` (A1); a cashflow beyond the curve returns a `PricingFailure` (failure is a value).

### Oracle
- **Par swap reprices to zero NPV through the L4 engine: worst |PV| = 5.6e-16** (unit notional; doc 18
  C2 / doc 22 §Q2 backstop). Bootstrap converged, max|residual| = 5.8e-16.
- Flat-curve `df(t) = exp(-r·t)` to 1e-12 (the single-cashflow discounting anchor).
- DV01 analytic (−N·annuity) vs central finite-difference: |diff| = 1.7e-12 (< 1e-6).
- Repricing byte-identical (statelessness).

### Docs
- Ratified F1 (redesign/19 rev 3), F2 (redesign/22 rev 3), **CLAUDE.md §3d — Building-block
  discipline**; 8 superseded design docs moved to `redesign/archive/`.

## [0.84.0] - 2026-07-20

Standing rule (Bernardo): **no deferred item before market-data (F1) unless a downstream topic genuinely
owns and will shape it — "waits on an event" is not a topic.** Applied to the `AC-*` ledger: **22 → 15**
deferrals. Red→green throughout.

### Fixed
- **AC-T4.7 — `is_holiday` year−1 spill.** A December holiday observed *forward* into January (e.g. 31 Dec
  Sunday → 1 Jan) was missed; `is_holiday` now checks `year−1` as well as `year`/`year+1`.
- **AC-T4.8 — `observe()` parameterised off the weekend rule.** Was hardcoded Sat/Sun, so a FRI_SAT
  market under a mondayising regime left a Friday holiday unshifted; substitution now derives from the
  calendar's own weekend days (no change for SAT_SUN calendars).
- **AC-T4.9 — `NEAREST` tie-break RULED: roll forward** (QuantLib / common market practice), documented
  in the convention and tested.
- **AC-T4.11 — `growth_factor` / `convert_rate` reject a ≥100% loss.** A rate below −100% gave a bare
  `math domain error` (or a silent complex on a periodic basis); now raises naming the rate, basis and `t`.

### Added
- **`WeekendSchedule` (AC-T4.17)** — a frozen `((since_year, Weekend), …)` transition list a `Calendar`
  may carry in place of a single `Weekend`, so a weekend-rule change (Saudi 2013; a future ILS change) is
  *expressible*. Shape only — no market's future rule is guessed, and `Calendar` stays ≤5 fields (the
  `weekend` field's type widens, no field added).

### Changed
- **Ledger tightening.** Closed AC-T4.7/8/9/11/17 (above). **AC-3.6b** (FX-spot completion) **promoted out
  of the ledger into F1's scope** (`redesign/README.md`) — its trigger *is* F1, so it is scoped work, not
  a deferral. **AC-T4.18** (month-arith triplication) recorded as a **considered exception, not a
  deferral** (rule of three; consolidating now adds indirection with no present consumer). Ledger count
  **22 → 15**; `AC-C1` (half-day concept) stays deferred (its trigger is a real shaping consumer).

## [0.83.0] - 2026-07-20

Post-closure seam residue (`closed_POST_CLOSURE{,_FINDINGS}.md`): the gaps *between* findings each
marked FIXED — which the disposition census structurally cannot see. Nothing reopened a closed
disposition. Red→green throughout.

### Fixed
- **B1 — `accrued_rate` lockout underflow (silent wrongness).** A `lockout >= len(window)` drove
  `frozen` negative, and Python negative-indexing then silently froze the rate series to *early*
  dates (reachable from a short stub with a standard lockout). Now raises, naming the window. Test
  `test_b1_lockout_longer_than_window_raises`.
- **B2 — `PricingResult.clean` currency guard.** `clean` subtracted raw amounts, so a cross-currency
  `accrued` produced a silently wrong `clean`. Now `return self.pv - self.accrued`, delegating to
  `Money.__sub__`'s existing guard (a fix that deletes code). Test
  `test_b2_clean_rejects_cross_currency_accrued`.
- **A3 — `JointCalendar` by-name round trip.** A composite `"A+B"` identity could not rehydrate
  (`get_calendar("A+B")` raised), so the first serialized XCCY trade could not round-trip — a seam
  between audit 3.2 and 3.4, both FIXED. Added `JointCalendar.to_dict`; `get_calendar` splits on
  `"+"` into a `JointCalendar` (its return type widens to `CalendarProtocol`). Test
  `test_a3_jointcalendar_round_trips_by_name`.

### Ruled (recorded, code lands with first consumer)
- **A1 — `TimeMeasure(anchor, day_count)` is the only sanctioned `date→t` map** (`redesign/20`
  Part A addendum); build as an L0 module in Topic 1's first slice. Ledger `AC-T4.5` promoted to
  "before Topic 1".
- **A2 — `Frequency.per_year()` raises for non-integer tenors** (28D/daily/bullet); BUS-period
  products (TIIE/CDI) do not enter ICMA contexts. Ledger `AC-T4.15`.
- **B3 — `fx_spot_date` keeps joint intermediate-day counting.** The asymmetric ACI rule (a USD
  holiday on an intermediate day does not pause a USD pair's count) is **not** implemented — no
  citable source with a verifiable worked example, and the green-oracle gate forbids coding an
  unverifiable convention. Scope pinned in `OPEN.md` **AC-3.6b** + the `fx_spot_date` docstring.

### Removed
- **POST_CLOSURE C residue (~41 lines, most predating the closure).** Deleted the unread half-day
  machinery — `DayType`, `Calendar.day_type`, `HolidaySet.half_days`, `_half_days_of`,
  `day_after_thanksgiving` + the 3 US half-day rules + their exports and S5 test (`CalendarProtocol`
  deliberately excludes `day_type`; **S5 redirected** from classify-now to defer-to-first-fixing-
  cutoff-consumer — the *concept* is ledgered as `OPEN.md` **AC-C1**, trigger "first fixing-cutoff /
  early-close consumer", so the deferral carries an id like every other). Deleted `_SPOT_LAGS["USDRUB"]`
  (RUB unregistered, pair unconstructible). Dropped
  the unused `name` param of `register_unit`. `_boundary_slope` now returns the exact end-segment
  slope for LINEAR (mirrors `_boundary_slope_log`); the finite step is kept for splines.

### Changed
- `redesign/11` gains a 6th standing checkpoint review input (**V3**): re-read the whole `AC-*`
  deferred ledger and check each trigger, since no automated gate watches those items and six
  triggers are condition-driven rather than roadmap-driven. (`CLOSURE_VERIFICATION.md` V1/V2 were
  already fixed on the closure branch; `closed_POST_CLOSURE.md` carries the D2 falsifier-pointer.)

## [0.82.0] - 2026-07-19

### Fixed
- **Ledger tightening — reclassified the 19 audit-closure ledger items against "wrong answer / invalid
  input today?" Only one was a latent bug wearing a Tier-4 badge:**
  - **AC-T4.2 — `Tenor` accepted non-positive counts** (invalid input). `Tenor.parse("0D")`/`"-3M"` and
    `Tenor(0, …)` now raise (`__post_init__` guard) — a zero step never advances a schedule loop.
    Removed from `OPEN.md`. Test: `test_t4_2_non_positive_tenor_is_rejected`.

### Added
- **EURIBOR_6M** — the standard EUR 6M vanilla floating leg (EUR, TARGET, ACT/360). Its absence was a
  gap in an index set presented as complete (`EURIBOR_3M` already shipped). Test:
  `test_t4_1_euribor_6m_is_registered`. The other missing indices (EFFR, BBSW, AONIA, CORRA, TIIE, …)
  stay ledgered — absent capabilities, deferred to their currency/product topics.

### Notes
- The remaining 17 ledger items confirmed **NO** on the wrong-answer/invalid-input test (absent
  capability or clean rejection — building them now would reintroduce the speculative infra Phase 4
  deleted, §6b) and stay in `OPEN.md`. Six of their triggers are condition/event/usage-driven rather
  than roadmap topics (AC-T4.7/8/9/11/17/18) — flagged as such in the ledger.

## [0.81.0] - 2026-07-19

### Removed
- **PONYTAIL_AUDIT micro-cuts (findings 4/5/8).** `Currency.value`/`Unit.value` alias properties
  (zero surviving call sites); `RfrConvention.none()` (byte-identical to the default — the `_term`
  factory already names the "term rate, no RFR mechanics" intent); the one-entry `_ANNUAL_BASIS` dict
  (inlined as a direct `BUS_252` conditional). Kept with reasons: `exponential_growth` (verified
  primitive + oracle, no schema hazard, near-term EM-bond consumer) and `Calendar._rule_set` (its
  union-narrowing is load-bearing for pyright).

### Changed
- **Foundation independent audit — CLOSED.** The three reports under `redesign/independent_audits/`
  are renamed `closed_AUDIT.md` / `closed_PONYTAIL_AUDIT.md` / `closed_PONYTAIL-DEBT.md`, each with a
  per-finding **disposition block** (fixed-with-a-test → CHANGELOG v0.75.0–v0.81.0 / ledgered →
  `OPEN.md` / rejected+reason). All Tier-4 items and the deferred sub-parts (NYSE+Fed-bank calendars,
  Tokyo Silver-Week/Olympic, FX quote-order registry, the interpolator-rebuild ponytail marker) are
  ledgered in `OPEN.md` with named re-open triggers. `redesign/README.md` row 0 now points at the
  closed record instead of "active work".

## [0.80.0] - 2026-07-19

### Removed
- **Foundation audit closure — Phase 4: A3 speculative-field cuts.** The design SHAPE was ratified;
  the guessed FIELDS were not (ruling A3 — a guessed field frozen into a schema is a costlier retrofit
  than the file-touch to reintroduce it correctly). Cut, each with zero consumers:
  - `underlying.py` sibling identities `ReferenceEntity` / `InflationIndex` / `FxFixing` /
    `EquityUnderlying` / `CommodityUnderlying` (guessed `fixing_time`, a required `grade`) — the file
    now holds only the `Underlying` protocol + `AssetClass`; each sibling returns *validated* when its
    asset class actually ships (§3c, one identity at a time).
  - `numerical_config.py` (`NumericalConfig` + sub-configs) — ships with the first engine that reads it;
    no engine exists yet, so no knob has a present consumer.
  - `PricingResult.cashflow_breakdown` / `sensitivities` / `diagnostics` and the `DiscountBasis`
    wrapper — `basis` is inlined to `Currency | None` (the collateral currency); greeks/breakdowns/
    diagnostics return with the L4/L5 layer that produces them. `results.py` drops its `fields-exempt`.

### Changed
- **A1 doc correction** (`interpolation.py`): documented that `CONTINUE_SLOPE` extends the end slope in
  the interpolation's *own* space (log space for `LOG_LINEAR`) — the fix that keeps extrapolated DFs
  positive.
- **A2 doc correction** (`AUDIT_topic0_foundation.md`, `HANDOFF_topic0_gate.md`,
  `handoff_topic1_conventions.md`): the S16 "record the invariant" ruling is **withdrawn** — business-day
  counting is one half-open `[start, end)` primitive, not a recorded invariant (the CDI/BUS-252 consumer
  needed the other convention, so the premise was false).

## [0.79.0] - 2026-07-19

### Changed
- **Foundation audit closure — Phase 3b: Schedule provenance (finding 3.5 discharged, red→green).**
  `Schedule.periods` emits a per-period **`SchedulePeriod`** record (accrual start/end, `is_stub`,
  payment date). **ACT/ACT ICMA Rule 251.2**: long coupons now sum the day count over their notional
  (quasi-coupon) periods — pinned to the ISDA 2006 §4.16 published long-first-coupon example
  (0.9157608696) — which **deletes the long-stub raise** (NG-DEFER-1 discharged). Explicit stub anchors
  via **`RegularPeriod(first_regular_date, last_regular_date)`** (the ISDA concept, folded into
  `ScheduleTerms.stub` as a union to stay ≤5 fields, no `fields-exempt`). **`PaymentRule(calendar, lag)`**
  places `payment_delay` — a payment settles `lag` business days after the adjusted accrual end on its
  own (often different, for XCCY) calendar; it was dead code until a schedule gave it a payment column.

## [0.78.0] - 2026-07-19

### Changed
- **Foundation audit closure — Phase 3: Tier-3 structural (red→green).** **3.2** `CalendarProtocol`
  (`is_business_day`/`adjust`/`add_business_days`/`identity`); `JointCalendar` implements it via a shared
  arithmetic mixin, and every `Calendar` consumer slot (`RollRule.calendar`, `year_fraction`,
  `settlement_date`, `accrued_rate`) is retyped to it — cross-currency schedules now type-check and work.
  **3.3** open registries: public `register_calendar`/`register_rate_index`, all `register_*` raise on
  conflicting re-registration (was a silent overwrite), `temporary_*` context managers for test isolation.
  **Q1** the USD calendar is renamed `NEW_YORK_SIFMA → US_GOVERNMENT_SECURITIES` (it is the govvies
  calendar, not a generic NY one) and SOFR binds to it explicitly. **3.5(partial)** ACT/ACT ICMA long
  stub RAISES rather than mis-accruing (multi-period support lands with 3b). **3.6** `fx_spot_date` (T+2
  joint-calendar; T+1 USD/CAD; a cross cannot settle on a US holiday); `spot_lag` moved out of
  `CurrencyPair` identity into a pair-conventions registry. **3.7** `_denominator` raises on unsupported
  day counts (no silent 360); `FixingSource` protocol on `accrued_rate` (`FixingHistory` is the impl).

## [0.77.0] - 2026-07-19

### Fixed
- **Foundation audit closure — Phase 2: four Tier-2 convention bugs (red→green).**
  **2.1** SOFR was declared with a non-standard `observation_shift=2`; ISDA SOFR OIS is plain
  compounded-in-arrears (`RfrConvention(payment_delay=2)`) — the LIBOR-fallback index correctly keeps
  the shift. **2.2** the `NEW_YORK_SIFMA` calendar was missing **Good Friday** (SOFR does not publish
  → `FixingHistory` raised on real data annually) and used federal Sat→Fri observance (wrongly closing
  2021-12-31); it now includes Good Friday and uses `SUNDAY_ONLY` (SIFMA does not shift Saturday
  holidays). **2.3** LONDON was missing the 2022–23 one-off bank holidays (Platinum Jubilee, state
  funeral, coronation, 2020 VE-Day move) — added a `dates()` one-off DSL combinator and `since/until`
  gating on `nth`. **2.4** Tokyo equinoxes were hardcoded (wrong in 2024–26); now computed
  astronomically (`equinox()`), plus the Emperor's-Birthday move (`since=2020`). Three existing
  calendar tests that encoded the buggy SIFMA Sat→Fri observance were corrected.

## [0.76.0] - 2026-07-19

### Fixed
- **Foundation audit closure — Phase 1: five Tier-1 computational bugs (red→green).**
  **1.1** ACT/ACT AFB undercounted leap-to-leap spans (2004-02-29→2008-02-29 gave 3.9973, now 4.0) —
  whole years are counted from `end` directly (`end − k·years`), not by accumulating single-year clamps.
  **1.2** `LOG_LINEAR` + `CONTINUE_SLOPE` returned a **negative** discount factor (DF(30) = −0.275);
  per ruling **A1** it now extrapolates in the interpolation's own (log) space → +0.209.
  **1.3** BUS/252 and CDI counted business days over different intervals; per ruling **A2** there is now
  one primitive, `business_days_between` counting `[start, end)`, and the S16 invariant is withdrawn.
  **1.4** backward schedule generation drifted the roll day through short-month clamps (May 31 quarterly
  → Nov 29) and keyed EOM on `start`; now generated as `anchor ± k·tenor` with EOM anchored on the
  generation seed (maturity for backward). **1.5** furikae substitution iterates `sorted(holidays)`
  (deterministic; the substitute union was already order-invariant, so no answer changed).

## [0.75.0] - 2026-07-19

### Added
- **Foundation audit closure — Phase 0: the foundation is now a real, importable package.** Added
  `src/pricebook_ng/foundation/__init__.py` with an explicit `__all__` public-API surface (the contract
  upper layers may depend on), a `py.typed` marker (typed code no longer reads as `Any` downstream), and
  a root `pyproject.toml` (src layout, dynamic version, numpy/scipy deps) — `pip install -e .` works.
  **Renamed `foundation/calendar.py` → `calendars.py`** so it no longer shadows stdlib `calendar` once
  `foundation/` is on `sys.path`. No behaviour change (136 tests, all gates + pyright green).

## [0.74.3] - 2026-07-19

### Fixed
- **L0 is now static-type clean (pyright 22 → 0 errors), no behaviour change (136 tests green).**
  (1) `Currency` (37), `Unit` (9) and `Frequency` (7) named constants are declared as `ClassVar`, so
  `Currency.USD` / `Unit.BARREL` / `Frequency.MONTHLY` type-check **and autocomplete** — the static half
  of the open registry (undoes A3's accepted-cost note; the registry stays open via `register_*`).
  (2) the closed registries use a mutable backing + frozen `MappingProxyType` **view** (`_registry`→
  `_REGISTRY`, `_calendars`→`_CALENDARS`) instead of rebinding a `dict`-typed name. (3) `Calendar`
  narrows the `HolidaySet | tuple[Rule,...]` union via a `_rule_set` property. (4) scipy `brentq`'s
  union return is `cast` to `float`. `verify.py fields` now excludes `ClassVar` (definitionally not a
  dataclass field) — a real gate correction.

## [0.74.2] - 2026-07-19

### Fixed
- **Foundation audit (fix/foundation-audit) — three RFR/calendar correctness fixes, red→green.**
  **F2 (silent-wrongness):** `accrued_rate` under `observation_shift` compounded the shifted
  observation window but normalised by the *interest-period* day-count fraction; the two windows can
  differ by a day (a shift crossing a holiday), silently scaling the rate (e.g. 5.72% for a flat 5%
  series). Now normalises by the numerator window's own days (`total/basis`) — consistent for both
  observation-shift and lookback (SOFR 1e-12 oracle unchanged). **F1 (silent-wrongness + crash):** a
  valid accrual containing no business day returned `0.0` (COMPOUNDED) or raised `ZeroDivisionError`
  (AVERAGED/EXPONENTIAL); now raises `ValueError` cleanly (S14). **F3 (wrong-answer, latent):**
  `Calendar.add_business_days(d, 0)` returned `d` even when `d` was not a business day (a `fixing_lag=0`
  lookup could land on a non-business date); `n==0` now requires a business day and raises otherwise —
  callers snap via `adjust()`. Systematic checks (Easter, observance regimes, EOM, IMM/CDS, solvers)
  verified clean against published references.

## [0.74.1] - 2026-07-19

### Changed
- **L0 final cleanup (last work before Topic 1).** (A1) `Accrual` moved `cashflow.py` → `day_count.py`
  — it is an *applied day count*, not a cashflow concept; the move **drops the semantically-wrong
  `rate_index → cashflow` import edge** (rate_index 8→7 imports), no new edges. (A2) the calendar and
  rate-index registries are frozen with `types.MappingProxyType` (the quarry's bug was registry
  mutation at import); the **open** currency/unit registries keep a mutable backing behind the
  sanctioned `register_*` path but expose read-only `CURRENCIES`/`UNITS` views — direct mutation raises,
  runtime registration still works (S1). (A3) `money.py` records *why* `Currency` is an open registry
  and what reverting to an `Enum` would cost (silently dropping BRL / the LatAm scope). Pure/hardening
  change; no parking change (the 13 remain parked).

## [0.74.0] - 2026-07-19

### Changed
- **Topic 0 GATE CLOSE — foundation parked (drawdown 13/793).** All 8 gate slices (S1–S17, F1–F4)
  landed and green (125 L0 tests; `fields` on merit; `layers`/`acyclic`/`debt`/`version`/`provenance`/
  ruff; both regression oracles). Parked the Topic 0 set to `parked/topic-00-foundation/`: the 11
  covered files + `data_registry` (**dead** — import-time JSON registry ruled away) + `notional`
  (**absorbed** into `Money`/`Leg`). `core/fixings` is **reassigned→market-data** (immutable
  `FixingHistory` read model is the L0 type; the mutable store + file I/O is not L0). Roll-up refreshed;
  gate-close report `CP_topic0_gate_close.md`. Topic 1 (multicurve + linear rates) opens once Cowork
  ratifies the gate.

## [0.73.0] - 2026-07-19

### Added
- **Topic 0 gate Slice 8 — serialisation pattern demonstrated on a hard case.** Per-class
  `to_dict`/`from_dict` (+ `schema_version` at the serialised root) on `Leg` and its constituents
  `Cashflow`/`Delivery`/`Accrual`/`Money`/`Quantity` — one case exercising all three dimensions at
  once: a **collection** (flows), an **enum** (`DayCountConvention`), **nested value objects**, and a
  `Cashflow | Delivery` **union** via a `kind` discriminator. The round-trip is JSON-clean;
  `Leg.from_dict` refuses an unknown `schema_version`. No framework — the quarry's 831-line machinery
  is not carried (the pattern is the deliverable).

## [0.72.0] - 2026-07-19

### Changed
- **Topic 0 gate Slice 5 — L0 numerics are thin scipy adapters (S17).** `distributions.py`
  (`scipy.stats.norm`), `solvers.py` (`scipy.optimize`: `brent` · `newton` · `secant` · LM
  `least_squares`), `interpolation.py` (`scipy.interpolate` `CubicSpline`/`PchipInterpolator`/
  `Akima1DInterpolator`; linear/log-linear ours). **Removes** the hand-rolled `bisect_root`/
  `nelder_mead` (no duplicates). Interpolation now states its **extrapolation policy per end**
  (`FLAT | CONTINUE_SLOPE | RAISE`, default RAISE both) — closes C4's silent divergence. scipy is
  the single C++-port swap point (never called from engines/models); `numpy`/`scipy` pinned in CI
  for convergence reproducibility. Hagan-West monotone-convex stays in Topic 1 (curve construction).

## [0.71.0] - 2026-07-19

### Changed
- **Topic 0 gate — foundation parked (first physical drawdown).** The gate audit (F1–F4 + S1–S16) is
  landed and green; `git mv` the **11 covered quarry `core/` files** →
  `parked/topic-00-foundation/` with a per-file coverage manifest (each classified `covered`/`dead`/
  `reassigned` with consumer-analysis evidence; all shed features are forward-linked deferred
  *capabilities*, none blocking). `core/data_registry` + `core/notional` are **reassigned→topic-01**
  (no L0 counterpart). `quarry_reconciliation.md` is now a thin topic-method roll-up (pre-replan CP
  record frozen as history). **Drawdown 11/793.** Topic 1 (yield curves) opens once Cowork ratifies
  the gate.

### Added
- **Topic 0 gate Slice 1 — `date + Tenor` (S7) + rule-based schedule anchors (S8).** `Tenor.__radd__`
  gives the raw shifted date (day/week exact; month/year clamp to the target month's length) — the
  most-used curve-building op; business-day rolling stays a separate `RollRule` concern (finance-free).
  `RollConvention.IMM`/`CDS` on `ScheduleTerms.roll_day` anchors interior periods on the 3rd Wednesday /
  20th regardless of the effective date (IMM-dated FRAs/futures, standard CDS). Oracles: `date+3M` month
  clamps; IMM-anchored schedule lands on 3rd Wednesdays of Mar/Jun/Sep/Dec; CDS on the 20th.

## [0.70.0] - 2026-07-19

### Changed
- **Topic 0 gate rework (6b, final) — open `Currency`/`Unit` registries (audit S1/S4 + the meta-rule).**
  `Currency` is now an ISO code + **`minor_units`** value with an open **registry** (JPY/KRW/CLP are
  zero-decimal); `Unit` is a symbol + registry. A new market/commodity is `register_currency(...)` /
  `register_unit(...)` — a *declaration*, never an L0 enum edit (open-ended domain → registry). The
  standard members stay class constants (`Currency.USD`, `Unit.BARREL`), interned so `is`/`==` both hold;
  the `Money`/`Quantity` guards compare by value. **BRL-end-to-end gate oracle** (Currency · BUS/252 ·
  São Paulo) green — the in-scope LatAm claim is real.

## [0.69.0] - 2026-07-19

### Changed
- **Topic 0 gate rework (6a) — `Calendar` `day_type` / half-days (audit S5).** `Calendar.day_type(d)` →
  `BUSINESS | HALF | HOLIDAY | WEEKEND`: a **half-day** is an early close (a business day with a
  shortened session — affects fixing cut-offs/settlement), e.g. US July 3, Christmas Eve, the day after
  Thanksgiving. To carry half-days and stay ≤5 fields, the holiday rules bundle into a
  **`HolidaySet(holidays, half_days)`**; a bare rule tuple auto-wraps, so only the half-day calendar
  changed. `is_business_day` is unchanged (a half-day is still a business day).

## [0.68.0] - 2026-07-19

### Changed
- **Topic 0 gate rework (5/6) — convention completeness (audit S11/S8/S9/S16).**
  `DayCountConvention` gains **`1/1`** (always 1) and **`ACT/ACT AFB`** (whole years + leap-aware stub) —
  ISDA 2006 completeness (S11). `ScheduleTerms` gains an optional **`roll_day`** — the day-of-month the
  interior periods roll on (a bond the 15th, CDS the 20th), else anchored on `start` (S8). Recorded
  invariants: **time-of-day never enters `Calendar`** (fixing time is index metadata, expiry cut is L2 —
  S9); business-day counting is **start-exclusive/end-inclusive** (S16).

## [0.67.0] - 2026-07-19

### Changed
- **Topic 0 gate rework (4/5) — rate-quotation basis (audit S12, the biggest missing concept).**
  `foundation/rate_basis.py`: **`Compounding`(SIMPLE·ANNUAL·SEMI_ANNUAL·QUARTERLY·MONTHLY·CONTINUOUS)** —
  the basis a *quoted* rate compounds on — and **`convert_rate(rate, t, from, to)`** (via `growth_factor`).
  A rate is meaningless without its basis; treating semi-annual as continuous is silently wrong by ~r²/2.
  **Recorded invariant:** internal curve rates are continuous on the curve day-count; quotes carry their
  own basis and convert at the boundary (keeps `Rate` a plain float). The index enum
  **`CompoundingMethod` is renamed `AccrualMethod`** to kill the name collision (it is a different
  concept — index averaging, not quotation basis).

## [0.66.0] - 2026-07-19

### Changed
- **Topic 0 gate rework (3/5) — the index rework (audit F2/F3/F4/S10).**
  - **F2 (the critical fix): `RateIndex` carries its own calendar.** `accrued_rate` now reads
    `index.accrual.roll.calendar` — **no currency inference** (the reverted quarry flaw #14/#16). SOFR
    fixes on **SIFMA**; two same-currency indices on different calendars now differ. Regression oracle:
    SOFR-on-SIFMA ≠ a same-currency index on TARGET over a period spanning Columbus Day.
  - **F3: `RateIndex` decomposed** → `IndexId`(name·currency·`Tenor`) · `AccrualConvention`(day_count·
    `RollRule`) · `FixingRule`(observation_style·compounding·fixing_lag) · `RfrConvention`(shift·lookback·
    lockout·payment_delay, with `.none()` for IBORs) · `spread_adjustment` — 5 parts, **marker removed**.
  - **F4/S10: `foundation/underlying.py`** — the general `Underlying` protocol (`name`, `asset_class`)
    that `RateIndex` satisfies, plus sibling identities **defined now, populated later**:
    `ReferenceEntity`, `InflationIndex` (lag·interpolation·base), `FxFixing` (pair·source·time),
    `EquityUnderlying`, `CommodityUnderlying` (unit·**delivery location**·**grade** — Brent ≠ WTI).

## [0.65.0] - 2026-07-19

### Changed
- **Topic 0 gate rework (2/5) — config & result shapes (audit F1/S15/S6/S2/S13/S14).**
  - **`NumericalConfig` decomposed** by method family — `MonteCarloConfig`/`LatticeConfig`(tree folded
    in)/`IntegrationConfig`/`SolverConfig`, each ≤5 fields; the `fields-exempt` marker is **removed**
    (`verify.py fields` passes on merit; reads as `numerics.monte_carlo.paths`). RNG family **pinned**
    as an invariant `RNG_FAMILY` (S15 — not a field, which would push MC to 6). Nested serialisation.
  - **`PricingResult` full decomposition vocabulary** fixed once (pv · accrued · clean · cashflow
    breakdown · sensitivities · diagnostics), fields optional/unpopulated — a legitimate output-record
    exemption per §3b, so no asset class retouches L0 to add a field (S6).
  - **`Leg` holds `flows: tuple[Cashflow | Delivery, ...]`** — a physical/commodity leg is now
    expressible (S2); **pay/receive is the sign of the amount, no direction field** (S13).
  - **Degenerate periods raise** — a reversed/zero-length `Accrual`, and `year_fraction(end < start)`
    (S14).

## [0.64.0] - 2026-07-18

### Changed
- **Topic 0 gate rework (1/5) — `Tenor` value type + `Frequency` reshape (audit S7/S3).**
  `foundation/tenor.py`: **`Tenor(count, unit: D/W/M/Y)`** with `parse("28D")`/`__str__`/`months()` — the
  one primitive behind index tenors, schedule steps and curve pillars (overturns "Tenor stays a string").
  **`Frequency` is now a `Tenor`-step** (or `BULLET`, a single period), so it expresses **28-day (TIIE),
  daily, and single-period** — a month-int enum could not. Behaviour-preserving for the named
  frequencies (MONTHLY/QUARTERLY/… are class constants). Oracles: parse/str round-trip; 28D/daily/bullet
  schedules; standard frequencies unchanged.

## [0.63.0] - 2026-07-18

### Added
- **Topic 0, Slice 6 — `numerics-config`: the finite-difference/numeric floor + engine I/O (L0).**
  The last slice before the Topic 0 gate.
  - **Complete `NumericalConfig`** — the full reproducibility knob set designed up front (MC
    paths/seed/antithetic/sobol/bridge · PDE time/space/n-std-devs · tree steps · quadrature tol/max-iter
    · COS n/L · root-finder tol/max-iter · fd bump), so it never retrofits a foundational value type (the
    12 knobs deferred at CP-3 retire #1). `# fields-exempt: config aggregate`; positive-knob validation;
    the **serialisation pattern** (`to_dict`/`from_dict` + `schema_version`, no framework).
  - **`distributions`** (norm_cdf/pdf/ppf) · **`solvers`** (bisect_root, Nelder-Mead) · **`interpolation`**
    (linear + log-linear — *mechanism only*; extrapolation is an L1 curve policy, so out-of-range raises).
  - **`PricingResult`** (A2 decomposition: dirty PV + accrued ⇒ clean) now records its **basis** — value
    currency (`pv`) **and** the collateral/discounting `DiscountBasis` — so a PV is never ambiguous
    (settlement ruling §1; the numeraire *choice* stays L3). **`PricingFailure`** — failure as a value.
  - Deferred with their first consumer (no shape risk): the MC/PDE/Fourier-COS/tree/quadrature *engines*.
  - slice: `numerics-config` (Topic 0 S6)

## [0.62.0] - 2026-07-18

### Added
- **Topic 0, Slice 5 — `index-identity` (widened): `RateIndex` + `FixingHistory` + `accrued_rate` (L0).**
  `foundation/rate_index.py`. A new index is a **declaration, never a code change.**
  - **`RateIndex` covers all rate kinds:** the RFR set (`fixing_lag`/`observation_shift`/`lookback`/
    `lockout`/`payment_delay`/`compounding`) **plus the widening** — **`observation_style`**
    (BACKWARD_LOOKING RFR vs FORWARD_LOOKING term/IBOR) and **`spread_adjustment`** (ISDA fallback
    credit spread). It's an identity aggregate (`# fields-exempt`).
  - **`FixingHistory` is generic over index** (name→date→value), so it will also hold inflation levels
    / FX fixings / equity observations — the sibling identities land later under the same pattern.
  - **One generic `accrued_rate(index, accrual, fixings)`**, branching only on `CompoundingMethod`:
    FLAT/forward → the single fixing at the start; backward → compounded/averaged over the observation
    window, with **`lookback` (shift the rate only) vs `observation_shift` (shift the whole window)**
    distinct, plus `lockout`; `spread_adjustment` added (a fallback = base RFR + spread, not absorbed).
    `CompoundingMethod` also carries **`EXPONENTIAL`** — the Brazilian BUS/252 `(1+r)^(bd/basis)` used by
    CDI/SELIC (and LTN/NTN-F/DI), where a flat rate reprices to itself exactly (vs money-market
    `∏(1+r·δ)`); `CDI` (BRL) is declared. The **basis is derived from the day-count** (`BUS/252 → 252`),
    not hardcoded — another basis is a day-count entry. The daily-series (`rᵢ`, floating CDI in arrears)
    path is `accrued_rate`; the single-fixed-rate (`r`, LTN/NTN-F) growth factor is the separate
    `exponential_growth(rate, business_days, day_count)` primitive.
  - **Registry by explicit construction** (SOFR, SONIA, ESTR, TONA, SARON, EURIBOR_3M, TERM_SOFR_3M,
    a USD-LIBOR fallback) — **no import-time JSON reload** (the quarry rebound the whole `_REGISTRY`
    from a file, where one bad row dropped the other 27).
  - Oracles: compounded RFR vs a hand-computed series; lookback ≠ observation-shift; 0/0 ≠ 2/2;
    forward-looking term ≠ backward-looking compounded; fallback = base + spread. `verify.py layers` green.
  - slice: `index-identity` (Topic 0 S5)

## [0.61.0] - 2026-07-18

### Added
- **Topic 0, Slice 4b — `settlement`: the flow-shape vocabulary (L0).** `foundation/settlement.py`
  (new slice, ruled after S4 — `rulings_topic0_settlement_and_index.md`).
  - **`Delivery`(date, `Quantity`)** — the physical-world counterpart to `Cashflow(date, Money)`, giving
    the S4 `Quantity` a home in a flow. **`SettlementType`** (CASH / PHYSICAL / **AUCTION** — a marker
    only; CDS credit-event mechanics stay in the credit topic). **`SettlementTerms`**(type, currency,
    lag) — the settlement currency **may differ from the contract currency** (quanto / NDF) and is
    `None` for physical; cash/auction require one. **`settlement_date`** = trade + `lag` business days
    under a calendar (FX T+2).
  - Scoped strictly L0: no PV (the quarry's `cash_settlement` returned one — that's L4), no
    product→convention table (L2), no collateral/CSA discounting (numeraire is an **L3** model choice
    per §1). Content mined from the 398-LOC zero-fan-in orphan `core/settlement.py`.
  - Oracles: T+2 settlement date skips the weekend; cash pays `Money` vs physical delivers `Quantity`;
    settlement currency ≠ contract currency; physical carries no currency. `verify.py layers` green.
  - slice: `settlement` (Topic 0 S4b)

## [0.60.0] - 2026-07-18

### Added
- **Topic 0, Slice 4 — `money-quantity`: value types + instrument atoms (L0).**
  `foundation/money.py` + `foundation/cashflow.py`.
  - **`Money`(amount, currency)** with currency-guarded arithmetic — **mixing currencies is a
    `TypeError`**; `+`/`-`/unary `-`/scalar `*`. **`Currency`** covers the **37** markets (matches the
    Slice-1 calendars). **`Quantity`(amount, `Unit`)** — commodities settle in barrels/MWh/tonnes/troy
    ounces/…; closed under **same-unit** arithmetic only (barrels and MWh do not add).
    **`CurrencyPair`**(base, quote, spot_lag) with `.name` and T+2 default (USD/CAD T+1).
  - **`Accrual`(start, end, day_count)** with **`Accrual.year_fraction(*, coupon_period=None,
    calendar=None)`** — the ergonomic entry point over the Slice-2 primitive (bundles start+end+
    day_count; threads ICMA anchors / BUS-252 calendar). **`Cashflow`**(date, `Money`, accrual) ·
    **`Leg`**(cashflows, day_count).
  - Serialisation deferred to Slice 6 (per the topic plan). Oracles: currency-mixing type error;
    same-unit-only `Quantity`; `Accrual.year_fraction` == the S2 primitive (incl. strict-ICMA anchors).
    `verify.py layers` green (L0 finance-free).
  - slice: `money-quantity` (Topic 0 S4)

## [0.59.0] - 2026-07-18

### Fixed
- **Topic 0 S3-checkpoint corrections (Cowork ruling `rulings_topic0_s3.md`).** Three fixes to the
  merged calendars/daycounts slices, done before Slice 4.
  - **ANZAC-Day observance (§3.1 — the `observe`-lift correction).** The lift of the per-rule `observe`
    flag to a calendar-level `Observance` was *not* behaviour-preserving: AU/NZ **ANZAC Day (25 Apr)** is
    commemorated on the actual date and **not** mondayised, while New Year/Christmas in the same
    calendars are. `fixed()` regains a per-rule `observed=` override (default follows the regime);
    `SYDNEY`/`WELLINGTON` ANZAC set `observed=False`. Regression oracle: ANZAC on a weekend does not
    shift while New Year in the same calendar does.
  - **ACT/365L is frequency-dependent (§3.3, ISDA §4.16(i)).** Annual (or no context) → 366 iff a 29 Feb
    lies in the period; more frequent than annual → 366 iff the period **end** is in a leap year. Uses
    `CouponPeriod.frequency` (now serving three conventions — ICMA, 30E/360-ISDA, ACT/365L).
  - **`Coverage` marker (§4).** Eight EM calendars (Riyadh, Cairo, Istanbul, Tel Aviv, Beijing, Seoul,
    Mumbai, Bangkok) are **secular-only** — they omit lunar/religious holidays. Now marked
    `Coverage.SECULAR_ONLY` (not silently wrong); lunar data forward-linked to the EM-rates topic.
  - slice: `topic0-s3-corrections`

## [0.58.0] - 2026-07-18

### Added
- **Topic 0, Slice 3 — `schedules`: `RollRule`/`ScheduleTerms`/`Schedule` + IMM/CDS rolls (L0).**
  `foundation/schedule.py`.
  - `Frequency` · `StubType` (all four) · **`RollRule`**(calendar, convention, eom) ·
    **`ScheduleTerms` → `build_schedule` → `Schedule`**. A `Schedule` carries **both** the unadjusted
    period boundaries (accrual) **and** the business-day-adjusted dates (payment) — C2, not the same
    list. **EOM anchored once from `start`** (ISDA §4.10); stdlib month arithmetic (day clamped to
    month length), no `dateutil`.
  - **Long stubs are explicit** — the stub period merges with its neighbour by construction; the
    quarry's `first_gap < months*30*0.5` merge heuristic is **shed**.
  - **New: IMM roll dates** (`imm_date`/`next_imm` — 3rd Wednesday) **and CDS roll dates**
    (`cds_roll_date`/`next_cds_roll` — 20th of Mar/Jun/Sep/Dec). Neither existed in the quarry; futures
    and credit both need them.
  - Oracles: ISDA §4.10 EOM anchoring (month-end start → month-ends), all four stubs, adjusted ≠
    unadjusted under a holiday, published IMM/CDS tables. `verify.py layers` green (L0 finance-free).
  - slice: `schedules` (Topic 0 S3)

## [0.57.0] - 2026-07-18

### Added
- **Topic 0, Slice 2 — `daycounts`: 10 conventions + `CouponPeriod` (L0).** `foundation/day_count.py`
  — `year_fraction(start, end, convention, *, coupon_period=None, calendar=None)`.
  - The seven market-standard conventions (ACT/360, ACT/365F, **30U/360 US-SIA with the February
    rules**, 30E/360, ACT/ACT ISDA, ACT/ACT ICMA, BUS/252) **plus the three gaps: ACT/365L, 30E/360
    ISDA (with the termination-date rule), NL/365.**
  - **No hidden context (content mined, defaults dropped):** ICMA anchors ride on a `CouponPeriod`
    (reference_start/end, frequency, is_final) — **strict**: missing anchors *raise* (the deleted
    `strict_icma=False` silently fell back to ACT/365F and priced a UST coupon at 1.9836); BUS/252
    *requires* a `Calendar` — no São Paulo default; passing none raises.
  - Oracles: ISDA 2006 §4.16 (ACT/ACT ISDA worked example, 30U/360 Feb edges), ICMA Rule 251
    (**UST semi-annual coupon = exactly 2.0000**), ACT/365L & NL/365 leap-day handling, 30E/360-ISDA
    last-day-of-month + February-termination exception. `verify.py layers` green (L0 finance-free).
  - slice: `daycounts` (Topic 0 S2)

## [0.56.0] - 2026-07-18

### Added
- **Topic 0, Slice 1 — `calendars`: the holiday-rule DSL + all 37 markets, identity-keyed (L0).**
  `foundation/calendar.py` (engine) + `foundation/market_calendars.py` (declarations).
  - **DSL** (`fixed`/`easter`/`orthodox`/`nth`/`monday` + the `christmas_boxing`/`victoria_day`/
    `midsummer_eve`/`mexico_inauguration` cascades, `since`/`until` year-gating), Gregorian + Orthodox
    Easter, and the **three observance regimes** — US 5 U.S.C. §6103 (Sat→Fri, Sun→Mon), Commonwealth
    next-working-day (Sat/Sun→Mon), Johannesburg Sunday-only — plus Tokyo **furikae** and the
    Israel/MENA **Fri–Sat weekend**. `BusinessDayConvention` gains `NEAREST`. `JointCalendar` = union.
  - **Structure cleaned (content mined, not structure):** the quarry's ~38 `Calendar` subclasses +
    currency-keyed registry collapse into **one frozen `Calendar` value** (identity · rules · weekend ·
    observance — 4 fields) and **37 data declarations keyed by identity** (`NEW_YORK_SIFMA`, `TARGET`,
    …); currency → calendar is a lookup (`calendar_for_currency`), C1. The per-rule `observe` flag is
    lifted to the calendar's `Observance` regime.
  - Oracles: published holiday dates; US-vs-UK Saturday divergence; Juneteenth `since=2021`; Danish
    Store Bededag `until=2023`; Christmas/Boxing collision cascade; Tokyo furikae; Fri–Sat weekend;
    business-day adjustment (following/modified/nearest); joint-calendar union. `verify.py layers`
    green (L0 finance-free).
  - slice: `calendars` (Topic 0 S1)

## [0.55.0] - 2026-07-18

### Changed
- **Topic 0, Slice 0 — `ng-parking`: the whole ng tree parked, rebuild starts clean.** The pre-topic
  ng tree (54 modules + tests) is moved wholesale to `ng_parked/` and `src/pricebook_ng/` is reset to a
  bare package seed. **No behaviour claim** — this is a structural reset, not a feature change.
  - **Why:** the parked tree was built without `RollRule`, without identity-keyed calendars, without
    dual adjusted/unadjusted schedules. Editing it forward would inherit those decisions — the exact
    error we forbid with the quarry. `ng_parked/` is now a **content source only** (conventions,
    formulas, edge cases, oracle reference values); its *organisation carries no authority*
    (CLAUDE.md: mine for content, never for structure). `ng_parked/MANIFEST.md` maps each parked
    module → the topic that rebuilds it → its re-base oracle.
  - **New gate `verify.py layers`** — semantic layer conformance: L0 (`foundation/`) must be
    finance-free (no strikes/vols/payoffs/discounting). `acyclic` proves dependency *direction*; this
    catches a module on the *wrong layer* — the drift `foundation/black.py` (Black-76 at L0) slipped
    through. Wired into CI.
  - **CI repointed:** dropped the `--layer 6` tier (it guarded the now-parked tree); added the `layers`
    gate; the tree climbs from L0 as Topic 0 populates it.
  - Two quarry modules retired before the reset stay ticked (`core/numerical_config`,
    `fixed_income/fixed_leg`). Prior drawdown detail moves to per-topic manifests (redesign/13 §3.4).
  - slice: `ng-parking` (Topic 0)

## [0.54.0] - 2026-07-18

### Added
- **ZCIS serialisation (CP-3 tail, build-early per §4.5) — no drawdown change.** `ZeroCouponInflationSwap`
  gains `to_dict`/`from_dict` (+ `schema_version`), added to the property-based round-trip sweep.
  - **Retire-read: `fixed_income/inflation.py` is held a PARTIAL cross, NOT ticked** (drawdown stays
    7/768). It is a **multi-product module** (`CPICurve`, `ZCInflationSwap`, `YoYInflationSwap`,
    `InflationLinkedBond`); ng supersedes only the ZCIS (`ZeroCouponInflationSwap` + `ZCISEngine`, real
    curve via A5 `MarketKey(INFLATION, index)` + Fisher, which also supersedes `CPICurve` — 0 external
    consumers). But **`YoYInflationSwap` is `dead`** (0 production consumers, 2 test-refs) and
    **`InflationLinkedBond` has 2 production consumers** — `desks/api` + `inflation_indices` (both
    un-crossed) → `deferred→` those. Ticking would delete a module that defines a whole product ng never
    built — the first such case, so it is **routed to Cowork at CP-4** (multi-product-module retire
    pattern) rather than ticked unilaterally.
  - Oracles: dict round-trip; schema version present / absent-reads-v1 / future-rejected.
  - quarry: `python/pricebook/fixed_income/inflation.py` (ZCIS only) · slice: `serialisation-zcis`

## [0.53.0] - 2026-07-18

### Removed
- **`fixed_income/fixed_leg.py` retired → seventh quarry retire — CP-3 tail (drawdown 6 → 7/768).**
  A **no-code tick** (§4.5 "several may tick immediately"): ng already fully supersedes it, so no runtime
  change — only the reconciliation-map + version ledger advance.
  - **Superseded:** the `Cashflow` atom was **promoted** to `foundation/cashflow.py` (ng stores amount
    as `Money` + an `Accrual` period; the quarry's decomposed notional/rate/year_frac is shed —
    year_frac derives from the accrual); `FixedLeg` construction → `products/leg.py`
    `fixed_coupon_cashflows`; the container → `products/swap.py FixedLeg`; `FixedLeg.pv` → the engine.
  - **Consumer analysis (§4):** the 3 external quarry `FixedLeg(` sites are `swap.py` (un-crossed →
    `deferred→swap`) and `ois.py`/`bond.py` (already deletable). `annuity`/`weighted_annuity` (RPV01)
    are consumed only by un-crossed modules (swaption, CMS, desks) ⇒ `deferred→swap`, to be exposed as
    an **engine/curve building block** when swap crosses (CLAUDE.md §3), not a product method.
  - **Oracle:** no new code ⇒ no new red; the tick rests on ng's existing green leg/cashflow/swap/bond
    oracles + the consumer analysis. `floating_leg.py` is a separate retire (projection/multi-curve
    `pv`) that travels with the swap / multi-curve slice.
  - quarry: `python/pricebook/fixed_income/fixed_leg.py` · slice: `retire-fixed-leg`

## [0.52.0] - 2026-07-18

### Added
- **FixedRateBond serialisation → sixth quarry retire — CP-3 tail (drawdown 5 → 6/768).** `FixedRateBond`
  gains `to_dict`/`from_dict` (+ `schema_version`); its quarry counterpart `fixed_income/bond.py` is
  now **deletable**. *The heaviest retire so far — flagged for Cowork spot-check at CP-4.*
  - **Consumer-analysis retire-read (§4/§4.5):** ng supersedes the bond **product** (coupon+redemption
    cashflows) + curve pricing (`DiscountingEngine`) + **accrued / clean-vs-dirty** (the engine's A2
    decomposition, `PricingResult.accrued`/`clean`). All 8 production instantiations of the quarry
    `FixedRateBond` are in **un-crossed** modules (`desks/api` ×6, `benchmark_bonds`, `sukuk`).
  - **`deferred→` (whole yield-analytics surface, no crossed consumer):** `yield_to_maturity`,
    `macaulay/modified_duration`, `convexity`, `dv01_yield`, `price_from_yield_sc`, `irr_sc`,
    `risk_factor_sc` → `desks/api` + `benchmark_bonds` + `sukuk`. Per the spine these are **L4/L5 engine
    analytics, not product methods** — built when a consumer crosses, never cloned onto the product
    (§6b). `from_convention` → `composite_convention` + `esg_bonds` + `supranational` + `sovereign_bonds`.
    Forward-linked on those backlog rows.
  - **`deferred→persistence`:** serialisation itself (added early per §4.5 build-as-you-go — cheap,
    already in the module; never blocks the tick).
  - Serialisation reuses the shared `Cashflow`/`Money` encoders; `FixedRateBond` added to the
    property-based round-trip sweep.
  - Oracles: dict round-trip; schema version present / absent-reads-v1 / future-rejected.
  - quarry: `python/pricebook/fixed_income/bond.py` · slice: `serialisation-bond`

### Changed
- **Property-based serialisation oracle (CP-3 ruling §4.2).** A hypothesis sweep
  (`tests_ng/L4/test_serialisation_property.py`) round-trips *generated* instances of every
  serialisable type — `NumericalConfig`, `FixedCashflow`, `Deposit`, `ForwardRateAgreement`,
  `OvernightIndexSwap`, `FixedRateBond`, and the shared `Cashflow`/`Accrual`/`Money` atoms — asserting
  `T.from_dict(x.to_dict()) == x` for all valid `x`, strengthening the per-type one-example checks to
  "round-trips any instance". (The property run also confirmed the vanilla builders correctly fail-fast
  on day-counts needing extra context — `ACT_ACT_ICMA` coupon anchors, `BUS_252` a calendar — which
  are excluded from builder-based generation.)

## [0.51.0] - 2026-07-18

### Added
- **FixedCashflow serialisation → fifth quarry retire — CP-3 #5 (drawdown 4 → 5/768).** `FixedCashflow`
  gains `to_dict`/`from_dict` (+ `schema_version`) — the genuine residual that lets it **supersede the
  quarry `fixed_income/zero_coupon_bond.py`**: a zero-coupon bond *is* a single fixed cashflow
  (`Face·DF(T)`), which the `DiscountingEngine` already prices.
  - **Consumer-analysis retire-read (§4):** the quarry `ZeroCouponBond` has **no external production
    instantiation** (the only `ZeroCouponBond(` is its own docstring; production builds flow through
    `sovereign_bonds.py` via `from_convention`). Its money-market analytics
    (`price_from_yield_simple/discount_rate/continuous`, `yield_simple/continuous`, `modified_duration`,
    `dv01`) have **zero production consumers** — only `tests/test_sovereign_bonds.py` — and the quarry
    already has a dedicated `fixed_income/tbill.py` (`TreasuryBill`) as the real home for T-Bill
    conventions, so ZCB's copies are **`dead` duplicates**.
  - **`shed:` `ZeroCouponBond.from_convention` = `deferred→sovereign_bonds`** — the one production
    consumer is `sovereign_bonds.py:479` (un-crossed quarry); the obligation forward-links onto the
    sovereign-bonds crossing (its row in `quarry_reconciliation.md`), it is not owed by this retire.
  - Serialisation reuses the shared `Cashflow`/`Money` encoders (no new lifting needed).
  - Oracles: dict round-trip; schema version present / absent-reads-v1 / future-rejected.
  - quarry: `python/pricebook/fixed_income/zero_coupon_bond.py` · slice: `serialisation-zcb`

## [0.50.0] - 2026-07-18

### Added
- **OIS serialisation → fourth quarry retire — CP-3 #4 (drawdown 3 → 4/768).**
  `OvernightIndexSwap` gains `to_dict`/`from_dict` (+ `schema_version`), the genuine residual that
  supersedes the quarry `fixed_income/ois.py`, now deletable.
  - **Consumer-analysis retire-read (§4):** the quarry `OISSwap` has 2 production instantiations —
    `desks/api.py:641` (un-crossed ⇒ `deferred→desks/api`) and `OISConvention.create_swap` (inside the
    quarry ois module itself ⇒ retires with it). ng supersedes single-curve pricing via `engine/ois.py`
    (`OIS == vanilla IRS`). The `pv_ctx` multi-currency `discount_curves` branch is a multi-curve role
    ⇒ deferred. Serialisation (DB `from_dict` dispatcher) is the real residual.
  - **`shed:` `OISSwap.from_convention` = `dead`** — sole caller is
    `tests/test_convention_factory.py` (a quarry test); no production consumer.
  - **Rule of two fired twice:** OIS's `FixedLeg` coupons carry `Accrual` and `Cashflow`, so
    `Accrual.to_dict`/`from_dict` (consumers: FRA + coupon cashflows) and `Cashflow.to_dict`/`from_dict`
    (consumers: deposit + OIS legs) are lifted to `foundation/cashflow.py`; FRA and deposit refactored
    to use them under their green oracles. `FixedLeg`/`FloatLeg` encoding stays inlined in OIS (its only
    serialising consumer) — lift a shared leg encoder when the vanilla swap serialises.
  - Oracles: dict round-trip; schema version present / absent-reads-v1 / future-rejected.
  - quarry: `python/pricebook/fixed_income/ois.py` · slice: `serialisation-ois`

## [0.49.0] - 2026-07-18

### Added
- **FRA serialisation → third quarry retire — CP-3 #3 (drawdown 2 → 3/768).** `ForwardRateAgreement`
  gains `to_dict`/`from_dict` (+ `schema_version`), the genuine residual that supersedes the quarry
  `fixed_income/fra.py`, now deletable.
  - **Consumer-analysis retire-read (per the new §4 phantom-residual rule):** the quarry `FRA` class
    has a single production instantiation — `desks/api.py:273` `FRA(...).pv(curve, projection_curve)`,
    a **multi-curve** desk path. `desks/` is un-crossed quarry ⇒ that role is `deferred→desks/api`
    (travels with the desks crossing / the multi-curve slice), **not a residual now**. ng already
    supersedes single-curve FRA pricing (`engine/fra.py`, incl. seasoned fixings). The only
    production-reachable reconstruction path is the DB dispatcher (`db.py from_dict`) ⇒ serialisation
    is the real residual, exactly as for deposit.
  - **`shed:` `FRA.from_convention` = `dead`** — sole caller is `tests/test_convention_factory.py::`
    `test_fra_from_convention` (a quarry test, retires with the quarry); no production consumer.
  - **Rule of two fired:** FRA is the second serialising product, so `Money.to_dict`/`from_dict` is
    lifted to `foundation/money.py` and both deposit + FRA use it. The `Accrual` (FRA) and `Cashflow`
    date (deposit) encodings stay inlined — one consumer each — to be lifted at their own second use.
  - Oracles: dict round-trip; schema version present / absent-reads-v1 / future-rejected.
  - quarry: `python/pricebook/fixed_income/fra.py` · slice: `serialisation-fra`

## [0.48.0] - 2026-07-18

### Added
- **Deposit serialisation → second quarry retire — CP-3 #2 (drawdown 1 → 2/768).** `Deposit` gains
  `to_dict`/`from_dict` (round-trippable wire form + `schema_version`), the genuine residual that lets
  it **supersede the quarry `fixed_income/deposit.py`**, now marked deletable.
  - **Finding (refines the CP-3 #2 ruling):** the ruling named *conventions/RateIndex* as deposit's
    residual, but the evidence says otherwise. The quarry `Deposit` class has **zero production
    consumers** (`grep 'Deposit(' python/pricebook` = 0 instantiations); it is exercised only by
    quarry tests. ng already supersedes every role: the product cashflows + `DiscountingEngine`
    pricing, and the **curve-pillar role via `DepositQuote`** in `bootstrap_discount_curve`
    (`1/(1+rτ)` closed form). The only reconstruction path that is production-reachable is the DB
    dispatcher (`db.py` `from_dict`) → **serialisation** is the real residual (same as CP-3 #1),
    deferred-consumed by the not-yet-crossed persistence/data-spine slice.
  - **`shed:` `Deposit.from_convention` = `dead`** — `grep 'Deposit.from_convention' python/` finds a
    single caller, `tests/test_convention_factory.py::test_deposit_from_convention` (a quarry test that
    retires with the quarry); no production consumer. `discount_factor`/`pv`/`pv_ctx`/`year_fraction`
    properties: no production consumer (0 `Deposit(` sites), superseded by ng.
  - **No conventions/RateIndex built** — it is not deposit's residual and ng has no present consumer
    for it (§6b / "watch sprawl": a cross-cutting slice must retire a module, not add speculative
    infra). Conventions re-aims at its genuine consumer (per-currency curve construction) when crossed.
  - Oracles: dict round-trip; schema version present / absent-reads-v1 / future-rejected.
  - Serialisation stays per-class (rule of two — `Money`/`Cashflow` encoding inlined; lift a shared
    helper at the second product, FRA/swap, CP-3 #3).
  - quarry: `python/pricebook/fixed_income/deposit.py` · slice: `serialisation-deposit`

## [0.47.0] - 2026-07-18

### Added
- **Serialisation → first quarry retire — CP-3 #1 (drawdown 0 → 1/768).** `NumericalConfig` gains
  `to_dict`/`from_dict` (round-trippable wire form + `schema_version`: absent = legacy v1, a newer
  version is refused not misread) and a `replace` convenience — the genuine residual that let it
  **supersede the quarry `core/numerical_config.py`**, now marked deletable.
  - Per the ratified "deletable = supersede-with-evidence" bar: the quarry's 12 extra knobs
    (`pde_*`, `cos_*`, `tree_steps`, `mc_antithetic/sobol/bridge`, `integration_*`, `rootfinder_*`,
    `extra`) are shed **`dead`** — `grep '\.<knob>' python/` finds **zero production consumers** (only
    the quarry module's own unit test + a same-named local kwarg). The quarry config was a
    half-adopted abstraction (its docstring: adoption "incremental"); ng correctly omitted them (§6b).
    Full `shed:` evidence in `quarry_reconciliation.md` (flagged for Cowork's close review).
  - Oracles: dict round-trip; schema version present / absent-reads-v1 / future-rejected; `replace`.
  - Serialisation is per-class (rule of two — no shared framework at one serialisable type yet).
  - quarry: `python/pricebook/core/numerical_config.py` · slice: `serialisation-numerical-config`

## [0.46.0] - 2026-07-17

### Added
- **OIS + `RateCurve` protocol + `curve.forward_rate` (L1/L2/L4) — CP-2c #4, closes the CP-2b
  ruling §4.1/§4.2.** `OvernightIndexSwap` + `OISEngine`: fixed vs compounded-overnight float.
  Single-curve, the compounded rate equals the curve forward, so the OIS **reprices identically to
  the vanilla IRS**.
  - **`curve.forward_rate(d1, d2, day_count)`** (§4.1) — the simply-compounded forward
    `(P(0,d1)/P(0,d2)-1)/τ` as a curve building block, now that OIS is the 2nd forward consumer.
  - **`RateCurve` protocol** (§4.2, `df`+`zero_rate`+`instantaneous_forward`+`forward_rate`) —
    distinct from `CurveHandle` (df-only / survival); consumers are Hull-White (now typed `RateCurve`,
    duck-type removed) and OIS.
  - Extracted a shared **`float_leg_pv`** used by both `SwapEngine` and `OISEngine` (forward via
    `curve.forward_rate`, seasoned via fixings); `FRAEngine` also moved onto `curve.forward_rate`.
    All byte-identical (255 green).
  - Oracles: `forward_rate` == DF-ratio forward (flat + bootstrapped); par OIS → 0; OIS == vanilla IRS.
  - **Deletable-bar read** (`fixed_income/ois.py`): residual before deletable — currency conventions
    (SOFR/SONIA/ESTR), `bootstrap_ois`, par_rate/annuity/dv01, daily-fixing compounding, multi-curve
    basis. Logged in the map. Drawdown 0/768.
  - quarry: `python/pricebook/fixed_income/ois.py` · slice: `ois-spine`

## [0.45.0] - 2026-07-17

### Added
- **Deposit product (L2) — CP-2c #3, fixed_income spine.** A money-market deposit modelled as its
  two cashflows (`−N` at start, `N·(1+rate·τ)` at maturity) priced by the existing `DiscountingEngine`
  — **no bespoke engine**. A2 reconciles the views: a forward deposit reprices to zero at par; a spot
  deposit's principal-today is realized cash (excluded from the mark), so the mark is the redemption
  value `N` at par. `Deposit(face, rate, cashflows)` — 3 fields (under the new `fields` gate).
  - Oracles: forward par → 0; spot par → principal; off-par closed form; par → 0 on a bootstrapped curve.
  - **Deletable-bar read** (`fixed_income/deposit.py`): ng covers pricing + forward/temporal (the quarry
    values the redemption only). Residual before deletable: convention builder, implied-DF-as-method
    (ng has it via `DepositQuote`), `pv_ctx`, serialisation — logged in `quarry_reconciliation.md`.
    Drawdown 0/768.
  - quarry: `python/pricebook/fixed_income/deposit.py` · slice: `deposit-spine`

## [0.44.0] - 2026-07-17

### Added
- **Seasoned FRA via `FixingHistory` (L4) — CP-2c #2, fixings / seasoned-float.** The `FRAEngine`
  now handles the temporal cases (A2): a forward-starting/spot period uses the curve forward; a
  **seasoned** period (`accrual.start < valuation`) uses the realized reset looked up in the
  snapshot's `FixingHistory`; a fully-paid period (`end <= valuation`) settles to PV 0 (the shell
  remembers the realized cash). First `FixingHistory`-consuming engine — the swap float leg and the
  L6 float realized P&L follow the same pattern.
  - Oracles: seasoned FRA prices to `face·τ·(fixing−K)·DF(end)`; zero at `K = fixing`; missing fixing
    → `PricingFailure`; fully-paid → 0; forward FRA unchanged.
  - **Deletable-bar read** (`fixed_income/fra.py`): quarry ISDA-settle-at-start equals ng
    end-settle for single-curve (`DF(start)/(1+fwd·τ)=DF(end)`), and the quarry FRA lacks fixings
    (ng now ahead). Residual before deletable: multi-curve `forward_rate(projection_curve)`,
    `par_rate`/`pv_ctx`, convention builder — logged in `quarry_reconciliation.md`. Drawdown 0/768.
  - quarry: `python/pricebook/fixed_income/fra.py` · slice: `fra-seasoned-fixings`

## [0.43.0] - 2026-07-17

### Added
- **`verify.py fields` merge gate (CP-2c #1).** The dataclass-field analogue of `PLR0913` (which
  only sees function args): a value dataclass has **≤5 fields** unless it carries an explicit
  `# fields-exempt: <reason>` marker. AST-based, scans all `src/pricebook_ng`; added to `verify all`
  and `redesign/09` / `CLAUDE.md §3b`.

### Changed
- **Product field-bundling (behaviour-preserving).** Closes the FRA smell flagged at the CP-2b
  checkpoint. Bundled loose primitives into value objects that already exist —
  `Money` (notional/strike + currency) and `Accrual` (start + end + day_count):
  - `ForwardRateAgreement` 7→4 (`face: Money`, `accrual: Accrual`); `CDS`, `ZeroCouponInflationSwap`
    6→5 (`face: Money`); `EquityOption`, `CommodityOption` 6→5 (`strike: Money`, the strike price).
  - Engines read `.face.amount`/`.face.currency`/`.strike.amount`/`.accrual.*`; **all PVs byte-identical**
    (243 green), guarded by every product oracle.
  - Legit-wide aggregates carry `# fields-exempt:` markers: `MarketSnapshot` (A5 shape), `XvaReport`
    (output record), `XvaReportConfig` (config).
  - Not a parity slice (no quarry module retired) — code-quality; drawdown unchanged 0/768.
  - slice: `product-field-bundling`

## [0.42.0] - 2026-07-17

### Added
- **FRA — forward rate agreement (L2 product + L4 engine) — CP-2b #3, fixed_income spine.**
  `ForwardRateAgreement` (pure data) + `FRAEngine`: pay fixed, receive the simply-compounded
  forward `L(T1,T2) = (P(0,T1)/P(0,T2)-1)/τ` over one period, settled at T2 —
  `PV(pay-fixed) = notional·τ·(L-K)·P(0,T2)`, composed from the curve's discount factors so it
  prices on any curve (flat **or** bootstrapped — the general-curve payoff for the spine).
  - Oracles: a par FRA (K = L) reprices to zero; off-par matches the closed form; receiving fixed
    flips the sign; and the implied forward reprices to par on a bootstrapped curve.
  - Scope: forward-starting / spot (`accrual_start ≥ valuation`); a seasoned FRA needs a fixing
    (`FixingHistory`, a later slice, like the seasoned float leg).
  - **Parity:** first new fixed_income vanilla under the parity-depth mode; steps `fixed_income/fra`
    toward deletable. bond/swap already price on general curves; deposit / OIS / seasoned-float remain.
  - quarry: `python/pricebook/fixed_income/fra.py` · slice: `fra-spine`

## [0.41.0] - 2026-07-17

### Changed
- **General-curve Hull-White (L3) — CP-2b #2, the biggest single parity gap under the XVA stack.**
  HW no longer asserts `FlatDiscountCurve`: it reads `df` **and** `instantaneous_forward` from any
  curve, replacing the flat `r0` with the market forward `f(0,t)` in `alpha(t)` and the `zero_bond`
  reconstitution, and taking its time axis from `market.valuation_date`. `forward_short_rate` and
  the risk-neutral path simulator are now **date-based** (they need `f(0,t)`), and their callers
  (`swaption_mc`, the exposure/MPOR engines) pass dates.
  - **Byte-identical on a flat curve** (`f(0,t)=r0`), so every existing swaption / exposure / XVA /
    measure-consistency / MPOR oracle stays green (239 total).
  - New oracles on a **bootstrapped** curve: the model refits the initial curve
    (`zero_bond(0,S,f(0,0)) == P^M(0,S)`); ZCB-option put-call parity; a flat-pillars curve matches
    `FlatDiscountCurve` exactly; and the analytic swaption == the MC swaption (`rel=2%`).
  - **Parity:** the whole XVA/exposure stack can now run on a real bootstrapped curve, not just the
    flat skeleton — steps `models/hull_white` toward deletable (term-structure vol + per-currency +
    trees remain the gap). Drawdown still 0/768 (narrowed).
  - quarry: `python/pricebook/models/hull_white.py` · slice: `general-curve-hw`

## [0.40.0] - 2026-07-17

### Added
- **General-curve rate accessors (L1) — CP-2b #1, the first parity-depth slice.** Both discount
  curves gain `zero_rate` (continuously-compounded `-ln P(0,t)/t`) and `instantaneous_forward`
  (`f(0,t) = -d/dt ln P(0,t)`) — the capability a general-curve Hull-White needs where the flat
  curve used a constant `r0`. `FlatDiscountCurve` returns the constant `rate`; the log-linear
  `DiscountCurve` returns a piecewise-**constant** forward per segment (exact `-slope`, not
  finite-difference), via a shared `_bracket_slope` that also backs `df`.
  - Oracles: flat curve → constant rate; constant-rate pillars → that same constant forward
    everywhere; a rising curve's segment forward equals the analytic log-DF slope and its running
    integral reconstructs `-ln df` at each pillar; `zero_rate = -ln df/t`.
  - **Parity:** steps `core/discount_curve` toward deletable (adds 2 of its 3 rate accessors);
    `forward_rate` (simply-compounded) and pluggable interpolation remain the recorded gap.
    Unblocks CP-2b #2 (general-curve HW). Drawdown still 0/768 (partial cross, gap narrowed).
  - quarry: `python/pricebook/core/discount_curve.py` + `curves/` · slice: `general-curve-rates`

## [0.39.0] - 2026-07-16

### Added
- **Consolidated XVA report (L6, A6.2)** — completes the CP-1 cluster. `xva_report(swaps, model,
  numerics, config)` in `shell/xva_report.py` simulates a netting set's exposure **once** and
  returns every adjustment (CVA/DVA/BCVA/FVA/KVA/MVA) + the EE/PFE/EAD profiles, consolidating the
  six separate L5 calls. Lives at L6 because a per-counterparty netting set is a book of trades.
  - Netting-set exposure: new `netting_set_exposure(swaps, model, numerics, pfe_quantile)` (L5)
    sums each swap's value on **shared paths** so offsetting trades net; KVA uses the netting-set
    SA-CCR EAD runoff (`netting_set_ead` as-of each grid date). The economy (discount + both
    parties' survival curves) rides on `model.market` (A5), read directly by the integrators.
  - Oracles: a single-trade netting set reproduces each standalone L5 value exactly (one pass, same
    draws); a payer + mirror receiver nets the portfolio exposure to zero, collapsing the netted CVA.
  - Refactor: `_simulate_swap_values` is now the single-swap case of `_simulate_netting_set`
    (byte-identical, guarded by the measure/BCVA/stochastic reproducibility oracles).
  - quarry: `python/pricebook/risk/` + `desks/` · slice: `xva-report`

## [0.38.0] - 2026-07-16

### Added
- **L6 trade lifecycle — the first vertical up into the shell (A6.2).** Extends the A3
  Trade/Book/benefit-table stub to the full realized-vs-mark split. New `Trade.mark(market,
  numerics, engine)` (sum of the products' PVs + accrued as of the snapshot) and `Book.value(...)`
  (the book's mark = Σ trade marks, linearity), sharing a `_combine` helper; `BookedTrade.value`
  now delegates to `Trade.mark` and remembers the observed mark.
  - Oracle over a bond's life: at issue the mark equals the full discounted PV (realized = 0);
    mid-life the mark prices **only future flows** (the engine excludes the paid ones, A2) while
    the benefit table holds the realized cash; **dirty = clean + accrued** at a mid-period date;
    at maturity mark = 0 and realized = the total nominal; **book mark & realized are linear**
    across trades. So `realized + mark` is the trade's total economics (A3).
  - Deferred: SQLite persistence of the benefit table (`pnl_history` behind the persistence
    interface) is its own data-spine slice; float-leg realized needs fixings (seasoned-float slice).
  - quarry: `python/pricebook/core/book.py` + `pnl_history` · slice: `l6-trade-lifecycle`

## [0.37.1] - 2026-07-16

### Added
- **Measure-consistency binding oracle (L5, Amendment A6.1).** The exposure stack runs two
  simulators — the per-date **forward-measure** engine (EE/PFE profiles) and the **risk-neutral
  joint-path** engine (MPOR). A6.1 rules them one model under a change of numeraire
  (`E^Q[D·max(V,0)] = P(0,t)·E^{T_t}[max(V,0)]`), so they may never silently diverge. The new
  test binds them: the risk-neutral joint-path marginal, shifted by the analytic forward-measure
  drift `m(t)`, reproduces the forward-measure EE **and** PFE per date (two independent MC
  estimates of the same discounted exposure, agreeing to `rel=4%`). No behaviour change — the
  `_simulate_rate_paths` docstring/provenance now document the ratified relationship.
- Ratified **Amendment A6** in `redesign/02_spine.md` (exposure measure + first-L6 rulings) and
  the **checkpoint-&-review cadence** (`redesign/11`, `CLAUDE.md §6`): stop at ≤6 slices or a
  capability-cluster boundary; every checkpoint carries an oracle audit, quarry drawdown `N/768`,
  a challenge-me list, and a smell/debt scan.
  - slice: `measure-consistency-oracle` (CP-1, first of the A6 cluster)

## [0.37.0] - 2026-07-16

### Added
- **MPOR path-simulated exposure (L5)** — the residual exposure that survives full
  collateralisation. At a counterparty default the collateral reflects the value one margin
  period of risk ago, so `E_mpor(t) = mean max(V(t) - V(t - MPOR), 0)`. This needs the joint
  distribution of `V(t)` and `V(t-MPOR)`, so the slice adds `_simulate_rate_paths` — a
  **risk-neutral joint-path simulator** (exact Ornstein-Uhlenbeck steps on the HW state,
  `r = x + α(t)`) — and `mpor_exposure(swap, model, numerics, mpor_days)`.
  - Oracles: the path simulator reproduces the analytic HW/OU moments — marginal mean `α(t)`,
    variance `σ²(1-e^{-2at})/2a`, and cross-date covariance `e^{-a(t-s)}·var(s)`; a zero gap
    gives exactly zero exposure; exposure grows with the gap; it feeds a positive CVA.
  - **Provisional measure choice (flagged for review):** the EE/PFE profiles use per-date
    forward measure; this path simulator uses the risk-neutral measure. For the local MPOR
    *difference* the choice is second-order, but unifying the exposure stack onto one measure
    is a design question for the L5 brainstorm — see the handoff.
  - Scope: single swap, zero threshold; float valued via `notional - couponbond` at the
    pre-gap date too (float ≈ par, O(MPOR) error). Netting-set / threshold MPOR is a refinement.
  - quarry: `python/pricebook/risk/` · slice: `mpor-paths`

## [0.36.0] - 2026-07-16

### Added
- **Margined (collateralised) exposure (L5)**. `collateralized_exposure(swap, model, numerics,
  threshold)` models a two-way CSA with variation margin and an uncollateralised threshold `H`:
  collateral posts the mark beyond `H`, so exposure is capped — `E_coll = min(max(±V, 0), H)`.
  `H = 0` is fully collateralised (exposure 0); a huge `H` recovers the uncollateralised
  `exposure_profiles`. Feeds a collateralised CVA/DVA below the uncollateralised one.
  - Oracles: a huge threshold reproduces `exposure_profiles` exactly (same draws); zero
    threshold gives zero exposure; `σ=0` caps the deterministic exposure exactly (and the cap
    bites); collateralised CVA < uncollateralised CVA.
  - Fourth consumer of the extracted `_simulate_swap_values` (means, PFE quantiles, collateral).
  - Scope: marginal (per-date) model — the margin-period-of-risk close-out gap that leaves
    residual exposure under full collateralisation needs joint-path simulation, a later slice.
  - quarry: `python/pricebook/risk/` · slice: `margined-exposure`

## [0.35.0] - 2026-07-15

### Added
- **PFE-quantile / dynamic-IM engine (L5)**. `pfe_profile(swap, model, numerics, quantile)`
  returns the potential future exposure at confidence `q`: `PFE_q(t_j)` = q-quantile of
  positive exposure `max(V(t_j), 0)` across the simulated paths — the exposure tail the EPE
  averages over, and a high-quantile PFE doubles as a dynamic initial-margin proxy that feeds
  `mva`.
  - Oracle: because the remaining swap value is monotonic in the Gaussian short rate, the
    q-quantile of V equals V at the q-quantile of r — so `PFE_q(t_j) = max(V(t_j; r_q), 0)`
    with `r_q = forward_short_rate(t_j, Φ⁻¹(q))`, matched by MC (`rel=2%`); `σ=0` collapses it
    to the deterministic exposure; PFE rises with `q` and funds a positive MVA.
  - Refactor: extracted `_simulate_swap_values` (per-path V by date), now shared by the EE
    means (`exposure_profiles`) and the PFE quantiles — byte-identical MC (same seed/draws), so
    the CVA/BCVA/stochastic-EAD oracles stay exact.
  - Scope: PFE-as-IM proxy; a margin-period-of-risk IM on ΔV is the noted refinement.
  - quarry: `python/pricebook/risk/` · slice: `pfe-quantile`

## [0.34.0] - 2026-07-15

### Added
- **MVA — margin valuation adjustment (L5)**, completing the XVA family. `mva(im, snapshot,
  key, funding_spread)`: `MVA = s_F·Σ IM(t_i)·DF(t_i)·S(t_i)·τ_i` — the funding cost of posting
  initial margin over the trade's life, the **same survival-weighted funding annuity** as FVA
  and KVA (now three consumers of the shared `_annuity_adjustment`), with the IM profile in
  place of net exposure / capital.
  - Oracles: MVA on unit IM equals `s_F · RPV01`; linearity in spread and IM; a vertical where
    an IM profile taken as the SA-CCR PFE (AddOn) runoff feeds MVA to a positive charge matching
    its annuity.
  - `IM(t)` is an input — generating it (SIMM, or a dynamic MC-quantile IM over the margin period
    of risk) is the upstream slice, as the exposure engine is upstream of CVA.
  - quarry: `python/pricebook/risk/` · slice: `mva`

## [0.33.0] - 2026-07-15

### Added
- **Netting-set SA-CCR (L5)**. `netting_set_ead(trades, valuation_date)` aggregates a
  netting set of IR swaps (each `(swap, mark)`) the Basel way: signed effective notionals
  `D = δ·notional·SD·MF` (δ = +1 payer / −1 receiver) net within maturity buckets (<1y,
  1–5y, >5y) and combine across buckets with the supervisory correlations
  (`√(ΣD² + 1.4(D₁D₂+D₂D₃) + 0.6·D₁D₃)`), while the marks net into one replacement cost.
  - Oracles: a one-trade set equals single-trade `saccr_ead`; a payer + mirror receiver
    perfectly nets (signed notionals and marks cancel → EAD 0); a two-bucket set matches
    the hand-computed correlation aggregation; netting is sub-additive vs standalone EADs.
  - Refactor: extracted `_effective_notional_magnitude` and `_ead_from_addon` (the
    RC/multiplier/EAD assembly), now shared by the single-trade and netting-set paths.
  - Scope: single-currency IR hedging set, unmargined, no collateral — margined MF, other
    asset classes, and collateral haircuts remain later refinements.
  - quarry: `python/pricebook/risk/` · slice: `netting-saccr`

## [0.32.0] - 2026-07-15

### Added
- **Stochastic-mark SA-CCR EAD profile (L5)** — unifies the two halves of the capital
  stack. `stochastic_ead_profile(swap, model, numerics)` sets SA-CCR's replacement cost to
  the MC exposure engine's expected positive exposure instead of the ATM zero:
  `EAD(t_j) = α·(EPE(t_j) + AddOn_remaining(t_j))`. Because `EPE ≥ 0` pins the multiplier at
  1, this is `forward_ead_profile` with `mark = EPE(t_j)`, and decomposes exactly as
  `forward_ead(t_j) + α·EPE(t_j)` — both pieces already oracle-checked.
  - Oracles: exact decomposition into the deterministic PFE profile plus `α·EPE`; it dominates
    the ATM profile; and its KVA charge exceeds the ATM one (expected exposure adds capital).
  - Closes the loop end-to-end: MC exposure → SA-CCR RC → capital profile → KVA.
  - quarry: `python/pricebook/risk/` · slice: `stochastic-ead`

## [0.31.0] - 2026-07-15

### Added
- **Forward SA-CCR EAD profile → KVA (L5)** — closes the SA-CCR → capital → KVA loop.
  `forward_ead_profile(swap, valuation_date)` reprices SA-CCR at each future coupon date on
  the shrinking remaining trade (an EAD **runoff**), and `capital_profile(ead, risk_weight)`
  scales it to `8%·RWA` — the capital `K(t)` that `kva` charges the cost of capital on. Under
  the ATM assumption (expected mark = 0 → RC = 0, multiplier = 1) the runoff is the deterministic
  supervisory PFE, so the whole chain has a closed-form oracle.
  - Oracles: each `EAD(t_j)` equals the closed-form `α·SF·notional·SD·MF` on the remaining
    maturity (first point == single-date `saccr_ead`); the profile runs off monotonically;
    `capital = 8%·EAD·RW`; KVA on it equals the cost-of-capital annuity.
  - Refactor: `saccr_ead` now delegates to a param-level `_ead_ir(notional, S, E, mark)` shared
    with the runoff (guarded by the SA-CCR oracle, no behaviour change).
  - Scope: ATM-mark runoff; a stochastic-mark RC (expected positive exposure from the MC engine)
    is the noted refinement.
  - quarry: `python/pricebook/risk/` · slice: `forward-ead-kva`

## [0.30.0] - 2026-07-15

### Added
- **SA-CCR — Basel standardised counterparty EAD & RWA (L5)**. New `risk/saccr.py`:
  `saccr_ead(swap, mark, valuation_date) = α·(RC + PFE)` for a single-trade interest-rate
  netting set (unmargined, uncollateralised), plus `risk_weighted_assets(ead, risk_weight)`
  and `saccr_capital(rwa) = 8%·RWA`. RC = max(V,0); PFE = multiplier·AddOn with the IR
  supervisory factor (0.5%), supervisory duration (5% decay), unmargined maturity factor,
  and the 5%-floored multiplier; α = 1.4.
  - Oracles: a 10y ATM $100mm IRS has EAD ≈ 5.5% of notional (the published SA-CCR anchor);
    RC adds `α·mark` in the money; deep out-of-the-money the multiplier hits its 0.05 floor
    (EAD → `0.05·EAD_atm`); RWA/capital identities.
  - This is the regulatory EAD generator that both counterparty RWA and (extended to a
    forward profile) the KVA capital input build on.
  - Scope: single IR trade, one hedging set, no collateral/margin — netting-set buckets +
    correlations, margined MF, other asset classes, and collateral haircuts are later slices.
  - quarry: `python/pricebook/risk/` · slice: `saccr`

## [0.29.0] - 2026-07-15

### Added
- **KVA — capital valuation adjustment (L5)**. `kva(capital, snapshot, key, cost_of_capital)`
  in `risk/xva.py`: `KVA = γ_K·Σ K(t_i)·DF(t_i)·S(t_i)·τ_i` — the cost of capital charged on
  the capital profile `K(t)`, discounted and survival-weighted. The **same funding annuity as
  FVA** (the CDS RPV01 structure), with capital in place of net exposure and the hurdle rate in
  place of the funding spread.
  - Oracles: KVA on unit capital equals `γ_K · RPV01`; capital proportional to EPE
    (`K = k·EPE`) integrates as expected; linearity in the cost of capital.
  - `K(t)` is an input — generating it from a regulatory model (SA-CCR EAD → RWA → capital)
    is the upstream RWA slice, exactly as the exposure engine is upstream of CVA.
  - quarry: `python/pricebook/risk/` · slice: `kva`

### Changed
- Extracted the shared **`_annuity_adjustment`** (`rate·Σ profile·DF·S·τ`) now backing both
  FVA and KVA — a survival-weighted annuity, the CDS RPV01 structure. `fva` refactored onto it
  under its green oracle, no behaviour change.

## [0.28.0] - 2026-07-15

### Added
- **FVA — funding valuation adjustment (L5)**. `fva(exposure, snapshot, key, funding_spread)`
  in `risk/xva.py`: `FVA = FCA - FBA = s_F·Σ (EPE_i - ENE_i)·DF(t_i)·S(t_i)·τ_i` — the
  funding spread carried over each interval on the **net** exposure, discounted and
  survival-weighted (funding stops on default). Reuses the same `ExposurePair` as CVA/DVA.
  - Where CVA/DVA weight exposure by a *protection leg* (default increments × `(1-R)`), FVA
    weights it by a *funding annuity* `S·τ` — the CDS RPV01 structure. So the oracle: FVA on
    unit positive exposure equals `s_F · RPV01` (the survival annuity) exactly; plus a
    symmetric-exposure zero (cost cancels benefit) and linearity in spread and exposure.
  - Scope: symmetric funding spread, single survival curve, discounting-approach FVA
    (FVA/DVA overlap and own-vs-joint survival are known modelling debates, out of scope).
  - quarry: `python/pricebook/risk/` · slice: `fva`

## [0.27.0] - 2026-07-15

### Added
- **DVA + bilateral BCVA (L5)**. `dva`, `bcva`, and the `CreditParty` bundle in
  `risk/xva.py`. DVA is the mirror of CVA — expected gain from *our own* default while
  out of the money — which is exactly the CVA integral on the **negative** exposure
  profile (ENE) against our own survival curve, so `dva` reuses `cva` and
  `bcva(exposure, snapshot, counterparty, self_party) = CVA - DVA` (net credit charge;
  value adjustment is `-BCVA`). `CreditParty(key, recovery)` keeps `bcva` under the
  5-arg ceiling.
  - Oracles: ENE of a payer swap equals EPE of the mirror receiver swap (exact, same
    simulated rates); BCVA decomposes into `CVA - DVA`; a default-free self (Q≡1) zeroes
    DVA so BCVA collapses to unilateral CVA.
  - Scope: unilateral pair (exposure ⟂ default, no first-to-default survival weighting —
    a later refinement multiplies each term by the other party's Q(t)).
  - quarry: `python/pricebook/risk/` · slice: `bcva`

### Changed
- **`expected_exposure` → `exposure_profiles`**, now returning an `ExposurePair`
  (EPE **and** ENE) from a single MC pass — ENE is free from the same paths. `ExposurePair`
  and `ExposureProfile` (docstring generalised to `E[(±V)^+]`) live in `risk/xva.py`.

## [0.26.0] - 2026-07-15

### Added
- **Monte-Carlo expected-exposure engine (L5)** — generates the real `EE(t)` profile
  that CVA consumes. `expected_exposure(swap, model, numerics)` in `risk/exposure.py`
  simulates the Hull-White short rate to each grid date under that date's t_j-forward
  measure (one exact Gaussian draw) and reprices the remaining swap analytically via
  `zero_bond`, returning an `ExposureProfile`. Closes the exposure-generation gap left
  open by the CVA slice.
  - Oracles: (1) `sigma = 0` -> `EE(t_j)` equals the deterministic forward swap value's
    positive part, exact to `1e-8`; (2) the forward-measure identity — `P(0,t_j)·EE(t_j)`
    equals the analytic co-terminal swaption expiring at `t_j` (Jamshidian), matched by
    MC within `rel=2%` at 120k paths; (3) end-to-end into `cva` (positive, finite).
  - Consequence: feeding this `EE(t)` to `cva` (which multiplies by `DF(t_j)`) yields the
    correct discounted expected exposure `Σ_j swaption(t_j)·ΔQ_j` — CVA as a swaption strip.
  - quarry: `python/pricebook/risk/` · slice: `mc-exposure`

### Changed
- **`HullWhite.forward_short_rate(t, z)`** extracted as a model capability — the exact
  t-forward-measure short-rate draw, now shared by the MC swaption and MC exposure engines
  (rule of two). `coupon_bond_cashflows` now takes a `VanillaSwap` (three consumers), and
  `SwaptionMCEngine` reuses `forward_short_rate` — pure refactors under the green MC/analytic
  swaption oracles, no behaviour change.

## [0.25.0] - 2026-07-15

### Added
- **Unilateral CVA (L5 risk & capital)** — the first XVA. New `risk/xva.py` with an
  `ExposureProfile` (`EE(t) = E[(V(t))^+]` on a time grid) and
  `cva(profile, snapshot, key, recovery)` = `(1-R)·Σ EE(t_i)·DF(t_i)·(Q(t_{i-1})-Q(t_i))`.
  Structurally a CDS **protection leg** with the unit notional replaced by the exposure
  profile — CVA is protection bought on your own counterparty exposure.
  - Keyed to the counterparty survival curve in the snapshot (A5), reached through the
    `CurveHandle` `df` capability — so a credit bump (`bump_curve`/`credit01`) already
    yields CVA sensitivity, no new machinery.
  - Oracles: unit-exposure CVA **equals** the CDS protection leg (`cds_pv` at zero
    spread, already oracle-checked) to `1e-14`; linearity in exposure; a default-free
    (Q≡1) counterparty gives zero CVA.
  - Scope (unilateral): exposure ⟂ default (no wrong-way risk), own default ignored
    (that is DVA). **Exposure generation is upstream/out of scope** — `EE(t)` is an
    input (analytic for deterministic trades, MC for optional ones — a later slice).
  - quarry: `python/pricebook/risk/` · slice: `cva`

## [0.24.0] - 2026-07-15

### Added
- **Joint HW `(a, sigma)` calibration from a cap strip** — the calibration front's
  first multi-instrument least-squares fit. `calibrate_hull_white_cap(snapshot, quotes)`
  fits both mean reversion and vol to a strip of caplet (ZCB-option) quotes by
  minimising the repricing SSE. A single caplet can't separate `a` from `sigma`; a
  strip spanning expiries can (needs ≥2 quotes). `sigma` is fitted via its magnitude
  (price depends only on `sigma^2`), so the model carries `sigma >= 0`.
  - Oracles: round-trip recovers `(a*, sigma*)` from a self-priced strip
    (`a` to `1e-4`, `sigma` to `1e-5`); fitted model reprices the strip (SSE `< 1e-14`).
  - quarry: `python/pricebook/calibration/` · slice: `hw-cap-strip`
- **`nelder_mead` (L0 numerical toolkit)** — derivative-free downhill-simplex minimiser
  (Nelder & Mead 1965), the stdlib least-squares engine behind multi-parameter
  calibration (no scipy — the ng tree stays stdlib-pure, like `bisect_root`). Converges
  on **both** a flat objective and a small simplex, so a weakly identified direction
  (HW `a`) still pins down instead of drifting. Oracle: quadratic bowl + Rosenbrock.

## [0.23.0] - 2026-07-15

### Changed
- **Rate & credit bootstraps migrated under the L3 calibration front.**
  `bootstrap_discount_curve` and `bootstrap_survival_curve` move from `market/` (L1)
  to `calibration/` (L3), joining `calibrate_hull_white` as the per-family solvers of
  the unified front (`market -> calibrate -> model`). The curve *types*
  (`DiscountCurve`, `SurvivalCurve`) and market observables (`DepositQuote`,
  `ParSwapQuote`, `CDSQuote`) and CDS leg math (`cds_pv`, …) stay at L1 — quotes and
  curves are market data, the *solvers* are calibration. Each bootstrap still reprices
  with L1 closed forms (curve `df` / `cds_pv`), never the L4 engine, so `acyclic` stays
  green with `calibration` at rank 3.
  - Pure relocation guarded by the existing reprice-to-par / reprice-to-zero oracles
    (their tests move `tests_ng/L1 -> L3` accordingly). No behaviour change; 174 green.
  - Import path change: `from pricebook_ng.calibration.discount_curve import
    bootstrap_discount_curve` (was `...market.discount_curve`); likewise survival.

## [0.22.0] - 2026-07-15

### Added
- **Unified calibration front (L3), first tenant: Hull-White vol.** New
  `calibration/` package establishing `market -> calibrate -> model -> price` (A1):
  `calibrate_hull_white(snapshot, quote, a)` fits the HW `sigma` (with mean reversion
  `a` fixed) so the model reprices a `ZCBOptionQuote` — a caplet, i.e. a European
  option on a zero-coupon bond (Brigo & Mercurio s.3.3, the textbook HW vol instrument).
  - Correctly layered: the fit reprices with the model's own analytic `zero_bond_option`,
    **not** the L4 engine — calibration depends only on L0/L1/L3 (verify `acyclic` green
    with `calibration` at rank 3). The ZCB-option price is monotone in `sigma`, so one
    bracketed root pins it; an unreachable quote (below intrinsic) raises `ValueError`.
  - Oracles: round-trip sigma recovery (`abs=1e-9`); calibrated model reprices the quote
    (`abs=1e-10`); unreachable-quote raise.
  - Establishes the front's shape (`calibrate_*(snapshot, quotes, …) -> CalibratedModel`);
    the rate/credit curve bootstraps are the sibling solvers that migrate under it next.
  - quarry: `python/pricebook/calibration/` · slice: `calibration-front`

## [0.21.0] - 2026-07-15

### Added
- **Key-rate (bucketed) dv01.** `key_rate_dv01(priceable, snapshot, numerics)` in
  `risk/greeks.py` returns per-pillar KR01 for the home bootstrapped curve — bump one
  pillar's zero at a time (`DiscountCurve.bump_pillar(i, shift)`) and reprice. Log-linear
  interpolation tents each bump between neighbours, so the buckets **partition** the
  parallel `dv01` (Σ buckets = dv01). This turns the single parallel number into a
  per-tenor risk vector a hedger can actually neutralise.
  - Oracles: (1) buckets sum to `dv01` (partition of unity); (2) a cashflow landing
    exactly on pillar j is carried only by bucket j (`KR01_j = -N·t_j·DF(t_j)·1bp`,
    neighbours ~0, since the tent vanishes at the node).
  - quarry: `python/pricebook/core/discount_curve.py` · slice: `key-rate-buckets`

## [0.20.0] - 2026-07-14

### Added
- **Bootstrapped-curve dv01.** `DiscountCurve.bumped(shift)` — a parallel zero-rate
  shift (`DF -> DF·exp(-shift·t)` at every pillar), so log-linear interpolation keeps
  the shift uniform between pillars. `dv01`/`curve01` now compute rate risk on a real
  **bootstrapped** discount curve, not only the flat curve — closing the gap noted when
  generic curve greeks landed. Same shape as `SurvivalCurve.bumped`; `bump_rate` /
  `bump_curve` dispatch through it polymorphically (no `isinstance`).
  - Oracle: `dv01 = -1bp·Σ cf_i·t_i·DF_boot(t_i)` (analytic vs central-difference on the
    actual bumped curve); plus a check that every pillar's zero rose by exactly `shift`.
  - quarry: `python/pricebook/core/discount_curve.py` · slice: `bootstrapped-dv01`

## [0.19.0] - 2026-07-14

### Added
- **Generic curve greeks** (completes the A5 unification for curves). `curve01` /
  `bump_curve` in `risk/greeks.py` — parallel-shift the curve at a `MarketKey` and
  reprice, whatever the curve type. This gives rate risk on the **FX foreign curve**,
  the **inflation real/breakeven curve** (and dividend/carry) for free.
  - Curves gained a polymorphic `bumped(shift)`: `FlatDiscountCurve` shifts its rate,
    `SurvivalCurve` shifts its hazard (`Q -> Q·exp(-shift·t)`). `bump_curve` dispatches
    through it (no `isinstance`).
  - `credit01` is now a named alias of `curve01` on a survival key; `bump_hazard` is
    folded into `SurvivalCurve.bumped`. `dv01`/`bump_rate` use the same `bumped`.
  - Oracle: `curve01` on the FX foreign curve matches `-base·spot·T·DF_base·1e-4`; on
    the inflation real curve matches `notional·(-T·DF_real)·1e-4`; `credit01 == curve01`
    on a survival key; `bump_curve` shifts only the keyed curve.

### Deferred
- Pillar-wise / key-rate bumps for a **bootstrapped** curve (today `bumped` is a flat
  rate shift); home-discount `dv01` still assumes the flat curve.

## [0.18.0] - 2026-07-14

### Added
- **Inflation — zero-coupon inflation swap (first inflation slice).**
  - `products/inflation.py`: `ZeroCouponInflationSwap` (index, notional, fixed rate,
    maturity, currency, receive/pay inflation), pure data.
  - `engine/inflation.py`: `ZCISEngine` — the inflation forward index ratio
    `I(T) = DF_real(T)/DF_r(T)` (Fisher), with the real curve keyed at
    `MarketKey(INFLATION, index)`; receiver PV = `notional·DF_r·(I(T) − (1+K)^T)`.
  - `AssetClass.INFLATION` (a real curve is the only new market data — another cheap
    keyed asset class, A5).
  - Oracle: par ZCIS (K = breakeven) reprices to zero; PV matches the formula;
    receiver = −payer; below-breakeven fixed is valuable to the inflation receiver;
    missing real curve fails.

### Deferred
- Year-on-year inflation swaps and inflation-linked bonds; a breakeven/inflation01
  greek (bump the real curve, keyed — like `credit01`); seasonality; index lag.

## [0.17.0] - 2026-07-14

### Added
- **Commodity — European commodity option (first commodity slice).** The A5 keyed
  registry made it cheap: `AssetClass.CMDTY` + a `CommodityOption` product + a thin
  `CommodityOptionEngine`, and the **greeks are free** (the generic `spot_delta` /
  `vol_vega` work with no new code — the whole point of A5).
  - `engine/spot_option.py`: shared `price_spot_option(option, asset, model, numerics)`
    — Black-Scholes on the forward `F = spot·DF_carry/DF_r`, keyed by
    `MarketKey(asset, ticker)`. Behind both the equity (carry = dividends) and
    commodity (carry = convenience yield net of storage) engines.
  - **`EquityOptionEngine` refactored** onto the shared engine (rule of two;
    behaviour-preserving — the equity oracles stay green).
  - Oracle: put-call parity ties to the commodity forward; independent Black recompute;
    `sigma -> 0` intrinsic; missing market fails; and a demonstration that `spot_delta`/
    `vol_vega` price commodity greeks with no commodity-specific code.

### Deferred
- Commodity forward, seasonality/term-structure carry, futures vs spot, a vol surface.

## [0.16.0] - 2026-07-14

### Changed
- **Amendment A5 — `MarketSnapshot` keyed market-data registry.** All market data
  except the home `discount_curve` moves into `curves` / `spots` / `vols` maps keyed
  by `MarketKey(asset: AssetClass, id: str)` (new `market/keys.py`).
  - `survival_curve` / `fx_*` / `equity_*` fields are removed; folded into the maps.
    Folding survival **adds multi-issuer** — a `CDS` now names its `issuer`, and the
    engine looks up `curves[MarketKey(CREDIT, issuer)]`. `SurvivalCurve` gains a `df`
    alias (a hazard curve is the credit-risky discount-factor curve), so it lives in
    the same `curves` map as discount/dividend/foreign curves.
  - **Greeks collapse to one generic each**: `bump_spot`/`bump_vol` +
    `spot_delta`/`vol_vega` keyed by `MarketKey` — the per-asset `fx_delta`/`equity_delta`,
    `fx_vega`/`equity_vega`, `bump_fx_*`/`bump_equity_*` are deleted. `credit01`/`bump_hazard`
    are keyed by issuer. A new asset class now adds **keys, not fields, and no new greeks**.
  - Behaviour-preserving: every FX/equity/credit/rates PV and greek is unchanged
    (all prior oracles reused). New: a `MarketKey` namespacing test (FX "EUR" ≠ equity "EUR").
  - `cds(...)` builder drops the schedule-terms arg (CDS premiums are annual ACT/360 by
    convention) and takes `issuer` — stays within the 5-arg ceiling.

## [0.15.0] - 2026-07-14

### Added
- **Equity greeks** — `bump_equity_spot` / `bump_equity_vol` + `equity_delta` /
  `equity_vega` in `risk/greeks.py`, keyed by ticker, on the same `Priceable`
  protocol as FX and rate greeks. Oracle: the bumps move only their field;
  `equity_delta` matches the analytic BS delta `quantity·DF_div·N(d1)`; a put's
  delta is negative; `equity_vega` matches the analytic Black vega
  `quantity·DF_r·F·φ(d1)·√T`.

## [0.14.0] - 2026-07-14

### Added
- **Equity — European equity option (Black-Scholes with dividends), first equity slice.**
  - `products/equity_option.py`: `EquityOption` (frozen pure data — ticker, quantity,
    strike, maturity, currency, call/put).
  - `engine/equity_option.py`: `EquityOptionEngine` — Black-Scholes as Black-76 on the
    equity forward `F = spot·DF_div/DF_r`, discounted by `DF_r`; `PricingFailure` if the
    equity market is absent; expired → 0.
  - `MarketSnapshot`: `equity_spots` / `equity_div_curves` / `equity_vols`, keyed by ticker.
  - `foundation/black.py`: shared **`black_76`** primitive (option on a forward), used by
    both the equity (BS) and FX (GK) engines.
  - Oracle: put-call parity ties to the equity forward value; matches an independent Black
    recompute; `sigma -> 0` intrinsic; ATM-forward call == put.

### Changed
- `FXOptionEngine` refactored onto the shared `black_76` (behaviour-preserving; GK oracle
  stays green).

### Deferred
- Equity greeks (delta/vega, bump `equity_spots`/`equity_vols` through the `Priceable`);
  foreign-listed equity (own currency curve); a real dividend schedule vs the flat repo
  curve; a vol surface.

## [0.13.0] - 2026-07-14

### Added
- **FX vega** — `bump_fx_vol` + `fx_vega` (∂PV per unit FX vol) in `risk/greeks.py`,
  on the same `Priceable` protocol as `fx_delta`/`dv01`. Oracle: `bump_fx_vol` moves
  only that vol; `fx_vega` matches the analytic Black vega
  `notional·DF_quote·F·φ(d1)·√T`; a long option is long vol (vega > 0).

### Changed
- Removed `fx_forward_priceable` — it was byte-identical to `discounting_priceable`;
  all FX products (forward + option) now bind via `discounting_priceable`.

## [0.12.0] - 2026-07-14

### Added
- **FX option — Garman-Kohlhagen.**
  - `products/fx_option.py`: `FXOption` (frozen pure data — base/quote legs,
    maturity, call/put) + `fx_option(...)` builder.
  - `engine/fx_option.py`: `FXOptionEngine` — GK as Black-76 on the FX forward
    `F = spot·DF_base/DF_quote`, discounted by the quote curve; `sigma -> 0`
    collapses to discounted intrinsic; `PricingFailure` if the FX market is absent.
  - `MarketSnapshot.fx_vols`: flat FX vol per pair (market data, §5.1).
  - Oracle: put-call parity ties to the FX forward PV (cross-slice); matches an
    independent Black recompute; `sigma -> 0` intrinsic; ATM-forward call == put.

### Deferred
- FX vega (bump `fx_vols` through the `Priceable`, like `fx_delta`) — trivial
  follow-up; a vol surface (strike/tenor) replacing the flat vol; American/barrier.

## [0.11.0] - 2026-07-13

### Changed
- **FX market data promoted into `MarketSnapshot`** (ruling §5.1, closing the FX
  loop as survival-in-snapshot did for credit). The snapshot now carries
  `fx_curves` (foreign-currency curves) and `fx_spots` (home units per foreign
  unit), keyed by currency. `FXForwardModel` is removed — the FX forward is a
  linear product priced with a `DiscountingModel` over the snapshot; the engine
  looks up the base curve/spot by the product's base currency and returns
  `PricingFailure` if the FX market is absent.

### Added
- **FX greeks on the `Priceable` protocol.** `bump_fx_spot` + `fx_delta` (∂PV per
  unit spot) in `risk/greeks.py`; `fx_forward_priceable` factory. The same FX
  Priceable feeds both `fx_delta` (spot bump) and the generic `dv01` (quote-curve
  bump).
  - Oracle: FX data lives in the snapshot; `bump_fx_spot` moves only that spot;
    `fx_delta` matches the analytic `base_notional·DF_base(T)`; sell = -buy; the
    same Priceable gives a non-zero `dv01`.

### Deferred
- Base-currency rate risk (bump `fx_curves`), a currency→curve map replacing the
  home/foreign split, FX options (Garman-Kohlhagen), and a `CurrencyPair` type.

## [0.10.0] - 2026-07-13

### Added
- **FX — FX forward (first FX slice).**
  - `products/fx_forward.py`: `FXForward` (frozen pure data — base leg, quote leg,
    maturity, buy/sell) and an `fx_forward(...)` builder taking a strike.
  - `models/fx_model.py`: `FXForwardModel(market, base_curve, spot)` — the quote-
    currency market + the base-currency curve + spot (quote per base).
  - `engine/fx_forward.py`: `FXForwardEngine` — values both legs in the quote
    currency by covered interest parity; buyer PV = base leg − quote leg; a matured
    forward settles to 0 (A2).
  - Oracle: a par forward (struck at `F = spot·DF_base/DF_quote`) prices to zero;
    PV matches CIP; sell = −buy; below-forward strike is valuable to the buyer;
    matured forward settles.

### Deferred
- Promote FX market data (base curve + spot) into the `MarketSnapshot` and unify
  FX greeks (delta, per-currency rate risk) on the `Priceable` protocol — the
  §5.1 follow-up, exactly as the CDS survival curve was promoted (multi-currency
  snapshot: curves keyed by currency + FX spots).
- FX options, NDFs, and a real `CurrencyPair`/quoting-convention type.

## [0.9.1] - 2026-07-13

### Changed
- Spelling fix: **`Pricable` → `Priceable`** everywhere — the `Priceable` protocol,
  the `discounting_priceable` / `hull_white_priceable` / `credit_priceable`
  factories, the module (`risk/priceable.py`), and the design docs (`CLAUDE.md`,
  `redesign/`). Pure rename, behaviour-preserving (all oracles green).

## [0.9.0] - 2026-07-13

### Changed
- **SurvivalCurve promoted into `MarketSnapshot`** (Cowork ruling §5.1). The
  credit/hazard curve is market data, so it now lives on the snapshot
  (`survival_curve`, reached through a new `SurvivalHandle` protocol, mirroring
  `CurveHandle`). `CreditModel(market, recovery)` reads it via `market.survival_curve`
  (its `survival` field is now a property).
- **Credit risk unified on the `Pricable` protocol.** `credit01` (CS01) moved into
  `risk/greeks.py` alongside `dv01`, both central-differencing a `Pricable` under a
  snapshot bump (`bump_rate` / `bump_hazard`) — one finite-difference core.
  `risk/credit_greeks.py` is removed.
  - `credit_pricable(product, recovery, engine, numerics)` builds the credit
    `Pricable`; the same pricable feeds both `credit01` (hazard bump) and `dv01`
    (rate bump) — a CDS now has rate risk *and* credit risk through one interface.
  - CDS pricing is behaviour-preserving (all prior oracles green).
  - Oracle: survival lives on the snapshot; `bump_hazard` moves only the credit
    curve; buyer credit01 > 0, seller = -buyer; matches an independent hazard FD;
    the CDS pricable also yields a non-zero rate dv01.

## [0.8.0] - 2026-07-13

### Added
- **Float-leg fixings — seasoned swaps** (consumes the `FixingHistory` A1 added).
  - The `SwapEngine` float leg is now temporality-aware: a period that already
    paid (`b <= valuation`) is settled; a period whose reset is strictly past
    (`a < valuation`) uses the realized fixing `market.fixings.get(a)`; a future
    period projects the curve forward. Missing fixing ⇒ `PricingFailure`.
  - `FloatLeg` gains `day_count` (needed to accrue a fixed current period from its
    reset); `vanilla_swap` sets it from the float schedule.
  - The old "float leg starts before valuation" guard is retired.
  - Oracle: a seasoned swap's current coupon uses the fixing and matches the
    independent per-period sum; an already-paid period is excluded; a missing
    fixing fails; a spot swap needs no fixings (behaviour-preserving).

### Deferred
- Fixing lag (reset a few days before accrual start), and swap-level accrued/clean
  decomposition on the float leg — add when needed.

## [0.7.0] - 2026-07-13

### Added
- **Monte-Carlo engine — HW swaption, `analytic vs MC convergence`** (closes the
  named oracle for the whole Hull-White arc).
  - `engine/swaption_mc.py`: `SwaptionMCEngine` prices the European swaption under
    the T0-forward measure — one exact Gaussian draw of `x(T0)` (mean `M`, variance
    `V`), reconstitutes the coupon bond via the model's `zero_bond`, averages the
    payer/receiver payoff, discounts by `P(0,T0)`. Stdlib `random`, no numpy.
  - `NumericalConfig` gains `mc_paths` and `mc_seed` (fixed seed ⇒ reproducible,
    referential transparency preserved).
  - `engine/swaption.py`: extracted the shared `coupon_bond_cashflows` helper (used
    by both the analytic and MC engines; analytic oracle preserved).
  - Oracle: MC converges to the S08 Jamshidian analytic within ~2% at 200k seeded
    paths (payer and receiver); exact at `sigma=0` (deterministic); reproducible
    under a fixed seed.

### Deferred
- Variance reduction (antithetics, Sobol), a general MC path engine for other
  products, and MC greeks — added when a product needs them.

## [0.6.0] - 2026-07-13

### Added
- **CDS credit01 / CS01** (`risk/credit_greeks.py`) — CDS PV sensitivity to a 1bp
  parallel credit-spread (hazard) shift, by central finite difference: `bump_hazard`
  scales each survival pillar by `exp(-dh*t)`, rebuilds the `CreditModel`, reprices.
  The hazard analogue of `dv01` (which bumps the discount rate).
  - Oracle: `bump_hazard` shifts each pillar by exactly `exp(-dh*t)` (anchor
    unchanged); buyer credit01 > 0 (protection gains as credit worsens); seller =
    -buyer; matches an independent hazard-bump central difference.

### Deferred
- Routing credit01 through a `survival -> PV` closure (like the `Pricable`
  factories) — added when a second hazard-sensitive product exists; today CDS is
  the only one, so it calls `CDSEngine` directly.

## [0.5.0] - 2026-07-13

### Added
- **CDS as an engine-priced product.**
  - `products/cds.py`: `CDS` (frozen pure data — premium schedule, spread,
    notional, buyer/seller) and a `cds(...)` builder.
  - `models/credit_model.py`: `CreditModel(market, survival, recovery)` — carries
    the discounting market + the bootstrapped hazard curve + recovery (A1).
  - `engine/cds.py`: `CDSEngine` — values the protection buyer via the L1 CDS leg
    math; the seller is the negative.
  - Oracle: a par CDS reprices to zero through the engine; the engine matches the
    L1 `cds_pv`; seller = -buyer; buyer value falls as the contract spread rises.

### Deferred
- CDS greeks — a `credit_pricable` factory drops the CDS onto the L5 `Pricable`
  protocol (rate dv01 today, credit01 once a hazard bump exists); add when wanted.
- Seasoned CDS (segment-and-settle on the premium leg) and quarterly premiums.

## [0.4.0] - 2026-07-12

### Added
- **Credit — hazard/survival curve + CDS bootstrap (first credit slice, L1).**
  - `market/survival_curve.py`: `SurvivalCurve` (piecewise-hazard, log-linear in
    `ln Q`, behind `survival(date)`), the single-name CDS leg math (`RPV01`,
    protection PV, `cds_par_spread`, `cds_pv` for the protection buyer), and
    `bootstrap_survival_curve` — sequential solve so each CDS reprices to zero at
    its par spread.
  - Oracle: `survival(valuation)=1`; each input CDS reprices to zero (`< 1e-10`);
    the curve-implied par spread equals each quote; survival strictly decreasing in
    (0,1]; log-linear between pillars. Mirrors the S03 discount-curve bootstrap.
  - Quarry: `core/survival_curve.py`.

### Deferred
- CDS as an **engine-priced product** (L2 `CDS` product + L3 `CreditModel` +
  L4 `CDSEngine` + greeks via `Pricable`) — the immediate follow-up, exactly as the
  discount curve preceded the bond/swap.
- Quarterly premiums, accrual-on-default, and a finer protection integral (the
  reprice-to-zero oracle is exact on the shared discretisation regardless).

## [0.3.0] - 2026-07-12

### Added
- **Risk relocated to L5 on the `Pricable` protocol** (spine structural fix).
  - `risk/pricable.py`: `Pricable` — a `snapshot -> PV` closure that risk consumes;
    factories `discounting_pricable` (linear products, any engine over a
    `DiscountingModel`) and `hull_white_pricable` (rebuilds HW under the snapshot).
  - `risk/greeks.py`: generic `dv01` (central-difference bump-and-reprice) and
    `bump_rate` (parallel shift). One `dv01` prices rate delta for a cashflow, a
    bond, a swap, and an HW swaption — the swaption rebuilds the model under the
    bumped snapshot (Amendment A1). **No `isinstance`-on-product ladders.**
  - Oracle: `dv01` matches the analytic sensitivity for a single cashflow and a
    bond (`< 1e-6`); is generic over any `Pricable` (a raw closure); and for the HW
    swaption equals a manual rebuild-and-reprice bump (the model-rebuild path).

### Changed
- The Slice-0 `risk/dv01.py` (specific to `DiscountingModel`) is replaced by the
  generic `risk/greeks.dv01` on the `Pricable` protocol; its analytic-vs-FD oracle
  is preserved through the new API.

### Deferred
- Higher greeks (gamma, vega), pillar-wise bumps of a bootstrapped curve, and
  XVA/RWA — all land on the same `Pricable` protocol in later slices.

## [0.2.0] - 2026-07-12

### Added
- **Amendment A3 — Product / Trade / Book + the benefit table (L6 shell).**
  - `shell/booking.py`: `Trade` (a collection of products + a start date), `Book`
    (a collection of trades), and `BookedTrade` with the **benefit table** —
    `realized(as_of)` sums cashflows that have already paid as actual cash, **never
    discounted**. `value(...)` aggregates the products' marks (dirty PV + accrued).
  - Oracle: realized at issue is 0; realized sums paid cashflows undiscounted;
    realized + remaining nominal = total nominal; at end of life realized = total
    and the mark is 0; a `Book` aggregates realized across trades.

### Changed
- **Renamed the L2 atom `instrument -> product`** (Amendment A3): the
  `instruments/` package is now `products/`; `FixedCashflowTrade -> FixedCashflow`;
  the engine protocol `CashflowInstrument -> CashflowProduct`. "Trade" is now an
  L6 concept (a collection of products), freeing the name. Behaviour-preserving.
- CI layer tier bumped to `--layer 6` (the slice reaches the L6 shell).

### Deferred
- Realized P&L for float legs (needs fixings) — wired with a seasoned-float slice.
- Per-product model dispatch in `Trade.value` (all products are linear today, so
  one `DiscountingModel` suffices); a registry/facade arrives when a trade mixes
  model families.

## [0.1.0] - 2026-07-12

### Added
- **Amendment A2 — valuation is temporality-aware.** The engine partitions a
  product's cashflows by `model.market.valuation_date`:
  - cashflows on or before valuation are **historical** — excluded from PV (the
    shell settles them), never discounted; the "fail on past cashflow" guard is
    retired in favour of **segment-and-settle**.
  - future cashflows discount from valuation.
  - `PricingResult` is now a **decomposition**: `pv` (dirty), `accrued`
    (earned-but-unpaid, nominal), and `clean = pv - accrued`.
  - `Cashflow` gains an optional `Accrual(start, end, day_count)`; fixed-leg
    coupons carry it, so a **seasoned bond** accrues the current period on its own
    day count.
  - Oracle (closed-form, exact): seasoned bond excludes paid coupons and matches
    the sum over remaining flows; forward-starting prices only future flows;
    accrued matches the day-count fraction; `dirty = clean + accrued`; a cashflow
    exactly on the valuation date is historical.
  - Behaviour-preserving for at-issue/forward pricing (accrued = 0): every prior
    oracle stays green.

### Deferred
- Fixing resolution for seasoned **float** legs (reset ≤ valuation → realized
  `FixingHistory`) — no such instrument present yet; wired when one arrives (A3+).

## [0.0.11] - 2026-07-12

### Changed
- **Amendment A1 — the engine depends on the model, not a market argument.**
  `price(product, model, numerics)`: the model carries the `MarketSnapshot` it was
  calibrated to (`model.market`); the engine reaches curves/valuation-date through
  it. Market/model mismatch is now structurally impossible (there is no second
  market to pass). Behaviour-preserving — every S00–S08 oracle stays green.
  - New L3 `DiscountingModel(market)` (thin model for linear products) and a
    `CalibratedModel` protocol.
  - `HullWhite` now carries a `MarketSnapshot` instead of a bare curve.
  - `DiscountingEngine` / `SwapEngine` / `SwaptionEngine` drop the `market` arg;
    `book.value` builds the model for the date's snapshot; `dv01` bumps the
    snapshot and rebuilds the model (risk flows through the model).
  - `FixingHistory` is now first-class on `MarketSnapshot` (empty default; the
    economy = curves + fixings). Its seasoned-period consumer lands with A2.
  - Oracle: engine-model binding test (no `market` param; a model only prices
    against its own snapshot) + unchanged PVs.

### Ratified
- `CLAUDE.md` §0/§2/§3 and `redesign/02_spine.md` Amendments A1/A2/A3 (Cowork).

## [0.0.10] - 2026-07-12

### Added
- **S08 — Hull-White European swaption (Jamshidian).**
  - `instruments/swaption.py`: `Swaption(expiry, swap)` — a European option on a
    forward-starting `VanillaSwap` (payer/receiver via `swap.pay_fixed`), pure data.
  - `engine/swaption.py`: `SwaptionEngine` — Jamshidian decomposition into a
    portfolio of HW ZCB options (S07), with a bisection solve for the critical
    rate `r*` that prices the coupon bond at par.
  - `models/hull_white.py`: `zero_bond` reconstitution `P(T,S) = A e^{-B r}` (the
    state-dependent bond price the Jamshidian solve needs).
  - `foundation/solvers.py`: `bisect_root` — bracketed bisection (first root-finder
    of the L0 toolkit, migrated on demand).
  - Oracle (closed-form, exact): put-call parity `payer - receiver ==
    P(0,T0)*notional - sum(c_i P(0,t_i))`; ATM symmetry (payer == receiver at the
    forward par rate); `sigma -> 0` collapses to the discounted intrinsic
    `max(forward swap PV, 0)`, cross-checked against the S06 `SwapEngine`.
  - Quarry: `fixed_income/` (swaption), `pricing/`, `core/solvers.py`.

### Deferred
- MC engine + analytic-vs-MC convergence oracle (the **next slice, S09**), where
  `NumericalConfig` gains the MC knobs (`mc_paths`, `mc_seed`).

## [0.0.9] - 2026-07-12

### Added
- **S07 — Hull-White 1F analytic core (first L3 model).**
  - `models/hull_white.py`: `HullWhite(a, sigma, curve)` fitted to a flat curve
    (reprices it by construction); the `B(t,T)` factor and the closed-form
    European option on a zero-coupon bond (Brigo & Mercurio 3.40-3.41).
  - `foundation/distributions.py`: `norm_cdf` via `math.erf` — first piece of the
    L0 numerical toolkit, migrated on demand (dependency-free).
  - Oracle (all closed-form, exact < 1e-12): the model refits the initial curve;
    `B(t,T) -> (T-t)` as `a -> 0`; ZCB-option put-call parity
    `call - put == P(0,S) - K*P(0,T)`; `sigma -> 0` collapses to discounted
    intrinsic; and a match against an independent recompute of the ZBC formula.
  - Quarry: `models/` (hull_white), `numerical/_distributions.py` (norm_cdf).

### Deferred
- HW swaption engine (Jamshidian decomposition) + analytic-vs-MC convergence —
  the **next slice (S08)**, where the MC engine and `NumericalConfig` MC knobs land.
- General (bootstrapped) curve fit, time-dependent `a`/`sigma`, and the L3/L4
  boundary for analytic-model option formulas (flagged for the L3 report).

## [0.0.8] - 2026-07-12

### Added
- **S06 — vanilla single-curve interest-rate swap.**
  - `instruments/swap.py`: `FixedLeg`, `FloatLeg` (structural — schedule + face
    only), `VanillaSwap`, `SwapTerms`, and a `vanilla_swap(...)` builder.
  - `engine/swap.py`: `SwapEngine` — discounts the fixed leg (reusing
    `DiscountingEngine`) and computes the float leg's coupons as the curve's
    forwards (`DF(a)/DF(b) - 1`) at pricing time; NPV is payer/receiver aware.
  - `instruments/leg.py`: shared `fixed_coupon_cashflows` — one definition of a
    fixed leg's coupons, now used by both the bond and the swap (rule of two).
  - Oracle: par swap reprices to zero NPV; float leg telescopes to
    `notional*(DF(start)-DF(maturity))`; off-par NPV `= notional*annuity*(par-rate)`;
    receiver `= -payer`; and a swap matching an S03 bootstrap input reprices to ~0.
  - Quarry: `fixed_income/` (swap / fixed + float legs).

### Changed
- `fixed_rate_bond` builds its coupons via the shared `fixed_coupon_cashflows`
  (behaviour identical; the S04 bond oracle stays green).

### Deferred
- Multi-curve (OIS discount / IBOR projection), basis spread on the float leg,
  and an engine registry/facade selecting engine per instrument — no consumer yet.

## [0.0.7] - 2026-07-12

### Changed
- Signature discipline (CLAUDE.md §3b) is now enforced by the **CI ruff step**
  (`ruff check src/pricebook_ng`, rule `PLR0913`/`max-args=5`) rather than a
  bespoke `verify.py signatures` check — aligning with `redesign/09` ("same CI
  ruff step, not a bespoke checker"). `ruff.toml` is unchanged (it's the config
  that step reads); `verify.py signatures` is removed.
- Ratified the `CLAUDE.md §3b` and `redesign/09` guardrail text (previously
  uncommitted).

## [0.0.6] - 2026-07-12

### Added
- **Signature discipline (CLAUDE.md §3b).** New `verify.py signatures` check —
  the 5-argument ceiling (ruff `PLR0913`/`max-args=5`), enforced in the merge
  gate and CI; `self`/`cls` and `*args`/`**kwargs` are not counted. Root
  `ruff.toml` carries the matching `PLR0913` rule for editor/dev feedback
  (quarry `python/` exempt).
- Frozen grouping value objects to collapse wide signatures:
  `CouponPeriod` (ICMA anchors), `RollRule` (calendar / business-day / eom),
  `ScheduleTerms` (frequency / day-count / roll).

### Changed
- `year_fraction(start, end, convention, *, period=None, calendar=None)` — ICMA
  anchors bundled into `CouponPeriod` (7→5 args).
- `generate_schedule(start, end, frequency, roll=None)` — roll conventions
  bundled into `RollRule` (6→4 args).
- `fixed_rate_bond(face, coupon_rate, start, maturity, terms)` — notional+currency
  as `Money` face, schedule/accrual conventions as `ScheduleTerms` (9→5 args).
- No behaviour change: every S00–S04 oracle stays green (same expected values).

## [0.0.5] - 2026-07-11

### Added
- **S04 — fixed-rate bond (first L2/L4-pricing slice).**
  - `instruments/fixed_rate_bond.py`: `FixedRateBond` (frozen pure data — coupon
    + redemption cashflows, no `pv` method) and a `fixed_rate_bond(...)` builder
    that expands schedule + day-count into explicit `Cashflow`s.
  - Oracle: closed-form discounted-cashflow PV on a flat curve and on the S03
    bootstrapped curve (independent sum), exact < 1e-12; plus cashflow-structure
    checks and the zero-coupon tie-back to the Slice 0 pure-discount result.
  - Quarry: `fixed_income/` (fixed-rate bond / fixed leg).

### Changed
- `engine/discounting.py` generalised from a single cashflow to a **cashflow
  leg**: it now prices any instrument satisfying the structural
  `CashflowInstrument` protocol (`.cashflows`) — no `isinstance`, no import of
  concrete instrument classes. `FixedCashflowTrade` gained a `.cashflows` view;
  the Slice 0 oracle stays green.
- CI layer tier bumped to `--layer 4` (the slice now prices through the engine).

### Deferred
- Seasoned-bond pricing (dropping already-paid coupons), accrued interest / clean
  vs dirty price, and business-day-adjusted coupon dates — no consumer yet.

## [0.0.4] - 2026-07-11

### Added
- **S03 — bootstrapped discount curve (first L1 slice).**
  - `market/discount_curve.py`: `DepositQuote`, `ParSwapQuote`, a log-linear
    interpolated `DiscountCurve` (behind the existing `CurveHandle`), and
    `bootstrap_discount_curve` — deposits give short-end DFs in closed form,
    par swaps extend the curve by a sequential closed-form solve (single-curve).
  - Oracle: every input reprices to par — deposits to their closed-form DF, swaps
    to zero NPV via the single-curve telescoping identity — exact < 1e-12; plus
    df(valuation)=1, strictly-decreasing DFs, and the log-linear interpolation law.
  - Quarry: `core/discount_curve.py`.
- CI layer tier bumped to `--layer 1` (the slice now reaches L1).

### Deferred
- Business-day-adjusted curve pillars, multi-curve (OIS discount / IBOR
  projection), non-pillar swap coupons (interpolated bootstrap), and QuantLib
  cross-check — the closed-form self-consistency oracle is stronger here; these
  arrive with the slices that need them.

## [0.0.3] - 2026-07-11

### Added
- **S02 — schedule & business-day calendar.**
  - `foundation/calendar.py`: `BusinessDayConvention` (UNADJUSTED / FOLLOWING /
    MODIFIED_FOLLOWING / PRECEDING / MODIFIED_PRECEDING) and a minimal
    data-driven `Calendar` (weekend + explicit holiday set) with `is_business_day`,
    `adjust`, `business_days_between`.
  - `foundation/schedule.py`: `Frequency` and `generate_schedule` — regular
    periods, short front stub (backward generation), EOM roll, optional
    business-day adjustment. No third-party dependency (stdlib month arithmetic).
  - `foundation/time.py`: BUS/252 completed now that calendars exist.
  - Oracle: hand-computed reference dates/counts (adjustments, coupon schedules
    incl. EOM + short front stub, BUS/252 day counts) — exact.
  - Quarry: `core/calendar.py`, `core/schedule.py`, `core/day_count.py` (BUS/252).

### Deferred
- Concrete national calendars (TARGET, US, London, Sao Paulo, ...) and long/back
  schedule stubs — no current consumer; they land with the instrument slice that
  first needs them (avoids the quarry's approximate long-stub heuristic).

## [0.0.2] - 2026-07-11

### Added
- **S1 — day-count conventions.** Extended `foundation/time.py` beyond the
  Slice 0 ACT/365F stub to the calendar-free conventions: ACT/360, 30/360
  (US bond basis), 30E/360 (Eurobond basis), ACT/ACT ISDA, ACT/ACT ICMA.
  - Oracle: published ISDA 2006 s.4.16 / ICMA Rule 251.1 year-fraction vectors,
    each expected value written as the convention's defining arithmetic, exact
    < 1e-12.
  - Quarry: `core/day_count.py`.

### Changed
- ACT/ACT ICMA now **requires** its coupon-period anchors (`ref_start`,
  `ref_end`, `frequency`) and raises when they are missing or invalid.

### Removed
- Debt shed (CLAUDE.md §5): the quarry's `strict_icma` flag and its silent
  fallback to ACT/365F on missing anchors (audit finding A.1 B1 — hidden
  wrongness) does not cross into the new tree.

### Deferred
- BUS/252 day-count, business-day `Calendar`, and `Schedule` generation move to
  their own slice (they need the calendar); not part of S1's named oracle.

## [0.0.1] - 2026-07-11

### Added
- **Slice 0 — walking skeleton.** A single fixed cashflow discounted on a flat,
  continuously-compounded curve, priced end-to-end L0->L6 through the stateless
  engine. Proves the spine holds before any further migration.
  - L0 `Money`/`Currency`, `Cashflow` (promoted from `fixed_income`),
    `year_fraction` (ACT/365F), `NumericalConfig`, `PricingResult`/`PricingFailure`.
  - L1 `MarketSnapshot` + `FlatDiscountCurve` behind a `CurveHandle` (df = exp(-r t)).
  - L2 `FixedCashflowTrade` (frozen, no `pv` method).
  - L4 `DiscountingEngine.price(...)` (null model; failure-as-value).
  - L5 `dv01` by bumping the snapshot; L6 `book(trade).value(...)`.
  - Oracle: PV = notional·exp(-r·t) closed form < 1e-12; analytic vs
    central-difference DV01 < 1e-6; repricing byte-identical (statelessness).
  - Quarry: `core/currency.py`, `core/day_count.py`, `core/numerical_config.py`,
    `core/discount_curve.py`, `fixed_income/fixed_leg.py` (Cashflow).

## [0.0.0] - 2026-07-11

### Added
- Bootstrap of the new tree: layer packages (`foundation`, `market`,
  `instruments`, `models`, `engine`, `risk`, `shell`), `verify.py`
  (`acyclic`/`tests`/`debt`/`provenance`/`version`/`all`), CI matrix
  (Ubuntu + Windows, Python 3.12), `.gitattributes` (LF), root `conftest.py`.
