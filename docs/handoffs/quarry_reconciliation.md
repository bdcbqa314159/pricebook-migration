# Quarry reconciliation map

## TOPIC-METHOD ROLL-UP (current — supersedes the pre-replan record below)

Date: 2026-07-19 · Version: `0.73.0`. Under the **Topic Method** (#13) this doc is a *thin roll-up*;
the per-topic **manifest** is where files are tracked. The pre-replan drawdown record (CP-1…CP-4,
`fixed_income` retires, drawdown /768) is **frozen history** — those retire *ticks* were never
git-mv'd, and their modules (linear products / curve pillars) belong to **Topic 1**, retired when it
closes. The physical drawdown restarts here.

| topic | scope | status | manifest | parked |
|---|---|---|---|---|
| **Topic 0 — Foundation (L0)** | conventions · money/quantity · index identity · settlement · numerics-config (scipy, S17) · serialisation pattern | **PARKED** (gate green: F1–F4 + S1–S17 landed; both regression oracles pass) | `parked/topic-00-foundation/MANIFEST.md` | **13** |
| **Topic 1 — the first complete vertical (L0→L6)** | curves (C1) · Black models + vol (C2) · risk + shell (C3) | **CLOSED v0.98.0** — the spine proven L0→L6 for a full instrument lifecycle | `parked/topic-01-yield-curve/MANIFEST.md` | **6 parked** (git-mv'd at T1 close) |

**Files parked: 13 / 793** (reported, never steered — #12). **This is the single source of truth for
the drawdown denominator** (CLAUDE.md §4/§6 point here, not to a hardcoded literal). **Convention
(pinned):** the total is *every `.py` file in the original quarry* = files remaining in
`python/pricebook/` (**780**) + files already parked under `parked/` (**13**) = **793**, `__init__.py`
markers included. Verified 2026-08-01 by direct count.

**Deletable (the §4 drawdown bar): 26 / 793** — **all 26 are TICKED; none is physically moved**
(park-model amendment, 2026-10-26: a park is a tracker/MANIFEST state, not a `git mv` — CLAUDE.md §4,
doc 13 §7, ruling `rulings_quarry_park_model.md`). The 19 formerly physically parked at the Topic-0
(v0.74.0) and Topic-1 (v0.98.0) closes have been **restored to their original quarry paths**: those
moves broke `import pricebook` for 265 of 583 modules, because 294 live modules import those 19
directly. `parked/*/MANIFEST.md` remains the record of what crossed; the quarry is deleted **once**,
at v1.0. Formerly *"19 physically parked + 4 ticked awaiting the batch park"* (`options/sabr.py`, slice 22,
v0.108.0; `options/capfloor.py`, slice 23, v0.109.0; `options/implied_vol.py`, slice 24, v0.110.0;
`options/swaption_vol_cube.py`, slice B, v0.114.0 —
physical `git mv` batches at the next topic close, doc 18 §9). The 6 Topic-1 modules below are now git-mv'd into `parked/topic-01-yield-curve/`:
- **slice-3 retire read (2):** `curves/bootstrap.py` and `core/discount_curve.py`, superseded by ng
  `calibrate` / `DiscountCurve` (deposits→FRAs→futures→swaps dual-curve sequential, minus deferred
  capabilities).
- **slice-4 retire read (3):** `curves/ncurve_solver.py`, `curves/global_solver.py`,
  `curves/multicurve_solver.py`, all superseded by ng's **simultaneous** solve (scipy LM). Hand-rolled
  damped Newton + FD Jacobian are §7bb-shed (scipy); analytic Jacobian → `deferred→C3/AAD`; N-curve > 2
  → `deferred→3rd-projection-curve`; 0 ng consumers of any shed bit (evidence: `CP_slice4_global_solve.md`).
  **`multicurve_solver`: full cross ratified (Cowork), 3 ticks stand, 19/793.** §4 grep confirmed 0
  production/dynamic consumers of `multicurve_newton`/`validate_curve`/`curve_analytical_jacobian` (bare-
  name search across `python/**` source+tests: only quarry-internal test files, which retire with the
  quarry). `validate_curve`/`curve_analytical_jacobian` forward-linked → C3 risk.
- **slice-5 retire read (1) — `core/forward_interpolation.py` (housekeeping 2026-08):** full cross.
  Its 3 methods map — `MONOTONE_CONVEX` → ng `HAGAN_WEST` (slice 5); `PIECEWISE_CONSTANT` (flat forwards ≡
  linear log-df) → ng `LOG_LINEAR`; `PIECEWISE_LINEAR` → shed (`deferred→` future interp-method consumer).
  Interpolate-on-forwards-then-integrate architecture superseded by ng's DF-interpolation + `forward()`
  atom. §4 grep: 0 production/dynamic consumers (only its own `test_forward_interpolation.py`; the
  `test_commodity_vol_surface` hit is a method-name collision, not an import).

- **slice-6c retire read (0 ticks — ratified):** the xccy/CSA/FX quarry suite (`fixed_income/xccy_swap`,
  `xccy_basis`, `xccy_bond`, `xccy_swaption`, `csa`, `credit/bilateral_csa`, `risk/collateral_*`,
  `curves/ndf_implied`, and all of `fx/*` — `multi_currency_curves`, `fx_basis`, `fx_forward*`, `ndf`,
  `prdc`, `fx_smile_cube`, …) is **NOT superseded** by 6c. ng's 6c delivers one minimal foreign-collateral
  *discount curve* (constant-notional, single-curve-per-ccy, basis-as-spread); the quarry suite is
  full-featured FX/XVA breadth (vol surfaces, exotics, NDFs, collateral optimisation, bilateral CSA).
  A curve does not supersede a product+risk suite → **0 ticks (correct, ratified C1 domain depth, doc 18
  §4/§9)**. Named crossing: these files retire with the **FX / XVA topics**, not Topic 1. Drawdown
  unchanged at **19 / 793**.

- **C2 slice-1 retire read (0 ticks — PARTIAL crosses):** `models/black76.py` (Black-76 *price* crosses → ng
  `black()`; `black76_delta/gamma/vega/theta` → C3 risk, `bachelier_*` → 2nd vol consumer) and
  `options/capfloor.py` (single caplet *price* crosses → ng `Caplet`+`price_caplet`; floorlet → its consumer,
  `CapFloor` strip → B5, `strip_caplet_vols` → vol-calibration slice, `calibrate_capfloor_sabr` → SABR/B4).
  Both remain resident (greeks/Bachelier/strips/stripping/SABR deferred) → **tick 0, drawdown 19/793**. Full
  evidence: `CP_C2_slice1_black_caplet.md` §Drawdown.

- **C2 slice-2 retire read (0 ticks — PARTIAL cross):** `options/swaption.py` — the European
  Black×annuity swaption *price* crosses (ng `Swaption` + `price_swaption`, `PV = N·rpv01·black(S,K,vol,t)`
  on the shared atoms). Resident/deferred: `price_swaption_sabr_hw` (SABR/HW blend) → SABR slice (B4);
  greeks → C3; cash-settled/IRR → first cash-settled consumer; the separate `swaption_vol_cube.py`,
  `bermudan_swaption*.py`, `midcurve_swaption.py` → their own slices (cube/(A)-fork Bermudan/midcurve). Partial
  → **tick 0, drawdown 19/793**. Evidence: `CP_C2_slice2_black_swaption.md` §Drawdown.

- **C2 slice-3 retire read (0 ticks — PARTIAL crosses):** `options/capfloor.py` — the caplet-vol
  *term-structure strip* now crosses (ng `strip_caplet_vols`), but `calibrate_capfloor_sabr` + the smile/
  cube generation stay resident → SABR/smile slice; the `CapFloor` strip container + greeks were already
  deferred (slice 1). `options/vol_calibration.py` — a MULTI-ASSET surface calibrator; only the IR caplet
  term-structure portion of `calibrate_ir_surface` is superseded — `calibrate_fx/equity/commodity_surface`,
  `CalibratedSABRNode`, `CalibratedVolSurface` travel with their asset topics (FX/equity/commodity) and the
  SABR slice. Both remain resident → **tick 0, drawdown 19/793**. Evidence: `CP_C2_slice3_caplet_vol_strip.md`.

- **C3 opening retire read (0 ticks — PARTIAL crosses):** the generic bump-and-reprice greek *mechanism*
  now exists at L5 (`ir_delta` DV01 + `vol_vega` on the `Priceable` protocol), **discharging the accrued
  "greeks exist at L5" →C3 forward-links** (curve DV01, caplet/swaption vega — any priceable gets them for
  free). But every quarry risk file retains breadth beyond ng's parallel first-order pair: `risk/greeks.py`
  (`bump_greeks` — gamma/theta resident), `curves/key_rate_risk.py` (key-rate/bucketed DV01 → bucketed-risk
  consumer), `curves/curve_risk.py` (`curve_jacobian`/rolldown → C3-later/AAD), `risk/pathwise_greeks.py`
  (AAD), `curves/curve_bumper.py` (pillar bumps), `core/greeks.py` (`Greeks` aggregate → portfolio consumer);
  `models/black76.py` delta/gamma/theta stay partial (analytic greeks → their slice). All partial →
  **tick 0, drawdown 19/793**. Evidence: `CP_C3_opening_risk_greeks.md`.

- **L6 opening retire read (0 ticks — PARTIAL cross):** the frozen-description + mark + portfolio-DV01
  *concept* crosses (ng `Trade`/`Book` + `mark`/`mark_book`/`book_dv01`; the quarry's `Trade.pv(ctx)`
  self-pricing is **realigned** to the shell `mark()`, shed not migrated). But `core/trade.py`/`core/book.py`
  stay resident: serialisation (`to_dict`/`from_dict` → persistence slice), mutable `Book.add`, `Desk`,
  `Position`/`BookLimits`/limit-breaches, tenor-bucketed DV01, counterparty netting (→ stateful/desk/limits
  slices), **and ~10+ un-crossed desk consumers** (`desks/*`, `credit_risk` — deleting would orphan them).
  Realized-P&L/benefit-table/`BookedTrade` travel with the next (stateful) L6 slice. Partial → **tick 0,
  drawdown 19/793**. Evidence: `CP_L6_opening_shell.md`.

- **L6-realized retire read (0 new ticks — PARTIAL, but the Topic-1 PARKING event fires):** the
  realized-vs-mark / benefit-table *concept* crosses (ng `BookedTrade`/`realized`/`total` + the invariant-6
  engine exclusion; the quarry's `Trade.pv(ctx)` self-pricing is realigned to the shell `mark`). But
  `core/trade.py`/`core/book.py`/`core/fixings.py` stay resident — serialisation, `Desk`, limits/positions/
  netting, lifecycle events, mutable fixing store + file I/O, AND ~10 un-crossed desk consumers — so the
  booking modules do NOT tick. **Because this CLOSES C3 and Topic 1**, the 6 accumulated Topic-1 deletables
  were **physically parked** (one `git-mv` event into `parked/topic-01-yield-curve/`): `bootstrap`,
  `discount_curve`, `ncurve_solver`, `global_solver`, `multicurve_solver`, `forward_interpolation`. ng is
  unaffected (never imports the quarry); the merge gate never touches `python/`. Drawdown **19/793, now all
  physically parked** (13 Topic-0 + 6 Topic-1) — the numerator is unchanged (no new tick; booking partial),
  the *parking* is the physical realization. Evidence: `CP_Topic1_close.md`.

- **#7 (ICMA + BUS/252) retire read (0 ticks — capability slice):** the ICMA/BUS252 year-fraction
  *capability* now lives in the shared atoms (`rpv01`/`float_leg_pv` read convention context from the
  self-describing `Schedule`), discharging audit repro C + the `is_stub`-zero-consumer note + AC-T4.15
  (`Frequency.per_year()`). But no whole quarry module is superseded by this alone: `fixed_income/fixed_leg.py`
  carries full leg machinery, and the BRL/CDI product suite is deferred to its consumers. **Tick 0.**

- **T1 slice-20 SABR-caplet-read retire read (0 ticks — PARTIAL cross):** `options/sabr.py` — the SABR
  lognormal *implied-vol* (`sabr_implied_vol`, Hagan 2002) and its *caplet price* (`sabr_price`) cross to
  ng `models/sabr.py` (`sabr_vol` + `SABRModel`, read-not-solved; the caplet reprices through the unchanged
  engine, capability rule-of-two). Resident: calibration, `shifted_sabr_*`, `sabr_normal_vol` → their slices.
  Partial → **tick 0, drawdown 19/793**. Evidence: `CHANGELOG` v0.106.0.

- **T1 slice-21 SABR-calibrate retire read (0 ticks — PARTIAL cross):** `options/sabr.py` — the smile
  *calibration* (`sabr_calibrate`/`calibrate_sabr_smile`) now crosses to ng `calibration/sabr_calibrate.py`
  (`calibrate_sabr_smile`, bounded LS over the shared `sabr_vol` atom, the quarry's SSE/Nelder-Mead + `1e10`
  penalty **shed** for a real box). Resident (blocks full retire): `shifted_sabr_implied_vol`/`shifted_sabr_price`
  (negative-rate variant → shifted-SABR slice), `sabr_normal_vol` (Bachelier → normal-SABR slice), and the
  `SABRCalibrationResult`/`CanonicalCalibrationResult` DB-persistence artefact → DB-spine crossing. Partial →
  **tick 0, drawdown 19/793**. Evidence: `CHANGELOG` v0.107.0.

- **T1 slice-22 SABR-multilaw retire read (+1 TICK — `options/sabr.py` DELETABLE, 19 → 20 / 793):** the
  module's remaining content crosses. **Shifted SABR** (`shifted_sabr_implied_vol`/`shifted_sabr_price`)
  → the ng `ShiftedLognormal(shift)` law (the same lognormal expansion + `black` evaluated on the shifted
  pair — one composition, not a second formula). **Normal SABR** (`sabr_normal_vol`) → `Normal` +
  `sabr_normal_vol` + `bachelier`, and here ng **SUPERSEDES rather than clones**: the quarry converted the
  lognormal vol (`σ_B·√(FK)`, its own docstring calling it an approximation "for moderate moneyness", exact
  only at the money and still needing `F > 0`), while ng implements the **β=0 Hagan expansion** whose
  `z = (ν/α)(F − K)` carries no log-moneyness and therefore prices through zero — which is the entire
  point of the normal law. Numbers differ by construction (~3e-3 in vol near ATM); the quarry's only
  consumer of the conversion is its own `tests/test_shifted_sabr.py`, which retires with the quarry.
  Also crossed this slice: `models/black76.py`'s `bachelier_price` → ng `models/bachelier.py` (that module
  was already partially crossed for `black76_price` in C2 slice 1; it stays resident for its vega/theta/
  implied-vol helpers).
  **Shed, with evidence (§4 protocol — bare-name greps over `python/pricebook/**` + `python/tests/**`):**
  `max(result, 1e-10)` vol floor, the `ratio <= 0 → z/χ = 1` fallback, the `sqrt_arg`/`1−ρ` clamps
  (unreachable inside ng's `|ρ| ≤ 0.9999` box), and `T ≤ 0 → return α` (wrong for β≠1) — all shed as
  hidden-wrongness debt or dead defensive code; `rmse`/`reprice_errors_bp`/`max_error_bp`/`max_rmse_bp`
  **`dead`** (every one derivable from the `residuals` ng already returns). `warnings.warn`-on-bad-fit is
  superseded by the ACCEPTANCE GATE (Cowork ruling 1): a converged-but-unacceptable fit is a
  `CalibrationFailure` carrying its residuals, not a warning the caller may ignore.
  **Genuine residual: the persistence artefact only** — `SABRCalibrationResult` /
  `CanonicalCalibrationResult` / `_build_calibration_record` / `to_dict` / `db.save_calibration` →
  **`deferred→DB-spine`**, forward-linked on the DB-spine row in the Topic-1 MANIFEST. §4 grep: **0 ng
  consumers** (ng has no DB spine at all); quarry consumers are `desks/api.py` + `test_provenance_carrier`
  / `test_calibration_result_lmm_sabr` / `test_calibrator_provenance_conformance`, none crossed. A deferred
  *capability* (not a product) does not block a tick (§4) → **TICK. Drawdown 20 / 793.** Evidence:
  `redesign/handoffs/AUDIT_sabr_multilaw.md` + `CP_sabr_multilaw.md` + `CHANGELOG` v0.108.0.

- **T1 slice-23 cap/floor retire read (+1 TICK — `options/capfloor.py` DELETABLE, 20 → 21 / 793):** the
  vanilla cap/floor crosses whole. `CapFloor.__init__`/`.periods` → L2 `CapFloor(index, schedule, strike,
  notional, option_type)` + the **`cap_ladder` atom** (§3d: the ONE definition of which caplets a cap is,
  composed by the L4 pricer, the vol strip and the cap-SABR calibration); `CapFloor.price` → L4
  `price_capfloor` = Σ `price_caplet` (so the model's vol law, the ruling-2 F-identity guard and
  invariant 6 all apply per caplet, for free, instead of the quarry's duck-typed
  `hasattr(model, "price_ir_option")`); `strip_caplet_vols` → the **#10-fixed** ladder strip;
  `calibrate_capfloor_sabr` → composition of that strip with the slice-21 smile fit.
  **Audit #10 discharged** (its trigger — "a real cap with intra-tenor caplets" — is this slice's
  product): a 5Y quote set now strips **19** caplet pillars, not 4.
  **Shed, with evidence (§4 protocol — bare-name greps over `python/pricebook/**` + `python/tests/**`):**
  `strip_caplet_vols_from_quotes` **shed as debt** — its own comment concedes
  `# Simplified: use the flat cap vol as the caplet vol for this bucket`, i.e. it never strips (1 quarry
  test consumer, 0 production); `calibrate_capfloor_sabr`'s **synthetic smile**
  (`avg_vol·(1 + 0.1·(K−F)/F)`), its 0.5Y tenor bucketing with forward/vol averaging, and its
  `except Exception` → hardcoded `(α=avg_vol, ρ=0, ν=0.3)` fallback — all **shed as debt** (a fabricated
  skew fitted as if it were market data; ng fits vols stripped from real quotes and returns
  `CalibrationFailure` otherwise); `strip_caplet_vols`' `except Exception: caplet_vol = flat_vol`
  likewise; the first-period `t_fix ≤ 0 → intrinsic off the FORWARD` branch **shed as a correction** (a
  fixed period's payoff follows its FIXING, not a curve forward — ng excludes the already-set caplet per
  market convention); `_capfloor_pv_ctx` **shed by design** (§2 — products do not price themselves).
  **Residual: three deferred CAPABILITIES, no deferred product** — per-caplet greeks
  (**`deferred→L5`**, 3 quarry test consumers, 0 production), `_cf_from_convention`
  (**`deferred→conventions`**, 0 consumers anywhere — the same dead registry retire #2 found), and
  `to_dict` + the `convention` serialisation field (**`deferred→DB-spine`**, as the SABR artefact).
  A deferred capability never blocks a tick (§4) → **TICK. Drawdown 21 / 793.** Evidence:
  `redesign/handoffs/AUDIT_capfloor.md` + `CP_capfloor.md` + `CHANGELOG` v0.109.0.

- **T1 slice-24 implied-vol retire read (+1 TICK — `options/implied_vol.py` DELETABLE, 21 → 22 / 793):**
  two quarry functions, one algorithm (Newton-on-vega → bisection fallback, duplicated once per law),
  cross as **ONE law-generic inverter**: `models/implied_vol.py::implied_vol(law, call_price, forward,
  strike, t)` inverts `law.price`, so lognormal, **shifted** (which the quarry never had) and normal
  are the same code and `law.defined` decides the domain. The `option_type` parameter is replaced by
  the named parity atom `call_price_from_put` — the implied vol of a put IS its call's, exact in every
  law. §3d holds by construction: the inverse composes the very function it inverts.
  **The slice also promotes a duplicated search to L0:** `foundation/solvers.py::invert_increasing`
  (monotone inverse with an expanding upper bracket) now serves BOTH the new inverter and
  `vol_strip._solve_vol`, whose hand-rolled bracket loop is deleted — two real in-slice consumers,
  stripped vols byte-identical.
  **Shed, with evidence (§4 protocol):** `df` inside the signature (re-shaped — ng inverts the
  UNDISCOUNTED price, as `black`/`bachelier` do); **Newton-on-vega** (§7bb — it needed a bisection
  fallback precisely because it is not unconditionally convergent; `black_vega` stays for L5 risk);
  `return 0.5*(lo+hi)` after 200 failed bisection steps (**hidden wrongness** — a returned
  non-solution); the Bachelier bracket `hi = forward * 5.0` (**a BUG** — negative for a negative
  forward, zero at F=0, i.e. broken in exactly the negative-rate case the normal law exists for); the
  silent 500% cap; `tol` conflated as both a price and a vol tolerance; the law-specific upper-bound
  checks (**subsumed** — the bound is finite for lognormal and unbounded for normal, so only the
  generic bracket report is law-correct); `_norm_pdf` imported privately (ng has the §7bb adapter).
  **Consumer evidence:** `implied_vol_black76` has **7 production consumers** (`options/sabr_mc`,
  `desks/api`, `models/hw_calibration`, `models/rough_equity`, `models/jump_calibration`,
  `models/g2pp_calibration`, `equity/joint_calibration`) — a load-bearing capability ng must have for
  those modules to cross; `implied_vol_bachelier` has **0** production consumers (test-only) and is
  absorbed at zero cost by the generic inverter. **ng consumers today: zero** — stated plainly; this
  lands because it RETIRES a module (§4), as one concrete function, not an abstraction.
  **Residual: EMPTY** (no deferred capability, no deferred product) → **TICK. Drawdown 22 / 793.**
  Evidence: `redesign/handoffs/AUDIT_implied_vol.md` + `CHANGELOG` v0.110.0.

- **T1 slice-25 swaption-SABR-read retire read (0 ticks — PARTIAL cross):** `options/swaption_vol_cube.py`
  — the per-node **smile READ** crosses to ng as `SABRModel.swaption_vol` plus the cube *shape*
  `{SwaptionSurfaceKey(index, swap_tenor) → SabrSurface}`; **no cube TYPE is ported**. Shed with the
  read: the quarry's **nearest-node strike hack** (snapping a requested strike to the closest quoted
  node, i.e. silently pricing a different strike) and its **silent calibration fallback** (fabricating
  params when a fit fails) — both hidden-wrongness debt of the same family as `calibrate_capfloor_sabr`'s
  synthetic smile, already shed in slice 23. **Resident, blocking the tick:** the cube's CALIBRATION and
  node scanner → **slice B** (which will also be the first ng consumer of slice 24's implied-vol
  inverter, since a cube built from prices needs it). Cross-expiry/tenor node interpolation →
  `deferred→` the first off-pillar-node consumer. **Tick 0; drawdown unchanged at 22 / 793** — the full
  tick lands with slice B. Evidence: `AUDIT_swaption_sabr_read.md` + `CHANGELOG` v0.111.0.

- **T1 slice-B swaption-cube retire read (+1 TICK — `options/swaption_vol_cube.py` DELETABLE, 22 → 23 / 793):**
  the partial cross recorded at slice 25 (the smile READ) closes here with the **calibration + node
  scanner** → ng `calibration/swaption_cube.py`: `build_swaption_vol_cube` returns the outcome for
  **every quoted node**, keyed `(SwaptionSurfaceKey, expiry)`, successes as
  `(SabrParams, CalibrationResult)` and failures as that node's `CalibrationFailure` with residuals;
  `swaption_cube()` derives `{key → SabrSurface}` from the successes and `calibrated_count()` is
  **derived, never stored** (a stored count is the proxy §6's second clause forbids). Spec + rulings:
  `spec_slice_B_swaption_cube.md` (B1–B4). Audits: `AUDIT_swaption_vol_cube.md` (9 findings),
  `AUDIT_slice_B_forward_threading.md` (the align-step STOP).
  **Superseded:** `SwaptionVolCube` + its read surface (`vol`/`vol_by_years`/`atm_vol`/`smile`) by
  `SabrSurface` + `SABRModel.swaption_vol` (slice A); `SABRNode` by `SabrParams`/`SabrSurface`.
  **Shed, with evidence (§4 protocol — bare-name search over `quarry/` source *and* tests, plus
  string-key/getattr/kwargs checks):** `SABRNode` **0 external refs**; `SwaptionVolCubeResult`
  **0 external refs** (shed for the ratified `CalibrationResult`); `_nearest_sabr` — the nearest-node
  strike snap, which ranked nodes by `(Δexpiry)² + (Δtenor)²` (mixed units) under a magic
  `dist < 4.0` commented *"within ~2Y on each axis"* (false: it admits 2.0Y on one axis or 1.41Y on
  both) and then priced the requested strike against a **different** node's smile; the `SABRNode.vol`
  ATM fast-path (made the smile discontinuous at the money — grid-ATM at K=F, Hagan at K=F±1e-8);
  and the bare fallbacks returning grid-ATM / `0.0` on failure (the silent-wrongness family already
  shed in slices 23 and 25).
  **`bumped()` is NOT ported — it is wrong, measured.** It added an absolute vol shift to SABR
  `alpha`, which is a vol only at β=1. Against ng's own `sabr_vol` (F=0.03, β=0.5, ATM=20%, T=5Y):
  intended +1.0bp, realised **+5.97bp at K=F, +5.43bp at 1.25F, +6.19bp at 0.80F** — bracketing the
  predicted `1/F^(1-β) = 5.77×`, and strike-dependent, so it *tilted* the smile while its docstring
  claimed to keep it consistent. ng has no cube bump, so nothing inherited it.
  **`deferred→` (each a capability, never a product — §4, so none blocks the tick):**
  off-pillar / cross-node interpolation **and** the shared `interp_surface` L0 atom → **first
  off-pillar consumer**; the cube vol bump, rebuilt correctly (bump the vol, re-imply alpha) →
  **L5 risk**; arb-free SABR (Hagan-2002 wing arb) → its own slice.
  **Resident quarry importer does not block the tick** (precedent: `options/sabr.py` ticked at slice 22
  with 25 quarry importers; the physical `git mv` batches at the topic close). `options/synthetic_swaption_data.py`
  imports `SwaptionVolCube`/`build_swaption_vol_cube` — **forward-linked on its own row below**.
  Evidence: `AUDIT_swaption_vol_cube.md` + `AUDIT_slice_B_forward_threading.md` + `CHANGELOG` v0.114.0.
  **COWORK RATIFIED 2026-10-26 (tick 22 → 23 / 793):** retire-read spot-checked per §4 — every omission
  evidenced (`SABRNode`/`SwaptionVolCubeResult` 0 external refs; `_nearest_sabr`/ATM-fast-path/bare-
  fallbacks shed as silent-wrongness; `bumped()` not ported, 5.4–6.2× measured), all three deferrals
  are capabilities not products (none blocks the tick), resident-importer precedent (`sabr.py` @ 25)
  sound. Deletable bar met; the tick stands. Thread 0011; carried into the swaption-cluster checkpoint
  as the drawdown review input.

- **T1 swaption-cluster TAIL retire sweep (+2 TICKS — 23 → 25 / 793; Cowork-ruled 2026-10-26, thread 0019):**
  a six-module consumer-analysis sweep (§4 dead-evidence protocol over `quarry/pricebook` **and**
  `quarry/tests`' 952 files, plus dynamic reachability). Evidence + verdicts:
  `handoffs/RETIRE_swaption_cluster_tail.md`, carrying Cowork's spot-check ruling.
  - **`options/swaption_vol.py` DELETABLE (+1).** Exports exactly `SwaptionVolSurface` (a 2D ATM
    `vol(expiry, tenor)` grid); **1** production importer. **Superseded:** the container →
    `{SwaptionSurfaceKey(index, swap_tenor): Surface}` — ng types
    `surfaces: Mapping[SurfaceKey | SwaptionSurfaceKey, Surface | SabrSurface]`, so one 2D grid
    decomposes into keys × term structures (doc 19 closed-shapes×open-keys). **Oracle verified:**
    `tests/L4/test_swaption_sabr.py:254` prices a swaption off `Surface.flat(0.22)` under that key.
    `.bumped(shift)` → `risk/greeks.py::vol_vega` — and note it is **dimensionally correct**, unlike
    the cube's `bumped` (slice B F7, 5.4–6.2× wrong): a `Surface`'s entries *are* vols, whereas
    `alpha` is a vol only at β=1. **`deferred→`:** the 2D off-pillar interpolation
    (`_interp_2d`/`_interp_expiry`/`_interp_tenor`) → first off-pillar consumer; the one importer
    `desks/swaption_desk.py` → `deferred→swaption_desk`. Both capabilities, not products (§4).
  - **`options/swaption_conventions.py` DELETABLE (+1).** All five public names (`VolQuoteType`,
    `SmileType`, `SwaptionConvention`, `get_swaption_convention`, `list_swaption_currencies`):
    **0 production consumers**; two have 1 test hit each, in a shared test that retires with the
    module. **Superseded by design, not by a type:** slice A established a swaption's conventions are
    the **swap's** (fixed-leg frequency + day counts), which `RateIndex` cannot carry — so a
    per-currency lookup registry is the shape ng deliberately lacks; the contract states its
    conventions instead of defaulting them. Precedent: retire-#2's quarry `Deposit` with zero
    production instantiations — conventions with no ng consumer are shed debt, not residual.
    **`deferred→`:** the convention *content* → first currency-defaulting consumer.
  - **Left resident, with evidence (4):** `vol_arbitrage_scanner.py` — ng has **zero** arb machinery
    and `options/vol_calibration.py:112` lazily imports `scan_surface` live, so a tick would be a paper
    tick; `vol_surface_strike.py` + `vol_smile.py` — **general** strike-axis vol machinery consumed by
    **equity and FX** desks, with no ng counterpart (ng's only strike-dependent object is the *fitted*
    `SabrSurface`, not an interpolating container); `synthetic_swaption_data.py` — live consumer
    `models/hw_per_currency.py:114`.
  - **Method note (the protocol asks how, not just what):** the dynamic sweep returned exactly one
    hit — `market_data/_types.py` holding the string `"swaption_vol"` — and it is a **false positive**
    (`SWAPTION_VOL = "swaption_vol"` is a `QuoteKind` enum *value* sharing the text). Recorded because
    retire-#1's false negative was this family. Separately `vol_arb.py`'s apparent `enforce_no_arb`
    use is a **docstring** cross-reference, so that name has 0 real source consumers. Cowork's own
    first grep over-claimed for the same reason (substring `swaption_vol` matches `_cube`,
    `synthetic_swaption_data`, the enum) and its precise re-check confirmed the read.

  **This closes the swaption / vol cluster whole** — smile read (slice 25/A) → forward-threaded fit
  (slice B, B4) → cube calibration (slice B) → tail sweep. Six modules retired across it:
  `options/{sabr, capfloor, implied_vol, swaption_vol_cube, swaption_vol, swaption_conventions}.py`.

- **B6 credit slice-1 retire read (0 TICKS — PARTIAL cross; drawdown unchanged at 25 / 793):**
  `quarry/pricebook/core/survival_curve.py` (271 lines, 14 methods, **59 production importers**)
  crosses **partially** as ng `market/survival_curve.py` — `SurvivalCurve` (log-linear Q =
  piecewise-flat hazard), `survival`, `hazard`, `bumped` (hazard shift), `with_pillar`,
  `flat_hazard`, plus the `SurvivalHandle` capability and `CurveSet.survival(entity)`. **No tick:**
  the deletable bar is an *empty* residual, not "looks covered" (§4), and nine methods are unmatched.
  **Resident residual, each with its named destination:**
  `default_prob(d1,d2)` and `forward_hazard`/`forward_survival`/`marginal_default_density`
  (conditional//marginal reads) → **the CDS product + engine (slice 2)** and whichever credit
  product first needs conditional survival; `term_structure`/`pillar_hazards` (introspection) →
  **credit reporting/risk**; `bumped_at` (single-pillar bump) → **L5 credit key-rate risk**
  (ng has the parallel hazard bump only); `_sc_to_dict`/`_sc_from_dict` → **`deferred→persistence`**,
  the established serialisation pattern. `to_calibration_result` is **superseded by shape** — ng
  returns `(curve, CalibrationResult)` as a pair, never hanging the result off the curve (doc 19:
  the result sits BESIDE the model/curve, never on it).
  **Also landed this slice, not from this module:** `foundation/reference_entity.py` (the one L0
  identity credit adds, §3c corollary — `underlying.py` had recorded that it "returns with
  *validated* fields when its asset class actually ships"), and the two shared credit atoms
  `risky_annuity` / `protection_leg` in `market/building_blocks.py`, which the quarry spread across
  `credit/cds.py`'s `premium_leg_pv`/`protection_leg_pv`/`risky_annuity` — mined for **content**
  (the half-period accrual-on-default convention, the midpoint-discounted protection integral), not
  for shape. `credit/cds.py` (1035 lines) is itself untouched and crosses with slice 2.
  Evidence: `spec_credit_B6_slice1.md` + `CHANGELOG` v0.118.0.

- **B6 credit slice-2 retire read (0 TICKS — two PARTIAL crosses; drawdown unchanged at 25 / 793):**
  - **`quarry/pricebook/credit/cds.py`** (1035 lines, **20 production importers**) crosses
    **partially** as ng `products/credit.py` (`CDS`, `PremiumLeg` — pure data) + `engine/credit.py`
    (`price_cds`). **Superseded:** `protection_leg_pv` / `premium_leg_pv` / `risky_annuity` → the two
    shared atoms in `market/building_blocks.py` (one definition, composed by both the bootstrap and
    the engine — §3d); `bootstrap_credit_curve` → `calibration/credit.py` (slice 1);
    `CDS.pv`/`pv_protection`/`pv_premium`/`pv_ctx` → `price_cds` (products do not price themselves,
    §2); `CDS.rpv01` → the shared `risky_annuity`. **Resident residual — the quarry `CDS` carries 20
    methods and ng's product carries none by design**, so most of it is forward-linked, not shed:
    `par_spread`/`upfront`/`isda_upfront`/`to_upfront` (quote-convention conversions) →
    **`deferred→` the first upfront-quoted consumer** (and NG-DEFER-CREDITISDA for the ISDA form);
    `cs01`/`bucket_cs01`/`rec01`/`spread_duration`/`spread_convexity`/`theta` → **L5 credit risk**
    (ng has the parallel hazard bump only — `bumped`); `carry`/`roll_down` → **credit P&L/carry**;
    `average_notional`/`_aged_notional` (amortising notional) → **`deferred→` the first
    variable-notional CDS**; `CDSPnLAttribution` + `cds_pnl_attribution` → **L6 P&L attribution**;
    `ForwardCDSCurveResult` + `forward_cds_par_spread` + `forward_risky_annuity` → **`deferred→` the
    forward-CDS product**; `StandardCDS` (+ `from_market`, `upfront_pct`) → **`deferred→` the
    standard-contract convention consumer**, its `to_dict`/`from_dict` → `deferred→persistence`.
  - **`quarry/pricebook/core/survival_curve.py` residual SHRINKS but still does not tick.** Slice 1
    forward-linked nine methods as needed-by-slice-2; two of them landed here —
    `default_prob` (= 1 − Q) and `conditional_survival` (= Q(t₂)/Q(t₁), the Markov property the
    protection leg's increments already rely on). **Seven remain:** `forward_hazard`,
    `forward_survival`, `marginal_default_density` → the first consumer needing forward credit;
    `term_structure`, `pillar_hazards` → credit reporting; `bumped_at` (single-pillar) → L5 credit
    key-rate risk; `_sc_to_dict`/`_sc_from_dict` → `deferred→persistence`. Still a partial cross.
  **No tick on either**: the deletable bar is an *empty* residual, not "looks covered" (§4).
  Evidence: `spec_credit_slice2.md` + `CHANGELOG` v0.119.0.

- **B6 credit slice-3 retire read (+1 TICK — `credit/credit_risk.py` DELETABLE, 25 → 26 / 793):**
  294 lines, 6 production importers. **The decisive evidence is WHO those importers are:** every one
  of them (`credit/cds.py` ×3, `credit/cds_index_product.py` ×2, `desks/cva_desk.py`,
  `desks/trs_desk.py`, `core/survival_curve.py` ×2) imports the module's **private**
  `_bump_survival_curve` / `_bump_survival_curve_at` helpers — **not** its public API. Those two
  helpers are exactly what ng now supersedes (`SurvivalCurve.bumped`, slice 1; `.bumped_at`, this
  slice), so the module's load-bearing content has crossed.
  **Superseded (4 of 6 members):** `cs01` → ng `risk/credit.py::cs01` (parallel hazard bump through
  `Priceable`+`central_diff`, no `isinstance`); `spread_dv01` ("per-pillar credit spread sensitivity
  (key-rate CS01)") → ng `bucketed_cs01`, which additionally asserts the decomposition identity the
  quarry never checked; `_bump_survival_curve` → `SurvivalCurve.bumped`; `_bump_survival_curve_at` →
  `SurvivalCurve.bumped_at`.
  **`deferred→` (both CAPABILITIES, not products — §4, so neither blocks the tick):**
  `jump_to_default` (PV if the name defaults now) → **first JTD consumer**; `CreditPosition` +
  `CreditBook` (per-name netting, `total_cs01`, `cs01_by_name`, `jtd_by_name`) → **the L6 credit
  book** (ng has `shell/portfolio.py`/`booking.py` but no credit aggregation).
  **Why this ticks where `cds.py` did not** — the distinction is *realigned parity*, not the mere
  presence of deferrals: here ng supersedes 4 of 6 members **and** everything the live importers
  actually use, whereas `cds.py` keeps 20 methods on one class of which ng supersedes about a third.
  Same standard as `options/sabr.py` and `options/swaption_vol.py`, which ticked with `deferred→`
  capabilities outstanding.
  Evidence: `spec_credit_slice3_risk.md` + `CHANGELOG` v0.120.0.

- **`credit/cds.py` re-assessed (still PARTIAL, no tick):** this slice supersedes three more of its 20
  methods — `cs01` and `bucket_cs01` → ng `cs01`/`bucketed_cs01`, and its `_bump_survival_curve`
  imports go with `credit_risk.py`. Residual now ~15 methods: quote conversions
  (`upfront`/`isda_upfront`/`to_upfront`/`par_spread`), `rec01`, `spread_duration`,
  `spread_convexity`, `theta`, `carry`, `roll_down`, amortising notional, `CDSPnLAttribution`,
  forward CDS, `StandardCDS`. Bar still not empty.

- **B6 credit slice-4 (0 TICKS — a §3d-correcting refactor + one capability; 26 / 793 unchanged):**
  recovery moved from **two** ng homes (`products/credit.py` and the bootstrap spec) to **one**:
  `snapshot.scalars[RecoveryKey(entity)]`, per §3c (*"hazard/survival curve and recovery → L1 (risk
  bumps them)"*). **Measured before the move:** with the curve bootstrapped at R=0.40 and the CDS
  marked at R=0.30, a **par** quote priced to **+96,431 on 10mm** (≈96bp of notional), silently —
  the day-count divergence's twin, and now unrepresentable rather than merely untested.
  `rec01` lands as an ordinary `RecoveryBump`, which is only possible *because* recovery is snapshot
  state: as a product field it would have needed a second instrument-mutating bump mechanism beside
  the snapshot one, and a type-switch to choose (§1). `credit/cds.py`'s `rec01` is therefore now
  superseded too — residual ~14 methods, still not empty, still no tick.
  **Byte-identical guard:** full-precision `repr` of 5 CDS PVs, the seasoned pv+accrued, `cs01`, all
  5 buckets and all 6 bootstrapped survivals, captured before and compared after — **not one ULP
  moved**. A re-layering that changed a number would have been a different change.
  Evidence: `spec_credit_slice4_recovery.md` + `CHANGELOG` v0.121.0.

- **B7 slice-1 XVA retire read (0 TICKS — PARTIAL; 26 / 793 unchanged, as the spec expected):**
  `quarry/pricebook/risk/xva.py` (783 lines, **9 production importers**, 13 functions + `XVAResult`)
  crosses **partially** as ng `risk/xva.py` (`cva`, `swap_cva`) + `risk/exposure.py`
  (`swaption_exposure_profile`). **Superseded: `cva` only** — and even that partially, since the
  quarry's is MC-driven while ng's slice-1 exposure is the analytic swaption approximation; the two
  compose the **same** ng atom once MC lands, which is the point of splitting profile from integral
  (§3d). **Resident residual, each forward-linked:** `simulate_exposures` /
  `expected_positive_exposure` / `expected_negative_exposure` / `expected_exposure` /
  `simulate_wwr_exposures` → **the general-exposure (MC) slice**, which also crosses
  `models/mc_exposure.py` (163 lines) and is the slice that will actually move this bar; `dva` /
  `bilateral_cva` → **slice 3**; `fva` / `mva` / `kva` / `xva_spread_decomposition` /
  `effective_discount_rate` → **their own slices**; `XVAResult` → the consolidated XVA report
  (ng's `PricingResult` decomposition covers one trade, not an XVA family).
  **No tick, and the spec said not to manufacture one:** ng supersedes 1 of 13 functions. B7's bar
  moves on the **general-exposure slice**, not on this opener — the same shape as credit slice 1
  (capability first, tick later), and the consumer-narrow steering rule from `CP_credit_vertical.md`
  §2 says so too: `xva.py`'s 9 importers consume the MC exposure surface, not `cva`.
  Evidence: `spec_xva_B7_slice1.md` + `CHANGELOG` v0.123.0.

- **B7 slice-2 netting retire read (0 TICKS — PARTIAL; 26 / 793 unchanged, as the spec expected):**
  `risk/xva.py`'s netting surface crosses as L5 `netted_exposure_profile(swaps, model)` + L6
  `shell.book_cva(book, model, entity)`. **`cva` is unchanged** — netting was a new profile builder,
  which is what slice 1's split was for, and a signature test now asserts it so the claim cannot
  lapse. `risk/xva.py`'s residual is **unchanged at 12 of 13 functions**: the quarry's netting lives
  inside its MC exposure path (`simulate_exposures`), which travels with the general-exposure slice.
  **Analytic netting is constrained by construction:** the swaption proxy only has a netted exposure
  when the set aggregates to a swap-equivalent (one index / currency / schedule / day-count family),
  so a heterogeneous set is a `PricingFailure` naming **which** two indices and where it defers —
  `deferred→` MC exposure, never a silent mis-net.
  Evidence: `spec_xva_slice2_netting.md` + `CHANGELOG` v0.124.0.

- **Hull-White slice retire read (0 TICKS — PARTIAL):** `quarry/pricebook/models/hull_white.py`
  (299 lines) crosses **partially** as ng `models/hull_white.py`. **Superseded:** `B`, `_log_A`,
  `_forward_rate`, `zcb_price` — the A/B closed forms, mined for content; and the European swaption,
  which ng does by **Jamshidian closed form** where the quarry used a trinomial tree.
  **Resident residual:** `_evolve_state_prices` / `tree_zcb` / `build_tree_alphas` /
  `tree_european_swaption` → **the trinomial tree**, a numerical method whose consumers are
  American/Bermudan exercise and path dependence → `deferred→` the lattice slice; path **simulation**
  → `deferred→` the MC-exposure slice (§6b: simulation's first consumer is MC, so it arrives with
  MC, not here); term-structure `σ(t)` → `deferred→` a multi-expiry calibration consumer.
  **No tick:** ng supersedes the analytics and not the numerics, and the tree is the bulk of the
  quarry module. Evidence: `spec_hull_white_slice.md` + `AUDIT_hull_white_capability.md` +
  `CHANGELOG` v0.125.0.

- **Forward-links written onto the rows that will be read (§4 "forward-link every `deferred→X`"):**
  - `options/synthetic_swaption_data.py` — **on crossing:** it imports `SwaptionVolCube` and
    `build_swaption_vol_cube` from the now-deletable module. Re-point at ng's
    `calibration/swaption_cube.py` (or drop — it is a synthetic-data helper for "testing and
    calibration without external market data feeds", consumed only by
    `models/hw_per_currency.py:114` via a lazy import). Its import is what keeps the physical park
    of `swaption_vol_cube.py` batched rather than immediate.
  - **first off-pillar swaption-cube consumer** — **on crossing:** build the bilinear
    `interp_surface(expiries, tenors, grid, x, y)` **once**, in `foundation/interpolation` (bilinear
    is finance-free → L0), composed by both the cube calibration and the read (§3d, ruling B3). The
    quarry implemented this atom **twice in one file** and the copies disagreed — on a 1-expiry grid
    `_lookup_atm` returned `0.25` while `_interp_atm` raised `IndexError` — which is exactly the
    calibrate-with-one-atom / price-with-another failure §3d exists to prevent. Neither copy crosses.
    Also due here: an off-pillar query must be a `PricingFailure`, never the quarry's silent clamp to
    the edge value.
  - **L5 risk (cube vega / vol bump)** — **on crossing:** build the cube bump as *bump the vol and
    re-imply alpha*. Never port `bumped()` (see the measurement above).
  - **first off-pillar swaption/vol consumer** — **also on crossing:** `swaption_vol.py`'s 2D
    `(expiry, tenor)` grid interpolation retires here too, alongside the cube's `interp_surface` atom
    (ruling B3). One bilinear atom in `foundation/interpolation` serves both.
  - **`desks/swaption_desk.py`** — **on crossing:** it is the single production importer of the now-ticked
    `options/swaption_vol.py` (`SwaptionVolSurface`). Re-point at
    `{SwaptionSurfaceKey(index, swap_tenor): Surface}` in the snapshot; nothing to restore, since under
    the park model no file moved.
  - **first consumer wanting currency-DEFAULTED swaption conventions** — **on crossing:** mine
    `options/swaption_conventions.py` for content (USD Black/semi-annual, EUR normal, the standard
    expiry/tenor grids). ng states conventions on the contract (slice A), so this is a convenience
    layer over that, never a replacement for it.
  - **the arb-free-SABR slice** — **on crossing:** `options/vol_arbitrage_scanner.py` retires with it
    (`scan_surface`, `enforce_no_arb`, butterfly + calendar violation detection). Its live consumer
    `options/vol_calibration.py::VolSurface.arb_report` re-points then.
  - **the general vol-surface topic** (or whichever of equity / FX arrives first) — **on crossing:**
    `options/vol_smile.py` and `options/vol_surface_strike.py` retire together — an interpolating
    strike-smile container and the per-expiry surface built on it. Consumers today:
    `desks/equity_vol_desk.py`, `fx/fx_vol_surface.py`.
  - **the HW / per-currency-models topic** — **on crossing:** `options/synthetic_swaption_data.py`
    retires with `models/hw_per_currency.py`, its one live consumer (`synthetic_hw_targets`).

The six Topic-1 deletables are now **physically parked** (git-mv'd at the T1 close, one event, doc 18 §9).
Full retire evidence + resident inventory (file:line) + forward-links are in the Topic-1 MANIFEST retire
record + `CP_slice3`/`CP_slice4` checkpoints. *(The historical `/768` — CLAUDE.md and the
slice-1/2 records — is the same universe minus the 25 `python/pricebook/__init__.py` package markers;
`793 − 25 = 768`. Not wrong, a different convention; superseded by this all-`.py` count so the series is
consistent. The **PRE-REPLAN RECORD's** separate `7 / 768` below is frozen product-vertical-era history
and is left untouched.)* Topic 0's **13** files (11 covered —
`day_count`, `calendar`, `schedule`, `rate_index`, `currency`, `settlement`, `numerical_config`,
`interpolation`, `solvers`, `serialisable`, `serialization` — plus `data_registry` **dead** and
`notional` **absorbed** into `Money`/`Leg`) are git-mv'd to `parked/topic-00-foundation/`.
`core/fixings` is **reassigned→market-data** (its immutable read model `FixingHistory` is the L0 type;
the mutable store + file I/O is not L0 — not parked here). Topic 1 does not begin until this gate is
ratified by Cowork.

---

## PRE-REPLAN RECORD (frozen history — superseded by the roll-up above)

Date: 2026-07-17 (refreshed at CP-2c)   ·   Version: `0.46.0`.

Delivers the CP-2a ruling (`rulings_CP1.md`): the honest drawdown baseline and the ordered
parity-gap list, before parity-depth slices begin. **"Crossed" = the quarry module it supersedes
is *deletable* (realigned parity reached)** — a simplified skeleton is a *partial* cross with a
recorded gap, not a cross (`CLAUDE.md §4`).

## RETIRED (deletable) — the drawdown numerator

**Drawdown = 7 / 768 (0.91%).** Quarry modules superseded (CP-3 #1–#5 + tail bond, fixed_leg).

### `fixed_income/fixed_leg.py` → superseded by `foundation/cashflow.py` + `products/leg.py` + `products/swap.py` (v0.53.0) — CP-3 tail · **no-code tick** (§4.5 "ticks immediately")
- **Superseded (no new ng code):** the `Cashflow` atom → **promoted** to `foundation/cashflow.py`
  (ng stores amount as `Money` + `Accrual` period; the quarry's decomposed notional/rate/year_frac is
  shed — year_frac derives from the accrual); `FixedLeg` construction → `products/leg.py`
  `fixed_coupon_cashflows`; the leg container → `products/swap.py FixedLeg`; `FixedLeg.pv` → the engine
  (discounted cashflows). `Cashflow.to_dict` → ng `Cashflow.to_dict`/`from_dict` (already in the
  property sweep).
- **Consumer analysis (§4):** the 3 external quarry `FixedLeg(` sites are `swap.py` (un-crossed →
  `deferred→swap`) and `ois.py`/`bond.py` (**already deletable** → retire with them). Quarry `Cashflow`
  has 0 external production instantiations.
- **`deferred→swap` (+ options/structured/desks):** `FixedLeg.annuity` / `weighted_annuity` (RPV01
  building blocks) — consumed only by un-crossed modules (swaption, CMS, zc_swap, swap/asset desks); no
  crossed ng consumer. ng exposes annuity as an **engine/curve building block** when swap crosses
  (CLAUDE.md §3 "building blocks reused upward"), not as a product method.
- **Oracle:** no new code, so no new red — the tick rests on ng's existing green leg/cashflow/swap/bond
  oracles (which already exercise `fixed_coupon_cashflows` + `Cashflow` round-trip) + the consumer
  analysis above. `floating_leg.py` is a **separate** retire (projection/multi-curve `pv`) — travels
  with the swap / multi-curve slice.

### `fixed_income/bond.py` → superseded by `products/fixed_rate_bond.py` (v0.52.0) — CP-3 tail ⚠️ heaviest retire, flagged for Cowork CP-4 spot-check
- **Superseded:** the bond **product** (coupon+redemption cashflows) → ng `FixedRateBond`; curve
  pricing → `DiscountingEngine`; **`accrued_interest` + clean-vs-dirty → engine A2 decomposition**
  (`PricingResult.accrued`/`clean`).
- **Consumer analysis (§4/§4.5):** all 8 production instantiations of quarry `FixedRateBond` are in
  **un-crossed** modules (`desks/api` ×6, `benchmark_bonds`, `sukuk`). No **crossed** ng module consumes
  any bond yield-analytic (the only `duration`/`convexity` in ng is SA-CCR's unrelated *supervisory*
  duration). ⇒ nothing is needed-now beyond the product.
- **`deferred→` (large surface — the judgment call in this retire):** the whole yield-analytics suite
  (`yield_to_maturity`, `macaulay/modified_duration`, `convexity`, `dv01_yield`, `*_sc`) →
  `desks/api`+`benchmark_bonds`+`sukuk`; `from_convention` → `composite_convention`+`esg_bonds`+
  `supranational`+`sovereign_bonds`. Per the spine these are **L4/L5 engine analytics, not product
  methods** — built when a consumer crosses (§6b), never cloned onto the pure-data product.
- **`deferred→persistence`:** serialisation (added early, §4.5 — never blocked the tick).
- **Tick rationale:** under the ratified consumer-analysis rules the product is superseded and the
  analytics have no crossed consumer ⇒ deletable. But it rests on the largest deferred surface yet, so
  it is explicitly flagged for Cowork spot-check (may un-tick; reversal is cheap).

> **Serialisation classification (Cowork CP-3 ruling §4.5, `rulings_CP3.md`):** across all five CP-3
> retires, `to_dict`/`from_dict` is **`deferred→persistence`**, NOT a genuine residual — ng has no
> serialisation consumer yet (the DB `from_dict` dispatcher is quarry-side; the persistence/data-spine
> layer is un-crossed). It was **built early by deliberate policy** (adding it in-passing beats a mass
> retrofit after persistence lands), never to justify a tick. Binding rule (CLAUDE.md §4):
> **serialisation never blocks a tick** — where cheap and already in the module, add it; else retire
> and forward-link `→persistence`. The five ticks stand; nothing to rework.

### `fixed_income/zero_coupon_bond.py` → superseded by `products/fixed_cashflow.py` (v0.51.0) — CP-3 #5
- **Genuine residual — CLOSED:** `to_dict`/`from_dict` (reuses shared `Cashflow`/`Money` encoders). A
  ZCB *is* a single fixed cashflow (`Face·DF(T)`), priced by the existing `DiscountingEngine`.
- **Consumer analysis (§4):** quarry `ZeroCouponBond` has **no external production instantiation** (only
  its own docstring; production ZCBs flow via `sovereign_bonds.py from_convention`). The money-market
  yield analytics (`price_from_yield_*`, `yield_*`, `modified_duration`, `dv01`) have 0 production
  consumers (only `tests/test_sovereign_bonds.py`); the quarry's dedicated `fixed_income/tbill.py`
  (`TreasuryBill`) is the real home for T-Bill conventions ⇒ ZCB's copies are **`dead` duplicates**.
- **`shed:` `from_convention` = `deferred→sovereign_bonds`** — see the forward-link on that backlog row.

### `fixed_income/ois.py` → superseded by `products/ois.py` (v0.50.0) — CP-3 #4
- **Genuine residual — CLOSED:** `to_dict`/`from_dict` (round-trip + `schema_version`); DB-dispatcher path.
- **Consumer analysis (§4):** quarry `OISSwap` has 2 production instantiations — `desks/api.py:641`
  (`deferred→desks/api`) + `OISConvention.create_swap` (in-module, retires with it). ng supersedes
  single-curve pricing (`engine/ois.py`, `OIS == vanilla IRS`); `pv_ctx` multi-ccy branch = deferred.
- **`shed:` `from_convention` = `dead`** — sole caller `tests/test_convention_factory.py` (quarry test).
- **Refactor (rule of two ×2):** `Accrual.to_dict`/`from_dict` (FRA + coupon cashflows) and
  `Cashflow.to_dict`/`from_dict` (deposit + OIS legs) lifted to `foundation/cashflow.py`; FRA + deposit
  refactored under green oracles. Leg encoding stays inlined in OIS (its only serialising consumer).

### `fixed_income/fra.py` → superseded by `products/fra.py` (v0.49.0) — CP-3 #3
- **Genuine residual — CLOSED:** `to_dict`/`from_dict` (round-trip + `schema_version`). Same
  production-reachable path as #1/#2 — the DB dispatcher (`db.py from_dict`).
- **Consumer analysis (§4 phantom-residual rule):** the quarry `FRA` class has **one** production
  instantiation — `desks/api.py:273` `FRA(...).pv(curve, projection_curve)`, a **multi-curve** path.
  `desks/` is un-crossed ⇒ `deferred→desks/api` (multi-curve travels with it), **not owed now**. ng
  supersedes single-curve pricing via `engine/fra.py` (+ seasoned fixings).
- **`shed:` `from_convention` = `dead`** — sole caller `tests/test_convention_factory.py::`
  `test_fra_from_convention` (quarry test, retires with quarry); 0 production callers.
- **Refactor:** rule of two fired at the 2nd serialising product → `Money.to_dict`/`from_dict` lifted
  to `foundation/money.py` (deposit + FRA consume it); deposit refactored under its green oracle.

### `fixed_income/deposit.py` → superseded by `products/deposit.py` (v0.48.0) — CP-3 #2
- **Genuine residual — CLOSED:** `to_dict`/`from_dict` (round-trip + `schema_version`). Same residual
  as CP-3 #1: the production-reachable reconstruction path is the DB dispatcher (`db.py:310`
  `from_dict(json.loads(...))`), so a product must round-trip to be persistable.
- **Needed functionality covered:** the deposit *concept* (place `face`, receive `face·(1+rτ)`) as
  the two-cashflow `Deposit` product priced by `DiscountingEngine`; the **curve-pillar role**
  (`discount_factor = 1/(1+rτ)`) superseded by `DepositQuote` in `bootstrap_discount_curve`.
- **Evidence method** (CLAUDE.md §4): bare-name grep `Deposit` / `Deposit(` / `Deposit.from_convention`
  across `python/` source + tests; checked the DB serialisation dispatcher for dynamic reconstruction.
- **Key evidence — the quarry `Deposit` class has ZERO production instantiations:** `grep 'Deposit('
  python/pricebook` → 0 hits (bootstrap uses a loose `deposit_day_count` param + inline `year_fraction`,
  never the class). Every `Deposit(` site is a test.
- **`shed:`**
  - **`dead`** — `from_convention` (1 caller: `tests/test_convention_factory.py::test_deposit_from_convention`,
    a quarry test that retires with the quarry; 0 production callers — same interpretation as CP-3 #1's
    `mc_antithetic`); `discount_factor` / `pv` / `pv_ctx` / `year_fraction` / `cashflow` properties
    (0 production consumers; superseded by ng's product + engine + `DepositQuote`).
- **Ruling-refinement flag (for Cowork):** CP-3 #2 was scoped as *conventions/RateIndex → retire
  deposit*. The evidence shows deposit's residual was **serialisation, not conventions** — deposit has
  no production consumer of conventions at all. Conventions/RateIndex is real cross-cutting infra but
  belongs to its genuine consumer (per-currency curve construction, `curves/curve_builder`
  `get_conventions`), to be built when *that* is crossed — not speculatively here. **No conventions
  code was written.**

### `core/numerical_config.py` → superseded by `foundation/numerical_config.py` (v0.47.0) — tick confirmed (Cowork spot-check, `rulings_spotcheck_retire_1.md`)
- **Genuine residual — CLOSED:** `to_dict`/`from_dict` (round-trip + `schema_version`) and `replace`.
- **Needed functionality covered:** `mc_paths`, `mc_seed` (ng engines consume these) + `fd_bump`
  (ng's DV01 knob). Validation of positive knobs preserved.
- **Evidence method** (per CLAUDE.md §4 protocol — narrow `\.name` was too weak, missed constructor
  kwargs): bare-name grep across `python/` **source + tests**, + constructor-kwarg (`NumericalConfig(name=…)`)
  + serialisation-round-trip check. Hit counts recorded below.
- **`shed:` — the 12 knobs, re-classified (Cowork §2):**
  - **`dead`** (no consumer / no identifiable future one): `mc_antithetic` (3 hits — all the module's
    own test), `mc_use_sobol` (1), `mc_brownian_bridge` (0), `extra` (0 on `NumericalConfig.extra`;
    the 123 bare hits are a *different* `.extra` on calibration types).
  - **`deferred→X`** (identifiable future consumer in the un-crossed `numerical/` toolkit — forward-linked
    on X's backlog row):
    `cos_n`(6)/`cos_L`(0)→`numerical/_fourier`; `pde_time_steps`(4)/`pde_space_steps`(1)/`pde_n_std_devs`(0)→`numerical/_pde`;
    `tree_steps`(5, all `compare_engines` local kwarg)→`numerical/_trees`; `integration_tol`(2)/`integration_max_iter`(0)→`numerical/_integrate`;
    `rootfinder_tol`(2)/`rootfinder_max_iter`(0)→`numerical/_rootfinding`.
  - **Correction note:** my first pass labelled all 12 `dead` from an attribute-only grep; the audit
    caught `cos_n` reached via a serialisation-round-trip constructor kwarg → *not* `dead`. Deferred ≠ dead
    (deferred carries the obligation below). Tick stands: no ng module needs any of the 12 now.

## Headline

- **Quarry: 768 modules. New tree: 55 modules. Deletable: 7** (`core/numerical_config`,
  `fixed_income/deposit`, `fixed_income/fra`, `fixed_income/ois`, `fixed_income/zero_coupon_bond`,
  `fixed_income/bond`, `fixed_income/fixed_leg`).
- **Drawdown = 7 / 768 (0.91%)** — CP-3 serialisation cluster (#1 config, #2 deposit, #3 FRA, #4 OIS,
  #5 ZCB) + tail (bond, fixed_leg). The rest of the ng tree is a *simplified parallel build* still short of superseding its counterparts (below).
- **CP-2b progress (parity order #1→#3):** curve rate accessors added (`zero_rate`,
  `instantaneous_forward`); **HW de-flattened — the biggest single gap, now general-curve**; `FRA`
  added (was untouched backlog). Deletability still needs a rigorous per-module parity confirmation
  (the CP-2b process gap).
- Of the 49 ng modules, **~7 are redesign spine with no direct quarry counterpart** (they *enable*
  future crossings but don't themselves retire a quarry module): `market/keys` (A5 `MarketKey`),
  `market/snapshot` (A5), `models/discounting_model` (A1), `risk/priceable` (Priceable protocol),
  `foundation/results` (A2 decomposition), `foundation/numerical_config`, `market/discount_curve`
  partially (loglinear curve type).

## Per-ng-module parity (49) — all `partial`

### L0 foundation (10) → mostly `core/` + `numerical/`
| ng module | quarry counterpart(s) | parity gap |
|---|---|---|
| time | core/day_count, schedule, rate_index | subset of conventions; no ICMA/BUS252 breadth, no RateIndex fixings |
| schedule | core/schedule | no full roll/stub/calendar-adjusted breadth |
| calendar | core/calendar, market_conventions | minimal holiday model; no market_conventions |
| money | core/currency, notional | Money only; no currency table / notional conventions |
| cashflow | core/settlement, notional | atom only |
| distributions | numerical/_distributions(_theory) | `norm_cdf` only; no inverse/other laws |
| solvers | numerical/_rootfinding, _optimize | `bisect_root` + `nelder_mead` of a 30-module toolkit |
| black | models/black76 | one formula |
| numerical_config | core/numerical_config, models/mc_config | redesign knobs; not the quarry superset |
| results | core/pricing_context (decomposition) | redesign (A2); no direct quarry module |

### L1 market (4) → `core/` + `curves/` + `credit/`
| ng module | quarry counterpart(s) | parity gap |
|---|---|---|
| discount_curve | core/discount_curve, curves/bootstrap | +zero_rate/instantaneous_forward (CP-2b) + **forward_rate + RateCurve protocol (CP-2c, closes ruling §4.1/§4.2)**; pluggable interpolation + roll_down remain; vs curves/ (31) |
| survival_curve | core/survival_curve, credit/issuer_curve, hazard_term_structure | annual grid, log-linear; no term-structure breadth |
| snapshot | core/pricing_context, market_data | redesign (A5 keyed registry); enabler |
| keys | core/data_registry | redesign (A5); enabler |

### L3 models + calibration (6) → `models/` (90) + `curves/` + `credit/`
| ng module | quarry counterpart(s) | parity gap |
|---|---|---|
| models/hull_white | models/hull_white, hw_calibration, hw_per_currency, short_rate_models | **general-curve now (CP-2b — flat gap CLOSED)**; remaining: constant vol (no term structure), per-ccy, tree. Closest to parity. |
| models/discounting_model | core/pricing_context | redesign (A1); enabler |
| models/credit_model | credit/issuer_curve, credit_risk | thin adopt-market wrapper |
| calibration/discount_curve | curves/bootstrap, rfr_bootstrap, multicurve_solver | deposits+par-swaps single-curve |
| calibration/hull_white | models/hw_calibration | caplet + cap-strip least-squares; no swaption/co-terminal |
| calibration/survival_curve | credit/bond_hazard_bootstrap, hazard_term_structure | CDS par bootstrap only |

### L2 products (11) → `fixed_income/` (130) + `credit/` + `fx/` + `equity/` + `commodity/`
| ng module | quarry counterpart(s) | parity gap |
|---|---|---|
| fixed_rate_bond | fixed_income/bond, zero_coupon_bond | vanilla fixed only; vs 130-module bond zoo |
| swap | fixed_income/swap, ois | single-curve vanilla IRS; no OIS/basis/xccy |
| fra | fixed_income/fra | +seasoned via FixingHistory (CP-2c, quarry FRA lacks fixings). Deletable-bar read: quarry ISDA-settle == ng end-settle (single-curve). **Residual: multi-curve `forward_rate(projection_curve)`, `par_rate`/`pv_ctx`, convention builder.** Not deletable. |
| deposit | fixed_income/deposit | **new (CP-2c)**; 2-cashflow trade via DiscountingEngine (fwd par→0, spot par→principal via A2). Deletable-bar read: ng covers pricing + forward/temporal (quarry values redemption-only). **Residual: convention builder, implied-DF-as-method (ng has via DepositQuote), pv_ctx, serialisation.** Not deletable. |
| ois | fixed_income/ois | **new (CP-2c)**; single-curve OIS via shared `float_leg_pv` (== vanilla IRS). Deletable-bar read: ng covers single-curve pricing + par. **Residual: currency conventions (SOFR/SONIA/ESTR), `bootstrap_ois`, par_rate/annuity/dv01, daily-fixing compounding, multi-curve basis.** Not deletable. |
| swaption | fixed_income/(swaption), options | European payer/receiver only |
| leg | fixed_income/fixed_leg, floating_leg | fixed + structural float |
| fixed_cashflow | fixed_income (cashflow) | atom |
| inflation | fixed_income/inflation(_unit), jarrow_yildirim | ZCIS only |
| cds | credit/cds, cds_conventions | single-name vanilla |
| fx_forward / fx_option | fx/ (22) | outright fwd + GK vanilla |
| equity_option | equity/ (33) | BS vanilla |
| commodity_option | commodity/ (23) | BS-on-carry vanilla |

### L4 engine (14) → `pricing/` + `models/` + asset-class pricers
| ng module | quarry counterpart(s) | parity gap |
|---|---|---|
| discounting | pricing/pricing_engine, core | linear DF engine (A1/A2) |
| swap / swaption | fixed_income, models | vanilla + Jamshidian analytic |
| swaption_mc | models/mc_engine, mc_exposure, mc_pricer | T-fwd single-factor MC; no general MC framework |
| spot_option / equity_option / commodity_option / fx_option / fx_forward | models/black76, asset-class | closed-form vanillas |
| cds / inflation | credit, fixed_income | leg math / Fisher |

### L5 risk (5) → `risk/` (54) + `regulatory/` (23) + `models/mc_exposure`
| ng module | quarry counterpart(s) | parity gap |
|---|---|---|
| exposure | models/mc_exposure, risk/xva | HW-1F swap exposure (fwd + risk-neutral paths, MPOR, collateral); no general product/model |
| xva | risk/xva, network_xva, hybrid_xva, simm | CVA/DVA/BCVA/FVA/KVA/MVA on one netting set; no WWR/FTD/SIMM-sensitivities |
| saccr | regulatory/counterparty, credit_rwa | IR single hedging set; no margined MF / other asset classes / collateral |
| greeks | core/greeks, risk/greeks, pathwise_greeks | bump-and-reprice on Priceable; no AAD/pathwise |
| priceable | risk/ (protocol) | redesign; enabler |

### L6 shell (2) → `core/book, trade, daily_pnl` + `risk/valuation_report` + `desks/`
| ng module | quarry counterpart(s) | parity gap |
|---|---|---|
| booking | core/book, trade, daily_pnl, settlement | Trade/Book/benefit table + realized-vs-mark; no persistence (data-spine), no lifecycle events, float realized needs fixings |
| xva_report | risk/valuation_report, desks/ | swap-only netting set (parity gap, ruled); no Book input / non-linear products |

## Untouched backlog — quarry subpackages with ~no ng counterpart

| subpackage | modules | note |
|---|---|---|
| fixed_income | 130 | the bulk; ng has ~7 vanillas (swap/leg/cashflow/inflation); **deposit + fra + ois + zero_coupon_bond + bond + fixed_leg RETIRED (v0.48–0.53)**; `floating_leg` deferred→swap/multi-curve; repo/futures/sovereign/xccy families untouched. **Deferred — on crossing `sovereign_bonds.py`:** ZCB + bond `from_convention` path (per-currency conventions), deferred from the ZCB (v0.51) + bond (v0.52) retires. **Deferred — on crossing `esg_bonds`/`supranational`/`composite_convention`:** bond `from_convention`. **Deferred — `tbill.py` carries its own T-Bill analytics** (ZCB copies shed dead). **Deferred — on crossing `swap.py`:** expose `annuity`/`weighted_annuity` (RPV01) as an engine/curve building block, deferred from the `fixed_leg` retire (v0.53); `floating_leg` retire (projection pv) also travels with swap/multi-curve. |
| credit | 93 | ng has vanilla CDS + hazard; CDO/tranche/CLN/loan/hawkes/recovery untouched |
| models | 90 | ng has flat HW; PDE/MC framework, Levy/rough/LMM/G2++/trees untouched |
| options | 61 | fully untouched |
| risk | 54 | ng has exposure/xva/greeks/saccr; portfolio/attribution/optimisation/simm untouched |
| desks | 49 | fully untouched (trading-desk layer). **Deferred obligation — on crossing `desks/api.py`:** the bond **yield-analytics** suite (`yield_to_maturity`, `macaulay/modified_duration`, `convexity`, `dv01_yield`, `*_sc`), deferred from the bond retire (v0.52.0) — build as **L4/L5 engine analytics** (spine), not product methods. Same suite deferred to `benchmark_bonds`, `sukuk`. |
| equity | 33 | ~1 vanilla; rest untouched |
| curves | 31 | ng has 1 loglinear + bootstrap; NS/Smith-Wilson/multicurve/AAD untouched |
| numerical | 30 | ng has 2 solvers; PDE/MC/FFT/AD/QMC toolkit untouched. **Deferred obligations from `core/numerical_config` retire (v0.47.0)** — on crossing, add the knob back to `NumericalConfig`: `_fourier`←`cos_n,cos_L`; `_pde`←`pde_time_steps,pde_space_steps,pde_n_std_devs`; `_trees`←`tree_steps`; `_integrate`←`integration_tol,integration_max_iter`; `_rootfinding`←`rootfinder_tol,rootfinder_max_iter`. |
| core | 29 | ~10 crossed-partial; approximation/caching/serialization/interpolation untouched |
| commodity / regulatory / structured | 23 each | commodity ~1 vanilla; regulatory ~saccr-partial; structured untouched |
| fx | 22 | ~2 vanillas |
| statistics | 17 | untouched |
| crypto / viz / pricing / ts / data / db / pe / calibration | 15/13/8/7/5/2/4/4 | untouched (calibration = the quarry's own record types) |

## Ordered parity-gap priority (foundation-first, per the CP-2 ruling)

Progress now = **quarry modules retired**, not features added. Bring the foundational spine to
realigned parity + oracle until each quarry counterpart is deletable, then move up:

1. **curves — general / bootstrapped multi-pillar curve** — *CP-2b: rate accessors done; forward_rate
   + interpolation + roll_down remain.* Nelson-Siegel / Smith-Wilson / multicurve later.
2. **models/hull_white — general-curve HW-1F** — *CP-2b: DONE (flat gap closed).* hw_calibration and
   term-structure vol to parity remain.
3. **fixed_income spine** — bond / swap / leg / **deposit (RETIRED v0.48.0)** / **fra (CP-2b done)** /
   ois to parity, plus **fixings/seasoned-float** (the 130-module bulk). *In progress.*
4. **credit spine** — issuer/hazard curve + vanilla CDS to parity.
5. Then breadth (commodity, options, more XVA) resumes — only after the foundation supersedes its
   quarry modules.

## Checkpoint note

Refreshed at **CP-3 #2** (v0.48.0): **`fixed_income/deposit` retired → drawdown 2/768.** The retire
read refined the ruling: deposit's residual was **serialisation, not conventions** (it has zero
production consumers; `from_convention` is a quarry-test-only `dead` feature). No conventions/RateIndex
code was written — it re-aims at its genuine consumer (per-currency curve construction) when crossed.
Cowork ratified the correction (`rulings_CP3_correction.md`): serialisation through-line confirmed,
**§4 phantom-residual rule added** (residuals need consumer evidence; re-derive by consumer analysis at
retire time; gaps likely overstated → drawdown faster than the map claims). CP-3 #3 (FRA), #4 (OIS),
#5 (ZCB), tail (bond, fixed_leg) done via consumer-analysis retire-reads. CP-3 checkpoint written + ruled
(`rulings_CP3.md`, §4.5: serialisation deferred→persistence, built-early, never blocks a tick).
**inflation.py — held PARTIAL CROSS (v0.54, NOT ticked, drawdown stays 7):** multi-product module;
ng supersedes only ZCIS (`ZeroCouponInflationSwap`+`ZCISEngine`+A5 real curve, which also supersedes
`CPICurve`). `YoYInflationSwap` = `dead` (test-only); `InflationLinkedBond` = `deferred→desks/api`+
`inflation_indices` (un-crossed) but a whole UNBUILT product. ZCIS serialisation added (build-early).
**⚠️ CP-4 Cowork question: how to retire a multi-product module when ng has built only some of its
products** (delete-defining-whole-unbuilt-products is a new pattern beyond bond's deferred methods).
**Vanilla cluster now closed** (deposit/fra/ois/zcb/bond/fixed_leg retired; inflation partial).
**Next = the SWAP decision → CP-4.** **Watch:** swap has 29
production instantiations (curve pillars/XVA) — load-bearing, NOT a serialisation-only retire; its real
residual is larger (multi-curve/curve-build role). **⚠️ Bond (v0.52) is the heaviest tick — large
deferred yield-analytics surface; flagged for Cowork CP-4 spot-check (may un-tick).** **CP-4 checkpoint
at first of: (a) vanilla cluster retired + swap decision, (b) 6 slices since CP-3, (c) multi-curve introduced.**
