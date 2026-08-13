"""
FinChart TradingView Selection Manager module (Layer 1.9).
Manages selected chart entities (drawings, components) with multi-selection support.
"""

from typing import List, Optional, Any
from .event_subscription import EventRegistry


class SelectionManager:
    """Manages active entity selection state and multi-selection policies."""

    def __init__(self, event_registry: Optional[EventRegistry] = None):
        self.event_registry = event_registry
        self._selected_ids: List[str] = []

    def get_selected(self) -> List[str]:
        return list(self._selected_ids)

    def is_selected(self, entity_id: str) -> bool:
        return entity_id in self._selected_ids

    def select(self, entity_id: str, multi_select: bool = False) -> None:
        """Selects an entity. If multi_select is False, clears previous selection."""
        changed = False
        if not multi_select and self._selected_ids:
            # We clear the selection. Rather than calling clear_selection directly which
            # triggers multiple events, we clear manually and note the change.
            self._selected_ids.clear()
            changed = True

        if entity_id not in self._selected_ids:
            self._selected_ids.append(entity_id)
            changed = True
            if self.event_registry:
                self.event_registry.emit("drawing_selected", {"entity_id": entity_id})

        if changed and self.event_registry:
            self.event_registry.emit("selection_changed", {"selected": self.get_selected()})

    def deselect(self, entity_id: str) -> None:
        if entity_id in self._selected_ids:
            self._selected_ids.remove(entity_id)
            if self.event_registry:
                self.event_registry.emit("drawing_deselected", {"entity_id": entity_id})
                self.event_registry.emit("selection_changed", {"selected": self.get_selected()})

    def toggle_select(self, entity_id: str) -> None:
        if self.is_selected(entity_id):
            self.deselect(entity_id)
        else:
            self.select(entity_id, multi_select=True)

    def clear_selection(self) -> None:
        if self._selected_ids:
            cleared = list(self._selected_ids)
            self._selected_ids.clear()
            if self.event_registry:
                for eid in cleared:
                    self.event_registry.emit("drawing_deselected", {"entity_id": eid})
                self.event_registry.emit("selection_changed", {"selected": []})

# Added Features:
# - SelectionManager supporting single selection, multi-selection (Ctrl-click), and deselection events.
