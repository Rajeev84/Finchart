"""
DrawingRegistry: dict-like registry for DrawingAPI objects with additional lookup helpers.

Maintains synchronization with ChartState.drawings metadata for persistence.
"""
from typing import Dict, Any, List, Optional, Iterator


class DrawingRegistry:
    def __init__(self, chart_state: Any):
        self._store: Dict[str, Any] = {}
        self._chart_state = chart_state

    # Mapping protocol minimal surface
    def __setitem__(self, key: str, value: Any) -> None:
        self._store[key] = value
        # ensure metadata exists in chart_state.drawings
        if not any(d.get("id") == key for d in self._chart_state.drawings):
            self._chart_state.drawings.append({"id": key, "type": getattr(value, "shape_type", None), "points": getattr(value, "points", [])})

    def __getitem__(self, key: str) -> Any:
        return self._store[key]

    def __delitem__(self, key: str) -> None:
        if key in self._store:
            del self._store[key]
        # remove metadata
        self._chart_state.drawings = [d for d in self._chart_state.drawings if d.get("id") != key]

    def get(self, key: str, default: Optional[Any] = None) -> Optional[Any]:
        return self._store.get(key, default)

    def values(self) -> List[Any]:
        return list(self._store.values())

    def keys(self) -> List[str]:
        return list(self._store.keys())

    def clear(self) -> None:
        self._store.clear()
        self._chart_state.drawings.clear()

    def __contains__(self, key: str) -> bool:
        return key in self._store

    def __iter__(self) -> Iterator[str]:
        return iter(self._store)

    def items(self):
        return self._store.items()

    # Additional helpers
    def find_by_type(self, drawing_type: str) -> List[Any]:
        return [d for d in self._store.values() if getattr(d, "shape_type", None) == drawing_type]

    def search(self, predicate) -> List[Any]:
        return [d for d in self._store.values() if predicate(d)]
