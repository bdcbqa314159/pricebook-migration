"""Bachelier (normal-model) closed form — the sibling of Black-76 (L3).

`bachelier(forward, strike, vol, t, option_type)` is the UNDISCOUNTED normal-model optionlet value
under the T-forward measure: `E[(F − K)+]` (CALL) / `E[(K − F)+]` (PUT) where the forward diffuses
ARITHMETICALLY (`dF = σ dW`, σ an ABSOLUTE rate vol, `0.008` = 80bp), not geometrically. Discounting
is kept OUT (the L4 engine multiplies `df · N · τ`), exactly as for `black`.

Why it exists: the lognormal model cannot represent a negative forward at all, and post-2014 rates
markets quote through zero. The normal model is defined for every `F` and `K` of either sign — so
`Normal` is the one law whose `defined` is unconditionally true (`models/vol_law.py`).

Provenance:
  quarry: quarry/pricebook/models/black76.py (bachelier_price)
  source: Bachelier (1900); the normal/Bachelier market convention for negative rates
  oracle: an independent inline normal formula to <1e-15; exact put-call parity `C − P = F − K`
          for either sign of F and K; σ→0 / t→0 intrinsic
  slice:  sabr-multilaw (T1 slice 22)
"""

from __future__ import annotations

import math

from pricebook.foundation import norm_cdf, norm_pdf
from pricebook.products.option import OptionType


def bachelier(forward: float, strike: float, vol: float, t: float, option_type: OptionType) -> float:
    """Undiscounted normal-model optionlet value: `(F−K)·Φ(d) + σ√t·φ(d)` with `d = (F−K)/(σ√t)`
    (CALL); the PUT is `(K−F)·Φ(−d) + σ√t·φ(d)`. Degenerate (`vol ≤ 0` or `t ≤ 0`) returns the
    forward intrinsic. No positivity condition: `F` and `K` may be negative (the whole point)."""
    call = option_type is OptionType.CALL
    if vol <= 0.0 or t <= 0.0:
        return max(forward - strike, 0.0) if call else max(strike - forward, 0.0)
    s = vol * math.sqrt(t)
    d = (forward - strike) / s
    if call:
        return (forward - strike) * norm_cdf(d) + s * norm_pdf(d)
    return (strike - forward) * norm_cdf(-d) + s * norm_pdf(d)
