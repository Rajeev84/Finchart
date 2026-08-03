"""Selection Manager - Manages selected drawing, hover detection, and drag operations.

Provides centralized state management for drawing tool selection and manipulation.
"""
from __future__ import annotations

from typing import Optional, Dict, Any, List, Tuple, Set
from ..core.events import EventBus, EventType, Event


class SelectionManager:
    """Manages selected drawing, hover detection, and drag operations."""

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._selected_id: Optional[str] = None
        self._selected_ids: Set[str] = set()
        self._hovered_id: Optional[str] = None
        self._drag_mode: Optional[str] = None  # "endpoint", "whole", None
        self._drag_handle: Optional[str] = None  # "p1", "p2", "mid", etc.
        self._drag_start_x: float = 0.0
        self._drag_start_y: float = 0.0
        self._drag_start_index: float = 0.0
        self._drag_start_price: float = 0.0
        self._last_x: float = 0.0
        self._last_y: float = 0.0
        self._last_index: float = 0.0
        self._last_price: float = 0.0

    @property
    def selected_id(self) -> Optional[str]:
        return self._selected_id

    @property
    def selected_ids(self) -> Set[str]:
        return self._selected_ids.copy()

    @property
    def hovered_id(self) -> Optional[str]:
        return self._hovered_id

    @property
    def drag_mode(self) -> Optional[str]:
        return self._drag_mode

    def select(self, shape_id: str, toggle: bool = False, multi: bool = False) -> None:
        if toggle or multi:
            if shape_id in self._selected_ids:
                self._selected_ids.discard(shape_id)
                if self._selected_id == shape_id:
                    self._selected_id = next(iter(self._selected_ids), None)
            else:
                self._selected_ids.add(shape_id)
                self._selected_id = shape_id
            self._event_bus.emit_new(
                EventType.SELECTION_CHANGED, self,
                primary=self._selected_id,
                selected=list(self._selected_ids)
            )
        else:
            old = self._selected_id
            self._selected_ids = {shape_id}
            self._selected_id = shape_id
            self._event_bus.emit_new(
                EventType.SELECTION_CHANGED, self,
                old=old, new=shape_id,
                selected=list(self._selected_ids)
            )

    def select_all(self, shape_ids: List[str]) -> None:
        self._selected_ids = set(shape_ids)
        self._selected_id = shape_ids[0] if shape_ids else None
        self._event_bus.emit_new(
            EventType.SELECTION_CHANGED, self,
            primary=self._selected_id,
            selected=list(self._selected_ids)
        )

    def unselect(self) -> None:
        self._selected_ids.clear()
        self._selected_id = None
        self._event_bus.emit_new(
            EventType.SELECTION_CHANGED, self,
            primary=None, selected=[]
        )

    def is_selected(self, shape_id: str) -> bool:
        return shape_id in self._selected_ids

    def set_hovered(self, shape_id: Optional[str]) -> None:
        if self._hovered_id != shape_id:
            self._hovered_id = shape_id
            self._event_bus.emit_new(EventType.HOVER_CHANGED, self, id=shape_id)

    def start_drag(self, mode: str, handle: Optional[str], x: float, y: float, index: float, price: float) -> None:
        self._drag_mode = mode
        self._drag_handle = handle
        self._drag_start_x = x
        self._drag_start_y = y
        self._drag_start_index = index
        self._drag_start_price = price
        # Initialize last position to start position
        self._last_x = x
        self._last_y = y
        self._last_index = index
        self._last_price = price

    def update_drag(self, x: float, y: float, index: float, price: float) -> Dict[str, Any]:
        """Return delta info for the current drag operation."""
        if self._drag_mode == "endpoint":
            return {"mode": "endpoint", "handle": self._drag_handle, "new_index": index, "new_price": price}
        elif self._drag_mode == "whole":
            # Return INCREMENTAL deltas, not cumulative
            d_pixel_x = x - self._last_x
            d_pixel_y = y - self._last_y
            d_index = index - self._last_index
            d_price = price - self._last_price

            # Update last position for next frame
            self._last_x = x
            self._last_y = y
            self._last_index = index
            self._last_price = price

            return {
                "mode": "whole",
                "d_pixel_x": d_pixel_x,
                "d_pixel_y": d_pixel_y,
                "d_index": d_index,
                "d_price": d_price
            }
        return {}

    def end_drag(self) -> None:
        self._drag_mode = None
        self._drag_handle = None
