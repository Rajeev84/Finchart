"""Hit Testing Math Utilities - Geometric selection and handle detection algorithms.

Provides point-to-line distance, rectangle containment, and handle hitbox checks.
"""
from __future__ import annotations

import math
from typing import Tuple, List, Optional
from ..core.types import Point, Rect


def point_to_line_distance(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    """Calculate perpendicular distance from point (px, py) to line segment (x1, y1)-(x2, y2)."""
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)

    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))

    closest_x = x1 + t * dx
    closest_y = y1 + t * dy
    return math.hypot(px - closest_x, py - closest_y)


def is_point_near_line(px: float, py: float, x1: float, y1: float, x2: float, y2: float, tolerance: float = 6.0) -> bool:
    """Check if point (px, py) is within pixel tolerance of line segment."""
    return point_to_line_distance(px, py, x1, y1, x2, y2) <= tolerance


def is_point_in_rect(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> bool:
    """Check if point (px, py) is inside rectangle bounds (x1, y1)-(x2, y2)."""
    min_x, max_x = min(x1, x2), max(x1, x2)
    min_y, max_y = min(y1, y2), max(y1, y2)
    return min_x <= px <= max_x and min_y <= py <= max_y


def is_point_near_handle(px: float, py: float, hx: float, hy: float, size: float = 6.0) -> bool:
    """Check if point (px, py) is inside handle hitbox centered at (hx, hy)."""
    return math.hypot(px - hx, py - hy) <= size
