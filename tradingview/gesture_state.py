"""
FinChart TradingView Gesture State module (Layer 1.9).
Defines states and context structures for the Interaction / Gesture state machine.
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, Any
from .input_events import HitTarget


class GestureState(Enum):
    IDLE = "idle"
    PRESS_PENDING = "press_pending"
    DRAGGING_CHART = "dragging_chart"
    DRAGGING_PRICE_SCALE = "dragging_price_scale"
    DRAGGING_TIME_SCALE = "dragging_time_scale"
    ZOOMING_TIME = "zooming_time"
    ZOOMING_PRICE = "zooming_price"
    DRAGGING_SHAPE = "dragging_shape"
    RESIZING_SHAPE = "resizing_shape"
    RESIZING_PANE = "resizing_pane"
    KINETIC_SCROLL = "kinetic_scroll"


@dataclass
class GestureContext:
    state: GestureState = GestureState.IDLE
    press_x: float = 0.0
    press_y: float = 0.0
    initial_target: Optional[HitTarget] = None
    pane_id: str = "pane_main"
    entity_id: Optional[str] = None
    handle_id: Optional[str] = None
    initial_visible_start: float = 0.0
    initial_visible_end: float = 100.0
    initial_bar_spacing: float = 6.0
    initial_price_min: float = 0.0
    initial_price_max: float = 100.0
    initial_pane_height: float = 400.0

# Added Features:
# - GestureState enum and GestureContext dataclass tracking active gesture parameters.
