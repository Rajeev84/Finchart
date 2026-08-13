"""
FinChart TradingView Input & Event Management Engine (Layer 1.7).
Central framework-independent event normalizer, target resolver, and input dispatcher for ONE FinChart instance.
"""

import math
import time
from typing import Callable, List, Optional
from .constants import DEFAULT_DRAG_THRESHOLD_PX
from .enums import (
    PointerEventType, ClickType, TouchEventType, KeyboardEventType, FocusEventType,
    EventPropagation, HitRegion
)
from .input_events import (
    ModifierState, HitTarget, PointerEvent, WheelEvent, TouchPoint, TouchEvent,
    KeyboardEvent, FocusEvent, ResizeEvent, ChartInputEvent
)
from .hit_tester import HitTester
from .pointer_capture import PointerCaptureManager
from .focus_manager import FocusManager


class InputEngine:
    """Central FinChart Input & Event Management Engine."""

    def __init__(
        self,
        hit_tester: HitTester,
        focus_manager: Optional[FocusManager] = None,
        drag_threshold_px: float = DEFAULT_DRAG_THRESHOLD_PX,
        chart=None
    ):
        self.hit_tester = hit_tester
        self.focus_manager = focus_manager or FocusManager(initial_focus=False)
        self.pointer_capture = PointerCaptureManager()
        self.drag_threshold_px = drag_threshold_px

        self._event_listeners: List[Callable[[ChartInputEvent], None]] = []

        # Internal gesture-tracking state
        self._press_origin_x: float = 0.0
        self._press_origin_y: float = 0.0
        self._press_target: Optional[HitTarget] = None
        self._is_dragging: bool = False
        self._last_pointer_x: float = 0.0
        self._last_pointer_y: float = 0.0
        self._last_click_time: float = 0.0
        self._last_click_button: int = 0

        # Chart container geometry cache
        self.chart_width: float = 800.0
        self.chart_height: float = 600.0
        self.chart = chart

    def add_event_listener(self, listener: Callable[[ChartInputEvent], None]) -> None:
        """Registers a downstream interaction engine handler."""
        self._event_listeners.append(listener)

    def set_chart_dimensions(self, width: float, height: float) -> None:
        self.chart_width = max(1.0, width)
        self.chart_height = max(1.0, height)

    # -------------------------------------------------------------------------
    # Pointer Events
    # -------------------------------------------------------------------------

    def on_pointer_down(
        self,
        screen_x: float,
        screen_y: float,
        button: int = 1,
        buttons_down: int = 1,
        modifiers: Optional[ModifierState] = None,
        pointer_id: int = 1,
        device_type: str = "mouse"
    ) -> ChartInputEvent:
        modifiers = modifiers or ModifierState()

        # Focus acquisition on pointer click
        self.focus_manager.set_focus(True)

        # Hit test (pass authoritative Chart when available, otherwise pass cached dimensions)
        if getattr(self, "chart", None) is not None:
            target = self.hit_tester.hit_test(screen_x, screen_y, self.chart)
        else:
            target = self.hit_tester.hit_test(screen_x, screen_y, self.chart_width, self.chart_height)

        # Initialize press lifecycle
        self._press_origin_x = screen_x
        self._press_origin_y = screen_y
        self._last_pointer_x = screen_x
        self._last_pointer_y = screen_y
        self._press_target = target
        self._is_dragging = False

        # Establish pointer capture
        self.pointer_capture.set_capture(pointer_id, target)

        pe = PointerEvent(
            event_type=PointerEventType.DOWN,
            pointer_id=pointer_id,
            device_type=device_type,
            screen_x=screen_x,
            screen_y=screen_y,
            previous_x=screen_x,
            previous_y=screen_y,
            button=button,
            buttons_down=buttons_down,
            modifiers=modifiers
        )

        evt = ChartInputEvent(input_data=pe, hit_target=target)
        self._dispatch(evt)
        return evt

    def on_pointer_move(
        self,
        screen_x: float,
        screen_y: float,
        buttons_down: int = 0,
        modifiers: Optional[ModifierState] = None,
        pointer_id: int = 1,
        device_type: str = "mouse"
    ) -> ChartInputEvent:
        modifiers = modifiers or ModifierState()

        # Check drag threshold if pointer button is down
        if buttons_down > 0 and not self._is_dragging:
            dx = screen_x - self._press_origin_x
            dy = screen_y - self._press_origin_y
            dist = math.hypot(dx, dy)
            if dist >= self.drag_threshold_px:
                self._is_dragging = True

        # Use captured target if captured, otherwise hit test current position
        if self.pointer_capture.is_captured and self.pointer_capture.captured_pointer_id == pointer_id:
            target = self.pointer_capture.capture_target or HitTarget(target_type=HitRegion.CHART_BACKGROUND)
        else:
            if getattr(self, "chart", None) is not None:
                target = self.hit_tester.hit_test(screen_x, screen_y, self.chart)
            else:
                target = self.hit_tester.hit_test(screen_x, screen_y, self.chart_width, self.chart_height)

        pe = PointerEvent(
            event_type=PointerEventType.MOVE,
            pointer_id=pointer_id,
            device_type=device_type,
            screen_x=screen_x,
            screen_y=screen_y,
            previous_x=self._last_pointer_x,
            previous_y=self._last_pointer_y,
            button=0,
            buttons_down=buttons_down,
            modifiers=modifiers
        )

        self._last_pointer_x = screen_x
        self._last_pointer_y = screen_y

        evt = ChartInputEvent(input_data=pe, hit_target=target)
        self._dispatch(evt)
        return evt

    def on_pointer_up(
        self,
        screen_x: float,
        screen_y: float,
        button: int = 1,
        buttons_down: int = 0,
        modifiers: Optional[ModifierState] = None,
        pointer_id: int = 1,
        device_type: str = "mouse"
    ) -> ChartInputEvent:
        modifiers = modifiers or ModifierState()

        target = self.pointer_capture.capture_target if self.pointer_capture.captured_pointer_id == pointer_id else None
        target = target or (
            self.hit_tester.hit_test(screen_x, screen_y, self.chart) if getattr(self, "chart", None) is not None
            else self.hit_tester.hit_test(screen_x, screen_y, self.chart_width, self.chart_height)
        )

        click_type: Optional[ClickType] = None
        if not self._is_dragging:
            # Click discrimination
            now = time.time()
            if (now - self._last_click_time < 0.3) and (self._last_click_button == button):
                click_type = ClickType.DOUBLE
                self._last_click_time = 0.0
            else:
                click_type = ClickType.SINGLE
                self._last_click_time = now
                self._last_click_button = button

            if button == 2:
                click_type = ClickType.CONTEXT

        pe = PointerEvent(
            event_type=PointerEventType.UP,
            pointer_id=pointer_id,
            device_type=device_type,
            screen_x=screen_x,
            screen_y=screen_y,
            previous_x=self._last_pointer_x,
            previous_y=self._last_pointer_y,
            button=button,
            buttons_down=buttons_down,
            modifiers=modifiers,
            click_type=click_type
        )

        # Release capture
        self.pointer_capture.release_capture(pointer_id)
        self._is_dragging = False

        evt = ChartInputEvent(input_data=pe, hit_target=target)
        self._dispatch(evt)
        return evt

    def on_pointer_cancel(self, pointer_id: int = 1) -> ChartInputEvent:
        target = self.pointer_capture.capture_target or HitTarget(target_type=HitRegion.CHART_BACKGROUND)
        pe = PointerEvent(
            event_type=PointerEventType.CANCEL,
            pointer_id=pointer_id,
            screen_x=self._last_pointer_x,
            screen_y=self._last_pointer_y,
            previous_x=self._last_pointer_x,
            previous_y=self._last_pointer_y
        )
        self.pointer_capture.release_capture(pointer_id)
        self._is_dragging = False

        evt = ChartInputEvent(input_data=pe, hit_target=target)
        self._dispatch(evt)
        return evt

    # -------------------------------------------------------------------------
    # Wheel Events
    # -------------------------------------------------------------------------

    def on_wheel(
        self,
        delta_x: float,
        delta_y: float,
        screen_x: float,
        screen_y: float,
        modifiers: Optional[ModifierState] = None
    ) -> ChartInputEvent:
        modifiers = modifiers or ModifierState()
        if getattr(self, "chart", None) is not None:
            target = self.hit_tester.hit_test(screen_x, screen_y, self.chart)
        else:
            target = self.hit_tester.hit_test(screen_x, screen_y, self.chart_width, self.chart_height)

        we = WheelEvent(
            delta_x=delta_x,
            delta_y=delta_y,
            screen_x=screen_x,
            screen_y=screen_y,
            modifiers=modifiers
        )

        evt = ChartInputEvent(input_data=we, hit_target=target)
        self._dispatch(evt)
        return evt

    # -------------------------------------------------------------------------
    # Touch Events
    # -------------------------------------------------------------------------

    def on_touch(
        self,
        event_type: TouchEventType,
        points: List[TouchPoint],
        prev_points: Optional[List[TouchPoint]] = None
    ) -> ChartInputEvent:
        touch_count = len(points)
        cx = sum(p.screen_x for p in points) / touch_count if touch_count > 0 else 0.0
        cy = sum(p.screen_y for p in points) / touch_count if touch_count > 0 else 0.0

        prev_cx, prev_cy = cx, cy
        if prev_points and len(prev_points) > 0:
            prev_cx = sum(p.screen_x for p in prev_points) / len(prev_points)
            prev_cy = sum(p.screen_y for p in prev_points) / len(prev_points)

        dist = 0.0
        prev_dist = 0.0
        if touch_count >= 2:
            dist = math.hypot(points[0].screen_x - points[1].screen_x, points[0].screen_y - points[1].screen_y)
            if prev_points and len(prev_points) >= 2:
                prev_dist = math.hypot(prev_points[0].screen_x - prev_points[1].screen_x, prev_points[0].screen_y - prev_points[1].screen_y)

        if getattr(self, "chart", None) is not None:
            target = self.hit_tester.hit_test(cx, cy, self.chart)
        else:
            target = self.hit_tester.hit_test(cx, cy, self.chart_width, self.chart_height)

        te = TouchEvent(
            event_type=event_type,
            touch_points=points,
            touch_count=touch_count,
            center_x=cx,
            center_y=cy,
            previous_center_x=prev_cx,
            previous_center_y=prev_cy,
            distance=dist,
            previous_distance=prev_dist
        )

        evt = ChartInputEvent(input_data=te, hit_target=target)
        self._dispatch(evt)
        return evt

    # -------------------------------------------------------------------------
    # Keyboard & Focus Events
    # -------------------------------------------------------------------------

    def on_key(
        self,
        event_type: KeyboardEventType,
        key: str,
        key_code: Optional[int] = None,
        modifiers: Optional[ModifierState] = None,
        repeat: bool = False
    ) -> Optional[ChartInputEvent]:
        # Keyboard commands affect chart only when focused
        if not self.focus_manager.has_focus:
            return None

        modifiers = modifiers or ModifierState()
        ke = KeyboardEvent(
            event_type=event_type,
            key=key,
            key_code=key_code,
            modifiers=modifiers,
            repeat=repeat
        )

        target = HitTarget(target_type=HitRegion.CHART_BACKGROUND)
        evt = ChartInputEvent(input_data=ke, hit_target=target)
        self._dispatch(evt)
        return evt

    def on_focus_change(self, focused: bool) -> ChartInputEvent:
        self.focus_manager.set_focus(focused)
        fe = FocusEvent(event_type=FocusEventType.FOCUS_IN if focused else FocusEventType.FOCUS_OUT)
        target = HitTarget(target_type=HitRegion.CHART_BACKGROUND)
        evt = ChartInputEvent(input_data=fe, hit_target=target)
        self._dispatch(evt)
        return evt

    def on_resize(self, width: float, height: float) -> ChartInputEvent:
        self.set_chart_dimensions(width, height)
        re = ResizeEvent(width=width, height=height)
        target = HitTarget(target_type=HitRegion.CHART_BACKGROUND)
        evt = ChartInputEvent(input_data=re, hit_target=target)
        self._dispatch(evt)
        return evt

    # -------------------------------------------------------------------------
    # Internal Dispatcher
    # -------------------------------------------------------------------------

    def _dispatch(self, event: ChartInputEvent) -> None:
        for listener in self._event_listeners:
            listener(event)

# Added Features:
# - InputEngine managing normalization, hit testing, drag thresholding, pointer capture, wheel routing, touch pinch math, focus gating, and listener dispatching.
