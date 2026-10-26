"""L0 foundation — the public API surface (the vocabulary every upper layer speaks).

`__all__` is the *contract*: it is the set of names the market-data, model, product and
trade layers may depend on. Anything not listed is an implementation detail and may move.
Defined explicitly here (before consumers freeze it for us) per the foundation audit §3.1.
"""

from __future__ import annotations

from pricebook.foundation.calendars import (
    BusinessDayConvention,
    Calendar,
    CalendarProtocol,
    Coverage,
    HolidaySet,
    JointCalendar,
    Observance,
    Rule,
    Weekend,
    WeekendSchedule,
    christmas_boxing,
    easter,
    fixed,
    gregorian_easter,
    mexico_inauguration,
    midsummer_eve,
    monday,
    nth,
    orthodox,
    orthodox_easter,
    victoria_day,
)
from pricebook.foundation.cashflow import SCHEMA_VERSION, Cashflow, Leg
from pricebook.foundation.day_count import (
    Accrual,
    CouponPeriod,
    DayCountConvention,
    business_days_between,
    icma_coupon_period,
    year_fraction,
)
from pricebook.foundation.distributions import norm_cdf, norm_pdf, norm_ppf
from pricebook.foundation.interpolation import (
    Extrapolation,
    ExtrapolationEnds,
    Interpolation,
    interpolate,
)
from pricebook.foundation.hagan_west import MonotoneConvex, monotone_convex
from pricebook.foundation.market_calendars import (
    calendar_for_currency,
    get_calendar,
    list_calendars,
    register_calendar,
)
from pricebook.foundation.money import (
    CURRENCIES,
    UNITS,
    Currency,
    CurrencyPair,
    Money,
    Quantity,
    Unit,
    currency,
    list_currencies,
    list_units,
    register_currency,
    register_unit,
    unit,
)
from pricebook.foundation.rate_basis import Compounding, convert_rate, growth_factor
from pricebook.foundation.rate_index import (
    AccrualConvention,
    AccrualMethod,
    FixingHistory,
    FixingRule,
    FixingSource,
    IndexId,
    ObservationStyle,
    RateIndex,
    RfrConvention,
    accrued_rate,
    get_rate_index,
    list_rate_indices,
    register_rate_index,
)
from pricebook.foundation.results import PricingFailure, PricingResult
from pricebook.foundation.schedule import (
    Frequency,
    PaymentRule,
    RegularPeriod,
    RollConvention,
    RollRule,
    Schedule,
    SchedulePeriod,
    ScheduleTerms,
    StubType,
    build_schedule,
    cds_roll_date,
    future_periods,
    imm_date,
    next_cds_roll,
    next_imm,
)
from pricebook.foundation.settlement import (
    Delivery,
    SettlementTerms,
    SettlementType,
    fx_pair,
    fx_spot_date,
    register_fx_pair,
    settlement_date,
    spot_lag,
)
from pricebook.foundation.solvers import (
    brent,
    invert_increasing,
    least_squares,
    newton,
    root_nd,
    secant,
)
from pricebook.foundation.tenor import Tenor, TenorUnit
from pricebook.foundation.time_measure import TimeMeasure
from pricebook.foundation.reference_entity import ReferenceEntity
from pricebook.foundation.underlying import AssetClass, Underlying

__all__ = [
    # time & tenor
    "Tenor",
    "TenorUnit",
    "TimeMeasure",
    # calendars (the rule DSL + types)
    "Calendar",
    "JointCalendar",
    "HolidaySet",
    "Weekend",
    "WeekendSchedule",
    "Observance",
    "Coverage",
    "BusinessDayConvention",
    "Rule",
    "fixed",
    "easter",
    "orthodox",
    "nth",
    "monday",
    "christmas_boxing",
    "victoria_day",
    "midsummer_eve",
    "mexico_inauguration",
    "gregorian_easter",
    "orthodox_easter",
    "get_calendar",
    "calendar_for_currency",
    "list_calendars",
    "register_calendar",
    "CalendarProtocol",
    # day counts & accrual
    "DayCountConvention",
    "year_fraction",
    "CouponPeriod",
    "icma_coupon_period",
    "Accrual",
    "business_days_between",
    # schedules
    "Frequency",
    "StubType",
    "RollRule",
    "RollConvention",
    "RegularPeriod",
    "PaymentRule",
    "ScheduleTerms",
    "Schedule",
    "SchedulePeriod",
    "build_schedule",
    "future_periods",
    "imm_date",
    "next_imm",
    "cds_roll_date",
    "next_cds_roll",
    # money & quantity
    "Currency",
    "Unit",
    "Money",
    "Quantity",
    "CurrencyPair",
    "register_currency",
    "currency",
    "list_currencies",
    "CURRENCIES",
    "register_unit",
    "unit",
    "list_units",
    "UNITS",
    # rate basis
    "Compounding",
    "growth_factor",
    "convert_rate",
    # index identity
    "RateIndex",
    "IndexId",
    "AccrualConvention",
    "FixingRule",
    "RfrConvention",
    "AccrualMethod",
    "ObservationStyle",
    "FixingHistory",
    "FixingSource",
    "accrued_rate",
    "get_rate_index",
    "list_rate_indices",
    "register_rate_index",
    # underlying
    "Underlying",
    "AssetClass",
    "ReferenceEntity",
    # instrument atoms
    "Cashflow",
    "Leg",
    "SCHEMA_VERSION",
    # settlement
    "SettlementType",
    "Delivery",
    "SettlementTerms",
    "settlement_date",
    "fx_spot_date",
    "spot_lag",
    "fx_pair",
    "register_fx_pair",
    # numerics
    "PricingResult",
    "PricingFailure",
    "norm_pdf",
    "norm_cdf",
    "norm_ppf",
    "brent",
    "invert_increasing",
    "newton",
    "secant",
    "least_squares",
    "root_nd",
    "Interpolation",
    "Extrapolation",
    "ExtrapolationEnds",
    "interpolate",
    "MonotoneConvex",
    "monotone_convex",
]
