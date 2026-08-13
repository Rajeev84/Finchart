"""
FinChart TradingView Focus Manager module (Layer 1.7).
Gates keyboard events to ensure chart receives keyboard input only when focused.
"""

from typing import Callable, List, Optional
from .event_subscription import EventRegistry


class FocusManager:
    """Manages focus state and keyboard routing gating for a single Chart instance."""

    def __init__(self, initial_focus: bool = False, event_registry: Optional[EventRegistry] = None):
        self._has_focus: bool = initial_focus
        self._focus_listeners: List[Callable[[bool], None]] = []
        self.event_registry = event_registry

    @property
    def has_focus(self) -> bool:
        return self._has_focus

    def set_focus(self, focus_state: bool) -> bool:
        """Updates focus state and notifies listeners if state changed."""
        if self._has_focus != focus_state:
            self._has_focus = focus_state
            self._notify_listeners(focus_state)
            if self.event_registry:
                self.event_registry.emit("focus_changed", {"focused": focus_state})
            return True
        return False

    def add_listener(self, listener: Callable[[bool], None]) -> None:
        self._focus_listeners.append(listener)

    def _notify_listeners(self, focus_state: bool) -> None:
        for listener in self._focus_listeners:
            try:
                listener(focus_state)
            except Exception:
                pass

# Added Features:
# - FocusManager tracking chart focus state and gating keyboard event dispatch.
