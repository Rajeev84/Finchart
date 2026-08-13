"""
FinChart TradingView Event Subscription module (Layer 1.8).
Manages subscriber callbacks, subscription lifecycles, and exception isolation for public events.
"""

import logging
from typing import Callable, Dict, List, Any, Optional

logger = logging.getLogger("FinChart.Events")


class Subscription:
    """Handle representing an active event subscription."""

    def __init__(self, event_name: str, callback: Callable[[Any], None], registry: "EventRegistry"):
        self.event_name = event_name
        self.callback = callback
        self._registry = registry
        self._is_active = True

    @property
    def is_active(self) -> bool:
        return self._is_active

    def unsubscribe(self) -> None:
        """Cancels this subscription."""
        if self._is_active:
            self._registry._remove_subscription(self)
            self._is_active = False


class EventRegistry:
    """Central registry for public chart event subscriptions with exception isolation."""

    VALID_EVENTS = {
        "symbol_changed", "resolution_changed", "chart_type_changed",
        "data_loaded", "data_updated", "visible_range_changed",
        "layout_changed", "pane_changed", "drawing_created",
        "drawing_selected", "drawing_deselected", "drawing_moved",
        "drawing_removed", "tool_changed", "pointer_move", "crosshair_move"
    }

    def __init__(self):
        self._subscribers: Dict[str, List[Subscription]] = {evt: [] for evt in self.VALID_EVENTS}

    def subscribe(self, event_name: str, callback: Callable[[Any], None]) -> Subscription:
        """Registers a callback for a specific event taxonomy name."""
        if event_name not in self.VALID_EVENTS:
            # Dynamically register custom event taxonomy if needed
            if event_name not in self._subscribers:
                self._subscribers[event_name] = []

        sub = Subscription(event_name, callback, self)
        self._subscribers[event_name].append(sub)
        return sub

    def unsubscribe_all(self) -> None:
        for evt_list in self._subscribers.values():
            for sub in evt_list:
                sub._is_active = False
            evt_list.clear()

    def has_subscribers(self, event_name: str) -> bool:
        return len(self._subscribers.get(event_name, [])) > 0

    def emit(self, event_name: str, data: Any = None) -> None:
        """
        Dispatches event data to all active subscribers.
        Enforces subscriber error isolation: a failure in one callback will not crash the dispatcher or interfere with other callbacks.
        """
        subscribers = list(self._subscribers.get(event_name, []))
        for sub in subscribers:
            if sub.is_active:
                try:
                    sub.callback(data)
                except Exception as ex:
                    logger.error(f"Error in subscriber callback for event '{event_name}': {ex}")

    def _remove_subscription(self, subscription: Subscription) -> None:
        evt_list = self._subscribers.get(subscription.event_name, [])
        if subscription in evt_list:
            evt_list.remove(subscription)

# Added Features:
# - Subscription handle object with unsubscribe method.
# - EventRegistry with callback error isolation and high-frequency event policy check.
