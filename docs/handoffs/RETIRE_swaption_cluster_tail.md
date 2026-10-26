# Retire-sweep — the six swaption-cluster leftovers (proposals; Cowork rules the ticks)

**Date:** 2026-10-26 · **Baseline:** v0.116.0 · **Spec:** `spec_swaption_cluster_tail.md` §2
**Method:** §4 dead-evidence protocol — bare-name grep over `quarry/pricebook` **and** `quarry/tests`
(952 test files), plus dynamic reachability (string/dict keys, `getattr`, `importlib`, `**kwargs`).
Importer counts in the spec were the starting thread; the verdicts below are the read.

**Proposed: 2 ticks, 4 leave-resident → drawdown 23 → 25 / 793 if ruled.** Not applied — the tracker
is unchanged pending the ruling.

## Method note — one dynamic hit, checked and dismissed

The protocol's dynamic sweep returned exactly one hit: `market_data/_types.py` contains the string
`"swaption_vol"`. **It is a false positive** — `SWAPTION_VOL = "swaption_vol"` is a `QuoteKind` enum
*value* that happens to share the module's text, not a dynamic reference to the module. Recorded
because retire-#1's false negative came from exactly this family, and the protocol asks *how* a claim
was verified, not just the verdict. All other dynamic patterns: 0 hits across both trees.

Also corrected from the spec's thread: `vol_arb.py`'s apparent use of `enforce_no_arb` is a
**docstring cross-reference** (`* :func:`enforce_no_arb` — …`), not a consumer.

---

## 1. `swaption_vol.py` (186 lines) — **PROPOSE TICK**

**Surface:** `SwaptionVolSurface` — a 2D ATM vol grid `vol(expiry, tenor)`, with
`.vol`, `.vol_expiry_tenor`, `.bumped`, and three private interpolators (`_interp_expiry`,
`_interp_tenor`, `_interp_2d`).
**Consumers:** 1 production (`desks/swaption_desk.py`), 4 test files. Dynamic: 0 (see note).

**Superseded, with the ng path already built and oracled:**
- the **container** → `{SwaptionSurfaceKey(index, swap_tenor): Surface}`. ng's snapshot types
  `surfaces: Mapping[SurfaceKey | SwaptionSurfaceKey, Surface | SabrSurface]`, so the quarry's one 2D
  grid decomposes into keys × term structures — doc 19's closed-shapes×open-keys, the asset dimension
  in the key. **Oracled:** `tests/L4/test_swaption_sabr.py:254` prices a swaption off
  `{SwaptionSurfaceKey(INDEX, TENOR): Surface.flat(0.22)}`.
- `.vol_expiry_tenor` at-pillar → `Surface.at(expiry, …)` on the keyed surface.
- **`.bumped(shift)` → superseded by `risk/greeks.py::vol_vega`** + the bump machinery. Note this is
  *unlike* the cube's `bumped()` (slice B F7, wrong by 5.4–6.2×): an additive shift on an **ATM
  lognormal Surface** is dimensionally correct, because a Surface's entries *are* vols. Nothing is
  inherited and nothing is wrong here — worth saying, since the two bumps share a name.

**`deferred→` (capability, not product — §4, so it does not block the tick):** the 2D off-pillar
interpolation (`_interp_2d`/`_interp_expiry`/`_interp_tenor`) → **first off-pillar consumer**, already
the named deferral from slice B ruling B3 and audit F6. ng is at-pillar by ratified design.

**Genuine residual: empty.**

## 2. `swaption_conventions.py` (152 lines) — **PROPOSE TICK**

**Surface:** `VolQuoteType`, `SmileType`, `SwaptionConvention`, `get_swaption_convention`,
`list_swaption_currencies`, + `_STANDARD_EXPIRIES`/`_STANDARD_TENORS`.
**Consumers — bare-name, both trees:** `VolQuoteType` 0/0 · `SmileType` 0/0 · `SwaptionConvention`
0/0 · `get_swaption_convention` **0 src** / 1 test · `list_swaption_currencies` **0 src** / 1 test.
Dynamic: 0. **No production consumer anywhere in the quarry.** The one test
(`tests/test_swaption_infra.py`) is a shared test for "swaption conventions, synthetic data, HW per
currency" — there is no dedicated test file, and it retires with the module.

**Superseded by design, not by a counterpart type.** ng makes a swaption's conventions **explicit on
the contract**: slice A established that the fixed-leg frequency and day counts are the *swap's*, and
that `RateIndex` cannot carry them (ML-D1, 48.8bp). A per-currency lookup registry is therefore the
shape ng deliberately does not have — the contract states its conventions rather than defaulting them
by currency.

**Precedent for not treating the content as a residual:** retire-#2 — *"the quarry `Deposit` class had
zero production instantiations; building conventions would have been speculative infra with no ng
consumer."* Same situation.

**`deferred→`:** the convention *content* (USD Black/semi-annual, EUR normal, etc. — real market
knowledge) → **the first consumer that wants currency-defaulted swaption conventions.** Mined for
content if and when that arrives; no ng consumer exists today.

**Genuine residual: empty.**

## 3. `vol_arbitrage_scanner.py` (223 lines) — **PROPOSE LEAVE-RESIDENT**

**Surface:** `ArbViolation`, `ArbitrageScanResult`, `scan_surface`, `scan_all_surfaces`,
`enforce_no_arb`.
**Consumers:** `options/vol_calibration.py:112` — a **live** lazy import inside
`VolSurface.arb_report()`, which builds a default strike grid and calls `scan_surface`. Plus
`tests/test_vol_desk.py`.

**ng has no arbitrage scanner at all** (grep: zero butterfly/calendar-spread/arb machinery in
`src/pricebook/`). This is capability ng lacks entirely, not a container to re-key. It is also already
the named deferral from slice B: *"arb-free SABR (Hagan-2002 wing arb is a known limit) → its own
slice."*

**Forward-link → the arb-free-SABR slice.** A tick here would be a paper tick: nothing in ng
supersedes it, and its consumer is live.

## 4. `vol_surface_strike.py` (110 lines) — **PROPOSE LEAVE-RESIDENT**

**Surface:** `VolSurfaceStrike` — several `VolSmile`s, one per expiry, linearly interpolated.
**Consumers:** `desks/equity_vol_desk.py` and `fx/fx_vol_surface.py` — **equity and FX**, plus 4 test
files. Not a swaption module: no swaption consumer at all.

**General strike-axis vol machinery.** ng's only strike-dependent vol object is `SabrSurface` — a
*fitted* parametric smile, not an interpolating container — so there is no counterpart, and building
one now would be infra ahead of its consumer (§6b).

**Forward-link → the general vol-surface topic** (and the equity / FX topics that consume it). Travels
with whichever arrives first; it is not a swaption-cluster tick.

## 5. `vol_smile.py` (68 lines) — **PROPOSE LEAVE-RESIDENT**

**Surface:** `VolSmile` — strike-dependent vol at one expiry, interpolated from quoted (strike, vol)
pairs.
**Consumers:** `options/vol_surface_strike.py`, `desks/equity_vol_desk.py`, `fx/fx_vol_surface.py` +
5 test files. Same story as #4, one layer down, and #4 depends on it.

ng's nearest objects are `SmileQuote` (the *quotes*) and `SabrSurface` (the *fit*) — neither is an
interpolating smile container. **Forward-link → the general vol-surface topic**, with #4.

## 6. `synthetic_swaption_data.py` (121 lines) — **PROPOSE LEAVE-RESIDENT**

**Surface:** `synthetic_atm_surface`, `synthetic_smile_data`, `synthetic_hw_targets`, + per-currency
base-vol tables.
**Consumers:** `models/hw_per_currency.py:114` — a live lazy import of `synthetic_hw_targets` — plus
`tests/test_synthetic_curves.py` and `tests/test_swaption_infra.py`.

The spec flagged it as moot for the forward-link (correct — under the park model nothing moves, so its
import of the now-ticked `swaption_vol_cube` is not broken). But it is **not** trivially `dead`: its
one production consumer is live. ng generates synthetic test data inline where it needs it (slice B's
`_node_quote` builds a grid from a seed `SabrParams`), so there is no ng counterpart and no ng
consumer.

**Forward-link → the HW / per-currency-models topic**, with `hw_per_currency.py`.

---

## Summary

| module | lines | prod consumers | verdict | why |
|---|---|---|---|---|
| `swaption_vol.py` | 186 | 1 | **TICK** | container → keys × `Surface` (oracled); `bumped` → `vol_vega`; 2D interp `deferred→` off-pillar consumer |
| `swaption_conventions.py` | 152 | **0** | **TICK** | no production consumer; ng states conventions on the contract (slice A), registry shape deliberately absent |
| `vol_arbitrage_scanner.py` | 223 | 1 live | leave-resident | ng has no arb machinery; already `deferred→` arb-free-SABR slice |
| `vol_surface_strike.py` | 110 | 2 (equity, FX) | leave-resident | general strike-axis machinery; `deferred→` vol-surface topic |
| `vol_smile.py` | 68 | 3 (incl. equity, FX) | leave-resident | general smile container; `deferred→` vol-surface topic |
| `synthetic_swaption_data.py` | 121 | 1 live | leave-resident | `deferred→` HW/per-currency topic |

**Cowork's prediction held on 5 of 6.** It expected `swaption_conventions` and *possibly* `swaption_vol`
/ `vol_arbitrage_scanner` to tick, and `vol_smile` / `vol_surface_strike` to stay. The read agrees,
except **`vol_arbitrage_scanner` does not tick** — ng has no arb machinery at all and its consumer is
live, so a tick would be a paper tick.

**Neither proposed tick needs ng code.** Both are supersede-with-evidence against paths already built
and oracled, which is why this is a sweep and not two slices.

---

## COWORK RULING — 2026-10-26 16:39 (both ticks APPROVED, 23 → 25 / 793)

Spot-checked per §4, not rubber-stamped — and one claim was worth checking:

- **TICK 1 `swaption_vol.py` — APPROVED.** My first (crude substring) grep lit up ~10 modules and
  looked like an over-claim; it was my grep that was wrong — `swaption_vol` matches `swaption_vol_cube`,
  `synthetic_swaption_data` and the `QuoteKind` enum value. The precise module-import check confirms
  the read: `swaption_vol.py` exports exactly `SwaptionVolSurface`, imported by exactly **one**
  production module (`desks/swaption_desk.py`, un-crossed → `deferred→swaption_desk`, a capability not
  a product). Container superseded by `{SwaptionSurfaceKey: Surface}`, **oracle verified** at
  `tests/L4/test_swaption_sabr.py:254` (prices a swaption off `Surface.flat(0.22)` under that key);
  `.bumped`→`vol_vega` (dimensionally a vol bump, genuinely unlike the cube's `alpha` bug); 2D interp
  `deferred→` off-pillar consumer. Residual empty.
- **TICK 2 `swaption_conventions.py` — APPROVED.** Verified independently: all five public names are
  **0 src, 0 quarry-non-self**, only shared-test hits. Superseded by design (slice A — conventions are
  the swap's, stated on the contract; a per-currency registry is the shape ng deliberately lacks),
  retire-#2 precedent holds. Content `deferred→` the first currency-defaulting consumer. Residual empty.
- **The divergence is RIGHT — `vol_arbitrage_scanner` leave-resident, confirmed.** Grep for
  arb/butterfly/no-arb machinery in `src/` returns **nothing** — ng has none, the consumer is live, so
  a tick would be a paper tick. Correctly `deferred→` the arb-free-SABR slice. The other three
  leave-resident calls (`vol_surface_strike`, `vol_smile` → general vol-surface topic;
  `synthetic_swaption_data` → HW/per-currency topic) stand.

**Drawdown 23 → 25 / 793** on landing. Code lands the two tracker rows (carrying this ruling), the four
forward-links on their destination rows, and the version/CHANGELOG stamp in one slice.
