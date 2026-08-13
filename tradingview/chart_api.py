"""
FinChart TradingView Chart API module (Layer 1.8).
Primary root public API facade object representing ONE FinChart instance.
"""

import uuid
from typing import List, Dict, Any, Optional, Callable
from .enums import ChartType, PointerEventType
from .input_events import ChartInputEvent, PointerEvent
from .types import OHLCVBar, Instrument
from .constants import DEFAULT_BAR_SPACING
from .errors import (
    ChartRemovedError, EntityNotFoundError, InvalidSymbolError, InvalidResolutionError,
    InvalidChartTypeError, InvalidPaneError, InvalidDrawingError, InvalidIndicatorError
)
from .options import ChartOptions
from .event_subscription import EventRegistry, Subscription
from .chart_state import ChartState
from .chart_layout import ChartLayout, PaneModel
from .viewport_state import ViewportState
from .time_scale import TimeScale
from .price_scale import PriceScale
from .invalidation import InvalidationScheduler
from .hit_tester import HitTester
from .focus_manager import FocusManager
from .input_engine import InputEngine
from .data_series import OHLCVSeries
from .selection_manager import SelectionManager
from .gesture_engine import GestureEngine
from .command_history import CommandHistory
from .commands import AddDrawingCommand, RemoveDrawingCommand, ModifyDrawingCommand, AddSeriesCommand, RemoveSeriesCommand, AddIndicatorCommand, RemoveIndicatorCommand
from .api_entities import (
    SeriesAPI, IndicatorAPI, DrawingAPI, PaneAPI, TimeScaleAPI, PriceScaleAPI
)
from .canvas_adapter import CanvasAdapter
from .extension_contracts import ExtensionRegistry
from .handle_engine import HandleEngine


class CrosshairState:
    """Stores current crosshair screen position and visibility state."""

    def __init__(self):
        self.screen_x: float = 0.0
        self.screen_y: float = 0.0
        self.visible: bool = False
        self.pane_id: str = "pane_main"


class Chart:
    """Primary application-facing single-chart object for FinChart engine."""

    def __init__(self, symbol: str = "AAPL", interval: str = "1D", options: Optional[Dict[str, Any]] = None):
        self._lifecycle_state: str = "CREATED"  # CREATED, ACTIVE, REMOVED
        self.chart_id: str = f"chart_{uuid.uuid4().hex[:8]}"

        # Options and configuration
        self.options = ChartOptions()
        if options:
            self.options.apply_partial(options)

        # Event Subscription Layer (1.8)
        self.event_registry = EventRegistry()

        # Internal Subsystems (Dependency Inversion & Ownership)
        self.chart_state = ChartState(chart_id=self.chart_id, symbol=symbol, interval=interval)
        self.layout = self.chart_state.layout
        self.viewport = ViewportState()
        self.time_scale = TimeScale(
            width=self.options.dimensions.width,
            bar_spacing=self.options.time_scale.bar_spacing,
            right_offset=self.options.time_scale.right_offset,
            fix_left_edge=self.options.time_scale.fix_left_edge,
            fix_right_edge=self.options.time_scale.fix_right_edge
        )
        self.price_scales: Dict[str, PriceScale] = {
            "pane_main": PriceScale(pane_height=400.0)
        }
        self.invalidation_scheduler = InvalidationScheduler()

        # Drawing Handle Engine (Layer 1.7) — single source of truth for
        # handle definition, geometry, roles, visibility, rendering & hit testing
        self.handle_engine = HandleEngine()

        # Input & Event Layer (1.7)
        self.hit_tester = HitTester(layout=self.layout, time_scale=self.time_scale, price_scales=self.price_scales)
        self.focus_manager = FocusManager(initial_focus=False, event_registry=self.event_registry)
        self.input_engine = InputEngine(hit_tester=self.hit_tester, focus_manager=self.focus_manager, chart=self)

        # Selection & Gesture Engine (1.9)
        self.selection_manager = SelectionManager(event_registry=self.event_registry)
        self.gesture_engine = GestureEngine(
            layout=self.layout,
            viewport=self.viewport,
            time_scale=self.time_scale,
            price_scales=self.price_scales,
            selection_manager=self.selection_manager,
            invalidation_scheduler=self.invalidation_scheduler,
            event_registry=self.event_registry
        )
        # Provide chart dimensions to gesture engine for splitter math
        try:
            self.gesture_engine.chart_width = self.options.dimensions.width
            self.gesture_engine.chart_height = self.options.dimensions.height
        except Exception:
            pass
        # Apply kinetic configuration from options
        try:
            self.gesture_engine.kinetic_decay = float(self.options.kinetic.decay)
            self.gesture_engine.kinetic_steps = int(self.options.kinetic.steps)
            self.gesture_engine.kinetic_frame_ms = int(self.options.kinetic.frame_ms)
        except Exception:
            # Defensive: if options are malformed, keep defaults
            pass
        self.input_engine.add_event_listener(self.gesture_engine.process_event)
        self.input_engine.add_event_listener(self._emit_pointer_events)

        # Command History (Layer 1.11)
        self.command_history = CommandHistory(capacity=50)

        # Extension / sync hooks (Layer 1.14)
        self.extension_registry = ExtensionRegistry()

        # Bind event listener to handle drawing removal request from gesture/keyboard inputs
        self.event_registry.subscribe("request_drawing_removal", lambda data: self.remove_drawing(data["drawing_id"]))
        self.event_registry.subscribe("request_undo", lambda data: self.undo())
        self.event_registry.subscribe("request_redo", lambda data: self.redo())
        self.event_registry.subscribe("request_save", lambda data: self.save_session())
        # Keep price scales in sync when panes change
        self.event_registry.subscribe("pane_changed", lambda data: self._apply_layout_sizes())
        # Sync drawing visual selection state when SelectionManager changes
        self.event_registry.subscribe("selection_changed", lambda data: self._sync_drawing_selection_state())

        # Entity Registries
        self._series_registry: Dict[str, SeriesAPI] = {}
        self._indicator_registry: Dict[str, IndicatorAPI] = {}
        # Use DrawingRegistry which keeps ChartState.drawings in sync
        from .drawing_registry import DrawingRegistry
        self._drawing_registry = DrawingRegistry(self.chart_state)
        self._series_data: Dict[str, OHLCVSeries] = {}
        self._primary_series: Optional[OHLCVSeries] = None

        # Wire drawing registry into hit tester for categorized drawing hit testing
        self.hit_tester.drawings_provider = self._drawing_registry
        self.hit_tester.drawing_hit_tester.drawings_provider = self._drawing_registry

        # Crosshair state for Layer 1.3
        self.crosshair = CrosshairState()

        # API Entities
        self._time_scale_api = TimeScaleAPI(self)

        # Ensure layout sizes are applied to price scales initially
        self._apply_layout_sizes()

        # Mark active
        self._lifecycle_state = "ACTIVE"

    # -------------------------------------------------------------------------
    # Lifecycle Management
    # -------------------------------------------------------------------------

    def _verify_active(self) -> None:
        if self._lifecycle_state == "REMOVED":
            raise ChartRemovedError(f"Chart '{self.chart_id}' is removed and cannot accept operations.")

    def _emit_pointer_events(self, evt: ChartInputEvent) -> None:
        data = evt.input_data
        if not isinstance(data, PointerEvent):
            return
        if data.event_type != PointerEventType.MOVE:
            return

        self.crosshair.screen_x = data.screen_x
        self.crosshair.screen_y = data.screen_y
        self.crosshair.pane_id = evt.hit_target.pane_id or "pane_main"
        self.crosshair.visible = self.options.crosshair.mode != "hidden"

        self.event_registry.emit("pointer_move", {
            "screen_x": data.screen_x,
            "screen_y": data.screen_y,
            "pane_id": self.crosshair.pane_id,
            "buttons_down": data.buttons_down,
            "modifiers": {
                "shift": data.modifiers.shift,
                "ctrl": data.modifiers.ctrl,
                "alt": data.modifiers.alt,
                "meta": data.modifiers.meta
            }
        })

        if self.crosshair.visible:
            self.event_registry.emit("crosshair_move", {
                "screen_x": data.screen_x,
                "screen_y": data.screen_y,
                "pane_id": self.crosshair.pane_id
            })

    @property
    def is_active(self) -> bool:
        return self._lifecycle_state == "ACTIVE"

    def apply_options(self, opts: Dict[str, Any]) -> None:
        self._verify_active()
        self.options.apply_partial(opts)
        if "dimensions" in opts:
            w = opts["dimensions"].get("width", self.options.dimensions.width)
            h = opts["dimensions"].get("height", self.options.dimensions.height)
            self.resize(w, h)

        invalidated = False
        if "time_scale" in opts and isinstance(opts["time_scale"], dict):
            ts_opts = opts["time_scale"]
            if "bar_spacing" in ts_opts:
                self.time_scale.set_bar_spacing(ts_opts["bar_spacing"])
                self.viewport.bar_spacing = self.time_scale.bar_spacing
                invalidated = True
            if "right_offset" in ts_opts:
                self.time_scale.right_offset = ts_opts["right_offset"]
                self.viewport.right_offset = ts_opts["right_offset"]
                invalidated = True
            if "fix_left_edge" in ts_opts:
                self.viewport.fix_left_edge = ts_opts["fix_left_edge"]
                self.time_scale.fix_left_edge = ts_opts["fix_left_edge"]
                invalidated = True
            if "fix_right_edge" in ts_opts:
                self.viewport.fix_right_edge = ts_opts["fix_right_edge"]
                self.time_scale.fix_right_edge = ts_opts["fix_right_edge"]
                invalidated = True

            self.viewport.visible_start = self.time_scale.visible_start
            self.viewport.visible_end = self.time_scale.visible_end

        if invalidated and self.invalidation_scheduler:
            self.invalidation_scheduler.request_invalidation()

        # Apply kinetic option updates at runtime if provided
        if "kinetic" in opts and isinstance(opts["kinetic"], dict):
            k = opts["kinetic"]
            if "decay" in k:
                try:
                    self.gesture_engine.kinetic_decay = float(k["decay"])
                except Exception:
                    pass
            if "steps" in k:
                try:
                    self.gesture_engine.kinetic_steps = int(k["steps"])
                except Exception:
                    pass
            if "frame_ms" in k:
                try:
                    self.gesture_engine.kinetic_frame_ms = int(k["frame_ms"])
                except Exception:
                    pass

    def resize(self, width: float, height: float) -> None:
        self._verify_active()
        self.options.dimensions.width = max(1.0, width)
        self.options.dimensions.height = max(1.0, height)
        self.time_scale.width = self.options.dimensions.width
        # Keep gesture engine informed of chart dimensions
        try:
            self.gesture_engine.chart_width = self.options.dimensions.width
            self.gesture_engine.chart_height = self.options.dimensions.height
        except Exception:
            pass
        self.input_engine.set_chart_dimensions(self.options.dimensions.width, self.options.dimensions.height)
        self.invalidation_scheduler.request_invalidation()
        # Recompute pane sizes and update price scales
        self._apply_layout_sizes()

    def _set_viewport_to_latest_edge(self, data_count: int) -> None:
        right_offset = self.viewport.right_offset
        visible_end = max(100.0, float(data_count)) + right_offset
        visible_start = visible_end - (self.time_scale.width / self.time_scale.bar_spacing)
        self.viewport.visible_start = max(0.0, visible_start)
        self.viewport.visible_end = visible_end
        self.viewport.follow_latest = True
        self.time_scale.visible_start = self.viewport.visible_start
        self.time_scale.visible_end = self.viewport.visible_end

    def remove(self) -> None:
        if self._lifecycle_state == "REMOVED":
            return
        self._lifecycle_state = "REMOVED"
        self.input_engine.pointer_capture.release_capture()
        self.event_registry.unsubscribe_all()
        self._series_registry.clear()
        self._indicator_registry.clear()
        self._drawing_registry.clear()

    # -------------------------------------------------------------------------
    # Symbol, Resolution & Chart Type APIs
    # -------------------------------------------------------------------------

    def get_symbol(self) -> str:
        self._verify_active()
        return self.chart_state.symbol

    def set_symbol(self, symbol: str) -> None:
        self._verify_active()
        if not symbol or not isinstance(symbol, str):
            raise InvalidSymbolError("Symbol must be a non-empty string.")
        old_symbol = self.chart_state.symbol
        if old_symbol != symbol:
            self.chart_state.symbol = symbol
            self.event_registry.emit("symbol_changed", {"previous": old_symbol, "new": symbol})

    def get_resolution(self) -> str:
        self._verify_active()
        return self.chart_state.interval

    def set_resolution(self, interval: str) -> None:
        self._verify_active()
        if not interval:
            raise InvalidResolutionError("Interval must be a valid resolution string (e.g. '1m', '5m', '1D').")
        old_interval = self.chart_state.interval
        if old_interval != interval:
            self.chart_state.interval = interval
            self.event_registry.emit("resolution_changed", {"previous": old_interval, "new": interval})

    def get_chart_type(self) -> ChartType:
        self._verify_active()
        return self.chart_state.chart_type

    def set_chart_type(self, chart_type: Any) -> None:
        self._verify_active()
        if isinstance(chart_type, str):
            try:
                chart_type = ChartType(chart_type.lower())
            except ValueError:
                raise InvalidChartTypeError(f"Unsupported chart type: {chart_type}")
        elif not isinstance(chart_type, ChartType):
            raise InvalidChartTypeError("Invalid chart type object.")

        old_type = self.chart_state.chart_type
        if old_type != chart_type:
            self.chart_state.chart_type = chart_type
            self.event_registry.emit("chart_type_changed", {"previous": old_type.value, "new": chart_type.value})

    # -------------------------------------------------------------------------
    # Data & Series APIs
    # -------------------------------------------------------------------------

    def set_data(self, data: List[OHLCVBar]) -> None:
        self._verify_active()
        self._primary_series = OHLCVSeries(self.chart_state.symbol, data)
        self._series_data["primary"] = self._primary_series
        self.viewport.bar_spacing = self.time_scale.bar_spacing
        if self.viewport.follow_latest:
            self._set_viewport_to_latest_edge(len(data))
        else:
            self.time_scale.visible_start = self.viewport.visible_start
            self.time_scale.visible_end = self.viewport.visible_end
        if self.invalidation_scheduler:
            self.invalidation_scheduler.request_invalidation()
        self.event_registry.emit("data_loaded", {"count": len(data)})

    def update(self, bar: OHLCVBar) -> None:
        self._verify_active()
        if self._primary_series is None:
            self._primary_series = OHLCVSeries(self.chart_state.symbol, [])
            self._series_data["primary"] = self._primary_series
        self._primary_series.add_bar(bar)
        if self.viewport.follow_latest:
            self._set_viewport_to_latest_edge(len(self._primary_series))
            if self.event_registry:
                self.event_registry.emit("visible_range_changed", {"start": self.viewport.visible_start, "end": self.viewport.visible_end})
        if self.invalidation_scheduler:
            self.invalidation_scheduler.request_invalidation()
        self.event_registry.emit("data_updated", {"bar": bar})

    def get_data(self) -> List[OHLCVBar]:
        self._verify_active()
        primary = self._series_data.get("primary")
        return primary._bars if primary else []

    def add_series(self, series_type: str = "candlestick", options: Optional[Dict[str, Any]] = None, pane_id: str = "pane_main") -> SeriesAPI:
        self._verify_active()
        cmd = AddSeriesCommand(self, series_type, options, pane_id)
        self.command_history.push_and_execute(cmd)
        return cmd.api_series

    def get_series(self, series_id: str) -> Optional[SeriesAPI]:
        self._verify_active()
        return self._series_registry.get(series_id)

    def get_series_list(self) -> List[SeriesAPI]:
        self._verify_active()
        return list(self._series_registry.values())

    def remove_series(self, series_id: str) -> bool:
        self._verify_active()
        if series_id not in self._series_registry:
            return False
        cmd = RemoveSeriesCommand(self, series_id)
        self.command_history.push_and_execute(cmd)
        return True

    def _set_series_data(self, series_id: str, bars: List[OHLCVBar]) -> None:
        series = self._series_data.get(series_id)
        if series is None:
            raise EntityNotFoundError(f"Series {series_id} not found.")
        series._bars = bars

    def _update_series_bar(self, series_id: str, bar: OHLCVBar) -> None:
        self.update(bar)

    def _update_drawing_state(self, drawing_id: str, points: Optional[List[Dict[str, float]]] = None, properties: Optional[Dict[str, Any]] = None) -> None:
        self._verify_active()
        drawing = self._drawing_registry.get(drawing_id)
        if drawing is None:
            raise EntityNotFoundError(f"Drawing {drawing_id} not found.")

        if points is not None:
            drawing.points = list(points)
        if properties is not None:
            drawing.properties = dict(properties)

        for state_item in self.chart_state.drawings:
            if state_item.get("id") == drawing_id:
                if points is not None:
                    state_item["points"] = list(points)
                if properties is not None:
                    state_item["properties"] = dict(properties)
                break

        self.event_registry.emit("drawing_modified", {"drawing_id": drawing_id})

    def _calculate_indicator_output(self, indicator_id: str) -> List[float]:
        self._verify_active()
        indicator = self._indicator_registry.get(indicator_id)
        if indicator is None:
            raise EntityNotFoundError(f"Indicator {indicator_id} not found.")

        primary_series = self._series_data.get("primary")
        if primary_series is None:
            return []

        bars = primary_series._bars
        if not bars:
            return []

        name = (indicator.name or "").upper()
        length = int(indicator.inputs.get("length", 1) or 1)
        length = max(1, length)

        if name == "SMA":
            values: List[float] = []
            for idx in range(len(bars)):
                start = max(0, idx - length + 1)
                window = bars[start:idx + 1]
                if not window:
                    values.append(float(bars[idx].close))
                else:
                    values.append(sum(b.close for b in window) / len(window))
            indicator._output = values
            return values

        if name == "EMA":
            values = []
            multiplier = 2.0 / (length + 1.0)
            prev = None
            for bar in bars:
                if prev is None:
                    prev = float(bar.close)
                else:
                    prev = (float(bar.close) * multiplier) + (prev * (1.0 - multiplier))
                values.append(prev)
            indicator._output = values
            return values

        raise InvalidIndicatorError(f"Unsupported indicator: {indicator.name}")

    # -------------------------------------------------------------------------
    # Indicator & Pane APIs
    # -------------------------------------------------------------------------

    def add_indicator(self, name: str, pane_id: Optional[str] = None, inputs: Optional[Dict[str, Any]] = None) -> IndicatorAPI:
        self._verify_active()
        cmd = AddIndicatorCommand(self, name, pane_id, inputs)
        self.command_history.push_and_execute(cmd)
        return cmd.api_indicator

    def get_indicator(self, indicator_id: str) -> Optional[IndicatorAPI]:
        self._verify_active()
        return self._indicator_registry.get(indicator_id)

    def get_indicators(self) -> List[IndicatorAPI]:
        self._verify_active()
        return list(self._indicator_registry.values())

    def remove_indicator(self, indicator_id: str) -> bool:
        self._verify_active()
        if indicator_id not in self._indicator_registry:
            return False
        cmd = RemoveIndicatorCommand(self, indicator_id)
        self.command_history.push_and_execute(cmd)
        return True

    def panes(self) -> List[PaneAPI]:
        self._verify_active()
        return [PaneAPI(p.pane_id, self) for p in self.layout.get_all_panes()]

    def get_pane(self, pane_id: str) -> Optional[PaneAPI]:
        self._verify_active()
        p = self.layout.get_pane(pane_id)
        return PaneAPI(pane_id, self) if p else None

    def add_pane(self, pane_id: Optional[str] = None, height: float = 150.0) -> PaneAPI:
        self._verify_active()
        pid = pane_id or f"pane_{uuid.uuid4().hex[:6]}"
        self.layout.add_indicator_pane(pid, height=height)
        self.price_scales[pid] = PriceScale(pane_height=height)
        self.event_registry.emit("layout_changed", {"action": "add_pane", "pane_id": pid})
        # Apply layout reflow and propagate pane heights into price scales
        self._apply_layout_sizes()
        return PaneAPI(pid, self)

    def remove_pane(self, pane_id: str) -> bool:
        self._verify_active()
        if pane_id == self.layout.main_pane_id:
            raise InvalidPaneError("Cannot remove the primary main pane.")
        removed = self.layout.remove_pane(pane_id)
        if removed:
            if pane_id in self.price_scales:
                del self.price_scales[pane_id]
            self.event_registry.emit("layout_changed", {"action": "remove_pane", "pane_id": pane_id})
            # Apply layout reflow and propagate pane heights into price scales
            self._apply_layout_sizes()
        return removed

    def _apply_layout_sizes(self) -> None:
        """Calculate pane pixel heights from layout and update PriceScale.pane_height for each pane.

        Uses current chart dimensions and reserves a time scale area of 30px at the bottom.
        """
        total_h = max(0.0, self.options.dimensions.height - 30.0)
        self.layout.reflow_panes(total_h)
        # Update price scales with the computed pane heights
        for p in self.layout.get_all_panes():
            ps = self.price_scales.get(p.pane_id)
            if ps:
                ps.pane_height = p.height

    # -------------------------------------------------------------------------
    # Drawing APIs
    # -------------------------------------------------------------------------

    def create_shape(self, point: Dict[str, float], shape_type: str = "trend_line", pane_id: str = "pane_main") -> DrawingAPI:
        return self.create_multipoint_shape([point], shape_type=shape_type, pane_id=pane_id)

    def create_multipoint_shape(self, points: List[Dict[str, float]], shape_type: str = "trend_line", pane_id: str = "pane_main") -> DrawingAPI:
        self._verify_active()
        if not points:
            raise InvalidDrawingError("Points list cannot be empty.")
        drawing_id = f"draw_{shape_type}_{uuid.uuid4().hex[:6]}"
        cmd = AddDrawingCommand(self, drawing_id, shape_type, points, pane_id)
        self.command_history.push_and_execute(cmd)
        return self.get_drawing(drawing_id)

    def create_anchored_shape(self, x_percent: float, y_percent: float, shape_type: str = "text", pane_id: str = "pane_main") -> DrawingAPI:
        return self.create_multipoint_shape([{"x_percent": x_percent, "y_percent": y_percent}], shape_type=shape_type, pane_id=pane_id)

    def get_drawing(self, drawing_id: str) -> Optional[DrawingAPI]:
        self._verify_active()
        return self._drawing_registry.get(drawing_id)

    def get_drawings(self) -> List[DrawingAPI]:
        self._verify_active()
        return list(self._drawing_registry.values())

    def remove_drawing(self, drawing_id: str) -> bool:
        self._verify_active()
        if drawing_id in self._drawing_registry:
            cmd = RemoveDrawingCommand(self, drawing_id)
            self.command_history.push_and_execute(cmd)
            return True
        return False

    # -------------------------------------------------------------------------
    # Selection & Tools APIs
    # -------------------------------------------------------------------------

    def select(self, entity_id: str) -> None:
        self._verify_active()
        self.selection_manager.select(entity_id)

    def deselect(self, entity_id: str) -> None:
        self._verify_active()
        self.selection_manager.deselect(entity_id)

    def clear_selection(self) -> None:
        self._verify_active()
        self.selection_manager.clear_selection()

    def get_selected(self) -> List[str]:
        self._verify_active()
        return self.selection_manager.get_selected()

    def _sync_drawing_selection_state(self) -> None:
        """Sync the SelectionManager's entity selection into each drawing's
        properties so that rendering layers (GUI overlay, renderer) can display
        selection markers correctly.

        Triggered on every 'selection_changed' event.
        """
        self._verify_active()
        selected_ids = self.selection_manager.get_selected()
        for drawing_id, drawing in self._drawing_registry._store.items():
            if drawing_id in selected_ids:
                drawing.properties["selected"] = True
            else:
                drawing.properties.pop("selected", None)

    def has_focus(self) -> bool:
        self._verify_active()
        return self.focus_manager.has_focus

    def set_focus(self, focused: bool) -> None:
        self._verify_active()
        self.focus_manager.set_focus(focused)

    def render_frame(self, canvas: Optional[CanvasAdapter] = None) -> List[Dict[str, Any]]:
        self._verify_active()
        from .drawing_renderer import RenderPipeline

        pane_order = {pane.pane_id: idx for idx, pane in enumerate(self.layout.get_all_panes())}
        pipeline = RenderPipeline(canvas=canvas)
        return pipeline.render(self._drawing_registry, self.time_scale, self.price_scales, self.crosshair, pane_order=pane_order)

    def undo(self) -> bool:
        self._verify_active()
        res = self.command_history.undo()
        if res:
            self.event_registry.emit("undo_executed", {})
            if self.invalidation_scheduler:
                self.invalidation_scheduler.request_invalidation()
        return res

    def redo(self) -> bool:
        self._verify_active()
        res = self.command_history.redo()
        if res:
            self.event_registry.emit("redo_executed", {})
            if self.invalidation_scheduler:
                self.invalidation_scheduler.request_invalidation()
        return res

    def set_active_tool(self, tool_name: str) -> None:
        self._verify_active()
        old_tool = self.chart_state.active_tool
        if old_tool != tool_name:
            self.chart_state.active_tool = tool_name
            self.event_registry.emit("tool_changed", {"previous": old_tool, "new": tool_name})

    def get_active_tool(self) -> str:
        self._verify_active()
        return self.chart_state.active_tool

    # -------------------------------------------------------------------------
    # Event Subscriptions & Options Accessors
    # -------------------------------------------------------------------------

    def on(self, event_name: str, callback: Callable[[Any], None]) -> Subscription:
        self._verify_active()
        return self.event_registry.subscribe(event_name, callback)

    def off(self, subscription: Subscription) -> None:
        self._verify_active()
        subscription.unsubscribe()

    def register_extension_hook(self, name: str, callback: Callable[[Any], None]) -> Any:
        self._verify_active()
        return self.extension_registry.register(name, callback)

    def unregister_extension_hook(self, hook: Any) -> None:
        self._verify_active()
        self.extension_registry.unregister(hook)

    def notify_extension(self, name: str, payload: Optional[Dict[str, Any]] = None) -> None:
        self._verify_active()
        return self.extension_registry.notify(name, payload)

    @property
    def time_scale_api(self) -> TimeScaleAPI:
        self._verify_active()
        return self._time_scale_api

    def price_scale(self, pane_id: str = "pane_main") -> PriceScaleAPI:
        self._verify_active()
        return PriceScaleAPI(pane_id, self)

    def modify_drawing(self, drawing_id: str, points: Optional[List[Dict[str, float]]] = None, properties: Optional[Dict[str, Any]] = None):
        self._verify_active()
        drawing = self.get_drawing(drawing_id)
        if drawing is None:
            raise EntityNotFoundError(f"Drawing with ID '{drawing_id}' not found.")

        old_points = list(drawing.points)
        old_properties = dict(drawing.properties)
        new_points = points if points is not None else old_points
        new_properties = properties if properties is not None else old_properties

        cmd = ModifyDrawingCommand(self, drawing_id, old_points, old_properties, new_points, new_properties)
        self.command_history.push_and_execute(cmd)
        return self.get_drawing(drawing_id)

    # -------------------------------------------------------------------------
    # Persistence APIs
    # -------------------------------------------------------------------------

    def save_session(self) -> Dict[str, Any]:
        self._verify_active()

        def serialize_bar(bar: OHLCVBar) -> Dict[str, Any]:
            return {
                "timestamp": bar.timestamp,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume
            }

        session = {
            "state": self.chart_state.to_dict(),
            "options": self.options.to_dict(),
            "viewport": {
                "visible_start": self.viewport.visible_start,
                "visible_end": self.viewport.visible_end,
                "bar_spacing": self.viewport.bar_spacing,
                "follow_latest": self.viewport.follow_latest,
                "pane_price_ranges": dict(self.viewport.pane_price_ranges)
            },
            "price_scales": {
                pid: {
                    "pane_height": ps.pane_height,
                    "price_min": ps.price_min,
                    "price_max": ps.price_max
                }
                for pid, ps in self.price_scales.items()
            },
            "series": [
                {
                    "series_id": sid,
                    "series_type": api.series_type,
                    "pane_id": api.pane_id,
                    "options": api.options,
                    "visible": api.visible,
                    "bars": [serialize_bar(bar) for bar in self._series_data.get(sid, OHLCVSeries(self.chart_state.symbol, []))._bars]
                }
                for sid, api in self._series_registry.items()
            ],
            "indicators": [
                {
                    "indicator_id": iid,
                    "name": api.name,
                    "pane_id": api.pane_id,
                    "inputs": api.inputs,
                    "options": api.options,
                    "visible": api.visible
                }
                for iid, api in self._indicator_registry.items()
            ],
            "drawings": [
                {
                    "drawing_id": drawing.drawing_id,
                    "shape_type": drawing.shape_type,
                    "pane_id": drawing.pane_id,
                    "points": drawing.points,
                    "properties": drawing.properties,
                    "visible": drawing.visible
                }
                for drawing in self._drawing_registry.values()
            ],
            "selection": self.selection_manager.get_selected(),
            "crosshair": {
                "screen_x": self.crosshair.screen_x,
                "screen_y": self.crosshair.screen_y,
                "visible": self.crosshair.visible,
                "pane_id": self.crosshair.pane_id
            }
        }

        return session

    def autoscale_price(self, pane_id: str = "pane_main", series_id: str = "primary") -> None:
        """Autoscale the price scale for `pane_id` using bars from `series_id` visible in the viewport.

        If no series or price scale exists for the pane, the method is a no-op.
        """
        self._verify_active()
        series = self._series_data.get(series_id)
        if series is None:
            return

        # Determine integer render range from viewport
        start = int(self.viewport.visible_start)
        end = int(self.viewport.visible_end)
        bars = series.get_bars_in_range(start, end)
        p_scale = self.price_scales.get(pane_id)
        if not p_scale:
            return

        p_scale.set_range_from_bars(bars)
        # Keep viewport pane price ranges in sync
        self.viewport.set_pane_price_range(pane_id, p_scale.price_min, p_scale.price_max)
        if self.invalidation_scheduler:
            self.invalidation_scheduler.request_invalidation()
        self.event_registry.emit("price_scale_changed", {"pane_id": pane_id, "price_min": p_scale.price_min, "price_max": p_scale.price_max})

    def load_session(self, session_data: Dict[str, Any]) -> None:
        self._verify_active()
        if "state" in session_data:
            state_data = session_data["state"]
        else:
            state_data = session_data

        if "options" in session_data:
            self.options.from_dict(session_data["options"])
            self.time_scale.width = self.options.dimensions.width
            self.input_engine.set_chart_dimensions(self.options.dimensions.width, self.options.dimensions.height)

        self.chart_state.from_dict(state_data)
        self.layout = self.chart_state.layout
        self.hit_tester.layout = self.layout
        self.gesture_engine.layout = self.layout

        # Restore price scales for each pane
        self.price_scales = {
            pane.pane_id: PriceScale(pane_height=pane.height)
            for pane in self.layout.get_all_panes()
        }
        self.hit_tester.price_scales = self.price_scales
        self.gesture_engine.price_scales = self.price_scales
        self.hit_tester.drawing_hit_tester.price_scales = self.price_scales

        # Restore viewport state
        viewport_data = session_data.get("viewport", {})
        self.viewport.visible_start = viewport_data.get("visible_start", self.viewport.visible_start)
        self.viewport.visible_end = viewport_data.get("visible_end", self.viewport.visible_end)
        self.viewport.bar_spacing = viewport_data.get("bar_spacing", self.viewport.bar_spacing)
        self.viewport.follow_latest = viewport_data.get("follow_latest", self.viewport.follow_latest)
        self.viewport.pane_price_ranges = dict(viewport_data.get("pane_price_ranges", self.viewport.pane_price_ranges))
        self.time_scale.visible_start = self.viewport.visible_start
        self.time_scale.visible_end = self.viewport.visible_end
        self.time_scale.bar_spacing = self.viewport.bar_spacing
        self.gesture_engine.time_scale = self.time_scale
        self.hit_tester.time_scale = self.time_scale
        self.gesture_engine.viewport = self.viewport

        # Reset registries before rehydration
        self._series_registry.clear()
        self._series_data.clear()
        self._indicator_registry.clear()
        self._drawing_registry.clear()

        # Re-wire drawing registry into hit tester after rehydration
        self.hit_tester.drawings_provider = self._drawing_registry
        self.hit_tester.drawing_hit_tester.drawings_provider = self._drawing_registry

        for pane in self.layout.get_all_panes():
            pane.series_ids.clear()
            pane.indicator_ids.clear()

        for series_record in session_data.get("series", []):
            series_id = series_record["series_id"]
            series_api = SeriesAPI(series_id, series_record["series_type"], series_record.get("pane_id", "pane_main"), self)
            series_api.options = dict(series_record.get("options", {}))
            series_api.visible = bool(series_record.get("visible", True))
            self._series_registry[series_id] = series_api
            bars = [OHLCVBar(**bar) for bar in series_record.get("bars", [])]
            self._series_data[series_id] = OHLCVSeries(self.chart_state.symbol, bars)
            pane = self.layout.get_pane(series_api.pane_id)
            if pane:
                pane.series_ids.append(series_id)

        for indicator_record in session_data.get("indicators", []):
            indicator_id = indicator_record["indicator_id"]
            indicator_api = IndicatorAPI(
                indicator_id,
                indicator_record.get("name", "indicator"),
                indicator_record.get("pane_id", "pane_main"),
                self
            )
            indicator_api.inputs = dict(indicator_record.get("inputs", {}))
            indicator_api.options = dict(indicator_record.get("options", {}))
            indicator_api.visible = bool(indicator_record.get("visible", True))
            self._indicator_registry[indicator_id] = indicator_api
            pane = self.layout.get_pane(indicator_api.pane_id)
            if pane:
                pane.indicator_ids.append(indicator_id)

        for drawing_record in session_data.get("drawings", []):
            drawing_id = drawing_record["drawing_id"]
            drawing_api = DrawingAPI(
                drawing_id,
                drawing_record.get("shape_type", "trend_line"),
                drawing_record.get("points", []),
                drawing_record.get("pane_id", "pane_main"),
                self
            )
            drawing_api.properties = dict(drawing_record.get("properties", {}))
            drawing_api.visible = bool(drawing_record.get("visible", True))
            self._drawing_registry[drawing_id] = drawing_api
            self.chart_state.drawings.append({
                "id": drawing_id,
                "type": drawing_api.shape_type,
                "points": drawing_api.points,
                "pane_id": drawing_api.pane_id,
                "properties": drawing_api.properties
            })

        selection_data = session_data.get("selection", [])
        if isinstance(selection_data, list):
            self.selection_manager.clear_selection()
            for entity_id in selection_data:
                self.selection_manager.select(entity_id, multi_select=True)

        crosshair_data = session_data.get("crosshair", {})
        if isinstance(crosshair_data, dict):
            self.crosshair.screen_x = float(crosshair_data.get("screen_x", self.crosshair.screen_x))
            self.crosshair.screen_y = float(crosshair_data.get("screen_y", self.crosshair.screen_y))
            self.crosshair.visible = bool(crosshair_data.get("visible", self.crosshair.visible))
            self.crosshair.pane_id = crosshair_data.get("pane_id", self.crosshair.pane_id)

        if self.invalidation_scheduler:
            self.invalidation_scheduler.request_invalidation()

# Added Features:
# - Root public Chart facade object with complete lifecycle, symbol, resolution, chart type, series, indicator, layout pane, drawing shape, selection, subscription, and session persistence APIs.
