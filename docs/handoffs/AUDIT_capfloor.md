# Audit — Cap/Floor retirement (slice 23): quarry read, shed classification, build plan

**Baseline:** v0.108.0 · **Quarry module:** `python/pricebook/options/capfloor.py` (500 lines, read
end-to-end) · **Mandate:** Cowork — "Cap/Floor retirement: product + pricing + the #10 ladder fix +
SABR-cap calibration. Ticks `options/capfloor.py`." Ratified: **one `cap_ladder` atom** composed by
the pricer, the strip AND the SABR-cap calibration.

## 1. Quarry inventory (per-symbol, end-to-end read)

| quarry symbol | what it is | disposition |
|---|---|---|
| `CapFloor.__init__` + `.periods` | schedule generation → `(start, end)` period pairs | **crosses** → L2 `CapFloor(index, schedule, …)` + `cap_ladder` |
| `CapFloor.price` | per-period Black-76 via a duck-typed `model.price_ir_option` | **crosses, re-shaped** → L4 `price_capfloor` = Σ `price_caplet` (capability protocol, not `hasattr`) |
| `CapFloor.caplet_pvs` | per-caplet PV **+ greeks** dicts | PV crosses via the ladder; **greeks `deferred→L5`** (ng greeks are generic bumps on the engine) |
| `CapFloor.greeks` | sums the per-caplet greek dicts | **`deferred→L5`** (same) |
| `strip_caplet_vols` (L180) | real `CapFloor` + Brent, but takes **only the last new period** as the marginal | **crosses, FIXED** → the #10 ladder strip (all new caplets in the interval share the marginal) |
| `strip_caplet_vols_from_quotes` (L332) | dict quotes, dates from year-fractions | **shed (debt)** — it does **not strip**: `# Simplified: use the flat cap vol as the caplet vol for this bucket` |
| `StrippedCapletVol` + `to_dict` | the stripped-vol record | **crosses** as the ng `Surface` pillars; `to_dict` → **`deferred→DB-spine`** |
| `calibrate_capfloor_sabr` | buckets by `round(tenor*2)/2`, averages, **invents the smile** | **crosses, CORRECTED** → strip per strike → real `SmileQuote` per expiry → slice-21 fit |
| `_capfloor_pv_ctx` | `PricingContext` PV with per-caplet surface lookup | **shed** — `pv()`-on-product is forbidden (§2: products are pure data); ng prices in L4 |
| `_cf_from_convention` | build from `CurrencyConventions` | **`deferred→conventions`** (the same registry retire #2 found had no ng consumer) |
| serialisation (`convention` field, T4-CAP1) | round-trip fields | **`deferred→DB-spine`** |

## 2. Audit #10 — what was actually wrong, and why the oracle missed it

`vol_strip.py` builds **one caplet per quote**:
`accrual = Accrual(q.maturity, q.maturity + tenor, day_count)`. So a "2Y cap" quote is modelled as a
**single** caplet fixing at 2Y — not the ~7-caplet ladder a 2Y 3M-EURIBOR cap actually is. Two
consequences: the caplet grid is silently forced to equal the quote grid, and `q.maturity` is read as
the marginal caplet's **fixing** date (so a cap "maturing at M" pays at `M + tenor`).

**Why the existing oracle cannot see it:** the flat-in/flat-out test strips a flat cap-vol curve and
checks every stripped caplet vol equals the flat vol. With one caplet per quote *or* a full ladder,
a flat input gives a flat output exactly — the oracle is blind to the ladder's shape. The repricing
oracle is equally blind, because it reprices the same one-caplet object it stripped.

**The fix is therefore a COUNT oracle plus a finer-grid reprice**, not a tighter tolerance: assert the
2Y cap has 7 caplets (not 1, not 8), and reprice a cap whose caplet grid is *finer* than the quote
grid back to its flat-vol quote. Neither passes under the old code.

## 3. Shed classification (evidence protocol, §4)

Bare-name greps across `python/pricebook/**` source **and** `python/tests/**`:

| omitted quarry behaviour | class | evidence |
|---|---|---|
| per-caplet **greeks** (`caplet_pvs`, `greeks`) | **`deferred→L5`** | 3 quarry test consumers (`test_ir_deep`, `test_xi7_sabr_cap_caplet`, `test_options_hardening`), 0 production; ng risk is generic bump-and-reprice on the engine, so a cap gets greeks the moment it is `Priceable` |
| `strip_caplet_vols_from_quotes` | **shed (debt)** | its own comment admits it assigns the flat vol instead of stripping; consumers: 1 quarry test (`test_curves_advanced`). Superseded by a strip that actually solves |
| `calibrate_capfloor_sabr`'s **synthetic smile** `avg_vol·(1 + 0.1·(K−F)/F)` | **shed (debt)** | a fabricated 10%-per-unit-moneyness skew fitted as if it were market data; ng fits the **stripped** vols across real quoted strikes |
| its 0.5Y tenor **bucketing** + forward/vol averaging | **shed (debt)** | collapses distinct expiries into one bucket and fits SABR to the average — ng fits per expiry, on that expiry's own forward |
| its `except Exception` → hardcoded `(α=avg_vol, ρ=0, ν=0.3)` fallback | **shed (debt)** | a silent fake calibration; ng returns `CalibrationFailure` (invariant 4) |
| `strip_caplet_vols`' `except Exception: caplet_vol = flat_vol` | **shed (debt)** | same pattern — a failed solve silently becomes the flat vol |
| first-period **`t_fix ≤ 0` → intrinsic off the FORWARD** | **shed (correction)** | a fixed period's payoff is determined by its **fixing**, not by a curve forward; the quarry has no fixing there. ng excludes the first (already-set) caplet per market convention and the engine refuses a seasoned caplet as a value |
| `_capfloor_pv_ctx` (`pv_ctx` on the product) | **shed (design)** | §2 — products do not price themselves; its T4-CAP2 fix (per-caplet surface lookup) is how ng works by construction |
| `_cf_from_convention` | **`deferred→conventions`** | 0 production consumers, 0 tests (same finding as retire #2: the convention registry has no ng consumer yet) |
| `to_dict` / the `convention` serialisation field | **`deferred→DB-spine`** | travels with the DB spine, as the SABR persistence artefact does |
| `notional > 0` validation | **crosses** | kept on the ng product |

**Residual after this slice: greeks (`deferred→L5`), conventions constructor
(`deferred→conventions`), serialisation (`deferred→DB-spine`)** — three deferred *capabilities*, no
deferred *product*, so `options/capfloor.py` **ticks deletable** (§4) and drawdown goes **20 → 21/793**.

## 4. The `cap_ladder` atom (§3d) — and the one place I read Cowork's spec conservatively

`cap_ladder(cap) -> tuple[Caplet, ...]` derives the strip from the cap's **own** schedule, excluding
the first period. Composed by `price_capfloor` (L4), the vol strip (L3) and the SABR-cap calibration
(L3) — defined once, so no stage can disagree about which caplets a cap is.

**Excluding the first period is market convention, not a simplification.** A spot-starting cap's
first period fixes at the cap's start, so it is a known cashflow, not an option — caps are quoted
excluding it (Brigo–Mercurio §1.6). It is also what makes a spot cap *priceable at all* here: the
engine refuses a seasoned caplet as a value (#3a), so including period 0 would fail every cap the
strip needs to price. A genuinely **forward-starting** cap, whose first period fixes in the future,
therefore loses a caplet — deferred with a trigger (`OPEN.md`), because fixing that means threading
the valuation date into the ladder, which would make the atom valuation-dependent and break the
one-ladder invariant.

**Conservative reading:** Cowork wrote "each ladder caplet carries its **canonical** accrual". I build
each caplet from the cap's own schedule period (`Accrual(p.accrual_start, p.accrual_end,
index.accrual.day_count)`), which **equals** the canonical accrual for an unadjusted schedule at the
index tenor — the only kind in scope — and differs for an adjusted one. Substituting the canonical
accrual unconditionally would mean pricing a *different contract* than the one described (different τ,
different forward) and silently so. With the contract's own periods, `cap == Σ its own caplets` is
exact, and a non-canonical schedule trips the **ruling-2 guard per caplet** → `PricingFailure`. Loud,
not silent. Flagged for the checkpoint.

## 5. Build plan

**STEP A — product, pricing, the ladder, the #10 strip fix.**
1. L2: `Caplet` gains `option_type` (default CALL) — the floorlet its docstring promised "arrives with
   its consumer"; this slice is that consumer. `price_caplet` reads it (CALL default ⇒ byte-identical).
2. L2: `CapFloor(index, schedule, strike, notional, option_type)` (5 fields) + `cap_ladder(cap)`.
3. L4: `price_capfloor` = Σ `price_caplet` over `cap_ladder`, propagating the first failure. Law-
   polymorphic and ruling-2-guarded for free, because it composes the existing caplet pricer.
4. L3: `vol_strip` builds the LADDER per quote (schedule from the valuation date to `q.maturity` at
   `Frequency(index.id.tenor)`) and solves ONE marginal vol per quote interval, shared by every new
   caplet in it (piecewise-constant marginal vol). Surface pillars = every ladder caplet expiry.
   New guard: all quotes must share one strike — a `Surface` has no strike axis, so stripping mixed
   strikes into one is the same class of silent error as #10.

**STEP B — `calibrate_capfloor_sabr`.** Group quotes by strike → strip each strike's ladder → regroup
by expiry → `SmileQuote(expiry, strikes, vols)` → the slice-21 `calibrate_sabr_smile` per expiry →
`SabrSurface`. Reuses the bounded LS, the 1bp acceptance gate and the F-identity; no new fitting code.

## 6. Oracles

**A:** the 2Y 3M-EURIBOR ladder is **7** caplets, first excluded (the #10 count oracle); `cap == Σ
cap_ladder` exactly; **put-call parity** `cap − floor = Σ df·N·τ·(F − K)` composed from the `forward`
/`df` atoms (independent of the option path, exact to <1e-12); the #10-fixed strip reprices each cap
to its flat quote on a **finer** caplet grid; per-caplet F-identity; a floor prices as PUT caplets; a
normal-law cap prices at a negative forward (inherited from slice 22); a non-canonical cap →
`PricingFailure`. **Byte-identical:** the single-`Caplet` path and all of slices 1–22 unchanged.
**B:** round-trip on a quote grid equal to the caplet grid (exact seed recovery per expiry); reprice;
contradictory smile → `CalibrationFailure` (1bp gate). **§3d:** one `cap_ladder` — asserted by
comparing the ladder the strip builds with the pricer's and the calibrator's.
