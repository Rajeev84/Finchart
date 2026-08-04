"""Drawing Tools Implementation - TrendLine, HorizontalLine, VerticalLine, Rectangle, and MarketProfileOverlay.

All tools are pure Python with no numpy/pandas dependencies.
"""
from __future__ import annotations

from typing import List, Optional, Any, Dict
import math

from ..core.types import Point, Color, OHLCV
from ..coordinates.engine import CoordinateEngine
from ..rendering.pipeline import DrawCommand, Layer
from ..interaction.hit_test import is_point_near_line, is_point_in_rect, is_point_near_handle
from .base import DrawingTool, DrawingState


class TrendLine(DrawingTool):
    """Interactive trend line shape between two price/time anchor points."""

    def hit_test(self, px: float, py: float, coord_engine: CoordinateEngine) -> bool:
        if len(self.state.points) < 2:
            return False

        (idx1, p1), (idx2, p2) = self.state.points[:2]
        x1 = coord_engine.index_to_x(float(idx1))
        y1 = coord_engine.price_to_y(float(p1))
        x2 = coord_engine.index_to_x(float(idx2))
        y2 = coord_engine.price_to_y(float(p2))

        return is_point_near_line(px, py, x1, y1, x2, y2, tolerance=6.0)

    def render_commands(self, coord_engine: CoordinateEngine, viewport: Optional[Any] = None) -> List[DrawCommand]:
        if len(self.state.points) < 2:
            return []

        vp = viewport or coord_engine.viewport
        (idx1, p1), (idx2, p2) = self.state.points[:2]

        x1 = coord_engine.index_to_x(float(idx1))
        y1 = coord_engine.price_to_y(float(p1), vp)
        x2 = coord_engine.index_to_x(float(idx2))
        y2 = coord_engine.price_to_y(float(p2), vp)

        color = "#FFA500" if self.state.is_selected else self.state.color.to_hex()
        width = self.state.width + (1.0 if self.state.is_selected else 0.0)

        cmds = [
            DrawCommand(
                layer=Layer.DRAWING,
                tag=self.state.tag,
                item_type="line",
                coords=(x1, y1, x2, y2),
                options={"fill": color, "width": width, "dash": self.state.dash},
                z_index=0
            )
        ]

        if self.state.is_selected:
            h = 4.0
            for (hx, hy), htag in [((x1, y1), "h1"), ((x2, y2), "h2")]:
                cmds.append(DrawCommand(
                    layer=Layer.DRAWING,
                    tag=f"{self.state.tag}_{htag}",
                    item_type="oval",
                    coords=(hx - h, hy - h, hx + h, hy + h),
                    options={"fill": "#FFFFFF", "outline": "#000000", "width": 1},
                    z_index=10
                ))

        return cmds


class HorizontalLine(DrawingTool):
    """Horizontal price level line spanning full chart width."""

    def hit_test(self, px: float, py: float, coord_engine: CoordinateEngine) -> bool:
        if not self.state.points:
            return False
        price = float(self.state.points[0][1])
        y = coord_engine.price_to_y(price)
        return abs(py - y) <= 6.0

    def render_commands(self, coord_engine: CoordinateEngine, viewport: Optional[Any] = None) -> List[DrawCommand]:
        if not self.state.points:
            return []

        vp = viewport or coord_engine.viewport
        price = float(self.state.points[0][1])
        y = coord_engine.price_to_y(price, vp)

        color = "#FFA500" if self.state.is_selected else self.state.color.to_hex()
        return [
            DrawCommand(
                layer=Layer.DRAWING,
                tag=self.state.tag,
                item_type="line",
                coords=(vp.left, y, vp.right, y),
                options={"fill": color, "width": self.state.width, "dash": (4, 4)},
                z_index=0
            )
        ]


class VerticalLine(DrawingTool):
    """Vertical bar index line spanning full chart height."""

    def hit_test(self, px: float, py: float, coord_engine: CoordinateEngine) -> bool:
        if not self.state.points:
            return False
        idx = float(self.state.points[0][0])
        x = coord_engine.index_to_x(idx)
        return abs(px - x) <= 6.0

    def render_commands(self, coord_engine: CoordinateEngine, viewport: Optional[Any] = None) -> List[DrawCommand]:
        if not self.state.points:
            return []

        vp = viewport or coord_engine.viewport
        idx = float(self.state.points[0][0])
        x = coord_engine.index_to_x(idx)

        color = "#FFA500" if self.state.is_selected else self.state.color.to_hex()
        return [
            DrawCommand(
                layer=Layer.DRAWING,
                tag=self.state.tag,
                item_type="line",
                coords=(x, vp.top, x, vp.bottom),
                options={"fill": color, "width": self.state.width, "dash": (4, 4)},
                z_index=0
            )
        ]


class Rectangle(DrawingTool):
    """Interactive rectangle defined by two corner price/time anchor points."""

    def hit_test(self, px: float, py: float, coord_engine: CoordinateEngine) -> bool:
        if len(self.state.points) < 2:
            return False

        (idx1, p1), (idx2, p2) = self.state.points[:2]
        x1 = coord_engine.index_to_x(float(idx1))
        y1 = coord_engine.price_to_y(float(p1))
        x2 = coord_engine.index_to_x(float(idx2))
        y2 = coord_engine.price_to_y(float(p2))

        # Test edge hit (border)
        return (
            is_point_near_line(px, py, x1, y1, x2, y1) or
            is_point_near_line(px, py, x2, y1, x2, y2) or
            is_point_near_line(px, py, x2, y2, x1, y2) or
            is_point_near_line(px, py, x1, y2, x1, y1)
        )

    def render_commands(self, coord_engine: CoordinateEngine, viewport: Optional[Any] = None) -> List[DrawCommand]:
        if len(self.state.points) < 2:
            return []

        vp = viewport or coord_engine.viewport
        (idx1, p1), (idx2, p2) = self.state.points[:2]

        x1 = coord_engine.index_to_x(float(idx1))
        y1 = coord_engine.price_to_y(float(p1), vp)
        x2 = coord_engine.index_to_x(float(idx2))
        y2 = coord_engine.price_to_y(float(p2), vp)

        color = "#FFA500" if self.state.is_selected else self.state.color.to_hex()

        return [
            DrawCommand(
                layer=Layer.DRAWING,
                tag=self.state.tag,
                item_type="rectangle",
                coords=(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)),
                options={"outline": color, "fill": "", "width": self.state.width},
                z_index=0
            )
        ]


class MarketProfileOverlay:
    """Market Profile (TPO) overlay — calculates VAH, VAL, and POC from OHLCV data.

    Pure Python implementation using only stdlib.
    """

    def __init__(self) -> None:
        self.enabled = False
        self.tick_size = 0.05

    def calculate_poc(self, bars: List[OHLCV]) -> Optional[float]:
        """Return the Point of Control (price level with most time spent)."""
        if not bars:
            return None

        profile: Dict[float, int] = {}
        for bar in bars:
            low_p = math.floor(bar.low / self.tick_size) * self.tick_size
            high_p = math.ceil(bar.high / self.tick_size) * self.tick_size
            curr_p = low_p
            while curr_p <= high_p + 1e-9:
                key = round(curr_p, 8)
                profile[key] = profile.get(key, 0) + 1
                curr_p += self.tick_size

        if not profile:
            return None

        return max(profile, key=lambda k: profile[k])

    def calculate_value_area(self, bars: List[OHLCV], value_area_pct: float = 0.70) -> Optional[tuple]:
        """Calculate Value Area High (VAH) and Value Area Low (VAL)."""
        if not bars:
            return None

        profile: Dict[float, int] = {}
        for bar in bars:
            low_p = math.floor(bar.low / self.tick_size) * self.tick_size
            high_p = math.ceil(bar.high / self.tick_size) * self.tick_size
            curr_p = low_p
            while curr_p <= high_p + 1e-9:
                key = round(curr_p, 8)
                profile[key] = profile.get(key, 0) + 1
                curr_p += self.tick_size

        if not profile:
            return None

        total_tpo = sum(profile.values())
        target = int(total_tpo * value_area_pct)

        poc = max(profile, key=lambda k: profile[k])
        sorted_prices = sorted(profile.keys())
        poc_idx = sorted_prices.index(poc)

        accumulated = profile[poc]
        lo_idx = poc_idx
        hi_idx = poc_idx

        while accumulated < target and (lo_idx > 0 or hi_idx < len(sorted_prices) - 1):
            lo_add = profile[sorted_prices[lo_idx - 1]] if lo_idx > 0 else 0
            hi_add = profile[sorted_prices[hi_idx + 1]] if hi_idx < len(sorted_prices) - 1 else 0

            if lo_add >= hi_add and lo_idx > 0:
                lo_idx -= 1
                accumulated += lo_add
            elif hi_idx < len(sorted_prices) - 1:
                hi_idx += 1
                accumulated += hi_add
            else:
                break

        return sorted_prices[hi_idx], sorted_prices[lo_idx]  # VAH, VAL
