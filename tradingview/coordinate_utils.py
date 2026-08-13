"""Coordinate helper utilities for logical index <-> pixel/delta conversions.

These helpers provide stateless conversions used by TimeScale and renderers.
"""
from typing import Tuple
from .logical_index import snap_to_nearest_integer


def index_to_logical_delta(index: float, origin: float) -> float:
    """Return logical delta between index and viewport origin."""
    return index - origin


def logical_delta_to_pixel(logical_delta: float, spacing: float) -> float:
    """Convert logical delta to pixel delta using bar spacing."""
    return logical_delta * spacing


def pixel_to_logical_delta(pixel_delta: float, spacing: float) -> float:
    """Convert pixel delta to logical delta using bar spacing."""
    if spacing == 0:
        return 0.0
    return pixel_delta / spacing


def index_to_x(index: float, origin: float, spacing: float, origin_x: float = 0.0) -> float:
    """Convert logical index to screen X coordinate given viewport origin and spacing."""
    return origin_x + logical_delta_to_pixel(index_to_logical_delta(index, origin), spacing)


def x_to_index(x: float, origin: float, spacing: float, origin_x: float = 0.0) -> float:
    """Convert screen X to floating logical index given viewport origin and spacing."""
    return origin + pixel_to_logical_delta(x - origin_x, spacing)


def snap_index_to_pixel_grid(index: float, spacing: float) -> float:
    """Snap a floating logical index to the nearest integer that aligns with pixel grid at given spacing.

    This is useful for crisp rendering when bar spacing corresponds to integer bar positions.
    """
    if spacing <= 0:
        return snap_to_nearest_integer(index)
    return snap_to_nearest_integer(index)
