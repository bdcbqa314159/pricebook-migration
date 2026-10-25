# Audit — SABR multi-law (slice 22): quarry read, shed classification, build plan

**Baseline:** v0.107.0 · **Quarry module:** `python/pricebook/options/sabr.py` (377 lines, read
end-to-end) · **Mandate:** Cowork ruling on the SABR-cluster checkpoint — "Finish SABR: multi-law
promotion + shifted/normal variants. Ticks `options/sabr.py`." Ratified: a **`VolLaw` value**
(polymorphic, no `isinstance`).

## 1. Quarry inventory (per-symbol, end-to-end read)

| quarry symbol | what it is | disposition |
|---|---|---|
| `sabr_implied_vol` | Hagan 2002 lognormal expansion (2.17a + ATM 2.18) | **crossed v0.106.0** → ng `sabr_vol` |
| `sabr_price` | Hagan vol → `black76_price(…, df, …)` | **crossed v0.106.0** → L4 engine composes `df·N·τ·black` |
| `sabr_calibrate` | SSE / Nelder-Mead fit of (α, ρ, ν), `1e10` penalty | **crossed v0.107.0** → bounded LS (a real box) |
| `calibrate_sabr_smile` | `sabr_calibrate` + post-fit `warnings.warn` diagnostics | **crossed v0.107.0** (+ ruling 1, below) |
| `shifted_sabr_implied_vol` | Hagan applied to `(F+s, K+s)` | **this slice** → `ShiftedLognormal(shift)` law |
| `shifted_sabr_price` | shifted vol → `black76_price(F+s, K+s, …)` | **this slice** → `ShiftedLognormal.price` |
| `sabr_normal_vol` | σ_B · √(FK) — an ad-hoc *conversion*, not an expansion | **this slice, CORRECTED** → Hagan 2.17b |
| `SABRCalibrationResult` · `CanonicalCalibrationResult` · `_build_calibration_record` · `to_dict` | DB-persistence / provenance artefact (`db.save_calibration`) | **`deferred→DB-spine`** |

## 2. The one deliberate CORRECTION (copy-ADAPT, not clone)

The quarry's `sabr_normal_vol` converts the lognormal vol: `σ_N ≈ σ_B · √(F·K)`, with its own
docstring admitting "Approximation … for moderate moneyness." That is not the Hagan normal
expansion; it is a moneyness-dependent rescaling that is only exact in the ATM/β=1 limit. ng
implements **Hagan 2002 eq 2.17b** (the genuine normal/Bachelier expansion, with its own
numerator series `1 + L²/24 + L⁴/1920` and its own correction bracket
`−β(2−β)α²/24(FK)^{1−β} + ρβνα/4(FK)^{(1−β)/2} + (2−3ρ²)ν²/24`).

**Consequence:** ng's normal vol will NOT reproduce the quarry's numbers. This is a supersede, not
a parity gap (§4 "deletable = SUPERSEDE, not clone"); the quarry's only consumer of the conversion
is its own `tests/test_shifted_sabr.py`, which retires with the quarry.

## 3. Shed classification (evidence protocol, §4)

Bare-name greps across `python/pricebook/**` source **and** `python/tests/**`:

| omitted quarry behaviour | class | evidence |
|---|---|---|
| `SABRCalibrationResult` + canonical record + `to_dict` | **`deferred→DB-spine`** | 1 production consumer (`desks/api.py`) + 3 tests (`test_provenance_carrier`, `test_calibration_result_lmm_sabr`, `test_calibrator_provenance_conformance`); **0 ng consumers** — ng has no DB spine. Forward-linked on the DB-spine row. |
| `rmse` / `reprice_errors_bp` / `max_error_bp` / `max_rmse_bp` | **`dead`** (derivable) | all are functions of the per-strike residuals ng already returns on `CalibrationResult.residuals`; no ng consumer reads a pre-aggregated rmse |
| `warnings.warn` on a poor fit / out-of-range params | **shed as debt** | superseded by ruling 1 (failure is a value, invariant 4) and by the real parameter box |
| `max(result, 1e-10)` implied-vol floor | **shed as debt** | a silent clamp — hidden wrongness (§5); ng's parameter box keeps the expansion in its domain |
| `ratio <= 0 → z_over_x = 1.0` fallback | **shed as debt** | silently substitutes the ATM limit for a degenerate ρ; unreachable under ng's `|ρ| ≤ 0.9999` box |
| `sqrt_arg = max(1−2ρz+z², 0)` · `one_minus_rho = max(1−ρ, 1e-10)` | **`dead`** (defensive) | the discriminant is positive for every `|ρ| < 1`; both clamps are unreachable inside ng's box |
| `T <= 0 → return alpha` | **shed as correction** | wrong for β≠1 (α is not the zero-time vol unless β=1); ng's expansion evaluates its own `t=0` limit `α/F^{1−β}` |
| `sabr_price`'s `df` argument | **crossed, re-shaped** | discounting is kept out of the analytic block; the L4 engine multiplies `df·N·τ` (invariant) |
| 17 quarry source consumers of `sabr_implied_vol` (inflation, swaption cube, fx/equity/commodity smiles, lmm, cds, aad, desks) | **not an omission** | ng *has* the atom (`sabr_vol`); these are un-crossed quarry modules that will compose it when they cross. Physical parking batches at topic close (doc 18 §9), so the coupling is not a tick blocker. |

**Residual after this slice: the DB-persistence artefact only → `deferred→DB-spine`.** Per §4 a
deferred *capability* (not a product) never blocks a tick ⇒ `options/sabr.py` ticks **deletable**,
drawdown **19 → 20 / 793**.

## 4. Why a `VolLaw` value (the design, §6b rule of two)

Three laws arrive in this slice — lognormal, shifted-lognormal, normal — each pairing *three*
things that must never be mixed: an option formula (`black` / `black(F+s,·)` / `bachelier`), a SABR
expansion (2.17a / 2.17a-on-shifted / 2.17b), and a **domain** (where the law is defined at all:
`F>0` / `F+s>0` / everywhere). Pairing them in a value is what keeps the engine switch-free; the
alternative — an `if law is NORMAL` ladder in `price_caplet` — is exactly the §1 prohibition.

Rule of two is satisfied **three times over** in-slice; nothing speculative (no stub support, no
β-calibration, no second numeraire).

## 5. Build plan (STEP A before STEP B — refactor under green)

**STEP A — promote, numbers unchanged.**
1. `models/sabr.py` splits: analytic expansions stay; `SABRModel` moves to `models/sabr_model.py`
   (the existing `black.py` / `black_model.py` precedent). This is what lets `vol_law.py` import the
   expansions without a cycle.
2. `models/vol_law.py`: the `VolLaw` protocol (`price` · `sabr_vol` · `defined`) + `Lognormal`.
   `Lognormal.price` **delegates to `black`** — byte-identical by construction.
3. `BlackVol` → **`ImpliedVol`** (`black_vol` → `implied_vol`, + a `vol_law` property). The rename is
   the honest consequence of the law becoming data: a Normal-law model's vol is *not* a Black vol.
   The *signature* is unchanged (no `accrual` threaded — deferred to the first stub consumer).
4. `price_caplet` / `price_swaption` compose `model.vol_law.price(...)` instead of calling `black`
   directly, and replace the hard-coded lognormal `F ≤ 0` guard with `law.defined(F, K)`.
   No new red (§8 refactor carve-out); the existing oracles must not move a number.

**STEP B — add the laws (additive).**
5. `models/bachelier.py`: `bachelier(F, K, vol, t, type)` — the normal-model sibling of `black`.
6. `models/sabr.py`: `sabr_normal_vol` (the β=0 Hagan normal expansion + its removable `z → 0` limit).
7. `models/vol_law.py`: `ShiftedLognormal(shift)` · `Normal` · `vol_law_for(kind, shift)` — the ONE
   tag→law mapping.
8. L1 `SabrSurface` grows `law: VolLawKind` + `shift: float` (**data only**; L1 cannot import L3).
   `SabrParams` unchanged.
9. Ruling 1 — `calibrate_sabr_smile` returns `CalibrationFailure` (carrying the residuals) when the
   max |vol residual| exceeds `SolveConfig.tolerance`.
10. Ruling 2 — `price_caplet` guards `caplet.accrual == index.canonical_accrual(expiry)`; a
    non-canonical (stub) optionlet fails LOUD as a `PricingFailure`. `canonical_accrual` becomes the
    **one** shared definition (§3c rule 5: an index convention spoken by L3 and L4 ⇒ L0).

**Pre-checked:** every existing caplet fixture (`test_caplet`, `test_sabr_caplet`, `test_vol_strip`,
`test_greeks`, `test_audit_batch_a_l4`, `test_shell`) already builds
`Accrual(expiry, expiry + index.id.tenor, ACT_360)` on `EURIBOR_3M` (whose `accrual.day_count` *is*
ACT/360) ⇒ the ruling-2 guard is green on arrival, not retro-fitted to the tests.

## 6. Oracles

**A (promotion):** lognormal caplet + swaption byte-identical through `law.price`; contradictory
smile → `CalibrationFailure`; non-canonical accrual → `PricingFailure`.
**B (laws):** `sabr_normal_vol` vs its **ρ=0 `asinh` closed form** (`χ(z) = asinh(z)` — a genuinely
independent function, stronger than re-typing the same expression) to <1e-15; the **ν=0 ⇒ σ_N ≡ α at
every strike, negative strikes included** closed-form anchor; the **cross-law price check** (one β=0
dynamics priced through `black`@σ_B and `bachelier`@σ_N agrees to ~1e-4 relative, where the quarry's
conversion is ~3e-3 off — so the oracle discriminates);
`ShiftedLognormal(0)` ≡ `Lognormal` at every strike; a **negative-forward** caplet now PRICES under
the normal and shifted laws (discharges audit #15, which returned `PricingFailure` there);
Bachelier vs an independent inline normal formula + put-call parity; per-law round-trip calibration
recovering a known seed at the model-derived F; per-law reprice identity; the §3d F-identity per law.
**Structural:** no `isinstance`/law-switch in either pricer — the only tag→law dispatch is the
construction-time factory.
