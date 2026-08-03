"""Crosshair Renderer - Interactive crosshair cursor, axis labels, and bar highlight.

Tracks mouse cursor position, snaps to nearest bar timestamp, and generates
crosshair lines and coordinate badges on Layer.CROSSHAIR.

How other charting libraries (TradingView, lightweight-charts) handle crosshair
badges:
  - A vertical line spans ALL panes (main + subplots).
  - A horizontal line is drawn only in the pane the cursor is over.
  - On the right price-axis of EACH pane, a badge box is drawn showing the
    value at the crosshair position. For the main pane this is the price at
    cursor Y; for indicator subplots this is the indicator value at the
    snapped bar index.
  - At the bottom time-axis, a badge box shows the datetime at the snapped bar.
  - Old badge areas are cleared by releasing/re-creating items each frame
    (the retained-mode pipeline already handles this via item pool release).
"""
from __future__ import annotations

from typing import List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from ..core.types import Viewport, Color, OHLCV
from ..coordinates.engine import CoordinateEngine
from .pipeline import RenderingPipeline, DrawCommand, Layer


@dataclass
class CrosshairStyle:
    """Styling properties for crosshair rendering."""
    line_color: Color = field(default_factory=lambda: Color(149, 152, 161))
    line_width: float = 1.0
    line_dash: Tuple[int, ...] = (4, 4)  # Dashed line for TradingView-style appearance
    badge_bg: Color = field(default_factory=lambda: Color(54, 58, 69))
    badge_fg: Color = field(default_factory=lambda: Color(255, 255, 255))
    badge_font: Tuple[str, int] = ("Segoe UI", 9)
    highlight_color: Color = field(default_factory=lambda: Color(255, 255, 255))
    highlight_stipple: str = "gray12"
    time_axis_height: float = 25.0
    price_axis_width: float = 60.0
    # Cap the bar-highlight rectangle width so it doesn't grow unboundedly
    # when zooming in (per user report: "vertical line increases in width").
    max_highlight_width: float = 12.0


@dataclass
class PaneBadge:
    """Info for drawing a crosshair value badge on one pane's right axis.

    Attributes:
        badge_y:      Y pixel for the badge centre (mouse Y for main pane,
                      indicator-value Y for subplot panes).
        value_text:   Pre-formatted string to display inside the badge.
        pane_top:     Top Y of the pane (for clamping the badge).
        pane_bottom:  Bottom Y of the pane (for clamping the badge).
    """
    badge_y: float
    value_text: str
    pane_top: float
    pane_bottom: float


class CrosshairRenderer:
    """Renders crosshair lines, bar highlight, and price/time badges."""

    def __init__(
        self,
        pipeline: RenderingPipeline,
        coord_engine: CoordinateEngine,
        style: Optional[CrosshairStyle] = None
    ) -> None:
        self._pipeline = pipeline
        self._coord = coord_engine
        self._style = style or CrosshairStyle()

        self._mouse_x: float = -1.0
        self._mouse_y: float = -1.0
        self._is_visible: bool = False
        self._snapped_index: int = -1
        self._snapped_bar: Optional[OHLCV] = None
        self._data: List[OHLCV] = []
        self._pane_badges: List[PaneBadge] = []

    @property
    def is_visible(self) -> bool:
        return self._is_visible

    @property
    def snapped_index(self) -> int:
        return self._snapped_index

    @property
    def snapped_bar(self) -> Optional[OHLCV]:
        return self._snapped_bar

    @property
    def mouse_y(self) -> float:
        return self._mouse_y

    def set_data(self, data: List[OHLCV]) -> None:
        """Set bar data for snapping."""
        self._data = data

    def set_pane_badges(self, badges: List[PaneBadge]) -> None:
        """Set per-pane badge info computed by the widget.

        The widget knows which indicators live in which pane and can format
        the value text.  The crosshair renderer only handles drawing.
        """
        self._pane_badges = badges

    def on_mouse_move(self, x: float, y: float, chart_vp: Viewport) -> None:
        """Update crosshair state from mouse motion.

        Does not schedule a render by itself — the caller must call
        ``render()`` then ``schedule_layer(Layer.CROSSHAIR)`` so draw
        commands exist in the buffer before the incremental pass runs.
        """
        self._mouse_x = x
        self._mouse_y = y
        # Visible anywhere in the plot+subplot strip (not only main pane)
        vp = self._coord.viewport
        axis_y = vp.bottom - self._style.time_axis_height
        in_x = chart_vp.left <= x <= chart_vp.right
        in_y = chart_vp.top <= y <= axis_y
        self._is_visible = in_x and in_y

        if self._is_visible and self._data:
            snapped_float = self._coord.x_to_index(x)
            self._snapped_index = max(0, min(len(self._data) - 1, int(round(snapped_float))))
            self._snapped_bar = self._data[self._snapped_index]
        else:
            self._snapped_index = -1
            self._snapped_bar = None

    def on_mouse_leave(self) -> None:
        """Hide crosshair when mouse leaves canvas."""
        self._is_visible = False
        self._snapped_index = -1
        self._snapped_bar = None
        self._pane_badges = []
        self._pipeline.clear_layer_commands(Layer.CROSSHAIR)
        self._pipeline.schedule_layer(Layer.CROSSHAIR)

    def render(self, chart_vp: Viewport) -> None:
        """Render crosshair lines, bar highlight, and axis badges onto Layer.CROSSHAIR."""
        if not self._is_visible:
            return

        commands = []
        vp = self._coord.viewport

        # Determine snapped X centerline
        if self._snapped_index >= 0:
            snapped_x = self._coord.index_to_x(self._snapped_index)
        else:
            snapped_x = self._mouse_x

        hex_line = self._style.line_color.to_hex()
        axis_y = vp.bottom - self._style.time_axis_height

        # 1. Bar Background Highlight
        # Use fixed minimal width to prevent highlight from growing with zoom
        # (user-reported: "crosshair vertical line increases in width when chart zooming")
        highlight_width = self._style.line_width * 2  # e.g., 2px fixed
        half_w = highlight_width / 2.0
        commands.append(DrawCommand(
            layer=Layer.CROSSHAIR,
            tag="bar_highlight",
            item_type="rectangle",
            coords=(snapped_x - half_w, chart_vp.top, snapped_x + half_w, axis_y),
            options={
                "fill": self._style.highlight_color.to_hex(),
                "outline": "",
                "stipple": self._style.highlight_stipple
            },
            z_index=0
        ))

        # 2. Horizontal Crosshair Line (at mouse Y, across chart width)
        commands.append(DrawCommand(
            layer=Layer.CROSSHAIR,
            tag="crosshair_h",
            item_type="line",
            coords=(chart_vp.left, self._mouse_y, chart_vp.right, self._mouse_y),
            options={
                "fill": hex_line,
                "width": self._style.line_width,
                "dash": self._style.line_dash
            },
            z_index=1
        ))

        # 3. Vertical Crosshair Line (spans all panes, fixed 1px width)
        commands.append(DrawCommand(
            layer=Layer.CROSSHAIR,
            tag="crosshair_v",
            item_type="line",
            coords=(snapped_x, chart_vp.top, snapped_x, axis_y),
            options={
                "fill": hex_line,
                "width": self._style.line_width,
                "dash": self._style.line_dash
            },
            z_index=1
        ))

        # 4. Price Axis Badges — one per pane (main + subplots)
        # Each badge is a solid-fill rectangle on the right price-axis strip
        # with the value text centred inside it.  Drawing text *after* the
        # background (higher z_index) ensures the text is always visible
        # "above" the box.
        badge_h = 20.0
        price_axis_x = chart_vp.right  # left edge of price-axis strip
        price_axis_cx = chart_vp.right + (vp.right - chart_vp.right) / 2.0

        for i, badge in enumerate(self._pane_badges):
            # Clamp badge Y to pane bounds so it doesn't overflow into
            # adjacent panes.
            by = badge.badge_y
            bt = by - badge_h / 2.0
            bb = by + badge_h / 2.0
            if bt < badge.pane_top:
                bt = badge.pane_top
                bb = bt + badge_h
                by = bt + badge_h / 2.0
            if bb > badge.pane_bottom:
                bb = badge.pane_bottom
                bt = bb - badge_h
                by = bb - badge_h / 2.0

            commands.append(DrawCommand(
                layer=Layer.CROSSHAIR,
                tag=f"price_badge_bg_{i}",
                item_type="rectangle",
                coords=(price_axis_x, bt, vp.right, bb),
                options={
                    "fill": self._style.badge_bg.to_hex(),
                    "outline": hex_line,
                    "width": 1,
                    "stipple": "",
                },
                z_index=10
            ))

            commands.append(DrawCommand(
                layer=Layer.CROSSHAIR,
                tag=f"price_badge_txt_{i}",
                item_type="text",
                coords=(price_axis_cx, by),
                options={
                    "text": badge.value_text,
                    "fill": self._style.badge_fg.to_hex(),
                    "font": self._style.badge_font,
                    "anchor": "center"
                },
                z_index=11
            ))

        # 5. Time Axis Badge — clamped to the time-axis strip at the bottom
        if self._snapped_bar:
            time_str = self._format_timestamp(self._snapped_bar.timestamp)
            badge_w = len(time_str) * 7.0 + 12.0
            bx1 = snapped_x - badge_w / 2.0
            bx2 = snapped_x + badge_w / 2.0

            # Clamp badge to viewport horizontal edges
            if bx1 < vp.left:
                diff = vp.left - bx1
                bx1 += diff
                bx2 += diff
            if bx2 > chart_vp.right:
                diff = bx2 - chart_vp.right
                bx1 -= diff
                bx2 -= diff

            axis_mid_y = axis_y + self._style.time_axis_height / 2.0

            commands.append(DrawCommand(
                layer=Layer.CROSSHAIR,
                tag="time_badge_bg",
                item_type="rectangle",
                coords=(bx1, axis_y, bx2, vp.bottom),
                options={
                    "fill": self._style.badge_bg.to_hex(),
                    "outline": hex_line,
                    "width": 1,
                    "stipple": "",
                },
                z_index=10
            ))

            commands.append(DrawCommand(
                layer=Layer.CROSSHAIR,
                tag="time_badge_txt",
                item_type="text",
                coords=((bx1 + bx2) / 2.0, axis_mid_y),
                options={
                    "text": time_str,
                    "fill": self._style.badge_fg.to_hex(),
                    "font": self._style.badge_font,
                    "anchor": "center"
                },
                z_index=11
            ))

        self._pipeline.add_commands(commands)

    def _format_price(self, price: float) -> str:
        ap = abs(price)
        if ap >= 10000: return f"{price:,.0f}"
        if ap >= 100: return f"{price:,.2f}"
        if ap >= 1: return f"{price:,.4f}"
        return f"{price:.6f}"

    def _format_timestamp(self, ts: float) -> str:
        try:
            dt = datetime.fromtimestamp(ts)
            return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return str(int(ts))