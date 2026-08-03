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
from typing import List, Optional, Callable, Dict, Any, Union, Tuple
import json
import math
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
from ..interaction.selection_manager import SelectionManager
from ..interaction.tool_state import ToolContext, ToolState
from ..drawing.tools import TrendLine, HorizontalLine, VerticalLine, AngleLine, Rectangle, MarketProfileOverlay, LongShort
from ..drawing.base import DrawingState
from ..themes.style import Theme, DarkTheme, LightTheme
from ..session.manager import SessionManager


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

        # Clipboard for copy/paste drawings
        self._clipboard_drawing: Optional[DrawingState] = None
        self._copy_buffer: Optional[List[DrawingState]] = None

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
        self._interaction_controller.set_widget(self)

        # Drawing tools
        self._drawings: Dict[str, DrawingState] = {}
        self._drawing_tools: Dict[str, Any] = {}  # id -> DrawingTool instance
        self._selected_drawing_tags: set[str] = set()
        self._market_profile = MarketProfileOverlay()

        # Drawing tool state management
        self._selection_manager = SelectionManager(self._event_bus)
        self._tool_context: Optional[ToolContext] = None

        # Session Manager for per-symbol indicator isolation
        self._session_manager = SessionManager()
        self._session_manager.set_chart_widget(self)

        # Universal trigger callback
        self._trigger: Optional[Callable[[str, str, str, Dict[str, Any]], None]] = None

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

        # Auto-fit data when widget is mapped
        self.after_idle(self.fit_content)

    def append(self, bar: Union[OHLCV, dict]) -> None:
        """Append a new bar to dataset."""
        self._data_store.append(bar)
        self._series_renderer.set_data(self._data_store.data)
        self._crosshair_renderer.set_data(self._data_store.data)

        # Auto-scroll: pan to keep the new bar visible without changing zoom
        self._request_render()

    def update_last(self, bar: Union[OHLCV, dict]) -> None:
        """Update last bar in real-time streaming mode."""
        self._data_store.update_last(bar)
        self._series_renderer.set_data(self._data_store.data)
        self._crosshair_renderer.set_data(self._data_store.data)
        self._update_price_scale()
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

    def set_trigger(self, trigger: Callable[[str, str, str, Dict[str, Any]], None]) -> None:
        """Set a universal trigger callback for all mouse/keyboard events."""
        self._trigger = trigger

    def set_session_manager(self, session_manager: SessionManager) -> None:
        """Set the session manager for per-symbol indicator management.
        
        Args:
            session_manager: SessionManager instance
        """
        self._session_manager = session_manager
        self._session_manager.set_chart_widget(self)

    def set_context(self, symbol: str, timeframe: str, data: Optional[List[OHLCV]] = None) -> None:
        """Switch to a new symbol/timeframe context using SessionManager.
        
        Args:
            symbol: Symbol name (e.g., "AAPL")
            timeframe: Timeframe string (e.g., "1m", "1h", "1d")
            data: OHLCV data for the symbol (optional)
        """
        self._session_manager.set_context(symbol, timeframe, data)

    def refresh(self) -> None:
        """Trigger full rebuild from current session state."""
        self._session_manager._rebuild_indicators()
        self._pipeline.force_full_redraw()
        self._request_render()

    def _resolve_pane_and_shape(self, x: float, y: float) -> Tuple[str, str]:
        """Return (pane_name, shape_id_or_name) at pixel (x, y)."""
        # 1) Resolve pane by Y
        plot = "candlestick"
        for pane_name in self._layout_engine.panes:
            vp = self._coord_engine.get_pane_viewport(pane_name)
            if vp.top <= y <= vp.bottom:
                plot = pane_name
                break

        # 2) Resolve shape by hit-test (drawings first, top-most wins)
        shape = ""
        chart_vp = self._grid_renderer.get_chart_viewport()
        for sid, tool in reversed(list(self._drawing_tools.items())):
            pane_vp = chart_vp if tool.state.pane_name == "candlestick" else self._coord_engine.get_pane_viewport(tool.state.pane_name)
            if tool.hit_test(x, y, self._coord_engine, pane_vp):
                shape = f"{tool.state.tool_type}_{sid}"
                break
        else:
            # 3) Check for future indicator hit testing
            pass

        return plot, shape

    def _fire_trigger(self, event_type: str, x: float = -1, y: float = -1, **extra) -> None:
        if not self._trigger:
            return
        plot, shape = self._resolve_pane_and_shape(x, y)
        data = {"x": x, "y": y, **extra}
        self._trigger(plot, shape, event_type, data)

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
            self._drawing_tools = {}
            for tag, d_data in state.get("drawings", {}).items():
                drawing_state = DrawingState.from_dict(d_data)
                self._drawings[drawing_state.id] = drawing_state
                tool = self._create_tool(drawing_state)
                self._drawing_tools[drawing_state.id] = tool
            self._request_render()
        except Exception:
            pass

    # --- Drawing Tool Public API ---

    def add_drawing(self, state: DrawingState) -> Any:
        """Add a finalized drawing shape to the chart."""
        tool = self._create_tool(state)
        self._drawing_tools[state.id] = tool
        self._drawings[state.id] = state
        self._pipeline.force_full_redraw()
        self._request_render()
        return tool

    def remove_drawing(self, shape_id: str) -> None:
        """Remove a drawing by ID."""
        if shape_id in self._drawing_tools:
            del self._drawing_tools[shape_id]
            del self._drawings[shape_id]
            # Properly deselect via the manager's public API
            if self._selection_manager.is_selected(shape_id):
                self._selection_manager.select(shape_id, toggle=True, multi=True)
            self._pipeline.force_full_redraw()
            self._request_render()

    def clear_drawings(self) -> None:
        """Remove all drawings."""
        self._drawing_tools.clear()
        self._drawings.clear()
        self._selection_manager.unselect()
        self._pipeline.force_full_redraw()
        self._request_render()

    def delete_selected_drawings(self) -> None:
        """Remove all currently selected drawings."""
        to_delete = list(self._selection_manager.selected_ids)
        for sid in to_delete:
            self.remove_drawing(sid)

    def select_all_drawings(self) -> None:
        """Select every drawing on the chart."""
        ids = list(self._drawing_tools.keys())
        if ids:
            self._selection_manager.select_all(ids)

    def set_active_tool(self, tool_type: str, position_type: str = "") -> None:
        """Activate a drawing tool for creation mode.

        Args:
            tool_type: The type of drawing tool ("trendline", "hline", etc.)
            position_type: For longshort tool, specify "long" or "short"
        """
        self._tool_context = ToolContext(tool_type=tool_type, position_type=position_type, state=ToolState.WAIT_FIRST_CLICK)
        # Change cursor to crosshair
        self._canvas.config(cursor="crosshair")

    def deactivate_tool(self) -> None:
        """Cancel active tool and return to normal mode."""
        self._tool_context = None
        self._canvas.config(cursor="")
        self._pipeline.force_full_redraw()
        self._request_render()

    # --- Internal Drawing Tool Helpers ---

    def _create_tool(self, state: DrawingState) -> Any:
        mapping = {
            "trendline": TrendLine,
            "hline": HorizontalLine,
            "vline": VerticalLine,
            "angleline": AngleLine,
            "rectangle": Rectangle,
            "longshort": LongShort,
        }
        cls = mapping.get(state.tool_type, TrendLine)
        tool = cls(state)
        # For LongShort, ensure position type is set from context if available
        if state.tool_type == "longshort" and self._tool_context and self._tool_context.position_type:
            if hasattr(tool, '_position_type'):
                tool._position_type = self._tool_context.position_type
        return tool

    def copy_selected(self) -> None:
        """Copy the currently selected drawing to clipboard."""
        if self._selection_manager.selected_id:
            selected_id = self._selection_manager.selected_id
            if selected_id in self._drawings:
                import copy
                self._clipboard_drawing = copy.deepcopy(self._drawings[selected_id])

    def copy_selected_drawings(self) -> List[DrawingState]:
        """Copy all selected drawings."""
        import copy
        return [copy.deepcopy(self._drawings[sid]) 
                for sid in self._selection_manager.selected_ids 
                if sid in self._drawings]

    def paste_drawings(self, states: List[DrawingState]) -> None:
        """Paste multiple drawings with incremental offsets."""
        import copy
        import uuid
        for i, src in enumerate(states):
            new_state = copy.deepcopy(src)
            new_state.id = uuid.uuid4().hex
            # Stagger offset so multiple pastes don't overlap perfectly
            offset = 10.0 + (i * 5.0)
            new_state.points = [
                (idx + offset if idx is not None else None, price) 
                for idx, price in new_state.points
            ]
            self.add_drawing(new_state)

    def update_live_price(self, price: Optional[float]) -> None:
        """Update live price for LongShort position PnL calculation."""
        for tool in self._drawing_tools.values():
            if hasattr(tool, 'update_live_price'):
                tool.update_live_price(price)
        self._request_render()

    # ==================== Internal Subsystem Routing ====================

    def _bind_internal_events(self) -> None:
        """Bind internal event bus routing handlers."""
        self.bind("<Configure>", self._on_resize)

        eb = self._event_bus
        eb.subscribe(EventType.MOUSE_MOVE, self._on_mouse_move_event)
        eb.subscribe(EventType.SCALE_CHANGED, self._on_scale_changed_event)
        eb.subscribe(EventType.DATA_CHANGED, self._on_data_changed_event)
        eb.subscribe(EventType.SELECTION_CHANGED, self._on_selection_changed)
        eb.subscribe(EventType.HOVER_CHANGED, self._on_hover_changed)
        # NEW subscriptions
        eb.subscribe(EventType.MOUSE_DOWN, self._on_mouse_down_event)
        eb.subscribe(EventType.MOUSE_UP, self._on_mouse_up_event)
        eb.subscribe(EventType.MOUSE_WHEEL, self._on_mouse_wheel_event)
        eb.subscribe(EventType.KEY_DOWN, self._on_key_down_event)

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
        dragging = event.data.get("dragging", False)
        chart_vp = self._grid_renderer.get_chart_viewport()

        if event.data.get("leave") or x < 0 or y < 0:
            self._crosshair_renderer.on_mouse_leave()
            return

        self._crosshair_renderer.on_mouse_move(x, y, chart_vp)

        # Trigger: hover OR drag
        etype = "drag" if dragging else "hover"
        self._fire_trigger(etype, x, y)

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

    def _on_selection_changed(self, event: Event) -> None:
        """Handle selection changed events."""
        selected = event.data.get("selected", [])
        if not selected and event.data.get("new"):
            selected = [event.data.get("new")]
        for sid, state in self._drawings.items():
            state.selected = sid in selected
        self._pipeline.force_full_redraw()
        self._request_render()

    def _on_hover_changed(self, event: Event) -> None:
        """Handle hover changed events."""
        hid = event.data.get("id")
        for sid, state in self._drawings.items():
            state.hovered = (sid == hid)
        self._pipeline.force_full_redraw()
        self._request_render()

    def _on_mouse_down_event(self, event: Event) -> None:
        x = event.data.get("x", -1)
        y = event.data.get("y", -1)
        num = event.data.get("num", 1)
        is_double = event.data.get("double", False)
        if is_double:
            etype = "doubleclick"
        else:
            etype = "rightclick" if num == 3 else "click"
        self._fire_trigger(etype, x, y, button=num, double=is_double)

    def _on_mouse_up_event(self, event: Event) -> None:
        x = event.data.get("x", -1)
        y = event.data.get("y", -1)
        self._fire_trigger("mouseup", x, y)

    def _on_mouse_wheel_event(self, event: Event) -> None:
        x = event.data.get("x", -1)
        y = event.data.get("y", -1)
        factor = event.data.get("factor", 1.0)
        self._fire_trigger("scroll", x, y, factor=factor)

    def _on_key_down_event(self, event: Event) -> None:
        keysym = event.data.get("keysym", "")
        char = event.data.get("char", "")
        self._fire_trigger("keydown", key=keysym, char=char)

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

        self._coord_engine.set_price_range(min_p, max_p, emit_event=False)



    def _request_render(self) -> None:
        """Execute unified render pass across all renderers."""
        # Drop stale commands so incremental layer passes only see this frame.
        self._pipeline.clear_commands()

        # Render main candlestick pane
        chart_vp = self._grid_renderer.get_chart_viewport()
        self._series_renderer.render(chart_vp)
        self._grid_renderer.render(self._data_store.data)

        # Render indicators from session manager
        self._render_session_indicators(chart_vp)

        # Render subplot panes (future indicators will be rendered here)
        for pane_name in self._layout_engine.panes:
            if pane_name == "candlestick":
                continue
            pane_vp = self._coord_engine.get_pane_viewport(pane_name)
            if pane_vp.height > 0:
                self._grid_renderer.render(self._data_store.data, pane_name=pane_name)
    
    def _render_session_indicators(self, chart_vp) -> None:
        """Render indicators from the session manager.
        
        Args:
            chart_vp: Main chart viewport
        """
        if not self._session_manager:
            return
        
        current_context = self._session_manager.get_current_context()
        if not current_context:
            return
        
        # Get indicator adapters for current context
        if not hasattr(self._session_manager, '_indicator_adapters'):
            return
        
        adapters = self._session_manager._indicator_adapters.get(current_context, [])
        if not adapters:
            return
        
        # Get visible range
        vr = self._coord_engine.visible_range
        
        # Render each indicator
        for adapter in adapters:
            subplot = adapter._subplot
            
            # Get appropriate viewport
            if subplot == "candlestick":
                viewport = chart_vp
            else:
                # Ensure subplot exists in layout
                if subplot not in self._layout_engine.panes:
                    self._layout_engine.add_pane(subplot, weight=1.0)
                    self._update_viewport()
                viewport = self._coord_engine.get_pane_viewport(subplot)
            
            # Generate draw commands
            try:
                commands = adapter.render(
                    self._coord_engine,
                    self._pipeline,
                    viewport,
                    vr.start_index,
                    vr.end_index
                )
                self._pipeline.add_commands(commands)
            except Exception as e:
                # Skip indicators that fail to render
                continue

        # Render all drawings
        # Push live price to LongShort tools for PnL calculation
        live_price = None
        if not self._data_store.is_empty:
            last_bar = self._data_store.data[-1]
            live_price = last_bar.close  # Use last bar close as live price
        
        for tool in self._drawing_tools.values():
            if not tool.state.visible:
                continue
            if hasattr(tool, 'update_live_price'):
                tool.update_live_price(live_price)
            pane_vp = chart_vp if tool.state.pane_name == "candlestick" else self._coord_engine.get_pane_viewport(tool.state.pane_name)
            cmds = tool.render_commands(self._coord_engine, pane_vp)
            self._pipeline.add_commands(cmds)

        # Render preview shape during drawing tool creation
        if self._tool_context and self._tool_context.preview_tool and self._tool_context.preview_shape:
            preview_tool = self._tool_context.preview_tool
            if preview_tool.state.visible:
                cmds = preview_tool.render_commands(self._coord_engine, chart_vp)
                self._pipeline.add_commands(cmds)

        self._pipeline.schedule_layer(Layer.DRAWING)

        # Crosshair rendered last (overlay on top of everything)
        # Hide crosshair during drawing tool activation
        if not self._tool_context or self._tool_context.state == ToolState.IDLE:
            self._update_crosshair_badges()
            self._crosshair_renderer.render(chart_vp)
            self._pipeline.schedule_layer(Layer.CROSSHAIR)
        # Incremental layer update + pool option reset keeps axes stable while
        # pan/stream rebuild series/grid/indicators without full canvas wipe.
        self._pipeline.schedule_render(full_redraw=False)

    # ==================== Crosshair Badge Computation ====================

    def _update_crosshair_badges(self) -> None:
        """Compute per-pane badge info and push it to the crosshair renderer.

        TradingView behavior: A badge appears on the right axis of EVERY pane,
        showing the value at the crosshair's Y-level in that pane.
        """
        cr = self._crosshair_renderer
        if not cr.is_visible or cr.snapped_index < 0:
            cr.set_pane_badges([])
            return

        snapped_idx = cr.snapped_index
        mouse_y = cr.mouse_y
        chart_vp = self._grid_renderer.get_chart_viewport()
        badges: List[PaneBadge] = []

        # Show badges for ALL panes simultaneously (TradingView standard)
        for pane_name in self._layout_engine.panes:
            pane_vp = self._coord_engine.get_pane_viewport(pane_name)
            if pane_vp.height <= 0:
                continue

            if pane_name == "candlestick":
                # Main pane: use mouse Y position to get price
                # Clamp to pane bounds so the badge never leaves the pane area
                clamped_y = max(chart_vp.top, min(chart_vp.bottom, mouse_y))
                price_val = self._coord_engine.y_to_price(clamped_y, chart_vp, pane="candlestick")
                badges.append(PaneBadge(
                    badge_y=clamped_y,
                    value_text=self._format_price_value(price_val),
                    pane_top=chart_vp.top,
                    pane_bottom=chart_vp.bottom,
                ))
            else:
                # Subplot pane: clamp mouse_y to this pane's vertical extent so
                # that when the mouse is over a *different* pane the badge still
                # shows a value that makes sense within the subplot's scale.
                clamped_y = max(pane_vp.top, min(pane_vp.bottom, mouse_y))
                indicator_val = self._coord_engine.y_to_price(clamped_y, pane_vp, pane=pane_name)
                badges.append(PaneBadge(
                    badge_y=clamped_y,
                    value_text=self._format_price_value(indicator_val),
                    pane_top=pane_vp.top,
                    pane_bottom=pane_vp.bottom,
                ))

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
