# Checkpoint — SABR multi-law (the vol law becomes a value; SABR finishes)

**Version:** v0.108.0 · **Slice:** `slice/22-sabr-multilaw` · **Baseline:** v0.107.0 (SABR cluster).
**Trigger:** a new capability family (the normal/Bachelier law) **+ a module tick** — both §6 stops.
**Mandate:** the Cowork ruling on `CP_SABR_cluster.md`, executed in full (rulings 1 and 2 folded in,
shifted + normal variants added, `options/sabr.py` retired).

## 1. The headline — the law was a hidden assumption; now it is data

Every slice before this one assumed *lognormal* in three places at once: `black` in the pricer, the
Hagan 2.17a expansion in the model, and `F > 0` in a hard-coded engine guard. Those three are **one
fact** — a law — and they were spread across three layers. `VolLaw` binds them into a value
(formula · expansion · domain · α-scale), and the three real laws arrive together.

What that bought, concretely:
- the pricer stopped knowing which law it prices in (asserted over its **AST**: no law import, no law
  name, `isinstance` only on the capability protocols);
- the `F ≤ 0` guard became `law.defined(F, K)` — so **audit #15 is discharged** by the design rather
  than patched: a negative forward is a failure under `Lognormal` and ordinary under `Normal`;
- the calibrator became law-generic for free — one code path fits a lognormal, shifted or normal smile
  in that law's own units, because it composes `model.vol_law.sabr_vol` and `seed_alpha`;
- `BlackVol` → `ImpliedVol`: with the law as data, a method named `black_vol` returning a normal vol
  was a lie the type system could not catch.

**The promotion moved no number.** 47 lognormal pricing paths (Black caplet × strikes/vols, SABR
caplet × params/strikes, Black swaption × rates/vols/both parities) were dumped as exact float reprs
before STEP A and after STEP B: byte-identical. `Lognormal.price` *delegates* to `black`, so the
refactor is an identity by construction, not by luck (§8 carve-out, used as intended).

## 2. The one place the ruling was not followed literally (and why)

**The normal expansion is the β=0 form, not general-β eq 2.17b.** The general-β normal expansion is
written in `log(F/K)` and `(FK)^p`, so it is undefined for a negative forward — which contradicts
*this slice's own requirement* that a negative-forward caplet price under the normal law, and
contradicts `Normal.defined = True`. A law claiming domain "everywhere" whose expansion raises at
`F < 0` is incoherent. So `Normal` is the β=0 dynamics, whose exact expansion variable is
`z = (ν/α)(F − K)` — no logs, prices through zero, and the standard negative-rates object. The
general-β-CEV-quoted-in-normal-units case is a **law conversion**; it RAISES rather than being
silently approximated (`ML-D2`), and `SabrSurface` enforces β=0 for a `NORMAL` tag at the data
boundary so the mismatch cannot reach a pricer. Recorded in the audit doc as a build-time revision.

**Ruling 1 was folded in with one correction:** the gate is NOT `SolveConfig.tolerance`. That knob is
the solver's step/objective xtol (1e-12); an acceptable *fit* is a vol-residual question (1bp is
market practice, and the quarry's own `max_rmse_bp` default). Gating on 1e-12 would have rejected the
slice-21 round-trip fit, which is exact to 8e-11 — a perfect fit failing a quality gate. The
threshold is a module constant (one consumer ⇒ concrete, §6b), ledgered `ML-D3`.

## 3. Oracle-quality audit

| Oracle | Class | Result |
|---|---|---|
| **47 lognormal pricing paths before vs after the promotion** | **byte-identical (same-process)** | exact |
| `bachelier` vs an independent inline normal formula (erf), 288 cases, both parities | closed-form cross-impl | <1e-15 |
| **Bachelier put-call parity `C − P = F − K`**, F and K of either sign | **exact identity** | <1e-15 |
| `sabr_normal_vol` at ρ=0 vs its `asinh` closed form (`χ(z) = asinh(z)`) | closed-form, independent function | <1e-15 |
| **ν=0 ⇒ σ_N ≡ α at every strike, negative strikes included** | closed-form anchor | <1e-16 |
| F=K ATM branch (removable `z/χ` singularity) | limit check | <1e-16 |
| **One β=0 dynamics priced via `black`@σ_B vs `bachelier`@σ_N** | cross-law consistency (approx) | ~1e-4 rel (asserted <5e-4; the quarry conversion misses by ~3e-3) |
| `ShiftedLognormal(0)` ≡ `Lognormal`; `ShiftedLognormal(s)` ≡ lognormal on the shifted pair | structural identity | exact |
| Negative-forward caplet through the engine vs inline `bachelier`/`black`-on-shifted | closed-form cross-engine | <1e-10 |
| **Per-law round-trip:** NORMAL recovers its seed (reprice identity) | **known-answer** | <1e-8 / <1e-8 |
| **Per-law round-trip:** SHIFTED recovers its seed at a **negative** forward | **known-answer** | <1e-6 / <1e-6 |
| Contradictory smile → `CalibrationFailure` with residuals > 1bp; real smile passes | value-not-raise + control | asserted |
| Stub caplet · odd-day-count caplet → `PricingFailure`; canonical caplet prices | value-not-raise + control | asserted |
| Negative-forward smile under the lognormal law → `CalibrationFailure` | domain, one definition | asserted |
| Pricer AST carries no law import / no law name / no non-capability `isinstance` | structural guard | asserted |

Two things worth naming. First, the **round-trips are known-answer, not fit-converges**, and recovering
the seed *also* re-proves the F-identity per law (the fit's forward must equal the generating one).
Second, the laws' identities (`ShiftedLognormal(0) ≡ Lognormal`, delegation to `black`) are **exact**
because they are the same call, not two implementations agreeing — composition guaranteeing an
identity rather than a test chasing one (§3d).

## 4. Challenge-me

- **`seed_alpha` is a fourth member on `VolLaw`, and it is a *numerical* fact in a *financial* value.**
  It is there because the lognormal seed `σ_ATM·F^{1−β}` is **not even real** for a negative forward
  (Python returns a complex), and because α means different things per law. The alternative was a law
  switch in the calibrator — forbidden. Still: a protocol carrying "how to seed a solver" is a slight
  smell. If a second numerical fact wants in (bounds per law, say), the honest move is a separate
  `LawCalibrationHints` value rather than growing `VolLaw` member by member.
- **The model-law/surface-tag guard duplicates what `for_index` already guarantees.** `for_index` is
  the sanctioned constructor; the guard in `implied_vol` exists because the dataclass constructor is
  still reachable with an explicit law. It is cheap (a frozen-value comparison through the same
  factory, no reverse mapping) and it caught nothing in testing — kept because a law/params mismatch
  is silently wrong by a factor of F. **Is a loud guard the right answer, or should `SABRModel`'s
  constructor be made private so the factory is the only path?**
- **One law per surface, one law per model (`ML-D4`).** A real desk might quote a shifted smile at the
  front and a lognormal one further out. Deferred with a trigger, not designed for.
- **The F-identity guard refuses a product class the quarry priced.** A stub caplet used to price
  (wrongly, silently, if a smile model was involved); it now fails as a value. That is a deliberate
  **capability regression in exchange for correctness**, ledgered `ML-D1` with the signature change it
  defers. Worth an explicit ruling: is refusing stubs acceptable until a consumer appears?
- **`ImpliedVol`/`SwaptionVol` now extend `CalibratedModel`.** This couples "has a vol" to "is bound to
  a market" — defensible (a vol without its market is meaningless, and the calibrator needs both from
  one object) but it does narrow doc 22 Q1's orthogonal-capability story.

## 5. Smell + debt scan

- `verify.py` acyclic / fields / layers / provenance / version / **debt** all green; `pyright` **0
  errors** (repo config); **320 tests** (+29).
- **§3d exception-count: 0.** No `isinstance`/type-switch on a product or model in any pricer or
  calibrator; the only tag→law dispatch is `vol_law_for`, at construction. The `SabrSurface` narrowing
  stays in the model/market modules, so the §1 guard test over `risk/` stays green.
- **Atoms shared, not re-derived:** `canonical_accrual` is now ONE definition (L0) composed by the
  model, the calibrator and the engine — it was duplicated inline in two of them before this slice.
  `sabr_vol`/`bachelier`/`black` each have exactly one implementation, reached through the law.
- **Field/arg discipline:** `SabrSurface` 3 fields, `SabrParams` 4, `SabrCalibrationSpec` 5; `price` 5
  args, `sabr_vol`/`seed_alpha` ≤4, `bachelier` 5. No new grouping type was needed, and none was
  invented speculatively.
- **No suppressions added** (balance unchanged). Four deferred-scope rows (`ML-D1`…`ML-D4`), each with
  a named trigger, each failing loud today.
- **Pre-existing, out of scope:** `ruff PLR0913` flags an 8-arg helper in `tests_ng/L0/test_rate_index.py`.
  CLAUDE.md §3b scopes the limit to `src/pricebook_ng/**`, so this is not debt — noted so it is not
  re-discovered as a finding.

## 6. Drawdown (§4) — 19 → **20 / 793** (+1 TICK)

`options/sabr.py` is **deletable**. Slices 20–22 cross its whole vol/pricing/calibration content;
the only genuine residual is the `SABRCalibrationResult`/`CanonicalCalibrationResult` persistence
artefact → **`deferred→DB-spine`**, grep-confirmed to have **0 ng consumers** and forward-linked on
the DB-spine row of the Topic-1 MANIFEST. A deferred *capability* (not a product) does not block a
tick. Everything else is classified with evidence in `AUDIT_sabr_multilaw.md` §3 — including four
pieces shed as hidden-wrongness debt (a silent vol floor, a degenerate-ρ fallback, two unreachable
clamps) and the `T ≤ 0 → return α` branch shed as a **correction** (wrong for β≠1).

Physical `git mv` batches at the next topic close (doc 18 §9), as for the Topic-1 six.

## 7. Named next checkpoint

Whichever comes first (§6): **≤6 slices**, or the next capability-cluster boundary.

**Recommended next work, now that drawdown moves again:** stay on retiring. `options/capfloor.py` and
the swaption/vol-cube modules are the natural next targets — the cap/floor **strip** and
`calibrate_capfloor_sabr` are the named residuals already forward-linked to "the SABR/smile slice",
and that slice's building blocks (the laws, the smile calibrator, the strip) now all exist. That would
tick modules rather than add surface. The forward alternative (swaption-SABR / a vol cube) buys
breadth but ticks nothing, and §4's "breadth waits while drawdown is stuck" has only just been
satisfied once.
