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
        if len(self.state.points) < 2 or self.state.locked:
            return False

        (i1, p1), (i2, p2) = self.state.points[:2]
        x1 = coord_engine.index_to_x(float(i1))
        y1 = coord_engine.price_to_y(float(p1))
        x2 = coord_engine.index_to_x(float(i2))
        y2 = coord_engine.price_to_y(float(p2))

        # Wider tolerance when hovered/selected
        tol = 10.0 if (self.state.hovered or self.state.selected) else 6.0
        return is_point_near_line(px, py, x1, y1, x2, y2, tolerance=tol)

    def get_handles(self, coord_engine: CoordinateEngine, viewport: Optional[Any] = None) -> List[Tuple[float, float, str]]:
        if len(self.state.points) < 2:
            return []
        (i1, p1), (i2, p2) = self.state.points[:2]
        return [
            (coord_engine.index_to_x(float(i1)), coord_engine.price_to_y(float(p1)), "p1"),
            (coord_engine.index_to_x(float(i2)), coord_engine.price_to_y(float(p2)), "p2"),
        ]

    def compute_angle(self, coord_engine: CoordinateEngine) -> Optional[float]:
        if len(self.state.points) < 2:
            return None
        (i1, p1), (i2, p2) = self.state.points[:2]
        x1, y1 = coord_engine.index_to_x(float(i1)), coord_engine.price_to_y(float(p1))
        x2, y2 = coord_engine.index_to_x(float(i2)), coord_engine.price_to_y(float(p2))
        # Canvas Y increases downward, so invert dy for geometric angle
        angle_rad = math.atan2(-(y2 - y1), x2 - x1)
        angle_deg = math.degrees(angle_rad)
        # Normalize to 0-180 for line angle display
        if angle_deg < 0:
            angle_deg += 180
        return round(angle_deg, 1)

    def move_endpoint(self, handle_id: str, new_index: float, new_price: float) -> None:
        idx = 0 if handle_id == "p1" else 1
        pts = list(self.state.points)
        pts[idx] = (new_index, new_price)
        self.state.points = pts

    def move_whole(self, d_index: float, d_price: float) -> None:
        pts = []
        for i, p in self.state.points:
            pts.append((i + d_index, p + d_price))
        self.state.points = pts

    def render_commands(self, coord_engine: CoordinateEngine, viewport: Optional[Any] = None) -> List[DrawCommand]:
        if len(self.state.points) < 2 or not self.state.visible:
            return []

        vp = viewport or coord_engine.viewport
        (i1, p1), (i2, p2) = self.state.points[:2]
        x1 = coord_engine.index_to_x(float(i1))
        y1 = coord_engine.price_to_y(float(p1), vp)
        x2 = coord_engine.index_to_x(float(i2))
        y2 = coord_engine.price_to_y(float(p2), vp)

        # Appearance based on state
        color = self.state.color.to_hex()
        if self.state.selected:
            color = "#FFA500"  # Orange when selected
        elif self.state.hovered:
            color = "#FFD700"  # Gold when hovered

        width = self.state.width + (1.5 if self.state.selected else 0.0) + (0.5 if self.state.hovered else 0.0)
        dash = {"solid": (), "dashed": (4, 4), "dotted": (2, 2)}.get(self.state.style, ())

        cmds: List[DrawCommand] = []

        # Main line
        cmds.append(DrawCommand(
            layer=Layer.DRAWING,
            tag=f"line_{self.state.id}",
            item_type="line",
            coords=(x1, y1, x2, y2),
            options={"fill": color, "width": width, "dash": dash},
            z_index=5
        ))

        # Label text (if provided)
        if self.state.label:
            mid_x = (x1 + x2) / 2.0
            mid_y = (y1 + y2) / 2.0
            cmds.append(DrawCommand(
                layer=Layer.DRAWING,
                tag=f"label_{self.state.id}",
                item_type="text",
                coords=(mid_x, mid_y - 12),
                options={
                    "text": self.state.label,
                    "fill": color,
                    "font": ("Segoe UI", 9),
                    "anchor": "center"
                },
                z_index=6
            ))

        # Selection visuals
        if self.state.selected:
            # Endpoint handles
            h = 5.0
            for (hx, hy), htag in [((x1, y1), "h1"), ((x2, y2), "h2")]:
                cmds.append(DrawCommand(
                    layer=Layer.DRAWING,
                    tag=f"handle_{self.state.id}_{htag}",
                    item_type="oval",
                    coords=(hx - h, hy - h, hx + h, hy + h),
                    options={"fill": "#FFFFFF", "outline": "#000000", "width": 1},
                    z_index=15
                ))

            # Price guide (vertical blue bar between y1 and y2)
            guide_x = min(x1, x2) - 15
            cmds.append(DrawCommand(
                layer=Layer.DRAWING,
                tag=f"price_guide_{self.state.id}",
                item_type="rectangle",
                coords=(guide_x - 3, min(y1, y2), guide_x + 3, max(y1, y2)),
                options={"fill": "#2196F3", "outline": "", "stipple": "gray50"},
                z_index=4
            ))

            # Time guide (horizontal blue bar between x1 and x2)
            guide_y = max(y1, y2) + 15
            cmds.append(DrawCommand(
                layer=Layer.DRAWING,
                tag=f"time_guide_{self.state.id}",
                item_type="rectangle",
                coords=(min(x1, x2), guide_y - 3, max(x1, x2), guide_y + 3),
                options={"fill": "#2196F3", "outline": "", "stipple": "gray50"},
                z_index=4
            ))

            # Angle text above x2,y2
            angle = self.compute_angle(coord_engine)
            if angle is not None:
                cmds.append(DrawCommand(
                    layer=Layer.DRAWING,
                    tag=f"angle_{self.state.id}",
                    item_type="text",
                    coords=(x2, y2 - 18),
                    options={
                        "text": f"Angle {angle}°",
                        "fill": "#FFFFFF",
                        "font": ("Segoe UI", 9, "bold"),
                        "anchor": "center"
                    },
                    z_index=16
                ))

        return cmds


class HorizontalLine(DrawingTool):
    """Horizontal price level line spanning full chart width."""

    def hit_test(self, px: float, py: float, coord_engine: CoordinateEngine) -> bool:
        if not self.state.points or self.state.locked:
            return False
        _, price = self.state.points[0]
        if price is None:
            return False
        y = coord_engine.price_to_y(float(price))
        tol = 10.0 if (self.state.hovered or self.state.selected) else 6.0
        return abs(py - y) <= tol

    def get_handles(self, coord_engine: CoordinateEngine, viewport: Optional[Any] = None) -> List[Tuple[float, float, str]]:
        if not self.state.points:
            return []
        _, price = self.state.points[0]
        if price is None:
            return []
        vp = viewport or coord_engine.viewport
        y = coord_engine.price_to_y(float(price), vp)
        return [(vp.center_x, y, "mid")]

    def move_endpoint(self, handle_id: str, new_index: float, new_price: float) -> None:
        self.state.points = [(None, new_price)]

    def move_whole(self, d_index: float, d_price: float) -> None:
        _, price = self.state.points[0]
        if price is not None:
            self.state.points = [(None, price + d_price)]

    def render_commands(self, coord_engine: CoordinateEngine, viewport: Optional[Any] = None) -> List[DrawCommand]:
        if not self.state.points or not self.state.visible:
            return []
        vp = viewport or coord_engine.viewport
        _, price = self.state.points[0]
        if price is None:
            return []
        y = coord_engine.price_to_y(float(price), vp)

        color = self.state.color.to_hex()
        if self.state.selected:
            color = "#FFA500"
        elif self.state.hovered:
            color = "#FFD700"

        width = self.state.width + (1.0 if self.state.selected else 0.0)
        dash = {"solid": (), "dashed": (4, 4), "dotted": (2, 2)}.get(self.state.style, (4, 4))

        cmds: List[DrawCommand] = []
        cmds.append(DrawCommand(
            layer=Layer.DRAWING,
            tag=f"hline_{self.state.id}",
            item_type="line",
            coords=(vp.left, y, vp.right, y),
            options={"fill": color, "width": width, "dash": dash},
            z_index=5
        ))

        # Label on right axis
        if self.state.label:
            cmds.append(DrawCommand(
                layer=Layer.DRAWING,
                tag=f"label_{self.state.id}",
                item_type="text",
                coords=(vp.right - 5, y - 10),
                options={"text": self.state.label, "fill": color, "font": ("Segoe UI", 9), "anchor": "e"},
                z_index=6
            ))

        if self.state.selected:
            h = 5.0
            cmds.append(DrawCommand(
                layer=Layer.DRAWING,
                tag=f"handle_{self.state.id}_mid",
                item_type="oval",
                coords=(vp.center_x - h, y - h, vp.center_x + h, y + h),
                options={"fill": "#FFFFFF", "outline": "#000000", "width": 1},
                z_index=15
            ))

        return cmds


class VerticalLine(DrawingTool):
    """Vertical bar index line spanning full chart height."""

    def hit_test(self, px: float, py: float, coord_engine: CoordinateEngine) -> bool:
        if not self.state.points or self.state.locked:
            return False
        idx, _ = self.state.points[0]
        if idx is None:
            return False
        x = coord_engine.index_to_x(float(idx))
        tol = 10.0 if (self.state.hovered or self.state.selected) else 6.0
        return abs(px - x) <= tol

    def get_handles(self, coord_engine: CoordinateEngine, viewport: Optional[Any] = None) -> List[Tuple[float, float, str]]:
        if not self.state.points:
            return []
        idx, _ = self.state.points[0]
        if idx is None:
            return []
        vp = viewport or coord_engine.viewport
        x = coord_engine.index_to_x(float(idx))
        return [(x, vp.center_y, "mid")]

    def move_endpoint(self, handle_id: str, new_index: float, new_price: float) -> None:
        self.state.points = [(new_index, None)]

    def move_whole(self, d_index: float, d_price: float) -> None:
        idx, _ = self.state.points[0]
        if idx is not None:
            self.state.points = [(idx + d_index, None)]

    def render_commands(self, coord_engine: CoordinateEngine, viewport: Optional[Any] = None) -> List[DrawCommand]:
        if not self.state.points or not self.state.visible:
            return []
        vp = viewport or coord_engine.viewport
        idx, _ = self.state.points[0]
        if idx is None:
            return []
        x = coord_engine.index_to_x(float(idx))

        color = self.state.color.to_hex()
        if self.state.selected:
            color = "#FFA500"
        elif self.state.hovered:
            color = "#FFD700"

        width = self.state.width + (1.0 if self.state.selected else 0.0)
        dash = {"solid": (), "dashed": (4, 4), "dotted": (2, 2)}.get(self.state.style, (4, 4))

        cmds: List[DrawCommand] = []
        cmds.append(DrawCommand(
            layer=Layer.DRAWING,
            tag=f"vline_{self.state.id}",
            item_type="line",
            coords=(x, vp.top, x, vp.bottom),
            options={"fill": color, "width": width, "dash": dash},
            z_index=5
        ))

        # Label on top axis
        if self.state.label:
            cmds.append(DrawCommand(
                layer=Layer.DRAWING,
                tag=f"label_{self.state.id}",
                item_type="text",
                coords=(x + 5, vp.top + 10),
                options={"text": self.state.label, "fill": color, "font": ("Segoe UI", 9), "anchor": "w"},
                z_index=6
            ))

        if self.state.selected:
            h = 5.0
            cmds.append(DrawCommand(
                layer=Layer.DRAWING,
                tag=f"handle_{self.state.id}_mid",
                item_type="oval",
                coords=(x - h, vp.center_y - h, x + h, vp.center_y + h),
                options={"fill": "#FFFFFF", "outline": "#000000", "width": 1},
                z_index=15
            ))

        return cmds


class AngleLine(TrendLine):
    """Trend line that always shows its angle label and uses 45-degree preset angle."""

    FIXED_ANGLE = 45.0  # Preset 45-degree angle

    def render_commands(self, coord_engine: CoordinateEngine, viewport: Optional[Any] = None) -> List[DrawCommand]:
        cmds = super().render_commands(coord_engine, viewport)
        # Always add angle text (TrendLine only adds it when selected)
        if len(self.state.points) >= 2 and self.state.visible:
            (i1, p1), (i2, p2) = self.state.points[:2]
            x2 = coord_engine.index_to_x(float(i2))
            y2 = coord_engine.price_to_y(float(p2), viewport or coord_engine.viewport)
            angle = self.compute_angle(coord_engine)
            if angle is not None:
                cmds.append(DrawCommand(
                    layer=Layer.DRAWING,
                    tag=f"angle_{self.state.id}",
                    item_type="text",
                    coords=(x2, y2 - 18),
                    options={
                        "text": f"Angle {angle}°",
                        "fill": self.state.color.to_hex(),
                        "font": ("Segoe UI", 9, "bold"),
                        "anchor": "center"
                    },
                    z_index=16
                ))
        return cmds


class Rectangle(DrawingTool):
    """Interactive rectangle defined by two corner price/time anchor points."""

    def hit_test(self, px: float, py: float, coord_engine: CoordinateEngine) -> bool:
        if len(self.state.points) < 2 or self.state.locked:
            return False

        (idx1, p1), (idx2, p2) = self.state.points[:2]
        x1 = coord_engine.index_to_x(float(idx1))
        y1 = coord_engine.price_to_y(float(p1))
        x2 = coord_engine.index_to_x(float(idx2))
        y2 = coord_engine.price_to_y(float(p2))

        # Test edge hit (border)
        tol = 10.0 if (self.state.hovered or self.state.selected) else 6.0
        return (
            is_point_near_line(px, py, x1, y1, x2, y1, tolerance=tol) or
            is_point_near_line(px, py, x2, y1, x2, y2, tolerance=tol) or
            is_point_near_line(px, py, x2, y2, x1, y2, tolerance=tol) or
            is_point_near_line(px, py, x1, y2, x1, y1, tolerance=tol)
        )

    def get_handles(self, coord_engine: CoordinateEngine, viewport: Optional[Any] = None) -> List[Tuple[float, float, str]]:
        if len(self.state.points) < 2:
            return []
        (i1, p1), (i2, p2) = self.state.points[:2]
        vp = viewport or coord_engine.viewport
        x1 = coord_engine.index_to_x(float(i1))
        y1 = coord_engine.price_to_y(float(p1), vp)
        x2 = coord_engine.index_to_x(float(i2))
        y2 = coord_engine.price_to_y(float(p2), vp)
        return [
            (x1, y1, "p1"),
            (x2, y1, "p2"),
            (x2, y2, "p3"),
            (x1, y2, "p4"),
        ]

    def move_endpoint(self, handle_id: str, new_index: float, new_price: float) -> None:
        handle_map = {"p1": 0, "p2": 1, "p3": 2, "p4": 3}
        idx = handle_map.get(handle_id, 0)
        pts = list(self.state.points)
        if len(pts) < 2:
            pts = [(new_index, new_price), (new_index, new_price)]
        else:
            if idx == 0:
                pts[0] = (new_index, new_price)
            elif idx == 1:
                pts[1] = (new_index, pts[0][1])
            elif idx == 2:
                pts[1] = (new_index, new_price)
            elif idx == 3:
                pts[0] = (new_index, pts[1][1])
        self.state.points = pts

    def move_whole(self, d_index: float, d_price: float) -> None:
        pts = []
        for i, p in self.state.points:
            pts.append((i + d_index, p + d_price))
        self.state.points = pts

    def render_commands(self, coord_engine: CoordinateEngine, viewport: Optional[Any] = None) -> List[DrawCommand]:
        if len(self.state.points) < 2 or not self.state.visible:
            return []

        vp = viewport or coord_engine.viewport
        (idx1, p1), (idx2, p2) = self.state.points[:2]

        x1 = coord_engine.index_to_x(float(idx1))
        y1 = coord_engine.price_to_y(float(p1), vp)
        x2 = coord_engine.index_to_x(float(idx2))
        y2 = coord_engine.price_to_y(float(p2), vp)

        color = self.state.color.to_hex()
        if self.state.selected:
            color = "#FFA500"
        elif self.state.hovered:
            color = "#FFD700"

        width = self.state.width + (1.0 if self.state.selected else 0.0)

        # Fill color with transparency support
        fill_color = self.state.fill.to_hex() if self.state.fill else ""
        # Use stipple pattern for transparency effect when fill is set
        fill_stipple = "gray25" if self.state.fill else ""

        cmds: List[DrawCommand] = []
        cmds.append(DrawCommand(
            layer=Layer.DRAWING,
            tag=f"rect_{self.state.id}",
            item_type="rectangle",
            coords=(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)),
            options={"outline": color, "fill": fill_color, "width": width, "stipple": fill_stipple},
            z_index=5
        ))

        # Label at center
        if self.state.label:
            mid_x = (x1 + x2) / 2.0
            mid_y = (y1 + y2) / 2.0
            cmds.append(DrawCommand(
                layer=Layer.DRAWING,
                tag=f"label_{self.state.id}",
                item_type="text",
                coords=(mid_x, mid_y),
                options={
                    "text": self.state.label,
                    "fill": color,
                    "font": ("Segoe UI", 9),
                    "anchor": "center"
                },
                z_index=6
            ))

        if self.state.selected:
            h = 5.0
            for (hx, hy), htag in [((x1, y1), "h1"), ((x2, y1), "h2"), ((x2, y2), "h3"), ((x1, y2), "h4")]:
                cmds.append(DrawCommand(
                    layer=Layer.DRAWING,
                    tag=f"handle_{self.state.id}_{htag}",
                    item_type="oval",
                    coords=(hx - h, hy - h, hx + h, hy + h),
                    options={"fill": "#FFFFFF", "outline": "#000000", "width": 1},
                    z_index=15
                ))

        return cmds


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
