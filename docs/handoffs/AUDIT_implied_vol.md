# Audit — Implied-vol inversion (slice 24): quarry read, shed classification, plan

**Baseline:** v0.109.0 · **Quarry module:** `python/pricebook/options/implied_vol.py` (182 lines, read
end-to-end) · **Mandate:** none from Cowork — this is the retiring slice recommended in
`CP_capfloor.md` §7 and authorised by Bernardo while the slice-22/23 rulings are pending. Chosen
because it is small, ticks a module on its own, and is the natural next thing now that **both** laws
exist (the quarry has one inverter per law; ng needs one inverter, period).

## 1. Quarry inventory (end-to-end read)

| quarry symbol | what it is | disposition |
|---|---|---|
| `implied_vol_black76(price, F, K, T, df, type, tol, max_iter)` | Newton-on-vega → bisection fallback, discounted price | **crosses, re-shaped** → the law-generic inverter |
| `implied_vol_bachelier(…)` | the same body with `bachelier_price` and its own vega | **absorbed** — one generic inverter covers it (and the SHIFTED law the quarry never had) |

Two functions, one algorithm, duplicated: the only difference is which price function and which vega.
Since slice 22 made the law a **value** with `price(F, K, σ, t, type)`, the inversion is law-generic
for free — so the ng counterpart is ONE function, and it covers three laws rather than two.

## 2. Consumer evidence (§4 protocol — bare-name greps, `python/pricebook/**` + `python/tests/**`)

| symbol | production consumers | verdict |
|---|---|---|
| `implied_vol_black76` | **7** — `options/sabr_mc.py:140`, `desks/api.py:999`, `models/hw_calibration.py:126`, `models/rough_equity.py:141`, `models/jump_calibration.py:162`, `models/g2pp_calibration.py:385`, `equity/joint_calibration.py:24` (+ `test_xi5_equity_forward_option_iv`) | a **real, load-bearing capability** — the standard "model price → implied vol for comparison" utility every MC/model calibration in the quarry leans on. ng must have it for those modules to cross. |
| `implied_vol_bachelier` | **0** (only `test_implied_vol.py`, `test_implied_vol_roundtrip.py`) | `dead` in production — but absorbed at zero cost by the generic inverter, so it is not *shed*; the normal law simply becomes one of the laws the one function inverts. |

**ng consumers today: zero.** Stated plainly rather than dressed up: this capability lands because it
**retires a module** (§4 — cross-cutting work is justified by what it retires) whose capability seven
un-crossed quarry modules depend on. It is one concrete function, not an abstraction layer, so §6b's
rule of two does not bite; the *atom* it introduces does have two real in-slice consumers (below).

## 3. Shed classification

| omitted quarry behaviour | class | reasoning / evidence |
|---|---|---|
| `df` inside the signature (inverts a **discounted** price) | **crosses, re-shaped** | discounting stays out of an analytic block (§2, as for `black`/`bachelier`): ng inverts the UNDISCOUNTED price and the caller divides `df·N·τ` out — the same split the engine uses to multiply it in |
| **Newton-on-vega** as the primary solver | **shed (§7bb)** | it needed a bisection fallback *precisely because* Newton is not unconditionally convergent here (the quarry falls back on `vega < 1e-15` and on `vol <= 0`). Brent on a guaranteed bracket converges always, and §7bb puts scipy's numerics ahead of hand-rolled ones. `black_vega` stays (L5 risk uses it); no capability is lost. |
| `return 0.5 * (lo + hi)` after 200 failed bisection steps | **shed (hidden wrongness)** | returns a **non-solution** silently — the exact failure §5 forbids. ng raises. |
| Bachelier bracket `hi = forward * 5.0` | **shed (BUG)** | negative for a negative forward and zero at `F = 0` — an inverted/degenerate bracket in precisely the negative-rate case the normal law exists for. ng's bracket is a vol range, never a function of `F`. |
| Black bracket hard-capped at `5.0` with no report | **shed (hidden wrongness)** | a true vol above 500% silently returns ≈2.5. ng raises a message naming the cap. |
| `tol` used as BOTH a price tolerance (`abs(diff) < tol`) and a vol tolerance (`hi - lo < tol`) | **shed (conflated units)** | ng solves to Brent's `xtol` on the vol and the oracle checks the price residual separately |
| explicit upper-bound check (`call ≤ df·F`, `put ≤ df·K`) | **shed, subsumed** | the bound is law-specific (finite for lognormal, **unbounded** for normal), so a hard-coded check cannot be law-generic. The bracket expansion reports exactly this condition generically — "not attainable below the vol cap" — and the lower bound falls out of `law.price(…, vol=0, …)`, which IS the intrinsic (the laws' degenerate branch). One generic mechanism replaces two law-specific bounds. |
| `_norm_pdf` imported privately from `black76` | **shed** | ng has the `distributions` adapter (§7bb) |
| `option_type` parameter | **replaced by the parity atom** | the implied vol of a put IS the implied vol of the call at the same strike — that is the whole content of put-call parity, which is **exact and identical in every ng law** (`C − P = F − K`, oracled in slices 22–23). ng names the relation (`call_price_from_put`) instead of carrying a flag into the solver, and the round-trip oracle inverts PUT prices through it. |

**Residual: empty.** No deferred capability, no deferred product ⇒ `options/implied_vol.py` ticks
**deletable**, drawdown **21 → 22 / 793**.

## 4. The atom this slice promotes (§3d)

The quarry's bracket-expanding search is **already duplicated inside ng**: `vol_strip._solve_vol`
hand-rolls the same "evaluate at `lo` and `hi`, double `hi` until the sign flips or the cap is hit,
then Brent" loop. So the slice promotes it to L0 —

`invert_increasing(f, target, lo, hi, cap)` — the inverse of a monotonically increasing function,
with an expanding upper bracket; raises when `target` is unattainable, naming which end failed.

— and gives it **two real in-slice consumers**: the new single-option inverter and the strip's
marginal solve, refactored onto it (its hand-rolled loop deleted). Rule of two satisfied by existing
code, not by anticipation. L0 is legitimate: it is finance-free numerics (no strike, no vol, no
payoff in its vocabulary — `verify.py layers` enforces that literally).

## 5. Plan

1. **L0** `foundation/solvers.py`: `invert_increasing` (same constants/order of operations the strip
   used, so the strip's numbers stay byte-identical).
2. **L3** `models/implied_vol.py`:
   - `implied_vol(law, call_price, forward, strike, t)` — 5 args, law-generic, composes `law.price`
     and `law.defined`, solves with `invert_increasing`. §3d by construction: the inverse composes
     the very function it inverts, so price→vol→price cannot drift.
   - `call_price_from_put(put_price, forward, strike)` — the parity atom, exact in every law.
3. **L3** `calibration/vol_strip.py`: `_solve_vol` composes `invert_increasing` (dedupe).

## 6. Oracles

- **Round-trip per law** (`Lognormal`, `ShiftedLognormal(0.03)`, `Normal`), over a strike/vol/expiry
  grid: `price → implied_vol → price` recovers the vol to <1e-10 and the price to <1e-14. Known-answer
  at both ends (the input vol is the answer), not a self-consistency loop.
- **PUT prices invert through the parity atom** to the same vol as their calls (the `option_type`
  parameter's content, reproduced exactly).
- **Negative forward** inverts under `Normal` and `ShiftedLognormal` — the case whose quarry bracket
  (`hi = forward * 5.0`) was broken — and is refused by `Lognormal.defined`.
- **Failure, not a silent number** (the quarry's worst habit): below intrinsic, above the vol cap,
  `t ≤ 0`, outside the law's domain — each raises, each named.
- **Byte-identical:** the strip's stripped vols and all 47 legacy pricing paths unchanged.
