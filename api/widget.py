"""Chart Widget - Primary public API entry point for FinChart.

Subclass of tk.Frame that orchestrates all subsystems:
- Data Store
- Event Bus
- Coordinate Engine
- Layout Engine
- Rendering Pipeline (Series, Grid, Crosshair, Indicators, Drawings)
- Interaction Controller
"""
from __future__ import annotations

import tkinter as tk
from typing import List, Optional, Callable, Dict, Any, Union
import json
import os

from ..core.types import OHLCV, Viewport, ChartType, Color
from ..core.events import EventBus, EventType, Event
from ..core.store import DataStore
from ..coordinates.engine import CoordinateEngine
from ..layout.engine import LayoutEngine
from ..rendering.pipeline import RenderingPipeline, Layer
from ..rendering.series import SeriesRenderer, SeriesStyle
from ..rendering.grid import GridRenderer, GridStyle
from ..rendering.crosshair import CrosshairRenderer, CrosshairStyle, PaneBadge
from ..interaction.controller import InteractionController
from ..indicators.base import Indicator
from ..drawing.tools import DrawingTool, DrawingState, MarketProfileOverlay
from ..themes.style import Theme, DarkTheme, LightTheme


class ChartWidget(tk.Frame):
    """Professional pure-Python financial chart widget.
    
    Usage:
        import tkinter as tk
        from finchart import ChartWidget, OHLCV
        
        root = tk.Tk()
        chart = ChartWidget(root, width=800, height=600)
        chart.pack(fill="both", expand=True)
        chart.set_data(bars)
        root.mainloop()
    """

    def __init__(
        self,
        parent: tk.Widget,
        width: int = 800,
        height: int = 600,
        theme: Optional[Theme] = None,
        callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        **kwargs
    ) -> None:
        super().__init__(parent, **kwargs)

        self._explicit_width = width
        self._explicit_height = height
        self._callback = callback
        self._theme = theme or DarkTheme()

        # Core Subsystems
        self._event_bus = EventBus()
        self._data_store = DataStore(self._event_bus)
        self._coord_engine = CoordinateEngine(self._event_bus)
        self._layout_engine = LayoutEngine()

        # Canvas UI setup
        self.configure(highlightthickness=0)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._canvas = tk.Canvas(
            self,
            width=width,
            height=height,
            bg=self._theme.background.to_hex(),
            highlightthickness=0,
            borderwidth=0
        )
        self._canvas.grid(row=0, column=0, sticky="nsew")

        # Rendering Pipeline
        self._pipeline = RenderingPipeline(self._canvas, self._event_bus)

        # Specialized Renderers
        self._series_renderer = SeriesRenderer(
            self._pipeline,
            self._coord_engine,
            SeriesStyle(
                bullish_color=self._theme.bullish,
                bearish_color=self._theme.bearish,
                wick_color=self._theme.wick
            )
        )
        self._grid_renderer = GridRenderer(
            self._pipeline,
            self._coord_engine,
            GridStyle(
                grid_color=self._theme.grid_lines,
                axis_text_color=self._theme.axis_text,
                axis_bg_color=self._theme.axis_bg,
                axis_border_color=self._theme.grid_lines
            )
        )
        self._crosshair_renderer = CrosshairRenderer(
            self._pipeline,
            self._coord_engine,
            CrosshairStyle(
                line_color=self._theme.crosshair,
                badge_bg=self._theme.card_bg
            )
        )

        # Interaction Controller
        self._interaction_controller = InteractionController(
            self._canvas,
            self._coord_engine,
            self._event_bus
        )

        # Indicators & Drawing tools
        self._indicators: List[Indicator] = []
        self._drawings: Dict[str, DrawingState] = {}
        self._selected_drawing_tags: set[str] = set()
        self._market_profile = MarketProfileOverlay()

        # Configuration Flags
        self._auto_scale = True
        self._right_offset_bars = 5

        # Bind Internal Event Handlers
        self._bind_internal_events()

        # Apply initial layout
        self._update_viewport()

    # ==================== Public API ====================

    def set_data(self, data: Union[List[OHLCV], Any]) -> None:
        """Set or replace data bars."""
        self._data_store.set_data(data)
        self._series_renderer.set_data(self._data_store.data)
        self._crosshair_renderer.set_data(self._data_store.data)
        self._update_indicators()

        # Auto-fit data when widget is mapped
        self.after_idle(self.fit_content)

    def append(self, bar: Union[OHLCV, dict]) -> None:
        """Append a new bar to dataset."""
        self._data_store.append(bar)
        self._series_renderer.set_data(self._data_store.data)
        self._crosshair_renderer.set_data(self._data_store.data)
        self._update_indicators()

        # Auto-scroll: pan to keep the new bar visible without changing zoom
        self._request_render()

    def update_last(self, bar: Union[OHLCV, dict]) -> None:
        """Update last bar in real-time streaming mode."""
        self._data_store.update_last(bar)
        self._series_renderer.set_data(self._data_store.data)
        self._crosshair_renderer.set_data(self._data_store.data)
        self._update_indicators()
        self._update_price_scale()
        self._request_render()

    def add_indicator(self, indicator: Indicator, pane: str = "candlestick") -> Indicator:
        """Add a technical indicator to specified pane."""
        # Use the indicator's pane attribute if set, otherwise fall back to passed pane
        if hasattr(indicator, 'pane') and indicator.pane:
            active_pane = indicator.pane
        else:
            active_pane = pane
        
        # Create subplot pane for non-candlestick indicators if not already present
        if active_pane != "candlestick" and active_pane not in self._layout_engine.panes:
            self._layout_engine.add_pane(active_pane, weight=1.0)
            self._update_viewport()
        
        self._indicators.append(indicator)
        if not self._data_store.is_empty:
            indicator.update(self._data_store.data)
        self._update_price_scale()
        self._pipeline.force_full_redraw()
        self._request_render()
        return indicator

    def remove_indicator(self, indicator: Indicator) -> None:
        """Remove an indicator from chart."""
        if indicator in self._indicators:
            self._indicators.remove(indicator)
            # Clean up empty subplot panes
            pane = indicator.pane if hasattr(indicator, 'pane') else "candlestick"
            if pane != "candlestick" and pane in self._layout_engine.panes:
                # Check if any remaining indicators use this pane
                pane_still_used = any(ind.pane == pane for ind in self._indicators)
                if not pane_still_used:
                    self._layout_engine.remove_pane(pane)
                    self._update_viewport()
            self._pipeline.force_full_redraw()
            self._request_render()

    def clear_indicators(self) -> None:
        """Remove all indicators."""
        self._indicators.clear()
        self._layout_engine.reset()
        self._update_viewport()
        self._pipeline.force_full_redraw()
        self._request_render()

    def set_chart_type(self, chart_type: ChartType) -> None:
        """Change chart type (Candlestick, Line, Area, Histogram)."""
        self._series_renderer.chart_type = chart_type
        self._pipeline.force_full_redraw()
        self._request_render()

    def set_theme(self, theme: Theme) -> None:
        """Apply color theme."""
        self._theme = theme
        self._canvas.configure(bg=theme.background.to_hex())
        self._grid_renderer.style.grid_color = theme.grid_lines
        self._grid_renderer.style.axis_text_color = theme.axis_text
        self._grid_renderer.style.axis_bg_color = theme.axis_bg
        self._series_renderer.style.bullish_color = theme.bullish
        self._series_renderer.style.bearish_color = theme.bearish
        self._series_renderer.style.wick_color = theme.wick
        # Update crosshair colours so badge text stays visible on both themes
        self._crosshair_renderer._style.line_color = theme.crosshair
        self._crosshair_renderer._style.badge_bg = theme.card_bg
        self._crosshair_renderer._style.badge_fg = theme.axis_text
        self._pipeline.force_full_redraw()
        self._request_render()

    def fit_content(self) -> None:
        """Fit all bars into viewport."""
        if self._data_store.is_empty:
            return

        # Ensure viewport is updated
        self._update_viewport()
        
        chart_vp = self._grid_renderer.get_chart_viewport()
        if chart_vp.width <= 0:
            # Retry after a delay if viewport not ready
            self.after(50, self.fit_content)
            return

        total_bars = self._data_store.count + self._right_offset_bars
        bar_spacing = chart_vp.width / max(1.0, total_bars)

        self._coord_engine.time_scale.bar_spacing = bar_spacing
        self._coord_engine.time_scale.offset = 0.0

        self._update_visible_range()
        self._update_price_scale()
        self._pipeline.force_full_redraw()
        self._request_render()

    def zoom(self, factor: float) -> None:
        """Zoom time scale by factor centered at canvas middle."""
        chart_vp = self._grid_renderer.get_chart_viewport()
        self._coord_engine.zoom(factor, anchor_x=chart_vp.center_x)
        self._update_visible_range()
        self._update_price_scale()
        self._request_render()

    def pan(self, delta_bars: float) -> None:
        """Pan chart view by delta_bars units."""
        delta_x = delta_bars * self._coord_engine.time_scale.bar_spacing
        self._coord_engine.pan(delta_x)
        self._update_visible_range()
        self._update_price_scale()
        self._request_render()

    # --- Session Persistence ---
    def save_session(self, filepath: str) -> None:
        """Serialize current drawings and indicators to JSON session file."""
        state = {
            "version": "1.0",
            "drawings": {
                tag: {
                    "tool_type": d.tool_type,
                    "points": d.points,
                    "color": d.color.to_hex(),
                    "width": d.width
                }
                for tag, d in self._drawings.items()
            }
        }
        with open(filepath, "w") as f:
            json.dump(state, f, indent=2)

    def load_session(self, filepath: str) -> None:
        """Load serialized session state from JSON file."""
        if not os.path.exists(filepath):
            return
        try:
            with open(filepath, "r") as f:
                state = json.load(f)
            self._drawings = {}
            for tag, d_data in state.get("drawings", {}).items():
                self._drawings[tag] = DrawingState(
                    tag=tag,
                    tool_type=d_data.get("tool_type", "line"),
                    points=d_data.get("points", []),
                    color=Color.from_hex(d_data.get("color", "#FFA500")),
                    width=d_data.get("width", 2.0)
                )
            self._request_render()
        except Exception:
            pass

    # ==================== Internal Subsystem Routing ====================

    def _bind_internal_events(self) -> None:
        """Bind internal event bus routing handlers."""
        self.bind("<Configure>", self._on_resize)

        eb = self._event_bus
        eb.subscribe(EventType.MOUSE_MOVE, self._on_mouse_move_event)
        eb.subscribe(EventType.SCALE_CHANGED, self._on_scale_changed_event)
        eb.subscribe(EventType.DATA_CHANGED, self._on_data_changed_event)

    def _on_resize(self, event: tk.Event) -> None:
        """Handle widget resize event."""
        self._update_viewport()
        self._update_visible_range()
        self._update_price_scale()
        self._pipeline.force_full_redraw()
        self._request_render()

    def _on_mouse_move_event(self, event: Event) -> None:
        """Route mouse movement to crosshair and hover callback."""
        x = event.data.get("x", -1.0)
        y = event.data.get("y", -1.0)
        chart_vp = self._grid_renderer.get_chart_viewport()

        if event.data.get("leave") or x < 0 or y < 0:
            self._crosshair_renderer.on_mouse_leave()
            return

        self._crosshair_renderer.on_mouse_move(x, y, chart_vp)

        # Trigger optional user callback
        if self._callback and self._crosshair_renderer.snapped_bar:
            bar = self._crosshair_renderer.snapped_bar
            self._callback("hover", {
                "x": event.data.get("x"),
                "y": event.data.get("y"),
                "index": self._crosshair_renderer.snapped_index,
                "bar": bar
            })

        # Compute per-pane badge info (price for main pane, indicator
        # values for subplot panes) and pass to crosshair before rendering.
        self._update_crosshair_badges()

        # Must buffer draw commands before scheduling the layer — otherwise
        # incremental render clears CROSSHAIR with an empty command list.
        self._pipeline.clear_layer_commands(Layer.CROSSHAIR)
        self._crosshair_renderer.render(chart_vp)
        self._pipeline.schedule_layer(Layer.CROSSHAIR)

    def _on_scale_changed_event(self, event: Event) -> None:
        """Route scale change events to visible range re-calculation."""
        self._update_visible_range()
        self._update_price_scale()
        self._request_render()

    def _on_data_changed_event(self, event: Event) -> None:
        """Route data change events to viewport updates."""
        action = event.data.get("action", "set")
        self._update_visible_range()
        self._update_price_scale()
        # Only request render for "set" actions; "append" and "update_last"
        # are handled by their respective methods to avoid double rendering
        if action == "set":
            self._request_render()

    def _update_viewport(self) -> None:
        """Synchronize coordinate engine viewport with canvas dimensions."""
        w = self._canvas.winfo_width()
        h = self._canvas.winfo_height()

        if w <= 1: w = self._explicit_width
        if h <= 1: h = self._explicit_height

        self._coord_engine.set_viewport(Viewport(x=0.0, y=0.0, width=float(w), height=float(h)))
        # Calculate layout and store pane viewports in coord engine
        pane_viewports = self._layout_engine.calculate_layout(self._coord_engine.viewport)
        for pane_name, pane_vp in pane_viewports.items():
            self._coord_engine.set_pane_viewport(pane_name, pane_vp)

    def _update_visible_range(self) -> None:
        """Calculate visible bar index window."""
        if self._data_store.is_empty:
            return

        chart_vp = self._grid_renderer.get_chart_viewport()
        first_idx = self._coord_engine.x_to_index(chart_vp.left)
        last_idx = self._coord_engine.x_to_index(chart_vp.right)

        start_idx = max(0, int(first_idx) - 1)
        end_idx = min(self._data_store.count, int(last_idx) + 2)

        self._coord_engine.set_visible_range(start_idx, end_idx, self._data_store.count)

    def _update_price_scale(self) -> None:
        """Auto-scale price axis based on visible data slice for each pane."""
        if not self._auto_scale or self._data_store.is_empty:
            return

        vr = self._coord_engine.visible_range
        total_data_count = self._data_store.count

        # Use full data range if visible range is empty (initial state)
        if vr.count <= 0:
            start_idx = 0
            end_idx = total_data_count
        else:
            start_idx = vr.start_index
            end_idx = vr.end_index

        # Update main candlestick pane price scale
        min_p, max_p = self._data_store.get_price_range(start_idx, end_idx)

        # Expand price scale to cover overlay indicators (SMA, EMA, BB)
        for ind in self._indicators:
            if ind.pane != "candlestick":
                continue  # Non-candlestick indicators have their own pane
            if ind._last_result:
                for key, vals in ind._last_result.values.items():
                    for i in range(start_idx, min(end_idx, len(vals))):
                        v = vals[i]
                        if v is not None:
                            min_p = min(min_p, v)
                            max_p = max(max_p, v)

        self._coord_engine.set_price_range(min_p, max_p, emit_event=False)

        # Update per-pane price scales for non-candlestick indicators
        for ind in self._indicators:
            if ind.pane == "candlestick" or not ind._last_result:
                continue
            p_min = float('inf')
            p_max = float('-inf')
            has_data = False
            for key, vals in ind._last_result.values.items():
                for i in range(start_idx, min(end_idx, len(vals))):
                    v = vals[i]
                    if v is not None:
                        p_min = min(p_min, v)
                        p_max = max(p_max, v)
                        has_data = True
            if has_data and p_max > p_min:
                # Volume pane should always start from zero so bars grow
                # upward from the bottom of the pane.
                if ind.pane == "volume":
                    p_min = 0.0
                self._coord_engine.set_pane_price_scale(ind.pane, p_min, p_max, emit_event=False)

    def _update_indicators(self) -> None:
        """Recalculate indicator values for current data."""
        if self._data_store.is_empty:
            return
        data = self._data_store.data
        for ind in self._indicators:
            ind.update(data)

    def _render_indicators(self, chart_vp: Viewport, pane: str = "candlestick") -> None:
        """Render commands for active indicators in the given pane."""
        vr = self._coord_engine.visible_range
        for ind in self._indicators:
            if ind.pane != pane:
                continue
            pane_vp = chart_vp
            if ind.pane != "candlestick":
                pane_vp = self._coord_engine.get_pane_viewport(ind.pane)
            cmds = ind.render_commands(self._coord_engine, vr.start_index, vr.end_index, pane_vp)
            self._pipeline.add_commands(cmds)
        self._pipeline.schedule_layer(Layer.INDICATORS)

    def _request_render(self) -> None:
        """Execute unified render pass across all renderers."""
        # Drop stale commands so incremental layer passes only see this frame.
        self._pipeline.clear_commands()

        # Render main candlestick pane
        chart_vp = self._grid_renderer.get_chart_viewport()
        self._series_renderer.render(chart_vp)
        self._grid_renderer.render(self._data_store.data)
        self._render_indicators(chart_vp, "candlestick")

        # Render subplot panes (RSI, MACD, etc.)
        for pane_name in self._layout_engine.panes:
            if pane_name == "candlestick":
                continue
            pane_vp = self._coord_engine.get_pane_viewport(pane_name)
            if pane_vp.height > 0:
                self._grid_renderer.render(self._data_store.data, pane_name=pane_name)
                self._render_indicators(pane_vp, pane_name)

        # Crosshair rendered last (overlay on top of everything)
        self._update_crosshair_badges()
        self._crosshair_renderer.render(chart_vp)
        self._pipeline.schedule_layer(Layer.CROSSHAIR)
        # Incremental layer update + pool option reset keeps axes stable while
        # pan/stream rebuild series/grid/indicators without full canvas wipe.
        self._pipeline.schedule_render(full_redraw=False)

    # ==================== Crosshair Badge Computation ====================

    def _update_crosshair_badges(self) -> None:
        """Compute per-pane badge info and push it to the crosshair renderer.

        For the main candlestick pane the badge shows the price at the
        cursor's Y position.  For each subplot pane (RSI, MACD, Volume, …)
        the badge shows the indicator's primary value at the snapped bar
        index, positioned at that value's Y coordinate.

        This mirrors how TradingView lightweight-charts renders a price
        label on the right axis of every pane.
        """
        cr = self._crosshair_renderer
        if not cr.is_visible or cr.snapped_index < 0:
            cr.set_pane_badges([])
            return

        snapped_idx = cr.snapped_index
        chart_vp = self._grid_renderer.get_chart_viewport()
        badges: List[PaneBadge] = []

        # --- Main candlestick pane badge (price at cursor Y) ---
        price_val = self._coord_engine.y_to_price(cr.mouse_y, chart_vp)
        badges.append(PaneBadge(
            badge_y=cr.mouse_y,
            value_text=self._format_price_value(price_val),
            pane_top=chart_vp.top,
            pane_bottom=chart_vp.bottom,
        ))

        # --- Subplot pane badges (indicator value at snapped bar) ---
        for pane_name in self._layout_engine.panes:
            if pane_name == "candlestick":
                continue
            pane_vp = self._coord_engine.get_pane_viewport(pane_name)
            if pane_vp.height <= 0:
                continue

            # Find the first indicator in this pane that has a result
            for ind in self._indicators:
                if ind.pane != pane_name or not ind._last_result:
                    continue
                # Use the first value-list as the "primary" series
                for key, vals in ind._last_result.values.items():
                    if snapped_idx < len(vals) and vals[snapped_idx] is not None:
                        val = vals[snapped_idx]
                        y = self._coord_engine.price_to_y(val, pane_vp, pane=pane_name)
                        badges.append(PaneBadge(
                            badge_y=y,
                            value_text=self._format_indicator_value(val, pane_name),
                            pane_top=pane_vp.top,
                            pane_bottom=pane_vp.bottom,
                        ))
                        break  # Only first value-list per indicator
                break  # Only first indicator per pane

        cr.set_pane_badges(badges)

    @staticmethod
    def _format_price_value(price: float) -> str:
        """Format a price for the crosshair badge."""
        ap = abs(price)
        if ap >= 10000:
            return f"{price:,.0f}"
        if ap >= 100:
            return f"{price:,.2f}"
        if ap >= 1:
            return f"{price:,.4f}"
        return f"{price:.6f}"

    @staticmethod
    def _format_indicator_value(val: float, pane_name: str) -> str:
        """Format an indicator value for the crosshair badge.

        Volume values are shown in M/B shorthand; other indicators use
        a compact numeric format.
        """
        if pane_name == "volume":
            if abs(val) >= 1e9:
                return f"{val/1e9:.2f}B"
            if abs(val) >= 1e6:
                return f"{val/1e6:.2f}M"
            if abs(val) >= 1e3:
                return f"{val/1e3:.2f}K"
            return f"{val:.2f}"
        # RSI, MACD, etc.
        if abs(val) >= 1000:
            return f"{val:,.0f}"
        if abs(val) >= 1:
            return f"{val:.2f}"
        return f"{val:.4f}"
