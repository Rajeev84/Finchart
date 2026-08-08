"""Grid Renderer - Renders horizontal/vertical grid lines and axis labels.

Uses nice-number step calculation algorithms for dynamic price and time ticks.
"""
from __future__ import annotations

from typing import List, Optional, Tuple
from dataclasses import dataclass, field
import math
from datetime import datetime

from ..core.types import Viewport, Color, OHLCV
from ..coordinates.engine import CoordinateEngine
from .pipeline import RenderingPipeline, DrawCommand, Layer


@dataclass
class GridStyle:
    """Visual styling properties for grid and axes."""
    grid_color: Color = field(default_factory=lambda: Color(42, 46, 57))
    grid_width: float = 1.0
    axis_text_color: Color = field(default_factory=lambda: Color(178, 181, 190))
    axis_font: Tuple[str, int] = ("Segoe UI", 9)
    axis_bg_color: Color = field(default_factory=lambda: Color(19, 23, 34))
    axis_border_color: Color = field(default_factory=lambda: Color(42, 46, 57))
    price_axis_width: float = 60.0
    time_axis_height: float = 25.0
    show_horizontal_grid: bool = True
    show_vertical_grid: bool = True


class GridRenderer:
    """Renders grid lines and price/time scale axes."""

    def __init__(
        self,
        pipeline: RenderingPipeline,
        coord_engine: CoordinateEngine,
        style: Optional[GridStyle] = None
    ) -> None:
        self._pipeline = pipeline
        self._coord = coord_engine
        self._style = style or GridStyle()

    @property
    def style(self) -> GridStyle:
        return self._style

    def render(self, data_list: Optional[List[OHLCV]] = None, pane_name: Optional[str] = None) -> None:
        """Render grid lines and axis ticks onto dedicated layers.

        Grid lines go to Layer.GRID, axis backgrounds to Layer.AXIS_BG,
        and axis labels to Layer.AXIS_TEXT. This ensures labels are always
        above backgrounds regardless of pool reuse order.

        If pane_name is provided, renders grid for that specific pane.
        """
        commands = []

        if pane_name and pane_name != "candlestick":
            # Render grid for a sub-pane (e.g., RSI, MACD)
            pane_vp = self._coord.get_pane_viewport(pane_name)
            chart_vp = self._get_pane_chart_viewport(pane_vp)

            # Vertical grid lines (shared time axis)
            if self._style.show_vertical_grid:
                commands.extend(self._render_vertical_grid(chart_vp))

            # Price axis for this pane (right side)
            commands.extend(self._render_pane_price_axis(chart_vp, pane_name))

            # Horizontal grid for this pane
            if self._style.show_horizontal_grid:
                commands.extend(self._render_pane_horizontal_grid(chart_vp, pane_name))
        else:
            # Render main chart grid (candlestick pane)
            chart_vp = self.get_chart_viewport()

            # Horizontal Grid (Price levels)
            if self._style.show_horizontal_grid:
                commands.extend(self._render_horizontal_grid(chart_vp))

            # Vertical Grid (Time levels)
            if self._style.show_vertical_grid:
                commands.extend(self._render_vertical_grid(chart_vp))

            # Price Axis Labels & Background
            commands.extend(self._render_price_axis(chart_vp))

            # Time Axis Labels & Background
            commands.extend(self._render_time_axis(chart_vp, data_list))

        self._pipeline.add_commands(commands)
        self._pipeline.schedule_layer(Layer.GRID)
        self._pipeline.schedule_layer(Layer.AXIS_BG)
        self._pipeline.schedule_layer(Layer.AXIS_TEXT)

    def get_chart_viewport(self) -> Viewport:
        """Return the main candlestick chart viewport excluding price axis.

        Uses the candlestick pane viewport from the coordinate engine if available,
        otherwise falls back to the full canvas viewport.
        """
        # Try to get the candlestick pane viewport first
        candlestick_vp = self._coord.get_pane_viewport("candlestick")
        if candlestick_vp and candlestick_vp.height > 0 and candlestick_vp.width > 0:
            vp = candlestick_vp
        else:
            vp = self._coord.viewport

        return Viewport(
            x=vp.x,
            y=vp.y,
            width=max(10.0, vp.width - self._style.price_axis_width),
            height=vp.height  # Don't subtract time axis height here; it's handled by layout
        )

    def _render_horizontal_grid(self, chart_vp: Viewport) -> List[DrawCommand]:
        """Generate horizontal price grid lines."""
        cmds = []
        ps = self._coord.price_scale
        if ps.price_range <= 0 or chart_vp.height <= 0:
            return cmds

        approx_lines = max(3, int(chart_vp.height / 50.0))
        raw_step = ps.price_range / approx_lines
        step = self._nice_number(raw_step)

        start_price = math.ceil(ps.min_price / step) * step
        curr_price = start_price

        while curr_price <= ps.max_price:
            y = self._coord.price_to_y(curr_price, chart_vp)
            if chart_vp.top <= y <= chart_vp.bottom:
                cmds.append(DrawCommand(
                    layer=Layer.GRID,
                    tag=f"hgrid_{curr_price:.6f}",
                    item_type="line",
                    coords=(chart_vp.left, y, chart_vp.right, y),
                    options={
                        "fill": self._style.grid_color.to_hex(),
                        "width": self._style.grid_width,
                        "dash": (2, 4)
                    },
                    z_index=0
                ))
            curr_price += step

        return cmds

    def _render_vertical_grid(self, chart_vp: Viewport) -> List[DrawCommand]:
        """Generate vertical time grid lines."""
        cmds = []
        vr = self._coord.visible_range
        if vr.count <= 0 or chart_vp.width <= 0:
            return cmds

        approx_labels = max(2, int(chart_vp.width / 100.0))
        step_bars = max(1, vr.count // approx_labels)
        step_bars = self._nice_bar_step(step_bars)

        start_idx = (vr.start_index // step_bars) * step_bars

        for i in range(start_idx, vr.end_index + 1, step_bars):
            x = self._coord.index_to_x(i)
            if chart_vp.left <= x <= chart_vp.right:
                cmds.append(DrawCommand(
                    layer=Layer.GRID,
                    tag=f"vgrid_{i}",
                    item_type="line",
                    coords=(x, chart_vp.top, x, chart_vp.bottom),
                    options={
                        "fill": self._style.grid_color.to_hex(),
                        "width": self._style.grid_width,
                        "dash": (2, 4)
                    },
                    z_index=0
                ))

        return cmds

    def _render_price_axis(self, chart_vp: Viewport) -> List[DrawCommand]:
        """Generate price axis background, border, and tick labels."""
        cmds = []
        axis_x = chart_vp.right

        # Price Axis Background - use chart_vp top/bottom to match candlestick pane
        cmds.append(DrawCommand(
            layer=Layer.AXIS_BG,
            tag="price_axis_bg",
            item_type="rectangle",
            coords=(axis_x, chart_vp.top, axis_x + self._style.price_axis_width, chart_vp.bottom),
            options={
                "fill": self._style.axis_bg_color.to_hex(),
                "outline": self._style.axis_border_color.to_hex(),
                "width": 1
            },
            z_index=5
        ))

        # Price Axis Labels
        ps = self._coord.price_scale
        if ps.price_range <= 0 or chart_vp.height <= 0:
            return cmds

        approx_lines = max(3, int(chart_vp.height / 50.0))
        raw_step = ps.price_range / approx_lines
        step = self._nice_number(raw_step)
        curr_price = math.ceil(ps.min_price / step) * step

        while curr_price <= ps.max_price:
            y = self._coord.price_to_y(curr_price, chart_vp)
            if chart_vp.top <= y <= chart_vp.bottom:
                label = self._format_price(curr_price)
                cmds.append(DrawCommand(
                    layer=Layer.AXIS_TEXT,
                    tag=f"price_tick_{curr_price:.6f}",
                    item_type="text",
                    coords=(axis_x + 6.0, y),
                    options={
                        "text": label,
                        "fill": self._style.axis_text_color.to_hex(),
                        "font": self._style.axis_font,
                        "anchor": "w"
                    },
                    z_index=10
                ))
            curr_price += step

        return cmds

    def _render_time_axis(self, chart_vp: Viewport, data_list: Optional[List[OHLCV]]) -> List[DrawCommand]:
        """Generate time axis background, border, and timestamp labels."""
        cmds = []
        vp = self._coord.viewport
        # Position time axis at the bottom of the canvas, below all panes
        axis_y = vp.bottom - self._style.time_axis_height

        # Time Axis Background
        cmds.append(DrawCommand(
            layer=Layer.AXIS_BG,
            tag="time_axis_bg",
            item_type="rectangle",
            coords=(vp.left, axis_y, vp.right, vp.bottom),
            options={
                "fill": self._style.axis_bg_color.to_hex(),
                "outline": self._style.axis_border_color.to_hex(),
                "width": 1
            },
            z_index=5
        ))

        vr = self._coord.visible_range
        if vr.count <= 0 or chart_vp.width <= 0 or not data_list:
            return cmds

        approx_labels = max(2, int(chart_vp.width / 100.0))
        step_bars = max(1, vr.count // approx_labels)
        step_bars = self._nice_bar_step(step_bars)

        start_idx = (vr.start_index // step_bars) * step_bars
        bar_spacing = self._coord.time_scale.bar_spacing

        for i in range(start_idx, min(vr.end_index + 1, len(data_list)), step_bars):
            x = self._coord.index_to_x(i)
            if chart_vp.left <= x <= chart_vp.right:
                ts = data_list[i].timestamp
                dt_str = self._format_timestamp(ts, bar_spacing)

                cmds.append(DrawCommand(
                    layer=Layer.AXIS_TEXT,
                    tag=f"time_tick_{i}",
                    item_type="text",
                    coords=(x, axis_y + 12.0),
                    options={
                        "text": dt_str,
                        "fill": self._style.axis_text_color.to_hex(),
                        "font": self._style.axis_font,
                        "anchor": "center"
                    },
                    z_index=10
                ))

        return cmds

    # --- Math Helpers ---
    def _nice_number(self, value: float) -> float:
        """Compute a human-friendly interval step (1, 2, 5, 10, 20, 50, etc.)."""
        if value <= 0:
            return 1.0
        exp = math.floor(math.log10(value))
        frac = value / (10 ** exp)
        if frac <= 1.5:
            nf = 1.0
        elif frac <= 3.0:
            nf = 2.0
        elif frac <= 7.0:
            nf = 5.0
        else:
            nf = 10.0
        return nf * (10 ** exp)

    def _nice_bar_step(self, step: int) -> int:
        """Compute nice integer step for bar indices."""
        if step <= 1: return 1
        if step <= 2: return 2
        if step <= 5: return 5
        if step <= 10: return 10
        if step <= 20: return 20
        if step <= 50: return 50
        return ((step // 50) + 1) * 50

    def _format_price(self, price: float) -> str:
        """Format price float into string with appropriate decimal precision."""
        ap = abs(price)
        if ap >= 10000: return f"{price:,.0f}"
        if ap >= 100: return f"{price:,.2f}"
        if ap >= 1: return f"{price:,.4f}"
        return f"{price:.6f}"

    def _get_pane_chart_viewport(self, pane_vp: Viewport) -> Viewport:
        """Return the chart viewport for a pane, excluding price axis width."""
        return Viewport(
            x=pane_vp.x,
            y=pane_vp.y,
            width=max(10.0, pane_vp.width - self._style.price_axis_width),
            height=pane_vp.height
        )

    def _render_pane_price_axis(self, chart_vp: Viewport, pane_name: str) -> List[DrawCommand]:
        """Generate price axis for a specific pane."""
        cmds = []
        axis_x = chart_vp.right

        # Price Axis Background
        cmds.append(DrawCommand(
            layer=Layer.AXIS_BG,
            tag=f"price_axis_bg_{pane_name}",
            item_type="rectangle",
            coords=(axis_x, chart_vp.top, axis_x + self._style.price_axis_width, chart_vp.bottom),
            options={
                "fill": self._style.axis_bg_color.to_hex(),
                "outline": self._style.axis_border_color.to_hex(),
                "width": 1
            },
            z_index=5
        ))

        # Price Axis Labels
        ps = self._coord.get_pane_price_scale(pane_name)
        if ps.price_range <= 0 or chart_vp.height <= 0:
            return cmds

        approx_lines = max(2, int(chart_vp.height / 50.0))
        raw_step = ps.price_range / approx_lines
        step = self._nice_number(raw_step)
        curr_price = math.ceil(ps.min_price / step) * step

        while curr_price <= ps.max_price:
            y = self._coord.price_to_y(curr_price, chart_vp, pane=pane_name)
            if chart_vp.top <= y <= chart_vp.bottom:
                label = self._format_price(curr_price)
                cmds.append(DrawCommand(
                    layer=Layer.AXIS_TEXT,
                    tag=f"price_tick_{pane_name}_{curr_price:.6f}",
                    item_type="text",
                    coords=(axis_x + 6.0, y),
                    options={
                        "text": label,
                        "fill": self._style.axis_text_color.to_hex(),
                        "font": self._style.axis_font,
                        "anchor": "w"
                    },
                    z_index=10
                ))
            curr_price += step

        return cmds

    def _render_pane_horizontal_grid(self, chart_vp: Viewport, pane_name: str) -> List[DrawCommand]:
        """Generate horizontal grid lines for a specific pane."""
        cmds = []
        ps = self._coord.get_pane_price_scale(pane_name)
        if ps.price_range <= 0 or chart_vp.height <= 0:
            return cmds

        approx_lines = max(2, int(chart_vp.height / 50.0))
        raw_step = ps.price_range / approx_lines
        step = self._nice_number(raw_step)

        start_price = math.ceil(ps.min_price / step) * step
        curr_price = start_price

        while curr_price <= ps.max_price:
            y = self._coord.price_to_y(curr_price, chart_vp, pane=pane_name)
            if chart_vp.top <= y <= chart_vp.bottom:
                cmds.append(DrawCommand(
                    layer=Layer.GRID,
                    tag=f"hgrid_{pane_name}_{curr_price:.6f}",
                    item_type="line",
                    coords=(chart_vp.left, y, chart_vp.right, y),
                    options={
                        "fill": self._style.grid_color.to_hex(),
                        "width": self._style.grid_width,
                        "dash": (2, 4)
                    },
                    z_index=0
                ))
            curr_price += step

        return cmds

    def _format_timestamp(self, ts: float, bar_spacing: float) -> str:
        """Format Unix timestamp into HH:MM or DD-Mon based on zoom level."""
        try:
            dt = datetime.fromtimestamp(ts)
            if bar_spacing >= 5.0:
                return dt.strftime("%H:%M")
            return dt.strftime("%d-%b")
        except (ValueError, OverflowError, OSError):
            return str(int(ts))