"""
FinChart TradingView Gesture Engine module (Layer 1.9).
Interprets normalized input events into high-level interaction gestures, viewport navigation, and layout mutations.
"""

import math
import threading
from typing import Optional, Any
from .enums import HitRegion, PointerEventType, ClickType, TouchEventType
from .input_events import ChartInputEvent, PointerEvent, WheelEvent, TouchEvent, ModifierState, KeyboardEvent, FocusEvent
from .gesture_state import GestureState, GestureContext
from .selection_manager import SelectionManager
from .chart_layout import ChartLayout
from .viewport_state import ViewportState
from .time_scale import TimeScale
from .price_scale import PriceScale
from .constants import DEFAULT_DRAG_THRESHOLD_PX
from .invalidation import InvalidationScheduler
from .event_subscription import EventRegistry


class GestureEngine:
    """Interprets low-level input events into view navigation and shape gestures."""

    def __init__(
        self,
        layout: ChartLayout,
        viewport: ViewportState,
        time_scale: TimeScale,
        price_scales: dict,
        selection_manager: Optional[SelectionManager] = None,
        invalidation_scheduler: Optional[InvalidationScheduler] = None,
        event_registry: Optional[EventRegistry] = None
    ):
        self.layout = layout
        self.viewport = viewport
        self.time_scale = time_scale
        self.price_scales = price_scales
        self.selection_manager = selection_manager or SelectionManager(event_registry=event_registry)
        self.invalidation_scheduler = invalidation_scheduler
        self.event_registry = event_registry

        self.context = GestureContext()
        self.drag_threshold_px = DEFAULT_DRAG_THRESHOLD_PX
        # Kinetic scroll configuration (decay per frame and number of steps)
        # These can be tuned for finer or coarser kinetic scrolling behavior.
        self.kinetic_decay: float = 0.85
        self.kinetic_steps: int = 12
        self.kinetic_frame_ms: int = 16
        # Runtime kinetic playback state
        self._kinetic_velocity_px: float = 0.0
        self._kinetic_active: bool = False
        self._kinetic_timer: Optional[threading.Timer] = None

    def process_event(self, evt: ChartInputEvent) -> None:
        """Main entrypoint for processing normalized ChartInputEvents from InputEngine."""
        data = evt.input_data
        if isinstance(data, PointerEvent):
            self._handle_pointer(evt, data)
        elif isinstance(data, WheelEvent):
            self._handle_wheel(evt, data)
        elif isinstance(data, TouchEvent):
            self._handle_touch(evt, data)
        elif isinstance(data, KeyboardEvent):
            self._handle_keyboard(evt, data)
        elif isinstance(data, FocusEvent):
            self._handle_focus(evt, data)

    def _handle_keyboard(self, evt: ChartInputEvent, ke: KeyboardEvent) -> None:
        if ke.key in ("Delete", "Backspace", "delete", "backspace"):
            selected = self.selection_manager.get_selected()
            if selected and self.event_registry:
                # Loop through a copy of the list because removing them modifies the selection
                for drawing_id in list(selected):
                    self.event_registry.emit("request_drawing_removal", {"drawing_id": drawing_id})
        elif ke.modifiers.ctrl or ke.modifiers.meta:
            if ke.key.lower() == "z":
                if ke.modifiers.shift:
                    self.event_registry.emit("request_redo", {})
                else:
                    self.event_registry.emit("request_undo", {})
            elif ke.key.lower() == "y":
                self.event_registry.emit("request_redo", {})
            elif ke.key.lower() == "s":
                self.event_registry.emit("request_save", {})

    def _handle_focus(self, evt: ChartInputEvent, fe: FocusEvent) -> None:
        if self.invalidation_scheduler:
            self.invalidation_scheduler.request_invalidation()

    # -------------------------------------------------------------------------
    # Pointer Handling
    # -------------------------------------------------------------------------

    def _handle_pointer(self, evt: ChartInputEvent, pe: PointerEvent) -> None:
        target = evt.hit_target

        if pe.event_type == PointerEventType.DOWN:
            # Interrupt any ongoing kinetic playback when user interacts.
            self.stop_kinetic()
            self.context.press_x = pe.screen_x
            self.context.press_y = pe.screen_y
            self.context.initial_target = target
            self.context.pane_id = target.pane_id or "pane_main"
            self.context.entity_id = target.target_id
            self.context.handle_id = target.handle_id
            self.context.state = GestureState.PRESS_PENDING

            # Capture initial scales/viewport snapshot
            self.context.initial_visible_start = self.viewport.visible_start
            self.context.initial_visible_end = self.viewport.visible_end
            self.context.initial_bar_spacing = self.time_scale.bar_spacing

            p_scale = self.price_scales.get(self.context.pane_id)
            if p_scale:
                self.context.initial_price_min = p_scale.price_min
                self.context.initial_price_max = p_scale.price_max

            pane_model = self.layout.get_pane(self.context.pane_id)
            if pane_model:
                self.context.initial_pane_height = pane_model.height

            # Selection handling on press
            if pe.button == 1:
                is_multi = pe.modifiers.ctrl or pe.modifiers.meta
                if target.target_type in (HitRegion.DRAWING_BODY, HitRegion.DRAWING_HANDLE):
                    if target.target_id:
                        self.selection_manager.select(target.target_id, multi_select=is_multi)
                elif target.target_type in (HitRegion.PANE_BODY, HitRegion.CHART_BACKGROUND):
                    if not is_multi:
                        self.selection_manager.clear_selection()

        elif pe.event_type == PointerEventType.MOVE:
            if pe.buttons_down > 0:
                self._process_drag_movement(pe)

        elif pe.event_type in (PointerEventType.UP, PointerEventType.CANCEL):
            self.context.state = GestureState.IDLE
            self.context.initial_target = None
            if self.invalidation_scheduler:
                self.invalidation_scheduler.request_invalidation()

    def _process_drag_movement(self, pe: PointerEvent) -> None:
        target = self.context.initial_target
        if not target:
            return

        dx = pe.screen_x - self.context.press_x
        dy = pe.screen_y - self.context.press_y

        if self.context.state == GestureState.PRESS_PENDING:
            distance = math.hypot(dx, dy)
            if distance < self.drag_threshold_px:
                return

            # Transition from PRESS_PENDING to active gesture
            if target.target_type == HitRegion.PANE_SPLITTER:
                self.context.state = GestureState.RESIZING_PANE
            elif target.target_type == HitRegion.PRICE_SCALE:
                self.context.state = GestureState.DRAGGING_PRICE_SCALE
            elif target.target_type == HitRegion.TIME_SCALE:
                self.context.state = GestureState.DRAGGING_TIME_SCALE
            elif target.target_type == HitRegion.DRAWING_HANDLE:
                self.context.state = GestureState.RESIZING_SHAPE
            elif target.target_type == HitRegion.DRAWING_BODY:
                self.context.state = GestureState.DRAGGING_SHAPE
            else:
                self.context.state = GestureState.DRAGGING_CHART

        # Execute active gesture
        if self.context.state == GestureState.DRAGGING_CHART:
            self._pan_chart(dx)
        elif self.context.state == GestureState.DRAGGING_PRICE_SCALE:
            self._scale_price(dy)
        elif self.context.state == GestureState.DRAGGING_TIME_SCALE:
            self._scale_time(dx)
        elif self.context.state == GestureState.RESIZING_PANE:
            self._resize_pane(dy)

        if self.invalidation_scheduler:
            self.invalidation_scheduler.request_invalidation()

    # -------------------------------------------------------------------------
    # Gesture Operations
    # -------------------------------------------------------------------------

    def _pan_chart(self, dx_pixels: float) -> None:
        """Executes horizontal chart panning."""
        if self.time_scale.bar_spacing <= 0:
            return
        delta_bars = dx_pixels / self.time_scale.bar_spacing
        # Delegate pan logic to ViewportState
        self.viewport.visible_start = self.context.initial_visible_start
        self.viewport.visible_end = self.context.initial_visible_end
        self.viewport.pan_by_bars(delta_bars)

        new_start = self.viewport.visible_start
        new_end = self.viewport.visible_end

        # Keep TimeScale in sync with the authoritative viewport
        self.time_scale.visible_start = new_start
        self.time_scale.visible_end = new_end

        if self.event_registry:
            self.event_registry.emit("visible_range_changed", {"start": new_start, "end": new_end})

    def _scale_price(self, dy_pixels: float) -> None:
        """Executes price scale dragging."""
        p_scale = self.price_scales.get(self.context.pane_id)
        if not p_scale or p_scale.pane_height <= 0:
            return
        factor = 1.0 + (dy_pixels / p_scale.pane_height)
        factor = max(0.1, min(factor, 5.0))
        center_price = (self.context.initial_price_min + self.context.initial_price_max) / 2.0
        half_span = ((self.context.initial_price_max - self.context.initial_price_min) / 2.0) * factor

        p_scale.set_range(center_price - half_span, center_price + half_span)
        self.viewport.set_pane_price_range(self.context.pane_id, p_scale.price_min, p_scale.price_max)

    def _scale_time(self, dx_pixels: float) -> None:
        """Executes time scale dragging."""
        factor = 1.0 + (dx_pixels / 200.0)
        new_spacing = self.context.initial_bar_spacing * factor
        self.time_scale.set_bar_spacing(new_spacing)
        self.viewport.bar_spacing = self.time_scale.bar_spacing
        self.viewport.visible_start = self.time_scale.visible_start
        self.viewport.visible_end = self.time_scale.visible_end

    def _resize_pane(self, dy_pixels: float) -> None:
        """Executes pane boundary splitter dragging."""
        # Determine available content height (chart height minus time scale area)
        chart_h = getattr(self, "chart_height", None)
        if chart_h is None:
            # fallback to using sum of pane heights as logical content height
            total_content_h = sum(p.height for p in self.layout.get_all_panes())
        else:
            # assume a reserved time scale area of 30px
            total_content_h = max(0.0, chart_h - 30.0)

        # Delegate split resizing to layout with pixel delta
        changed = self.layout.resize_splitter_by_pixels(self.context.pane_id, dy_pixels, total_content_h)
        if changed and self.event_registry:
            self.event_registry.emit("pane_changed", {"pane_id": self.context.pane_id, "action": "resize"})

    # -------------------------------------------------------------------------
    # Wheel & Touch Zooming
    # -------------------------------------------------------------------------

    def _handle_wheel(self, evt: ChartInputEvent, we: WheelEvent) -> None:
        target = evt.hit_target
        if target.target_type == HitRegion.PRICE_SCALE:
            self._wheel_zoom_price(target.pane_id or "pane_main", we.delta_y)
        else:
            self._wheel_zoom_time(we.screen_x, we.delta_y)

    def _wheel_zoom_time(self, cursor_x: float, delta_y: float) -> None:
        """Executes cursor-anchored wheel zooming."""
        zoom_direction = 1.0 if delta_y < 0 else -1.0
        self.time_scale.zoom_at(cursor_x, zoom_direction)
        self.viewport.bar_spacing = self.time_scale.bar_spacing
        self.viewport.visible_start = self.time_scale.visible_start
        self.viewport.visible_end = self.time_scale.visible_end

        if self.event_registry:
            self.event_registry.emit("visible_range_changed", {"start": self.viewport.visible_start, "end": self.viewport.visible_end})

        if self.invalidation_scheduler:
            self.invalidation_scheduler.request_invalidation()

    def _wheel_zoom_price(self, pane_id: str, delta_y: float) -> None:
        p_scale = self.price_scales.get(pane_id)
        if not p_scale:
            return
        factor = 0.9 if delta_y < 0 else 1.1
        center_price = (p_scale.price_min + p_scale.price_max) / 2.0
        half_span = ((p_scale.price_max - p_scale.price_min) / 2.0) * factor
        p_scale.set_range(center_price - half_span, center_price + half_span)

        if self.invalidation_scheduler:
            self.invalidation_scheduler.request_invalidation()

    def _handle_touch(self, evt: ChartInputEvent, te: TouchEvent) -> None:
        if te.event_type == TouchEventType.PINCH_MOVE and te.previous_distance > 0:
            factor = te.distance / te.previous_distance
            self._wheel_zoom_time(te.center_x, -100.0 if factor > 1.0 else 100.0)

    def apply_kinetic_scroll(self, initial_velocity_px: float, steps: int | None = None, decay: float | None = None) -> None:
        """Apply a synchronous, decaying kinetic scroll effect for testing/demo purposes.

        This method applies a series of small pans using the supplied initial velocity in pixels.
        Each step applies the current velocity as a delta, converts to bars, updates viewport and
        time scale, then decays the velocity. It is synchronous to simplify unit testing.
        """
        v = initial_velocity_px
        if steps is None:
            steps = self.kinetic_steps
        if decay is None:
            decay = self.kinetic_decay
        for _ in range(steps):
            if abs(v) < 1e-3:
                break
            dx = v
            # Use current bar spacing to compute bar delta
            if self.time_scale.bar_spacing <= 0:
                break
            delta_bars = dx / self.time_scale.bar_spacing
            self.viewport.pan_by_bars(delta_bars)
            # keep TimeScale in sync
            self.time_scale.visible_start = self.viewport.visible_start
            self.time_scale.visible_end = self.viewport.visible_end
            if self.event_registry:
                self.event_registry.emit("visible_range_changed", {"start": self.viewport.visible_start, "end": self.viewport.visible_end})
            v *= decay

    # -------------------------------------------------------------------------
    # Frame-driven kinetic playback (non-blocking)
    # -------------------------------------------------------------------------

    def start_kinetic(self, initial_velocity_px: float, decay: float | None = None) -> None:
        """Begin frame-driven kinetic scrolling using a background timer and the InvalidationScheduler.

        This schedules repeated pan steps at `self.kinetic_frame_ms` intervals. Playback can be
        interrupted by calling `stop_kinetic()` (automatically invoked on pointer down).
        """
        if decay is None:
            decay = self.kinetic_decay
        # Stop any existing playback
        self.stop_kinetic()
        self._kinetic_velocity_px = initial_velocity_px
        self._kinetic_active = True

        def _schedule_next():
            if not self._kinetic_active:
                return
            # run frame on background thread to avoid blocking callers
            try:
                self._kinetic_frame(decay)
            except Exception:
                pass

        # Kick off first frame immediately
        self._kinetic_timer = threading.Timer(self.kinetic_frame_ms / 1000.0, _schedule_next)
        self._kinetic_timer.daemon = True
        self._kinetic_timer.start()

    def _kinetic_frame(self, decay: float) -> None:
        if not self._kinetic_active:
            return
        v = self._kinetic_velocity_px
        if abs(v) < 1e-3:
            self.stop_kinetic()
            return

        # Apply a single step of kinetic pan
        if self.time_scale.bar_spacing <= 0:
            self.stop_kinetic()
            return
        delta_bars = v / self.time_scale.bar_spacing
        self.viewport.pan_by_bars(delta_bars)
        # keep TimeScale in sync
        self.time_scale.visible_start = self.viewport.visible_start
        self.time_scale.visible_end = self.viewport.visible_end
        if self.event_registry:
            self.event_registry.emit("visible_range_changed", {"start": self.viewport.visible_start, "end": self.viewport.visible_end})

        # Request a render frame
        if self.invalidation_scheduler:
            self.invalidation_scheduler.request_invalidation()

        # Decay velocity and schedule next frame
        self._kinetic_velocity_px *= decay
        if abs(self._kinetic_velocity_px) < 1e-3:
            self.stop_kinetic()
            return

        # Schedule next frame
        self._kinetic_timer = threading.Timer(self.kinetic_frame_ms / 1000.0, lambda: self._kinetic_frame(decay))
        self._kinetic_timer.daemon = True
        self._kinetic_timer.start()

    def stop_kinetic(self) -> None:
        """Stops any active kinetic playback and cancels timers."""
        self._kinetic_active = False
        try:
            if self._kinetic_timer:
                self._kinetic_timer.cancel()
        except Exception:
            pass
        self._kinetic_timer = None

# Added Features:
# - GestureEngine implementing state machine, panning, cursor-anchored zooming, scale dragging, splitter resizing, selection binding, and invalidation triggers.
