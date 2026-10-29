"""L4 engine — the stateless heart: product→pricer via the registry (CLAUDE.md §1).

Importing the package registers every pricer (their `@register` decorators run at import),
so `price` dispatches over all product types. New pricer modules are imported here to
populate the registry.
"""

from pricebook.engine.credit import price_cds
from pricebook.engine.equity import price_equity_option
from pricebook.engine.cash import price_deposit, price_fra, price_future
from pricebook.engine.linear import price, price_swap
from pricebook.engine.registry import register
from pricebook.engine.vanilla_option import price_caplet, price_swaption
from pricebook.engine.xccy import price_xccy

__all__ = [
    "price_equity_option",
    "price",
    "price_swap",
    "price_cds",
    "price_deposit",
    "price_fra",
    "price_future",
    "price_xccy",
    "price_caplet",
    "price_swaption",
    "register",
]
