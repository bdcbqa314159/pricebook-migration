"""MC slice 2 — netted MC exposure, and the heterogeneous set (`spec_mc_slice2_netting.md`).

**Why MC removes the analytic constraint.** The analytic netted exposure needs the set to aggregate
to *one swap*, because the swaption proxy prices a single underlying — so a multi-index set
`PricingFailure`s. MC needs no such thing: each trade is revalued on the same simulated `r(tᵢ)` with
its **own** flows, the MtMs are added path-wise, and the max is taken after. Netting path-wise is
strictly more general, and that generality is this slice's acceptance criterion rather than a bonus.

**Netting is net-first, and the identities are what prove it.** `max(Σ MtM, 0) ≤ Σ max(MtM, 0)` holds
for *any* implementation that sums exposures too, so `≤ Σ standalone` alone proves nothing. The
discriminating pair is: same-direction trades must show **no** benefit, and offsetting ones a real
one — which a sum-of-exposures implementation fails.
"""

import math
from datetime import date

import pytest

from pricebook.foundation import (
    DayCountConvention,
    Frequency,
    MonteCarloConfig,
    PricingFailure,
    RollRule,
    ScheduleTerms,
    Tenor,
    TenorUnit,
    TimeMeasure,
    build_schedule,
    currency,
    get_rate_index,
)
from pricebook.foundation.reference_entity import ReferenceEntity
from pricebook.market.curve import DiscountCurve
from pricebook.market.curve_set import CurveKey, CurveRole, CurveSet
from pricebook.market.snapshot import MarketSnapshot, RecoveryKey
from pricebook.market.survival_curve import SurvivalCurve
from pricebook.models.hull_white import HullWhite
from pricebook.products.swap import FixedLeg, FloatLeg, VanillaSwap
from pricebook.risk.exposure import mc_netted_exposure_profile, netted_exposure_profile
from pricebook.risk.xva import cva
from pricebook.shell.portfolio import Book, Trade, book_mc_cva

Y = TenorUnit.YEAR
DC365 = DayCountConvention.ACT_365_FIXED
DC360 = DayCountConvention.ACT_360
VAL = date(2026, 1, 15)
INDEX = get_rate_index("EURIBOR_3M")
OTHER = get_rate_index("EURIBOR_6M")
CCY = INDEX.id.currency
TM = TimeMeasure(VAL, DC365)
FAR = VAL + Tenor(30, Y)
TENOR = Tenor(5, Y)
RATE, A, SIGMA = 0.030, 0.05, 0.010
RECOVERY = 0.40
NOTIONAL = 10_000_000.0
CP = ReferenceEntity("COUNTERPARTY")
CFG = MonteCarloConfig(paths=120_000, seed=20261027)


def _market(hazard: float = 0.02, recovery: float = RECOVERY) -> MarketSnapshot:
    curves = CurveSet(
        {
            CurveKey(CurveRole.DISCOUNT, CCY): DiscountCurve.flat(TM, RATE, until=FAR),
            CurveKey(CurveRole.PROJECTION, INDEX): DiscountCurve.flat(TM, RATE, until=FAR),
            CurveKey(CurveRole.PROJECTION, OTHER): DiscountCurve.flat(TM, RATE, until=FAR),
            CurveKey(CurveRole.SURVIVAL, CP): SurvivalCurve.flat_hazard(TM, hazard, until=FAR),
        }
    )
    return MarketSnapshot(VAL, curves, scalars={RecoveryKey(CP): recovery})


def _hw(hazard: float = 0.02, recovery: float = RECOVERY) -> HullWhite:
    return HullWhite(_market(hazard, recovery), A, SIGMA, CCY)


def _swap(
    strike: float = RATE, notional: float = NOTIONAL,
    index=INDEX, freq: Frequency = Frequency.ANNUAL, tenor: Tenor = TENOR,
) -> VanillaSwap:
    sched = build_schedule(VAL, VAL + tenor, ScheduleTerms(frequency=freq, roll=RollRule(calendar=None)))
    return VanillaSwap(notional, CCY, FixedLeg(sched, DC365, strike), FloatLeg(sched, DC365, index))


def _mc_cva(swaps, hw: HullWhite, cfg: MonteCarloConfig = CFG) -> float:
    profile = mc_netted_exposure_profile(swaps, hw, cfg)
    assert not isinstance(profile, PricingFailure), profile
    return cva(profile, hw.market.curves.survival(CP), hw.market.recovery(CP))


# ── ORACLE 1 — agreement with the ANALYTIC netting, where both apply ─────────────────────
def test_mc_netting_agrees_with_analytic_netting_on_a_homogeneous_set() -> None:
    """The anchor: where the analytic proxy *can* net, MC must reproduce it. Both compose the same
    HW bond, so a disagreement beyond sampling error is a bug, not a model difference."""
    hw = _hw()
    swaps = [_swap(RATE), _swap(RATE + 0.004, notional=NOTIONAL / 2)]
    mc = mc_netted_exposure_profile(swaps, hw, CFG)
    analytic = netted_exposure_profile(swaps, hw)
    assert not isinstance(mc, PricingFailure) and not isinstance(analytic, PricingFailure)
    assert [d for d, _ in mc] == [d for d, _ in analytic]
    for (d, got), (_, exact) in zip(mc, analytic):
        if exact == 0.0:
            assert got == 0.0
            continue
        assert abs(got - exact) < 0.03 * exact, (d, got, exact)


def test_the_netted_mc_cva_agrees_with_the_analytic_netted_cva() -> None:
    hw = _hw()
    swaps = [_swap(RATE), _swap(RATE + 0.004, notional=NOTIONAL / 2)]
    mc = _mc_cva(swaps, hw)
    analytic = cva(
        netted_exposure_profile(swaps, hw), hw.market.curves.survival(CP), hw.market.recovery(CP)
    )
    assert abs(mc - analytic) < 0.03 * analytic, (mc, analytic)


# ── ORACLE 2 — THE POINT: the heterogeneous set analytic cannot do ───────────────────────
def test_a_heterogeneous_set_FAILS_analytically_and_SUCCEEDS_under_mc() -> None:
    """The acceptance criterion. Two indices cannot aggregate to one swap, so the swaption proxy
    refuses — correctly, rather than mis-netting. MC revalues each trade on the same `r(tᵢ)` with its
    own flows and adds path-wise, so it has no such constraint. Both facts asserted together, since
    either alone would be misleading."""
    hw = _hw()
    mixed = [_swap(RATE, index=INDEX), _swap(RATE + 0.002, index=OTHER, freq=Frequency.SEMI_ANNUAL)]

    analytic = netted_exposure_profile(mixed, hw)
    assert isinstance(analytic, PricingFailure), analytic
    assert "indices" in analytic.reason or "schedules" in analytic.reason

    mc = mc_netted_exposure_profile(mixed, hw, CFG)
    assert not isinstance(mc, PricingFailure), mc
    assert all(math.isfinite(ee) and ee >= 0.0 for _, ee in mc)
    assert any(ee > 0.0 for _, ee in mc)


def test_the_heterogeneous_mc_cva_converges_at_the_root_paths_rate() -> None:
    """No closed-form reference exists for the mixed set, so it is oracled by convergence: the
    scatter between independent seeds must shrink as 1/√P."""
    hw = _hw()
    mixed = [_swap(RATE, index=INDEX), _swap(RATE + 0.002, index=OTHER, freq=Frequency.SEMI_ANNUAL)]
    spreads = []
    for paths in (4_000, 64_000):
        vals = [_mc_cva(mixed, hw, MonteCarloConfig(paths=paths, seed=s)) for s in (1, 2, 3, 4)]
        spreads.append(max(vals) - min(vals))
    assert spreads[1] < spreads[0] / 2.0, spreads       # 16x paths ⇒ ≈4x tighter; 2x is a safe floor


def test_a_mixed_schedule_set_also_succeeds_under_mc() -> None:
    hw = _hw()
    mixed = [_swap(RATE, freq=Frequency.ANNUAL), _swap(RATE, freq=Frequency.QUARTERLY)]
    assert isinstance(netted_exposure_profile(mixed, hw), PricingFailure)
    mc = mc_netted_exposure_profile(mixed, hw, CFG)
    assert not isinstance(mc, PricingFailure), mc
    assert any(ee > 0.0 for _, ee in mc)


# ── ORACLE 3 — the netting identities, which distinguish netting from a SUM ──────────────
def test_netted_mc_cva_never_exceeds_the_sum_of_standalone_mc_cvas() -> None:
    hw = _hw()
    for swaps in (
        [_swap(RATE), _swap(RATE - 0.003)],
        [_swap(RATE), _swap(RATE, notional=-NOTIONAL / 2)],
        [_swap(RATE), _swap(RATE + 0.005, notional=-NOTIONAL / 3), _swap(RATE - 0.002)],
    ):
        netted = _mc_cva(swaps, hw)
        standalone = sum(_mc_cva([s], hw) for s in swaps)
        assert netted <= standalone * 1.001, (netted, standalone)


def test_same_direction_trades_show_NO_benefit_and_offsetting_ones_a_real_one() -> None:
    """**The discriminating pair.** `max(Σ,0) ≤ Σ max(·,0)` holds for a sum-of-exposures
    implementation too, so the inequality alone proves nothing. Same-direction trades must net to
    the sum (no benefit), and offsetting ones must be materially cheaper."""
    hw = _hw()
    same = [_swap(RATE), _swap(RATE)]
    offset = [_swap(RATE), _swap(RATE, notional=-NOTIONAL / 2)]
    same_netted, same_sum = _mc_cva(same, hw), sum(_mc_cva([s], hw) for s in same)
    off_netted, off_sum = _mc_cva(offset, hw), sum(_mc_cva([s], hw) for s in offset)
    assert abs(same_netted - same_sum) < 0.01 * same_sum        # no offset ⇒ no benefit
    assert off_netted < off_sum * 0.9                            # offset ⇒ a real benefit


def test_a_perfectly_offsetting_set_has_almost_no_exposure() -> None:
    """Payer + identical receiver is a flat position on every path, so the netted exposure is zero
    exactly (not merely within MC error) — the cancellation happens inside each path."""
    hw = _hw()
    profile = mc_netted_exposure_profile([_swap(RATE), _swap(RATE, notional=-NOTIONAL)], hw, CFG)
    assert not isinstance(profile, PricingFailure), profile
    assert all(abs(ee) < 1e-9 for _, ee in profile), profile
    assert _mc_cva([_swap(RATE)], hw) > 0.0                      # and each leg alone is not zero


# ── ORACLE 4 — the gate extends, and reproducibility ─────────────────────────────────────
def test_cva_signature_is_still_unchanged_by_mc_netting() -> None:
    """The gate from the analytic-netting slice, extended: MC netting is the third exposure method
    and `cva` has changed for none of them."""
    import inspect

    assert list(inspect.signature(cva).parameters) == ["profile", "survival", "recovery"]


def test_the_mc_netted_profile_is_byte_identical_for_the_same_seed() -> None:
    hw = _hw()
    swaps = [_swap(RATE), _swap(RATE + 0.004, notional=NOTIONAL / 2)]
    cfg = MonteCarloConfig(paths=20_000, seed=777)
    assert mc_netted_exposure_profile(swaps, hw, cfg) == mc_netted_exposure_profile(swaps, hw, cfg)


def test_the_profile_shape_is_still_date_and_ee() -> None:
    profile = mc_netted_exposure_profile([_swap(RATE)], _hw(), MonteCarloConfig(5_000, 3))
    assert not isinstance(profile, PricingFailure), profile
    for item in profile:
        assert isinstance(item, tuple) and len(item) == 2
        assert isinstance(item[0], date) and isinstance(item[1], float)


# ── ORACLE 5 — bump consistency ──────────────────────────────────────────────────────────
def test_bumping_recovery_moves_the_netted_mc_cva_by_the_lgd_ratio() -> None:
    swaps = [_swap(RATE), _swap(RATE - 0.003)]
    out = [_mc_cva(swaps, _hw(recovery=r)) for r in (0.40, 0.41)]
    assert abs(out[1] - out[0] * (0.59 / 0.60)) < 1e-9 * out[0]


def test_zero_hazard_gives_zero_netted_mc_cva() -> None:
    assert abs(_mc_cva([_swap(RATE), _swap(RATE - 0.003)], _hw(hazard=0.0))) < 1e-12


# ── layering + the shell entry ───────────────────────────────────────────────────────────
def test_the_book_level_entry_lives_in_the_SHELL_and_delegates_down() -> None:
    """L5 takes bare positions; the netting set is the L6 `Book`. Importing `Book` into L5 was the
    §1 error of the analytic netting slice (`risk(L5) imports shell(L6)`), caught by the acyclic
    gate — not repeated."""
    hw = _hw()
    swaps = [_swap(RATE), _swap(RATE - 0.003)]
    book = Book(tuple(Trade((s,), VAL) for s in swaps), name="netting-set")
    via_shell = book_mc_cva(book, hw, CP, CFG)
    assert not isinstance(via_shell, PricingFailure), via_shell
    assert abs(via_shell - _mc_cva(swaps, hw)) < 1e-12


def test_a_non_swap_product_in_the_set_is_a_failure() -> None:
    from pricebook.foundation import Money
    from pricebook.products.credit import CDS, PremiumLeg

    sched = build_schedule(
        VAL, VAL + TENOR, ScheduleTerms(frequency=Frequency.QUARTERLY, roll=RollRule(calendar=None))
    )
    cds = CDS(CP, PremiumLeg(sched, DC360, 0.01), Money(NOTIONAL, currency("EUR")))
    out = book_mc_cva(Book((Trade((cds,), VAL),), name="mixed"), _hw(), CP, CFG)
    assert isinstance(out, PricingFailure), out


def test_an_empty_set_has_no_exposure() -> None:
    assert mc_netted_exposure_profile([], _hw(), CFG) == ()
