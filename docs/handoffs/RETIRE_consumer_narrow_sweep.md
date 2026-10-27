# Retire — the consumer-narrow sweep

**Date:** 2026-10-27 · **By:** Code · **Answers:** `spec_consumer_narrow_sweep.md` (thread 0046) ·
**Baseline:** v0.129.0, drawdown 26 / 793. **Read/analysis pass — nothing ticked, no tracker edit.**

## Headline

| verdict | count | modules |
|---|---|---|
| **TICK-now** | **6** | `credit/credit_risk` · `options/implied_vol` · `options/vol_surface` · `options/capfloor` · `options/swaption` · `credit/cds_market` |
| **PARTIAL-cheap** | **4** | `options/sabr` · `fixed_income/swap` · `credit/cds` · `fixed_income/floating_leg` |
| **RESIDENT** | the rest | see §4 |

**10 modules, ~3,900 quarry lines, carrying a real backlog** → on the spec's own decision rule
(§4: "a real backlog ⇒ (b) is vindicated; harvest them") **(b) continues and (c)/equity waits.**
This is not a near-miss: six modules have their *entire production consumed surface* already
superseded by what ng shipped, and they were invisible to feature-diffing because each is mostly
code nothing imports.

## 1. Method, and what makes the numbers trustworthy

Built an **AST importer graph** over all 793 quarry modules (`from X import n`, `import X`, relative
imports, and `from pkg import submodule` resolved to the submodule). For each candidate that gives
the **exact names its live production importers bind** — which is what §4's consumed-surface rule
asks for, and is strictly better than grep because it sees multi-line parenthesised imports.

Three deliberate guards, each of which changed an answer:

1. **Attribute-level surface.** A class name understates consumption — the importer also calls
   methods. Walked every importer's AST for attribute access on the candidate's methods. This is
   what found the variable-notional split in `fixed_income/swap` (§3).
2. **Generic-name disambiguation.** The bare-name grep the dead-protocol mandates **over-reports**:
   `cs01` has 155 quarry hits, `mark_to_market` 15, `roll_pnl` 32 — almost all of them *other
   modules' own definitions*. Every such hit was re-tested for whether it actually reaches the
   candidate module (`from <dotted> import n`, `<mod>.n`, `getattr(<mod>, "n")`). **All of them
   resolved to zero.** A sweep that skipped this step would have reported ~5 false RESIDENTs.
3. **Tests counted separately.** §4's `dead` bar is "no consumer anywhere in the quarry, incl. its
   tests", so the test-side import graph was built too. Most omitted names are **test-only**, not
   `dead` — reported as its own category rather than folded into `dead`, because the distinction is
   Cowork's to rule, not mine to assume.

**One bug found, not mine:** `models/rough_vol.py:190` does
`from pricebook.options.implied_vol import implied_vol_newton` — **that name does not exist.** It is
a lazy import inside a function, so it only raises when that path runs
(`ImportError: cannot import name 'implied_vol_newton'`, verified). It is therefore **not a real
consumer**, which is why `options/implied_vol` has 7 live importers and not 8.

## 2. TICK-now — consumed production surface fully superseded

| module | L | live importers · names they bind | ng supersedes with | omissions (classified) |
|---|---|---|---|---|
| `credit/credit_risk.py` | 294 | 5 · `_bump_survival_curve`, `_bump_survival_curve_at` | `risk/bump.py: SurvivalBump`, `SurvivalPillarBump` — the parallel-hazard and per-segment bumps, *exactly* these two | `cs01`, `jump_to_default` → **superseded** (`risk/credit.py` has both); `spread_dv01`, `CreditPosition`, `CreditBook` → test-only (ng: `shell/portfolio.Book`) |
| `options/implied_vol.py` | 182 | 7 · `implied_vol_black76` | `models/implied_vol.py: implied_vol(law, …)` — **law-generic**, so it covers the Black-76 inversion through `Lognormal` | `implied_vol_bachelier` → **also superseded**, via the `Normal` law, not merely deferred |
| `options/vol_surface.py` | 191 | 6 · `FlatVol` (methods `vol`, `bumped`) | `market/vol_surface.py: Surface` + `flat_surface` + `Surface.bumped`; vega bump via `risk/bump.SurfaceBump` | `VolTermStructure`, `validate_vol_surface` → test-only; `VolSurfaceArbitrageResult` → **dead** (0 refs anywhere); the two arbitrage checks → test-only (`fx/fx_smile_cube` has its **own**, confirmed by §1 guard 2) |
| `options/capfloor.py` | 500 | 1 · `CapFloor` (methods `price`, `greeks`) | `products/option.py: CapFloor` + `cap_ladder`, `engine: price_capfloor`, `risk/greeks` | `strip_caplet_vols`, `calibrate_capfloor_sabr` → **superseded** (ng has both by name); `caplet_pvs`, `strip_caplet_vols_from_quotes` → test-only; `StrippedCapletVol` → **dead** |
| `options/swaption.py` | 375 | 3 · `Swaption`, `SwaptionType` (methods `price`, `greeks`, `annuity`, `forward_swap_rate`) | `products/option.py: Swaption` + `OptionType`, `engine: price_swaption`, `building_blocks: rpv01`/`forward`, `risk/greeks` | `pv_ctx` → **unused by any importer of this module**; `price_swaption_sabr_hw` (the SABR-HW blender) → test-only, 19 test refs, **ng has no blender** — flagged, see §5 |
| `credit/cds_market.py` | 334 | 3 · `build_cds_curve` | `calibration/credit.py: bootstrap_survival_curve` | upfront↔spread family (`spread_to_upfront`, `upfront_to_spread`, `bootstrap_from_upfronts`), `pricing_ladder`, `reprice_spreads`, `mark_to_market`, `roll_pnl` → **all test-only**; `LadderRung` → **dead**. ng genuinely lacks upfront↔spread — flagged, see §5 |

## 3. PARTIAL-cheap — superseded but for one named capability

| module | L | what is superseded | the gap, and who wants it |
|---|---|---|---|
| `options/sabr.py` | 377 | `sabr_implied_vol` (16 importers) → ng `sabr_vol`; `sabr_calibrate` (5) → ng `calibrate_sabr_smile` | **`shifted_sabr_implied_vol`** — ng's `sabr_vol`/`sabr_normal_vol` take `SabrParams` with **no shift**. One consumer: `desks/swaption_desk.py`. ng *has* `ShiftedLognormal` as a vol law, so the shift exists in the tree — it just is not threaded into SABR |
| `fixed_income/swap.py` | 419 | `pv`, `par_rate`, `annuity`, `dv01`, `cashflow_schedule` → ng `VanillaSwap` + `price_swap` + `rpv01` + `ir_delta` | **variable notional**: `notional_schedule` (3×) + `average_notional` (4×), used by `desks/api_desk`, `desks/swap_desk`. Also `from_convention` (2×), already a known deferral. **Note the asymmetry:** the *readers* are consumed but the *constructors* `amortising`/`accreting`/`roller_coaster` have **0 refs anywhere, incl. tests → dead** |
| `credit/cds.py` | 1035 | `CDS`, `bootstrap_credit_curve`, `risky_annuity`, `premium_leg_pv`, `protection_leg_pv` → ng `products/credit`, `engine/credit`, `building_blocks` | **`forward_cds_par_spread`** (3 consumers: `cds_swaption`, `index_cds_swaption`, `cds_index_product`) and **`cds_pnl_attribution`** (`desks/cds_desk`). Both consumer sets are un-crossed exotic credit, so this one *waits on its consumers*, not on us |
| `fixed_income/floating_leg.py` | 264 | `FloatingLeg` → ng `FloatLeg` + `float_leg_pv` | travels with swap/multi-curve as already forward-linked; all 4 importers (`basis_swap`, `frn`, `risky_floating`, `swap`) are themselves un-crossed |

**A standing forward-link is now satisfied:** `quarry_reconciliation.md` carries *"on crossing
`swap.py`: expose `annuity`/`weighted_annuity` (RPV01) as a building block"*. ng **has** `rpv01`
(`market/building_blocks.py`), so the `annuity` half is done; only `weighted_annuity` remains, and
it is the same notional-schedule gap above — one capability, not two.

## 4. RESIDENT — and why

- **`models/black76.py`** (234L, **107 importers**, 13 names) — the widest consumed surface in the
  quarry. ng has `black`, `black_vega`, `bachelier`, `OptionType`, `norm_cdf`/`norm_pdf`, but **not
  the analytic greeks** (`black76_delta/gamma/theta`, `bachelier_delta/gamma/theta/vega`): ng takes
  greeks by **bump** (`central_diff`). That is a deliberate design difference, not an oversight, but
  it leaves a wide un-superseded surface — and most of the 107 importers are un-built asset classes.
  Exactly the §4 "fat file with a wide consumed surface does not tick" case.
- **`risk/scenario.py`** (188L, 8 desks) — ng has the *bumps* (`risk/bump.py`) but no **scenario
  runner** (`run_scenarios`) and no `fx_spot_shock`. The framework, not the sensitivities, is what
  is consumed.
- **`risk/greeks.py`** (79L) — a trap worth naming: its consumed name `Greeks` is a **re-export**
  (`from pricebook.core.greeks import Greeks  # noqa: F401`). Its own content (`bump_greeks`) is
  test-only. So ticking it would supersede nothing ng built — the consumers want `core/greeks.py`.
  Reported as RESIDENT rather than a cheap tick, because the cheap tick would be fictitious.
- **`options/vol_smile.py`, `options/vol_surface_strike.py`** — consumers are `desks/equity_vol_desk`
  and `fx/fx_vol_surface`: un-built asset classes. Already forward-linked to the general vol-surface
  topic; unchanged.
- **`curves/bootstrap.py`** (712L, 9 importers) — ng has `calibration/calibrate.py` with
  `CurveBuild`/`CurrencyCurves`, but the consumers include `data/market_curve` and
  `pricing/pricing_server` (infrastructure, not pricing). **I did not verify this one to the depth
  of the others** — see §6.
- **The 266 zero-importer in-scope modules** — triaged by subject matter, not individually read.
  Nearly all are things ng has **never built**: ~40 country/convention modules, the repo family
  (~18), PDE/FEM/rough-vol numerics (~25), loans, autocallables, LMM, exotic payoffs. §4 is explicit
  that a product ng never built **blocks** the tick, so zero importers is not a tick signal — it is
  usually the opposite, an un-migrated vertical.

## 5. Two judgment calls I am flagging rather than deciding

1. **`options/swaption.py` and the SABR-HW blender.** `price_swaption_sabr_hw` has **19 test
   references and 0 production consumers**. ng has no blender. By the consumed-surface rule the
   module ticks; by "is this capability really shed?" it is a visible piece of market practice
   going away. I propose **TICK-now with the blender recorded as test-only**, but it is the one row
   where I would not be surprised to be overruled to PARTIAL.
2. **`credit/cds_market.py` and upfront↔spread.** Same shape: **ISDA-standard** conversions
   (`spread_to_upfront` / `upfront_to_spread` / `bootstrap_from_upfronts`), test-only, no production
   consumer. ng has no upfront leg at all. TICK-now by the rule; it is also the credit capability I
   would most expect a real desk to ask for first. Recorded against `NG-DEFER-CREDITISDA`, which
   already waits on a citable ISDA worked example.

Both are the same question — *does a test-only capability block a tick?* §4 answers for `dead` and
for `deferred→X`, and is silent on test-only. **That silence is itself worth a ruling**, because
this sweep shows test-only is the single most common omission class, not an edge case.

## 6. What I did NOT do

- **Did not tick anything.** No tracker edit, no version bump, per §5 of the spec.
- **Did not read all 386 in-scope candidates end-to-end.** 10 were read against their importers at
  method level; the rest were triaged by consumed-surface narrowness + subject matter. A TICK-now
  row is evidence-backed; a RESIDENT row for an un-built vertical is a triage call.
- **`curves/bootstrap.py` is under-verified** relative to the other nine — it plausibly belongs in
  §3 rather than §4, and I did not establish which. If the backlog above is accepted it does not
  change the decision, so I did not spend the pass on it.
- **Did not re-derive the drawdown.** Stays 26 / 793 until ticks are ruled.

---

# Part 2 — corrected counts and the test-only re-classification

**Date:** 2026-10-27 · **Answers:** `rulings_consumer_narrow_sweep.md` (thread 0048). Part 1 above is
left **as written** — a sweep record states what it found when it found it; the corrections are here.

## 7. The count was wrong, and one error survived Cowork's spot-check

Cowork caught that **3 of the 6 TICK-now were already deletable** (`credit/credit_risk` slice 3,
`options/implied_vol` slice 24, `options/capfloor` slice 23). Confirmed — all three are ticked rows in
this tracker. The cause is mine and it is embarrassing in a specific way: Part 1 netted the candidate
pool against **a hardcoded 7-module list I had scraped with a narrow regex**, and never asserted that
the list was the real deletable set. That is **the §6 floor rule, violated by the sweep that was
supposed to apply it** — a filter with no floor on what it filtered.

Netting properly against the reconciled set finds **one more that the spot-check did not**:

| module | Part 1 said | actually | source |
|---|---|---|---|
| `credit/credit_risk.py` | TICK-now | **already deletable** | slice 3, 25 → 26 |
| `options/implied_vol.py` | TICK-now | **already deletable** | T1 slice-24, 21 → 22 |
| `options/capfloor.py` | TICK-now | **already deletable** | T1 slice-23, 20 → 21 |
| **`options/sabr.py`** | **PARTIAL-cheap** | **already deletable** | **T1 slice-22, 19 → 20 — missed by both of us** |
| `curves/bootstrap.py` | RESIDENT (under-verified) | **already deletable** | T1 slice-3 |

`options/sabr.py` matters because it changes Cowork's figure too: the partial backlog is **3, not 4**.

**The population reconciles exactly**, which is the check Part 1 skipped:
Topic-0 (13) + Topic-1 (6) = 19 → `options/sabr` 20 → `options/capfloor` 21 → `options/implied_vol` 22
→ `options/swaption_vol_cube` 23 → `options/swaption_vol` + `options/swaption_conventions` 25 →
`credit/credit_risk` **26**. Matches the tracker's stated 26 / 793.

### Corrected headline

| verdict | Part 1 | **corrected** | modules |
|---|---|---|---|
| net-new TICK-now | 6 | **3** | `options/vol_surface` · `options/swaption` · `credit/cds_market` |
| net-new PARTIAL-cheap | 4 | **3** | `fixed_income/swap` · `credit/cds` · `fixed_income/floating_leg` |

**The decision does not change** — 3 ticks plus 3 partials is still a real backlog, so **(b) continues
and equity waits.** But the yield is 3, not 6, and the honest number is the one that goes in the record.

## 8. Test-only re-classification under the new clause

Every test-only omission below resolves to `dead` (evidenced) or `deferred→<named>`.

### `options/vol_surface.py` — proposed **TICK**

| omission | class | evidence |
|---|---|---|
| `VolTermStructure` | **superseded** — not shed at all | ng's `Surface` **is a term structure**: `vols[i]` at `expiries[i]`, interpolating total variance `w = σ²T` linear in `T`. Part 1 mis-filed this as a test-only omission; re-reading ng corrected it |
| `check_calendar_arbitrage`, `check_butterfly_arbitrage`, `validate_vol_surface` | **`deferred→` the arb-free-SABR slice** | a real capability ng lacks entirely. The target row already exists in this tracker with a **live** consumer (`options/vol_arbitrage_scanner.py`), so the forward-link has a named home rather than a vague "later" |
| `VolSurfaceArbitrageResult` | **`dead`** | 0 references in `quarry/pricebook` **and** 0 in `quarry/tests` — the only true `dead` in this batch |

Consumed surface: `FlatVol` (6 live importers; methods `vol`, `bumped`) → ng `Surface` + `flat_surface`
+ `Surface.bumped` + `risk/bump.SurfaceBump`.

### `options/swaption.py` — proposed **TICK**

| omission | class | evidence |
|---|---|---|
| `price_swaption_sabr_hw` (the SABR-HW blender) | **`dead`** — and on a stronger ground than "unconsumed" | see below |
| `pv_ctx` | **superseded** architecturally | ng's engine is `price(instrument, model)` and reaches market through `model.market` (§2). There is no `ctx` to pass; 0 importers of *this* module call it |
| `_swaption_from_convention` | **`deferred→` conventions** | same per-currency-convention deferral already forward-linked from the ZCB/bond/OIS/FRA retires; 0 callers here |

**On the blender, I go further than Cowork's "lean dead".** It computes
`vol = w·sabr_vol + (1−w)·hw_vol` with `w = exp(−T/blend_half_life)` and `blend_half_life = 5.0` — an
ad-hoc weighting with a guessed default and **no citation in the docstring**, so it could not pass the
§4 green-oracle gate as written. More decisively: **ng cannot express it without undoing v0.129.0.**
Its `hw_vol` input requires HW to quote a Black vol, and `HullWhite.swaption_vol` was deleted this
slice precisely because reconstructing an underlying to produce that vol was wrong by 381bp. Porting
the blender would mean re-introducing the defect we just made unwritable. That is `dead` by design,
not merely by consumer count — and Cowork's note that the old `deferred→SABR slice` link is **stale**
is confirmed: the SABR slice crossed without it.

Consumed surface: `Swaption`, `SwaptionType` (3 desks; methods `price`, `greeks`, `annuity`,
`forward_swap_rate`) → ng `Swaption` + `OptionType` + `price_swaption` + `rpv01`/`forward` +
`risk/greeks`.

### `credit/cds_market.py` — proposed **TICK**

| omission | class | evidence |
|---|---|---|
| `spread_to_upfront`, `upfront_to_spread`, `bootstrap_from_upfronts` | **`deferred→` the ng credit-desk / CDS quote-conversion slice** | agreed with Cowork: a **real** ISDA-standard capability, not dead. ng has no upfront leg at all. Related to `NG-DEFER-CREDITISDA`, which already waits on a citable ISDA worked example — so the quote-conversion slice and that ledger item share a trigger |
| `pricing_ladder`, `roll_pnl` | **`deferred→` the same credit-desk slice** | desk analytics (a bump-ladder of marks; roll P&L). ng has `cs01`/`bucketed_cs01` for sensitivities and `shell/benefit` for realized cash, but not these two shapes |
| `reprice_spreads` | **superseded** | reprices par spreads off a bootstrapped survival curve — this is exactly ng's credit-bootstrap round-trip oracle (`calibration/credit.py` + its reprice-to-quote test) |
| `mark_to_market` | **superseded** | ng `engine/credit.price_cds` + `shell/portfolio.mark` |
| `LadderRung` | **`dead`** | 0 references in source and 0 in tests |

Consumed surface: `build_cds_curve` (3 live importers) → ng `calibration/credit.bootstrap_survival_curve`.

## 9. The three §4 clauses, landed

Per the ruling, added to `CLAUDE.md` §4 in this slice:
1. **test-only never blocks a tick, and is never silently shed** — it is a prompt to classify as
   `dead` or `deferred→<named>`.
2. **the evidence protocol guards false positives too** — a bare-name hit is not a consumer until it
   resolves to the candidate; the instrument is an AST importer graph, not grep.
3. **net the candidate pool against the deletable set before counting** — a park is a tracker state,
   so every ticked module is still on disk and a tree-walking sweep re-finds it.

Clause 3 exists because this sweep needed it. Clause 2 exists because this sweep found it.

## 10. Proposed drawdown, if the three ticks are ruled

**26 → 29 / 793.** No tick is applied in this slice; the rows are proposals and the tracker is
unchanged until Cowork rules.
