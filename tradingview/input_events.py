"""
FinChart TradingView Input Events module (Layer 1.7).
Defines normalized, framework-independent event structures, target descriptions, and request events.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Any
import time
from .enums import (
    HitRegion, PointerEventType, ClickType, WheelEventType, TouchEventType,
    KeyboardEventType, FocusEventType, EventPropagation, ChartRequestEventType
)


@dataclass
class ModifierState:
    shift: bool = False
    ctrl: bool = False
    alt: bool = False
    meta: bool = False


@dataclass
class HitTarget:
    target_type: HitRegion = HitRegion.CHART_BACKGROUND
    target_id: Optional[str] = None
    pane_id: Optional[str] = "pane_main"
    component_id: Optional[str] = None
    handle_id: Optional[str] = None
    handle_role: Optional[str] = None
    hit_distance: float = 0.0
    logical_index: Optional[float] = None
    price_position: Optional[float] = None


@dataclass
class PointerEvent:
    event_type: PointerEventType
    pointer_id: int = 1
    device_type: str = "mouse"
    screen_x: float = 0.0
    screen_y: float = 0.0
    previous_x: float = 0.0
    previous_y: float = 0.0
    button: int = 0
    buttons_down: int = 0
    modifiers: ModifierState = field(default_factory=ModifierState)
    timestamp: float = field(default_factory=time.time)
    click_type: Optional[ClickType] = None


@dataclass
class WheelEvent:
    delta_x: float
    delta_y: float
    screen_x: float
    screen_y: float
    modifiers: ModifierState = field(default_factory=ModifierState)
    timestamp: float = field(default_factory=time.time)


@dataclass
class TouchPoint:
    touch_id: int
    screen_x: float
    screen_y: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class TouchEvent:
    event_type: TouchEventType
    touch_points: List[TouchPoint] = field(default_factory=list)
    touch_count: int = 0
    center_x: float = 0.0
    center_y: float = 0.0
    previous_center_x: float = 0.0
    previous_center_y: float = 0.0
    distance: float = 0.0
    previous_distance: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class KeyboardEvent:
    event_type: KeyboardEventType
    key: str
    key_code: Optional[int] = None
    modifiers: ModifierState = field(default_factory=ModifierState)
    repeat: bool = False
    timestamp: float = field(default_factory=time.time)


@dataclass
class FocusEvent:
    event_type: FocusEventType
    timestamp: float = field(default_factory=time.time)


@dataclass
class ResizeEvent:
    width: float
    height: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class ChartInputEvent:
    """Normalized FinChart Event combining input data, hit target, and propagation status."""
    input_data: Any  # PointerEvent, WheelEvent, TouchEvent, KeyboardEvent, FocusEvent, or ResizeEvent
    hit_target: HitTarget
    pane_local_x: float = 0.0
    pane_local_y: float = 0.0
    propagation: EventPropagation = EventPropagation.CONTINUE

    def stop_propagation(self) -> None:
        self.propagation = EventPropagation.HANDLED

    def cancel(self) -> None:
        self.propagation = EventPropagation.CANCELLED


@dataclass
class ChartRequestEvent:
    request_type: ChartRequestEventType
    payload: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

# Added Features:
# - Normalized event data models (PointerEvent, WheelEvent, TouchEvent, KeyboardEvent, FocusEvent, ResizeEvent, ChartInputEvent, ChartRequestEvent)
