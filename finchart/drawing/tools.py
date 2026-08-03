"""Drawing Tools Implementation - TrendLine, HorizontalLine, VerticalLine, Rectangle, and MarketProfileOverlay.

All tools are pure Python with no numpy/pandas dependencies.
"""
from __future__ import annotations

from typing import List, Optional, Any, Dict, Tuple
import math

from ..core.types import Point, Color, OHLCV
from ..coordinates.engine import CoordinateEngine
from ..rendering.pipeline import DrawCommand, Layer
from ..interaction.hit_test import is_point_near_line, is_point_in_rect, is_point_near_handle
from .base import DrawingTool, DrawingState


class TrendLine(DrawingTool):
    """Interactive trend line shape between two price/time anchor points."""

    def hit_test(self, px: float, py: float, coord_engine: CoordinateEngine, viewport: Optional[Any] = None) -> bool:
        if len(self.state.points) < 2 or self.state.locked:
            return False

        vp = viewport or coord_engine.viewport
        (i1, p1), (i2, p2) = self.state.points[:2]
        x1 = coord_engine.index_to_x(float(i1))
        y1 = coord_engine.price_to_y(float(p1), vp)
        x2 = coord_engine.index_to_x(float(i2))
        y2 = coord_engine.price_to_y(float(p2), vp)

        # Wider tolerance when hovered/selected
        tol = 10.0 if (self.state.hovered or self.state.selected) else 6.0
        return is_point_near_line(px, py, x1, y1, x2, y2, tolerance=tol)

    def get_handles(self, coord_engine: CoordinateEngine, viewport: Optional[Any] = None) -> List[Tuple[float, float, str]]:
        if len(self.state.points) < 2:
            return []
        vp = viewport or coord_engine.viewport
        (i1, p1), (i2, p2) = self.state.points[:2]
        return [
            (coord_engine.index_to_x(float(i1)), coord_engine.price_to_y(float(p1), vp), "p1"),
            (coord_engine.index_to_x(float(i2)), coord_engine.price_to_y(float(p2), vp), "p2"),
        ]

    def compute_angle(self, coord_engine: CoordinateEngine, viewport: Optional[Any] = None) -> Optional[float]:
        if len(self.state.points) < 2:
            return None
        vp = viewport or coord_engine.viewport
        (i1, p1), (i2, p2) = self.state.points[:2]
        x1, y1 = coord_engine.index_to_x(float(i1)), coord_engine.price_to_y(float(p1), vp)
        x2, y2 = coord_engine.index_to_x(float(i2)), coord_engine.price_to_y(float(p2), vp)

        # Always read left-to-right so the sign is consistent regardless
        # of which handle the user is dragging.
        if x1 > x2:
            x1, x2 = x2, x1
            y1, y2 = y2, y1

        # Canvas Y increases downward, so invert dy for geometric angle
        dx = x2 - x1
        dy = -(y2 - y1)
        angle_deg = math.degrees(math.atan2(dy, dx))

        # Clamp to trading-standard range (vertical lines can hit exactly ±90)
        if angle_deg > 90:
            angle_deg = 90
        elif angle_deg < -90:
            angle_deg = -90

        return round(angle_deg, 1)

    def move_endpoint(self, handle_id: str, new_index: float, new_price: float) -> None:
        idx = 0 if handle_id == "p1" else 1
        pts = list(self.state.points)
        pts[idx] = (round(new_index), new_price)  # Round X to nearest bar
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
            angle = self.compute_angle(coord_engine, viewport)
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

    def hit_test(self, px: float, py: float, coord_engine: CoordinateEngine, viewport: Optional[Any] = None) -> bool:
        if not self.state.points or self.state.locked:
            return False
        _, price = self.state.points[0]
        if price is None:
            return False
        vp = viewport or coord_engine.viewport
        y = coord_engine.price_to_y(float(price), vp)
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

    def hit_test(self, px: float, py: float, coord_engine: CoordinateEngine, viewport: Optional[Any] = None) -> bool:
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
            angle = self.compute_angle(coord_engine, viewport)
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

    def hit_test(self, px: float, py: float, coord_engine: CoordinateEngine, viewport: Optional[Any] = None) -> bool:
        if len(self.state.points) < 2 or self.state.locked:
            return False

        vp = viewport or coord_engine.viewport
        (idx1, p1), (idx2, p2) = self.state.points[:2]
        x1 = coord_engine.index_to_x(float(idx1))
        y1 = coord_engine.price_to_y(float(p1), vp)
        x2 = coord_engine.index_to_x(float(idx2))
        y2 = coord_engine.price_to_y(float(p2), vp)

        # 1) Interior hit — clicking anywhere inside the rectangle selects it
        if is_point_in_rect(px, py, x1, y1, x2, y2):
            return True

        # 2) Edge hit (border) with tolerance for handle-less selection
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
        if len(self.state.points) < 2:
            self.state.points = [(round(new_index), new_price), (round(new_index), new_price)]
            return

        pts = list(self.state.points)
        i0, p0 = pts[0]
        i1, p1 = pts[1]

        if handle_id == "p1":
            # Top-left: direct control of pts[0]
            pts[0] = (round(new_index), new_price)
        elif handle_id == "p2":
            # Top-right: x comes from pts[1], y comes from pts[0]
            pts[1] = (round(new_index), p1)
            pts[0] = (i0, new_price)
        elif handle_id == "p3":
            # Bottom-right: direct control of pts[1]
            pts[1] = (round(new_index), new_price)
        elif handle_id == "p4":
            # Bottom-left: x comes from pts[0], y comes from pts[1]
            pts[0] = (round(new_index), p0)
            pts[1] = (i1, new_price)

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
        if self.state.fill:
            # Use stipple pattern for transparency effect instead of color blending
            # This provides better visibility than blending with dark background
            fill_rgb = self.state.fill
            fill_color = fill_rgb.to_hex()
            
            # Use stipple patterns based on alpha value
            alpha = fill_rgb.a if fill_rgb.a is not None else 0.3
            if alpha >= 0.7:
                # For solid fill, don't set stipple at all
                fill_stipple = None
            elif alpha >= 0.5:
                fill_stipple = "gray12"  # Light stipple
            elif alpha >= 0.3:
                fill_stipple = "gray25"  # Medium stipple
            else:
                fill_stipple = "gray50"  # Heavy stipple for low opacity
        else:
            fill_color = ""
            fill_stipple = None

        # Build options dict, only include stipple if needed
        rect_options = {"outline": color, "fill": fill_color, "width": width}
        if fill_stipple is not None:
            rect_options["stipple"] = fill_stipple

        cmds: List[DrawCommand] = []
        cmds.append(DrawCommand(
            layer=Layer.DRAWING,
            tag=f"rect_{self.state.id}",
            item_type="rectangle",
            coords=(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)),
            options=rect_options,
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


class LongShort(DrawingTool):
    """
    TradingView-style Long/Short position shape.
    
    Points:
        [0] = (entry_index, entry_price)
        [1] = (width_index, target_price)
        [2] = (width_index, stop_price)
    """

    def __init__(self, state: DrawingState) -> None:
        super().__init__(state)
        self._live_price: Optional[float] = None

    def update_live_price(self, price: Optional[float]) -> None:
        """Called by ChartWidget before each render so PnL label stays live."""
        self._live_price = price

    # ── Geometry helpers ──────────────────────────────────────────

    @property
    def entry_index(self) -> float:
        return self.state.points[0][0] if self.state.points else 0.0

    @property
    def entry_price(self) -> float:
        return self.state.points[0][1] if self.state.points else 0.0

    @property
    def width_index(self) -> float:
        return self.state.points[1][0] if len(self.state.points) > 1 else self.entry_index

    @property
    def target_price(self) -> float:
        return self.state.points[1][1] if len(self.state.points) > 1 else self.entry_price

    @property
    def stop_price(self) -> float:
        return self.state.points[2][1] if len(self.state.points) > 2 else self.entry_price

    @property
    def is_long(self) -> bool:
        return self.target_price >= self.stop_price

    @property
    def quantity(self) -> float:
        try:
            return float(self.state.label) if self.state.label else 1.0
        except ValueError:
            return 1.0

    @property
    def risk_reward_ratio(self) -> Optional[float]:
        """Return Reward:Risk ratio (e.g., 2.5 means 2.5:1)."""
        risk = abs(self.entry_price - self.stop_price)
        reward = abs(self.target_price - self.entry_price)
        if risk < 1e-9:
            return None
        return reward / risk

    # ── Hit test ──────────────────────────────────────────────────

    def hit_test(self, px: float, py: float, coord_engine: CoordinateEngine,
                 viewport: Optional[Any] = None) -> bool:
        if len(self.state.points) < 3 or self.state.locked:
            return False

        vp = viewport or coord_engine.viewport
        ex = coord_engine.index_to_x(self.entry_index)
        ey = coord_engine.price_to_y(self.entry_price, vp)
        wx = coord_engine.index_to_x(self.width_index)
        ty = coord_engine.price_to_y(self.target_price, vp)
        sy = coord_engine.price_to_y(self.stop_price, vp)

        tol = 10.0 if (self.state.hovered or self.state.selected) else 6.0

        # 1) Handle hit (always, so dragging handles works even inside zones)
        for hx, hy, hid in self.get_handles(coord_engine, vp):
            if is_point_near_handle(px, py, hx, hy, size=8):
                return True

        # 2) Entry line
        if is_point_near_line(px, py, ex, ey, wx, ey, tolerance=tol):
            return True

        # 3) Target zone interior
        if is_point_in_rect(px, py, ex, ey, wx, ty):
            return True

        # 4) Stop zone interior
        if is_point_in_rect(px, py, ex, ey, wx, sy):
            return True

        return False

    # ── Handles ───────────────────────────────────────────────────

    def get_handles(self, coord_engine: CoordinateEngine,
                    viewport: Optional[Any] = None) -> List[Tuple[float, float, str]]:
        if len(self.state.points) < 3:
            return []
        vp = viewport or coord_engine.viewport
        ex = coord_engine.index_to_x(self.entry_index)
        ey = coord_engine.price_to_y(self.entry_price, vp)
        wx = coord_engine.index_to_x(self.width_index)
        ty = coord_engine.price_to_y(self.target_price, vp)
        sy = coord_engine.price_to_y(self.stop_price, vp)
        return [
            (ex, ey, "entry"),      # left  — entry price / index
            (wx, ty, "target"),     # right — target level
            (wx, sy, "stop"),       # right — stop level
            (wx, ey, "width"),      # right — width (opposite side of entry)
        ]

    # ── Mutation ────────────────────────────────────────────────────

    def move_endpoint(self, handle_id: str, new_index: float, new_price: float) -> None:
        if len(self.state.points) < 3:
            return

        pts = list(self.state.points)
        if handle_id == "entry":
            pts[0] = (round(new_index), new_price)
            # Keep width_index fixed when moving entry
            if len(pts) > 1:
                width_i = pts[1][0]
                pts[1] = (width_i, pts[1][1])
                pts[2] = (width_i, pts[2][1])
        elif handle_id == "target":
            width_i = pts[1][0]
            pts[1] = (width_i, new_price)
        elif handle_id == "stop":
            width_i = pts[2][0]
            pts[2] = (width_i, new_price)
        elif handle_id == "width":
            # Move width_index, preserve target/stop prices
            width_i = round(new_index)
            pts[1] = (width_i, pts[1][1])
            pts[2] = (width_i, pts[2][1])

        self.state.points = pts

    def move_whole(self, d_index: float, d_price: float) -> None:
        pts = []
        for i, p in self.state.points:
            pts.append((i + d_index, p + d_price))
        self.state.points = pts

    # ── Rendering ──────────────────────────────────────────────────

    def render_commands(self, coord_engine: CoordinateEngine,
                       viewport: Optional[Any] = None) -> List[DrawCommand]:
        if len(self.state.points) < 3 or not self.state.visible:
            return []

        vp = viewport or coord_engine.viewport
        ex = coord_engine.index_to_x(self.entry_index)
        ey = coord_engine.price_to_y(self.entry_price, vp)
        wx = coord_engine.index_to_x(self.width_index)
        ty = coord_engine.price_to_y(self.target_price, vp)
        sy = coord_engine.price_to_y(self.stop_price, vp)

        cmds: List[DrawCommand] = []

        # Determine direction and colors
        if self.is_long:
            # Long: green above entry, red below
            target_color = "#00C853"  # green
            stop_color = "#FF3D00"    # red
            top_y, bottom_y = ty, sy
        else:
            # Short: green below entry, red above
            target_color = "#00C853"  # green
            stop_color = "#FF3D00"    # red
            top_y, bottom_y = sy, ty

        # 1) Entry line (dashed orange)
        cmds.append(DrawCommand(
            layer=Layer.DRAWING,
            tag=f"entry_line_{self.state.id}",
            item_type="line",
            coords=(ex, ey, wx, ey),
            options={
                "fill": "#FF9800",
                "width": 1.5,
                "dash": (4, 4)
            },
            z_index=5
        ))

        # 2) Target zone (green)
        target_rect = (ex, min(ey, ty), wx, max(ey, ty))
        cmds.append(DrawCommand(
            layer=Layer.DRAWING,
            tag=f"target_zone_{self.state.id}",
            item_type="rectangle",
            coords=target_rect,
            options={
                "fill": target_color,
                "outline": "",
                "stipple": "gray25"
            },
            z_index=4
        ))

        # 3) Stop zone (red)
        # Only draw stop zone if it differs meaningfully from entry
        if abs(self.stop_price - self.entry_price) > 1e-9:
            stop_rect = (ex, min(ey, sy), wx, max(ey, sy))
            cmds.append(DrawCommand(
                layer=Layer.DRAWING,
                tag=f"stop_zone_{self.state.id}",
                item_type="rectangle",
                coords=stop_rect,
                options={
                    "fill": stop_color,
                    "outline": "",
                    "stipple": "gray25"
                },
                z_index=4
            ))

        # 4) Labels
        qty = self.quantity
        target_pnl = (self.target_price - self.entry_price) * qty if self.is_long else (self.entry_price - self.target_price) * qty
        stop_pnl = (self.stop_price - self.entry_price) * qty if self.is_long else (self.entry_price - self.stop_price) * qty
        
        # Live PnL if live price available
        if self._live_price is not None:
            live_pnl = (self._live_price - self.entry_price) * qty if self.is_long else (self.entry_price - self._live_price) * qty
            pnl_text = f"PnL: {live_pnl:+.2f}"
        else:
            pnl_text = f"PnL: 0.00"

        # Compute and display Risk/Reward ratio
        rr = self.risk_reward_ratio
        rr_text = f" RR 1:{rr:.1f}" if rr else ""

        # Entry label (quantity + price + Risk/Reward)
        box_left = min(ex, wx)
        box_right = max(ex, wx)
        entry_label = f"{qty} @ {self.entry_price:.2f}{rr_text}"
        cmds.append(DrawCommand(
            layer=Layer.DRAWING,
            tag=f"entry_label_{self.state.id}",
            item_type="text",
            coords=(box_left + 4, ey - 6),
            options={
                "text": entry_label,
                "fill": "#FFFFFF",
                "font": ("Segoe UI", 9, "bold"),
                "anchor": "nw"
            },
            z_index=6
        ))

        # PnL label (below entry)
        cmds.append(DrawCommand(
            layer=Layer.DRAWING,
            tag=f"pnl_label_{self.state.id}",
            item_type="text",
            coords=(ex + 5, ey + 10),
            options={
                "text": pnl_text,
                "fill": "#FFD700" if self._live_price else "#AAAAAA",
                "font": ("Segoe UI", 9),
                "anchor": "w"
            },
            z_index=6
        ))

        # Target label (aligned to right edge of box)
        target_label = f"Target: {self.target_price:.2f} ({target_pnl:+.2f})"
        label_y = ty - 5 if self.is_long else ty + 15
        cmds.append(DrawCommand(
            layer=Layer.DRAWING,
            tag=f"target_label_{self.state.id}",
            item_type="text",
            coords=(wx + 5, label_y),
            options={
                "text": target_label,
                "fill": target_color,
                "font": ("Segoe UI", 9),
                "anchor": "w"
            },
            z_index=6
        ))

        # Stop label (aligned to right edge of box)
        stop_label = f"Stop: {self.stop_price:.2f} ({stop_pnl:+.2f})"
        label_y = sy + 15 if self.is_long else sy - 5
        cmds.append(DrawCommand(
            layer=Layer.DRAWING,
            tag=f"stop_label_{self.state.id}",
            item_type="text",
            coords=(wx + 5, label_y),
            options={
                "text": stop_label,
                "fill": stop_color,
                "font": ("Segoe UI", 9),
                "anchor": "w"
            },
            z_index=6
        ))

        # 5) Selection handles
        if self.state.selected:
            h = 5.0
            handles = self.get_handles(coord_engine, vp)
            for hx, hy, hid in handles:
                cmds.append(DrawCommand(
                    layer=Layer.DRAWING,
                    tag=f"handle_{self.state.id}_{hid}",
                    item_type="oval",
                    coords=(hx - h, hy - h, hx + h, hy + h),
                    options={"fill": "#FFFFFF", "outline": "#000000", "width": 1},
                    z_index=15
                ))

        return cmds
