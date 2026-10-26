"""XVA slice 2 — netting (`spec_xva_slice2_netting.md`).

**Netting is the test of slice 1's profile/atom split.** If the split holds, netting is a *new
profile builder* and `cva` does not change at all. The first test below asserts exactly that, as a
signature check — the design decision turned into a gate, so a future slice cannot quietly move
netting logic into the atom and end up with two CVA definitions again.

The rest are the netting identities, which are decomposition oracles rather than scalars:
degenerate (one trade is the identity), the netting **benefit** (netted ≤ Σ standalone), and
**perfect offset** (payer + receiver → zero exposure → zero CVA), which also prices the receiver
direction that slice 1 only asserted.
"""

import inspect
from datetime import date

from pricebook.foundation import (
    DayCountConvention,
    Frequency,
    PricingFailure,
    RollRule,
    ScheduleTerms,
    Tenor,
    TenorUnit,
    TimeMeasure,
    build_schedule,
    get_rate_index,
)
from pricebook.foundation.reference_entity import ReferenceEntity
from pricebook.market.curve import DiscountCurve
from pricebook.market.curve_set import CurveKey, CurveRole, CurveSet
from pricebook.market.snapshot import MarketSnapshot, RecoveryKey
from pricebook.market.survival_curve import SurvivalCurve
from pricebook.market.vol_surface import Surface, SwaptionSurfaceKey
from pricebook.models.black_model import BlackModel
from pricebook.products.swap import FixedLeg, FloatLeg, VanillaSwap
from pricebook.risk.exposure import netted_exposure_profile, swaption_exposure_profile
from pricebook.risk.xva import book_cva, cva, swap_cva
from pricebook.shell.portfolio import Book, Trade

Y = TenorUnit.YEAR
DC365 = DayCountConvention.ACT_365_FIXED
VAL = date(2026, 1, 15)
INDEX = get_rate_index("EURIBOR_3M")
OTHER = get_rate_index("EURIBOR_6M")
CCY = INDEX.id.currency
TM = TimeMeasure(VAL, DC365)
FAR = VAL + Tenor(20, Y)
CP = ReferenceEntity("COUNTERPARTY")
RECOVERY = 0.40
NOTIONAL = 10_000_000.0
TENOR = Tenor(5, Y)
VOL = 0.22


def _swap(rate: float, notional: float = NOTIONAL, index=INDEX) -> VanillaSwap:
    sched = build_schedule(
        VAL, VAL + TENOR, ScheduleTerms(frequency=Frequency.ANNUAL, roll=RollRule(calendar=None))
    )
    return VanillaSwap(notional, CCY, FixedLeg(sched, DC365, rate), FloatLeg(sched, DC365, index))


def _book(*swaps: VanillaSwap) -> Book:
    return Book(tuple(Trade((s,), VAL) for s in swaps), name="netting-set")


def _market(hazard: float, recovery: float = RECOVERY) -> MarketSnapshot:
    curves = CurveSet(
        {
            CurveKey(CurveRole.DISCOUNT, CCY): DiscountCurve.flat(TM, 0.030, until=FAR),
            CurveKey(CurveRole.PROJECTION, INDEX): DiscountCurve.flat(TM, 0.035, until=FAR),
            CurveKey(CurveRole.PROJECTION, OTHER): DiscountCurve.flat(TM, 0.036, until=FAR),
            CurveKey(CurveRole.SURVIVAL, CP): SurvivalCurve.flat_hazard(TM, hazard, until=FAR),
        }
    )
    surfaces = {}
    for idx in (INDEX, OTHER):
        for y in range(1, TENOR.count + 1):
            surfaces[SwaptionSurfaceKey(idx, Tenor(y, Y))] = Surface.flat(VOL)
    return MarketSnapshot(VAL, curves, scalars={RecoveryKey(CP): recovery}, surfaces=surfaces)


def _model(hazard: float, recovery: float = RECOVERY) -> BlackModel:
    return BlackModel(_market(hazard, recovery))


# ── THE SPLIT, AS A GATE ───────────────────────────────────────────────────────────────────
def test_cva_signature_is_UNCHANGED_by_netting() -> None:
    """Slice 1 split the exposure method from the CVA atom so a new exposure method would need no
    change to `cva`. Netting is the first real test of that claim, so it is asserted rather than
    hoped for: if a future slice moves netting logic into the atom, this fails and the two-CVA-
    definitions failure mode is caught at the design level, not in a number."""
    params = list(inspect.signature(cva).parameters)
    assert params == ["profile", "survival", "recovery"]


# ── ORACLE 1 — degenerate: netting of one is the identity ─────────────────────────────────
def test_a_book_of_one_trade_nets_to_the_standalone_profile_byte_identically() -> None:
    swap = _swap(0.035)
    model = _model(0.02)
    standalone = swaption_exposure_profile(swap, model)
    netted = netted_exposure_profile(_book(swap), model)
    assert not isinstance(standalone, PricingFailure) and not isinstance(netted, PricingFailure)
    assert netted == standalone                      # byte-identical, not merely close


def test_a_book_of_one_trade_gives_the_standalone_cva_byte_identically() -> None:
    swap = _swap(0.035)
    model = _model(0.02)
    alone = swap_cva(swap, model, CP)
    booked = book_cva(_book(swap), model, CP)
    assert not isinstance(alone, PricingFailure) and not isinstance(booked, PricingFailure)
    assert booked == alone


# ── ORACLE 2 — the netting BENEFIT (the reason netting exists) ────────────────────────────
def test_netted_cva_never_exceeds_the_sum_of_standalone_cvas() -> None:
    """The defining property. A decomposition oracle: it relates the netted charge to its parts,
    which a single netted number cannot check on its own."""
    model = _model(0.02)
    for swaps in (
        (_swap(0.035), _swap(0.030)),                       # same direction — no benefit
        (_swap(0.035), _swap(0.035, -NOTIONAL / 2)),        # partial offset
        (_swap(0.035), _swap(0.040, -NOTIONAL / 3), _swap(0.025)),
    ):
        netted = book_cva(_book(*swaps), model, CP)
        standalone = [swap_cva(s, model, CP) for s in swaps]
        assert not isinstance(netted, PricingFailure), netted
        assert all(not isinstance(v, PricingFailure) for v in standalone)
        assert netted <= sum(standalone) + 1e-9, (netted, sum(standalone))


def test_offsetting_trades_give_a_STRICT_netting_benefit() -> None:
    """Same-direction trades net to the sum (no benefit); offsetting ones must be strictly cheaper,
    or the netting is not actually netting."""
    model = _model(0.02)
    same = (_swap(0.035), _swap(0.035))
    offset = (_swap(0.035), _swap(0.035, -NOTIONAL / 2))
    same_netted = book_cva(_book(*same), model, CP)
    same_sum = sum(swap_cva(s, model, CP) for s in same)
    off_netted = book_cva(_book(*offset), model, CP)
    off_sum = sum(swap_cva(s, model, CP) for s in offset)
    assert abs(same_netted - same_sum) < 1e-6 * same_sum      # no offset ⇒ no benefit
    assert off_netted < off_sum * 0.9                          # genuine offset ⇒ real benefit


# ── ORACLE 3 — perfect offset, which also prices the RECEIVER direction ───────────────────
def test_a_payer_and_an_identical_receiver_net_to_zero_cva() -> None:
    """Perfect offset: the net position is flat, so there is no exposure and no charge. This also
    exercises the receiver (negative-notional) path, which slice 1 derived but never priced —
    closing that flag with a number rather than an assertion."""
    model = _model(0.02)
    payer = _swap(0.035, NOTIONAL)
    receiver = _swap(0.035, -NOTIONAL)
    netted = book_cva(_book(payer, receiver), model, CP)
    assert not isinstance(netted, PricingFailure), netted
    assert abs(netted) < 1e-9

    # and each leg standalone is non-zero, so the zero is cancellation rather than two zeros
    for leg in (payer, receiver):
        alone = swap_cva(leg, model, CP)
        assert not isinstance(alone, PricingFailure), alone
        assert alone > 0.0


# ── ORACLE 4 — the limits still hold on the netted profile ────────────────────────────────
def test_zero_hazard_gives_zero_netted_cva() -> None:
    got = book_cva(_book(_swap(0.035), _swap(0.030)), _model(0.0), CP)
    assert not isinstance(got, PricingFailure), got
    assert abs(got) < 1e-12


def test_the_netted_profile_has_one_point_per_schedule_interval() -> None:
    model = _model(0.02)
    profile = netted_exposure_profile(_book(_swap(0.035), _swap(0.030)), model)
    assert not isinstance(profile, PricingFailure), profile
    assert len(profile) == 5
    assert [d for d, _ in profile] == sorted(d for d, _ in profile)
    assert profile[-1][1] == 0.0


# ── ORACLE 5 — bump consistency on the netted charge ─────────────────────────────────────
def test_bumping_recovery_moves_the_netted_cva_by_the_lgd_ratio() -> None:
    swaps = (_swap(0.035), _swap(0.030))
    base = book_cva(_book(*swaps), _model(0.02, recovery=0.40), CP)
    bumped = book_cva(_book(*swaps), _model(0.02, recovery=0.41), CP)
    assert not isinstance(base, PricingFailure) and not isinstance(bumped, PricingFailure)
    assert abs(bumped - base * (0.59 / 0.60)) < 1e-9 * base


def test_widening_the_hazard_raises_the_netted_cva() -> None:
    swaps = (_swap(0.035), _swap(0.030))
    values = [book_cva(_book(*swaps), _model(h), CP) for h in (0.005, 0.02, 0.06)]
    assert all(not isinstance(v, PricingFailure) for v in values)
    assert values == sorted(values)


# ── the net-to-a-swap constraint: fail as a VALUE, never a silent mis-net ─────────────────
def test_a_heterogeneous_netting_set_is_a_FAILURE_not_a_silent_mis_net() -> None:
    """The analytic swaption proxy only has a netted exposure when the set aggregates to a
    swap-equivalent. Two different indices do not — so this must fail loudly and defer to MC, rather
    than nets two incompatible positions and return a plausible number."""
    out = netted_exposure_profile(_book(_swap(0.035), _swap(0.035, index=OTHER)), _model(0.02))
    assert isinstance(out, PricingFailure), out
    assert "index" in out.reason.lower() or "heterogene" in out.reason.lower()


def test_an_empty_netting_set_has_no_exposure_and_no_charge() -> None:
    got = book_cva(Book((), name="empty"), _model(0.02), CP)
    assert not isinstance(got, PricingFailure), got
    assert got == 0.0


def test_a_set_with_a_non_swap_product_is_a_failure() -> None:
    from pricebook.products.credit import CDS, PremiumLeg

    sched = build_schedule(
        VAL, VAL + TENOR,
        ScheduleTerms(frequency=Frequency.QUARTERLY, roll=RollRule(calendar=None)),
    )
    from pricebook.foundation import Money

    cds = CDS(CP, PremiumLeg(sched, DayCountConvention.ACT_360, 0.01), Money(NOTIONAL, CCY))
    out = netted_exposure_profile(Book((Trade((cds,), VAL),), name="mixed"), _model(0.02))
    assert isinstance(out, PricingFailure), out
