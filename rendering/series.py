"""Series Renderer - Renders OHLCV data as Candlesticks, Line, Area, and Histogram.

Filters and renders only bars visible in the current viewport window.
"""
from __future__ import annotations

from typing import List, Optional, Tuple
from dataclasses import dataclass, field

from ..core.types import OHLCV, Color, ChartType, Viewport
from ..coordinates.engine import CoordinateEngine
from .pipeline import RenderingPipeline, DrawCommand, Layer


@dataclass
class SeriesStyle:
    """Styling properties for series rendering."""
    bullish_color: Color = field(default_factory=lambda: Color(8, 153, 129))  # TradingView Green
    bearish_color: Color = field(default_factory=lambda: Color(242, 54, 69))   # TradingView Red
    wick_color: Color = field(default_factory=lambda: Color(120, 123, 134))
    line_color: Color = field(default_factory=lambda: Color(33, 150, 243))
    area_color: Color = field(default_factory=lambda: Color(33, 150, 243))
    area_stipple: str = "gray25"
    line_width: float = 1.5


class SeriesRenderer:
    """Renders OHLCV data series onto Layer.SERIES."""

    def __init__(
        self,
        pipeline: RenderingPipeline,
        coord_engine: CoordinateEngine,
        style: Optional[SeriesStyle] = None
    ) -> None:
        self._pipeline = pipeline
        self._coord = coord_engine
        self._style = style or SeriesStyle()
        self._chart_type = ChartType.CANDLESTICK
        self._data: List[OHLCV] = []

    @property
    def style(self) -> SeriesStyle:
        return self._style

    @property
    def chart_type(self) -> ChartType:
        return self._chart_type

    @chart_type.setter
    def chart_type(self, value: ChartType) -> None:
        self._chart_type = value

    def set_data(self, data: List[OHLCV]) -> None:
        """Set bar data array for rendering."""
        self._data = data

    def render(self, viewport: Optional[Viewport] = None) -> None:
        """Render visible series bars onto layer command buffer."""
        if not self._data:
            return

        vr = self._coord.visible_range
        visible_count = vr.end_index - vr.start_index
        
        # Fast mode: skip bars when too many are visible (aggressive downsampling)
        if visible_count > 500:
            step = max(1, visible_count // 500)
            start_idx = max(0, vr.start_index - 1)
            end_idx = min(len(self._data), vr.end_index + 1)
            # Render only every Nth bar
            if self._chart_type == ChartType.CANDLESTICK:
                self._render_candlesticks_fast(start_idx, end_idx, viewport, step)
            elif self._chart_type == ChartType.BASELINE:
                self._render_baseline(start_idx, end_idx, viewport, step=step)
            elif self._chart_type == ChartType.STEP:
                self._render_step(start_idx, end_idx, viewport, step=step)
            elif self._chart_type in (ChartType.LINE, ChartType.AREA, ChartType.HISTOGRAM):
                self._render_with_step(start_idx, end_idx, viewport, step)
            else:
                # OHLC and Heikin-Ashi retain their bar semantics when zoomed out.
                self._render_ohlc(start_idx, end_idx, viewport, step=step) if self._chart_type == ChartType.OHLC else self._render_heikin_ashi(start_idx, end_idx, viewport, step=step)
        else:
            start_idx = max(0, vr.start_index - 1)
            end_idx = min(len(self._data), vr.end_index + 1)
            if self._chart_type == ChartType.CANDLESTICK:
                self._render_candlesticks(start_idx, end_idx, viewport)
            elif self._chart_type == ChartType.LINE:
                self._render_line(start_idx, end_idx, viewport)
            elif self._chart_type == ChartType.AREA:
                self._render_area(start_idx, end_idx, viewport)
            elif self._chart_type == ChartType.HISTOGRAM:
                self._render_histogram(start_idx, end_idx, viewport)
            elif self._chart_type == ChartType.OHLC:
                self._render_ohlc(start_idx, end_idx, viewport)
            elif self._chart_type == ChartType.BASELINE:
                self._render_baseline(start_idx, end_idx, viewport)
            elif self._chart_type == ChartType.STEP:
                self._render_step(start_idx, end_idx, viewport)
            elif self._chart_type == ChartType.HEIKIN_ASHI:
                self._render_heikin_ashi(start_idx, end_idx, viewport)

    def _render_candlesticks_fast(self, start_idx: int, end_idx: int, viewport: Optional[Viewport], step: int) -> None:
        """Render candlesticks with aggressive downsampling for performance."""
        bar_w = self._coord.get_bar_width()
        half_w = bar_w / 2.0
        wick_w = self._coord.get_wick_width()
        vp = viewport or self._coord.viewport
        
        bullish_hex = self._style.bullish_color.to_hex()
        bearish_hex = self._style.bearish_color.to_hex()

        # In fast mode, just render simple line chart instead of full candlesticks
        points = []
        for i in range(start_idx, end_idx, step):
            bar = self._data[i]
            x = self._coord.index_to_x(i)
            if x + half_w < vp.left or x - half_w > vp.right:
                continue
            y = self._coord.price_to_y(bar.close, vp)
            points.extend([x, y])

        if len(points) >= 4:
            self._pipeline.add_command(DrawCommand(
                layer=Layer.SERIES,
                tag="fast_line",
                item_type="line",
                coords=tuple(points),
                options={"fill": self._style.line_color.to_hex(), "width": 1.0},
                z_index=0
            ))
            self._pipeline.schedule_layer(Layer.SERIES)

    def _render_with_step(self, start_idx: int, end_idx: int, viewport: Optional[Viewport], step: int) -> None:
        """Render with step for fast mode."""
        vp = viewport or self._coord.viewport
        points = []
        for i in range(start_idx, end_idx, step):
            x = self._coord.index_to_x(i)
            y = self._coord.price_to_y(self._data[i].close, vp)
            points.extend([x, y])

        if len(points) >= 4:
            self._pipeline.add_command(DrawCommand(
                layer=Layer.SERIES,
                tag="line_series",
                item_type="line",
                coords=tuple(points),
                options={
                    "fill": self._style.line_color.to_hex(),
                    "width": self._style.line_width,
                },
                z_index=0
            ))
            self._pipeline.schedule_layer(Layer.SERIES)

    def _render_candlesticks(self, start_idx: int, end_idx: int, viewport: Optional[Viewport]) -> None:
        """Render candlestick wicks and bodies with aggressive batching."""
        bar_w = self._coord.get_bar_width()
        half_w = bar_w / 2.0
        wick_w = self._coord.get_wick_width()
        vp = viewport or self._coord.viewport
        
        # Pre-calculate bullish color hex
        bullish_hex = self._style.bullish_color.to_hex()
        bearish_hex = self._style.bearish_color.to_hex()

        # Collect all bars data first
        commands = []
        bars_data = []
        for i in range(start_idx, end_idx):
            bar = self._data[i]
            x = self._coord.index_to_x(i)

            # Skip bars outside viewport left/right
            if x + half_w < vp.left or x - half_w > vp.right:
                continue

            # Batch all coordinate transformations for this bar
            y_high = self._coord.price_to_y(bar.high, vp)
            y_low = self._coord.price_to_y(bar.low, vp)
            y_open = self._coord.price_to_y(bar.open, vp)
            y_close = self._coord.price_to_y(bar.close, vp)

            body_top = min(y_open, y_close)
            body_bottom = max(y_open, y_close)
            body_h = max(1.0, body_bottom - body_top)

            is_bullish = bar.close >= bar.open
            hex_color = bullish_hex if is_bullish else bearish_hex

            # Render wick as individual line segment (no batching to avoid connecting lines between candles)
            commands.append(DrawCommand(
                layer=Layer.SERIES,
                tag=f"wick_{i}",
                item_type="line",
                coords=(x, y_high, x, y_low),
                options={"fill": hex_color, "width": wick_w},
                z_index=0
            ))
            
            # Collect body data for batch rendering
            bars_data.append((i, x - half_w, body_top, x + half_w, body_top + body_h, hex_color))

        # Render candle bodies (still individual rectangles for now)
        for i, x0, y0, x1, y1, color in bars_data:
            commands.append(DrawCommand(
                layer=Layer.SERIES,
                tag=f"body_{i}",
                item_type="rectangle",
                coords=(x0, y0, x1, y1),
                options={"fill": color, "outline": color, "width": 1},
                z_index=i
            ))

        self._pipeline.add_commands(commands)
        self._pipeline.schedule_layer(Layer.SERIES)

    def _render_line(self, start_idx: int, end_idx: int, viewport: Optional[Viewport]) -> None:
        """Render line chart series."""
        vp = viewport or self._coord.viewport
        points = []
        for i in range(start_idx, end_idx):
            x = self._coord.index_to_x(i)
            y = self._coord.price_to_y(self._data[i].close, vp)
            points.extend([x, y])

        if len(points) >= 4:
            self._pipeline.add_command(DrawCommand(
                layer=Layer.SERIES,
                tag="line_series",
                item_type="line",
                coords=tuple(points),
                options={
                    "fill": self._style.line_color.to_hex(),
                    "width": self._style.line_width,
                },
                z_index=0
            ))
            self._pipeline.schedule_layer(Layer.SERIES)

    def _render_area(self, start_idx: int, end_idx: int, viewport: Optional[Viewport]) -> None:
        """Render area chart series with filled polygon."""
        vp = viewport or self._coord.viewport
        points = []
        for i in range(start_idx, end_idx):
            x = self._coord.index_to_x(i)
            y = self._coord.price_to_y(self._data[i].close, vp)
            points.extend([x, y])

        if len(points) >= 4:
            # Closed area polygon
            poly_points = list(points) + [points[-2], vp.bottom, points[0], vp.bottom]
            self._pipeline.add_command(DrawCommand(
                layer=Layer.SERIES,
                tag="area_fill",
                item_type="polygon",
                coords=tuple(poly_points),
                options={
                    "fill": self._style.area_color.to_hex(),
                    "outline": "",
                    "stipple": self._style.area_stipple,
                },
                z_index=0
            ))
            # Top boundary line
            self._pipeline.add_command(DrawCommand(
                layer=Layer.SERIES,
                tag="area_line",
                item_type="line",
                coords=tuple(points),
                options={
                    "fill": self._style.line_color.to_hex(),
                    "width": self._style.line_width,
                },
                z_index=1
            ))
            self._pipeline.schedule_layer(Layer.SERIES)

    def _render_ohlc(self, start_idx: int, end_idx: int, viewport: Optional[Viewport], step: int = 1) -> None:
        vp = viewport or self._coord.viewport
        commands = []
        half_w = max(2.0, self._coord.get_bar_width() * 0.35)
        for i in range(start_idx, end_idx, max(1, step)):
            bar = self._data[i]
            x = self._coord.index_to_x(i)
            if x + half_w < vp.left or x - half_w > vp.right:
                continue
            color = self._style.bullish_color if bar.close >= bar.open else self._style.bearish_color
            commands.extend([
                DrawCommand(Layer.SERIES, f"ohlc_v_{i}", "line",
                            (x, self._coord.price_to_y(bar.high, vp), x, self._coord.price_to_y(bar.low, vp)),
                            {"fill": color.to_hex(), "width": 1.0}, i),
                DrawCommand(Layer.SERIES, f"ohlc_o_{i}", "line",
                            (x - half_w, self._coord.price_to_y(bar.open, vp), x, self._coord.price_to_y(bar.open, vp)),
                            {"fill": color.to_hex(), "width": 1.0}, i),
                DrawCommand(Layer.SERIES, f"ohlc_c_{i}", "line",
                            (x, self._coord.price_to_y(bar.close, vp), x + half_w, self._coord.price_to_y(bar.close, vp)),
                            {"fill": color.to_hex(), "width": 1.0}, i),
            ])
        self._pipeline.add_commands(commands)
        self._pipeline.schedule_layer(Layer.SERIES)

    def _render_baseline(self, start_idx: int, end_idx: int, viewport: Optional[Viewport], step: int = 1) -> None:
        vp = viewport or self._coord.viewport
        baseline = self._data[0].close if self._data else 0.0
        points = []
        for i in range(start_idx, end_idx, max(1, step)):
            x = self._coord.index_to_x(i)
            y = self._coord.price_to_y(self._data[i].close, vp)
            points.extend([x, y])
        if len(points) >= 4:
            self._pipeline.add_command(DrawCommand(Layer.SERIES, "baseline_series", "line", tuple(points), {"fill": self._style.line_color.to_hex(), "width": self._style.line_width}, 0))
            y0 = self._coord.price_to_y(baseline, vp)
            self._pipeline.add_command(DrawCommand(Layer.SERIES, "baseline_level", "line", (vp.left, y0, vp.right, y0), {"fill": self._style.bearish_color.to_hex(), "width": 1.0, "dash": (4, 4)}, -1))
            self._pipeline.schedule_layer(Layer.SERIES)

    def _render_step(self, start_idx: int, end_idx: int, viewport: Optional[Viewport], step: int = 1) -> None:
        vp = viewport or self._coord.viewport
        indices = list(range(start_idx, end_idx, max(1, step)))
        points = []
        for pos, i in enumerate(indices):
            x = self._coord.index_to_x(i)
            y = self._coord.price_to_y(self._data[i].close, vp)
            if pos == 0:
                points.extend([x, y])
            else:
                prev_x = self._coord.index_to_x(indices[pos - 1])
                points.extend([x, self._coord.price_to_y(self._data[indices[pos - 1]].close, vp), x, y])
        if len(points) >= 4:
            self._pipeline.add_command(DrawCommand(Layer.SERIES, "step_series", "line", tuple(points), {"fill": self._style.line_color.to_hex(), "width": self._style.line_width}, 0))
            self._pipeline.schedule_layer(Layer.SERIES)

    def _render_heikin_ashi(self, start_idx: int, end_idx: int, viewport: Optional[Viewport], step: int = 1) -> None:
        vp = viewport or self._coord.viewport
        commands = []
        ha_open = None
        prev_ha_close = None
        half_w = self._coord.get_bar_width() / 2.0
        for i, bar in enumerate(self._data[:end_idx]):
            ha_close = (bar.open + bar.high + bar.low + bar.close) / 4.0
            if i == 0:
                ha_open = (bar.open + bar.close) / 2.0
            else:
                ha_open = (ha_open + prev_ha_close) / 2.0
            ha_high = max(bar.high, ha_open, ha_close)
            ha_low = min(bar.low, ha_open, ha_close)
            prev_ha_close = ha_close
            if i < start_idx or ((i - start_idx) % max(1, step)) != 0:
                continue
            x = self._coord.index_to_x(i)
            if x + half_w < vp.left or x - half_w > vp.right:
                continue
            y_high = self._coord.price_to_y(ha_high, vp)
            y_low = self._coord.price_to_y(ha_low, vp)
            y_open = self._coord.price_to_y(ha_open, vp)
            y_close = self._coord.price_to_y(ha_close, vp)
            top, bottom = min(y_open, y_close), max(y_open, y_close)
            color = self._style.bullish_color if ha_close >= ha_open else self._style.bearish_color
            commands.append(DrawCommand(Layer.SERIES, f"ha_wick_{i}", "line", (x, y_high, x, y_low), {"fill": color.to_hex(), "width": self._coord.get_wick_width()}, 0))
            commands.append(DrawCommand(Layer.SERIES, f"ha_body_{i}", "rectangle", (x-half_w, top, x+half_w, max(top+1.0, bottom)), {"fill": color.to_hex(), "outline": color.to_hex(), "width": 1}, i))
        self._pipeline.add_commands(commands)
        self._pipeline.schedule_layer(Layer.SERIES)

    def _render_histogram(self, start_idx: int, end_idx: int, viewport: Optional[Viewport]) -> None:
        """Render volume-style histogram bars."""
        vp = viewport or self._coord.viewport
        commands = []
        bar_w = self._coord.get_bar_width()
        half_w = bar_w / 2.0

        for i in range(start_idx, end_idx):
            bar = self._data[i]
            x = self._coord.index_to_x(i)
            if x + half_w < vp.left or x - half_w > vp.right:
                continue

            y = self._coord.price_to_y(bar.close, vp)
            color = self._style.bullish_color if bar.close >= bar.open else self._style.bearish_color

            commands.append(DrawCommand(
                layer=Layer.SERIES,
                tag=f"hist_{i}",
                item_type="rectangle",
                coords=(x - half_w, y, x + half_w, vp.bottom),
                options={"fill": color.to_hex(), "outline": ""},
                z_index=i
            ))

        self._pipeline.add_commands(commands)
        self._pipeline.schedule_layer(Layer.SERIES)
