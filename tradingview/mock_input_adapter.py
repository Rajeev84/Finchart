"""
Mock Input Adapter for FinChart (test/demo helper).
Provides a simple programmatic adapter that forwards simulated toolkit events to a connected `InputEngine`.
"""
from typing import Any, Optional
from .input_adapter import InputAdapter
from .input_events import ModifierState, TouchPoint
from .input_engine import InputEngine
from .enums import PointerEventType, TouchEventType, KeyboardEventType


class MockInputAdapter(InputAdapter):
    """Adapter that forwards simulated events to an InputEngine instance.

    Usage:
        adapter = MockInputAdapter(input_engine)
        adapter.bind(container)  # optional container reference
        adapter.simulate_pointer_down(100, 100, button=1)
        adapter.simulate_pointer_move(110, 100, buttons_down=1)
        adapter.simulate_pointer_up(110, 100, button=1)
        adapter.unbind()
    """

    def __init__(self, input_engine: InputEngine):
        self.input_engine = input_engine
        self._container: Optional[Any] = None
        self._bound = False

    def bind(self, container_widget: Any) -> None:
        self._container = container_widget
        self._bound = True

    def unbind(self) -> None:
        self._container = None
        self._bound = False

    # Simulated pointer API
    def simulate_pointer_down(self, x: float, y: float, button: int = 1, pointer_id: int = 1, modifiers: Optional[ModifierState] = None) -> None:
        self.input_engine.on_pointer_down(screen_x=x, screen_y=y, button=button, modifiers=modifiers, pointer_id=pointer_id)

    def simulate_pointer_move(self, x: float, y: float, buttons_down: int = 0, pointer_id: int = 1, modifiers: Optional[ModifierState] = None) -> None:
        self.input_engine.on_pointer_move(screen_x=x, screen_y=y, buttons_down=buttons_down, modifiers=modifiers, pointer_id=pointer_id)

    def simulate_pointer_up(self, x: float, y: float, button: int = 1, pointer_id: int = 1, modifiers: Optional[ModifierState] = None) -> None:
        self.input_engine.on_pointer_up(screen_x=x, screen_y=y, button=button, buttons_down=0, modifiers=modifiers, pointer_id=pointer_id)

    # Wheel
    def simulate_wheel(self, delta_x: float, delta_y: float, x: float, y: float, modifiers: Optional[ModifierState] = None) -> None:
        self.input_engine.on_wheel(delta_x=delta_x, delta_y=delta_y, screen_x=x, screen_y=y, modifiers=modifiers)

    # Keyboard
    def simulate_key(self, event_type: KeyboardEventType, key: str, key_code: int = None, modifiers: Optional[ModifierState] = None, repeat: bool = False) -> None:
        self.input_engine.on_key(event_type=event_type, key=key, key_code=key_code, modifiers=modifiers, repeat=repeat)

    # Touch
    def simulate_touch(self, event_type: TouchEventType, points: list, prev_points: list = None) -> None:
        self.input_engine.on_touch(event_type=event_type, points=points, prev_points=prev_points)

    # Focus
    def simulate_focus(self, focused: bool) -> None:
        self.input_engine.on_focus_change(focused)

    # Resize
    def simulate_resize(self, width: float, height: float) -> None:
        self.input_engine.on_resize(width, height)
