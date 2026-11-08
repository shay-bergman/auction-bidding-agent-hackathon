"""Small numeric helpers shared across the agent."""

from __future__ import annotations

import math
from typing import List


def clamp(x: float, lo: float, hi: float) -> float:
    """Clamp a value into an inclusive range.

    Args:
        x: Value to constrain.
        lo: Lower bound.
        hi: Upper bound.

    Returns:
        ``lo`` if ``x < lo``, ``hi`` if ``x > hi``, otherwise ``x``.
    """
    return lo if x < lo else hi if x > hi else x


def round2(x: float) -> float:
    """Round to the two decimal places the auction uses for bids.

    Args:
        x: Value to round.

    Returns:
        ``x`` rounded to two decimal places.
    """
    return round(float(x), 2)


def safe_quantile(xs: List[float], q: float, default: float) -> float:
    """Compute a linear-interpolation quantile that tolerates empty input.

    Args:
        xs: Sample values (unsorted is fine).
        q: Quantile in ``[0, 1]``; values outside are clamped.
        default: Value returned when ``xs`` is empty.

    Returns:
        The interpolated quantile of ``xs``, or ``default`` if ``xs`` is empty.
    """
    if not xs:
        return float(default)
    q = clamp(float(q), 0.0, 1.0)
    ys = sorted(xs)
    n = len(ys)
    if n == 1:
        return float(ys[0])
    pos = (n - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return float(ys[lo])
    weight = pos - lo
    return float(ys[lo]) * (1.0 - weight) + float(ys[hi]) * weight
