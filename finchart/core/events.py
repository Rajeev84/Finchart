"""Event Bus - Decoupled publish/subscribe messaging system.

Uses Python weakref (weakref.WeakMethod for bound methods and weakref.ref for functions)
to eliminate memory leaks when components or listeners are destroyed.
"""
from __future__ import annotations

import weakref
import inspect
from typing import Callable, Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum, auto


class EventType(Enum):
    """Core event types emitted across FinChart subsystems."""
    DATA_CHANGED = auto()
    VISIBLE_RANGE_CHANGED = auto()
    SCALE_CHANGED = auto()
    LAYOUT_CHANGED = auto()
    HOVER_CHANGED = auto()
    SELECTION_CHANGED = auto()
    CHART_TYPE_CHANGED = auto()
    THEME_CHANGED = auto()
    INDICATOR_ADDED = auto()
    INDICATOR_REMOVED = auto()
    DRAWING_ADDED = auto()
    DRAWING_REMOVED = auto()
    DRAWING_UPDATED = auto()
    ANIMATION_FRAME = auto()
    RESIZE = auto()
    MOUSE_DOWN = auto()
    MOUSE_MOVE = auto()
    MOUSE_UP = auto()
    MOUSE_WHEEL = auto()
    KEY_DOWN = auto()
    KEY_UP = auto()
    REQUEST_RENDER = auto()
    RENDER_COMPLETE = auto()


@dataclass(frozen=True)
class Event:
    """Immutable event payload container."""
    type: EventType
    source: Any
    data: Dict[str, Any]


class EventBus:
    """Central event bus with weak references to prevent memory leaks."""

    def __init__(self) -> None:
        self._subscribers: Dict[EventType, List[Any]] = {}
        self._subscription_info: Dict[int, Tuple[EventType, Any]] = {}
        self._counter = 0
        self._emitting = False
        self._queue: List[Event] = []

    def _make_weak_ref(self, callback: Callable[[Event], None]) -> Any:
        """Create appropriate weak reference for bound method or function."""
        if inspect.ismethod(callback):
            return weakref.WeakMethod(callback)
        return weakref.ref(callback)

    def subscribe(self, event_type: EventType, callback: Callable[[Event], None]) -> int:
        """Subscribe to an event type. Returns subscription ID.
        
        Args:
            event_type: EventType to listen for.
            callback: Listener function receiving Event instance.
            
        Returns:
            int: Subscription ID for un-subscribing.
        """
        self._counter += 1
        sub_id = self._counter

        wref = self._make_weak_ref(callback)
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []

        self._subscribers[event_type].append(wref)
        self._subscription_info[sub_id] = (event_type, wref)
        return sub_id

    def unsubscribe(self, sub_id: int) -> None:
        """Unsubscribe by subscription ID."""
        if sub_id not in self._subscription_info:
            return
        event_type, target_wref = self._subscription_info.pop(sub_id)
        if event_type in self._subscribers:
            self._subscribers[event_type] = [
                ref for ref in self._subscribers[event_type] 
                if ref is not target_wref and ref() is not None
            ]

    def emit(self, event: Event) -> None:
        """Emit an event to all active subscribers.
        
        Recursion-safe: queued if already inside an emit call.
        """
        if self._emitting:
            self._queue.append(event)
            return

        self._emitting = True
        try:
            refs = self._subscribers.get(event.type, [])
            alive_refs = []
            for ref in refs:
                cb = ref()
                if cb is not None:
                    alive_refs.append(ref)
                    try:
                        cb(event)
                    except Exception:
                        pass
            self._subscribers[event.type] = alive_refs
        finally:
            self._emitting = False
            while self._queue:
                queued = self._queue.pop(0)
                self.emit(queued)

    def emit_new(self, event_type: EventType, source: Any, **data) -> None:
        """Convenience method to construct and emit an Event."""
        self.emit(Event(type=event_type, source=source, data=data))
