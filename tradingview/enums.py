"""
FinChart TradingView Enums module.
Enumerated types across chart domain model, input management, layout, and event handling.
"""

from enum import Enum, auto


class ChartType(Enum):
    CANDLESTICK = "candlestick"
    BAR = "bar"
    LINE = "line"
    AREA = "area"


class PaneRole(Enum):
    MAIN = "main"
    INDICATOR = "indicator"
    CUSTOM = "custom"


class PlacementMode(Enum):
    OVERLAY = "overlay"
    NEW_PANE = "new_pane"
    EXISTING_PANE = "existing_pane"


class ScalePolicy(Enum):
    AS_SOURCE = "as_source"
    NEW_LEFT = "new_left"
    NEW_RIGHT = "new_right"
    NO_SCALE = "no_scale"


class HitRegion(Enum):
    CHART_BACKGROUND = "chart_background"
    SERIES = "series"
    INDICATOR = "indicator"
    DRAWING_BODY = "drawing_body"
    DRAWING_HANDLE = "drawing_handle"
    PRICE_SCALE = "price_scale"
    TIME_SCALE = "time_scale"
    PANE_BODY = "pane_body"
    PANE_SPLITTER = "pane_splitter"
    CROSSHAIR = "crosshair"
    TOOLBAR = "toolbar"
    UNKNOWN = "unknown"


class PointerEventType(Enum):
    ENTER = "pointer_enter"
    LEAVE = "pointer_leave"
    MOVE = "pointer_move"
    DOWN = "pointer_down"
    UP = "pointer_up"
    CANCEL = "pointer_cancel"


class ClickType(Enum):
    SINGLE = "click"
    DOUBLE = "double_click"
    CONTEXT = "context_click"


class WheelEventType(Enum):
    WHEEL = "wheel"


class TouchEventType(Enum):
    TOUCH_START = "touch_start"
    TOUCH_MOVE = "touch_move"
    TOUCH_END = "touch_end"
    PINCH_START = "pinch_start"
    PINCH_MOVE = "pinch_move"
    PINCH_END = "pinch_end"


class KeyboardEventType(Enum):
    KEY_DOWN = "key_down"
    KEY_UP = "key_up"


class FocusEventType(Enum):
    FOCUS_IN = "focus_in"
    FOCUS_OUT = "focus_out"


class ModifierKey(Enum):
    SHIFT = "shift"
    CTRL = "ctrl"
    ALT = "alt"
    META = "meta"


class PointerButton(Enum):
    NONE = 0
    PRIMARY = 1
    SECONDARY = 2
    MIDDLE = 4


class DeviceType(Enum):
    MOUSE = "mouse"
    TOUCH = "touch"
    PEN = "pen"


class EventPropagation(Enum):
    CONTINUE = "continue"
    HANDLED = "handled"
    IGNORED = "ignored"
    CANCELLED = "cancelled"


class ToolType(Enum):
    CURSOR = "cursor"
    CROSSHAIR = "crosshair"
    TREND_LINE = "trend_line"
    RECTANGLE = "rectangle"
    TEXT = "text"
    ERASER = "eraser"


class LayoutChangeType(Enum):
    PANE_ADDED = "pane_added"
    PANE_REMOVED = "pane_removed"
    PANE_REORDERED = "pane_reordered"
    PANE_RESIZED = "pane_resized"
    PANE_COLLAPSED = "pane_collapsed"
    PANE_VISIBILITY_CHANGED = "pane_visibility_changed"


class ChartRequestEventType(Enum):
    SYMBOL_SELECTION_REQUESTED = "symbol_selection_requested"
    INTERVAL_SELECTION_REQUESTED = "interval_selection_requested"
    CHART_TYPE_SELECTION_REQUESTED = "chart_type_selection_requested"
    DRAWING_SELECTION_REQUESTED = "drawing_selection_requested"
    DRAWING_MOVE_REQUESTED = "drawing_move_requested"
    DRAWING_RESIZE_REQUESTED = "drawing_resize_requested"
    INDICATOR_SELECTION_REQUESTED = "indicator_selection_requested"
    PANE_RESIZE_REQUESTED = "pane_resize_requested"
    VIEWPORT_PAN_REQUESTED = "viewport_pan_requested"
    VIEWPORT_ZOOM_REQUESTED = "viewport_zoom_requested"
    PRICE_SCALE_REQUESTED = "price_scale_requested"
    TIME_SCALE_REQUESTED = "time_scale_requested"
    SAVE_REQUESTED = "save_requested"
    UNDO_REQUESTED = "undo_requested"
    REDO_REQUESTED = "redo_requested"

# Added Features:
# - Standardized all enum types for FinChart layers 1.0 through 1.7.
