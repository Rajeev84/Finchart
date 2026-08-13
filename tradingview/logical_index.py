"""
Logical index primitives for working with floating logical indices.

Provides utilities for floor/ceil/round/clamp and snapping behavior used
by viewport and rendering code.
"""
from math import floor, ceil
from typing import Optional


def floor_index(index: float) -> int:
    return int(floor(index))


def ceil_index(index: float) -> int:
    return int(ceil(index))


def round_index(index: float) -> int:
    return int(round(index))


def clamp_index(index: float, minimum: Optional[int], maximum: Optional[int]) -> int:
    idx = round_index(index)
    if minimum is not None:
        idx = max(idx, minimum)
    if maximum is not None:
        idx = min(idx, maximum)
    return idx


def snap_to_nearest_integer(index: float) -> float:
    """Return floating index snapped to the nearest integer value."""
    return float(round_index(index))
