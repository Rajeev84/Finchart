"""Mathematical utility functions shared across FinChart subsystems.

Provides nice-number calculation algorithms, price formatting,
and general numeric clamping utilities.
"""
from __future__ import annotations

import math


def nice_number(value: float, round_up: bool = False) -> float:
    """Compute a human-friendly axis interval step (1, 2, 5, 10, 20, 50, ...).

    Args:
        value: Raw computed step value.
        round_up: If True, always round up to next nice number.

    Returns:
        A visually clean decimal step value.
    """
    if value <= 0:
        return 1.0

    exp = math.floor(math.log10(value))
    frac = value / (10.0 ** exp)

    EPS = 1e-9
    if round_up:
        if frac <= 1.0 + EPS:   nf = 1.0
        elif frac <= 2.0 + EPS: nf = 2.0
        elif frac <= 5.0 + EPS: nf = 5.0
        else:                   nf = 10.0
    else:
        if frac <= 1.5 + EPS:   nf = 1.0
        elif frac <= 3.0 + EPS: nf = 2.0
        elif frac <= 7.0 + EPS: nf = 5.0
        else:                   nf = 10.0

    return nf * (10.0 ** exp)


def nice_bar_step(step: int) -> int:
    """Compute a nice integer step size for bar-index axis labels.

    Args:
        step: Raw computed step (bars between labels).

    Returns:
        Snapped step value from set {1, 2, 5, 10, 20, 50, 100, 200, 500, ...}.
    """
    if step <= 1:  return 1
    if step <= 2:  return 2
    if step <= 5:  return 5
    if step <= 10: return 10
    if step <= 20: return 20
    if step <= 50: return 50
    if step <= 100: return 100
    if step <= 200: return 200
    if step <= 500: return 500
    # General case: round to nearest multiple of 500
    return ((step // 500) + 1) * 500


def format_price(price: float) -> str:
    """Format a price float with appropriate decimal precision.

    Rules:
        >= 10,000: No decimals (e.g. "15,234")
        >= 100:    2 decimals (e.g. "342.56")
        >= 1:      4 decimals (e.g. "12.4523")
        < 1:       6 decimals (e.g. "0.000123")

    Args:
        price: Numeric price value.

    Returns:
        Formatted price string.
    """
    ap = abs(price)
    if ap >= 10_000: return f"{price:,.0f}"
    if ap >= 100:    return f"{price:,.2f}"
    if ap >= 1:      return f"{price:,.4f}"
    return f"{price:.6f}"


def clamp(value: float, lo: float, hi: float) -> float:
    """Clamp value between lo and hi (inclusive).

    Args:
        value: Value to clamp.
        lo: Minimum allowed value.
        hi: Maximum allowed value.

    Returns:
        Clamped value.
    """
    return max(lo, min(hi, value))
