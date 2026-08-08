"""Canvas Item Pool - Reusable Tkinter Canvas item allocation manager.

Acquires and recycles C-level Tkinter Canvas item IDs using state="hidden"
to achieve zero allocations during panning and zooming.
"""
from __future__ import annotations

from typing import Dict, List, Optional
import tkinter as tk


class CanvasItemPool:
    """Manages reusable pool of Tkinter Canvas primitive items."""

    def __init__(self, canvas: tk.Canvas) -> None:
        self._canvas = canvas
        self._pools: Dict[str, List[int]] = {
            "line": [],
            "rectangle": [],
            "polygon": [],
            "oval": [],
            "text": [],
        }
        self._in_use: Dict[int, str] = {}

    @property
    def in_use_count(self) -> int:
        """Number of items currently active on canvas."""
        return len(self._in_use)

    @property
    def pooled_count(self) -> int:
        """Total number of items sitting inactive in pool."""
        return sum(len(items) for items in self._pools.values())

    def acquire(self, item_type: str) -> int:
        """Acquire a canvas item of given type ('line', 'rectangle', 'polygon', 'oval', 'text')."""
        if item_type not in self._pools:
            self._pools[item_type] = []

        pool = self._pools[item_type]
        if pool:
            item_id = pool.pop()
        else:
            item_id = self._create_item(item_type)

        self._in_use[item_id] = item_type
        return item_id

    def release(self, item_id: int) -> None:
        """Release an item back to pool and hide it on canvas."""
        if item_id not in self._in_use:
            return

        item_type = self._in_use.pop(item_id)
        try:
            self._canvas.itemconfig(item_id, state="hidden")
        except tk.TclError:
            return

        self._pools[item_type].append(item_id)

    def release_all(self, item_ids: List[int]) -> None:
        """Batch release multiple item IDs."""
        for item_id in item_ids:
            self.release(item_id)

    def _create_item(self, item_type: str) -> int:
        """Create a new hidden Tkinter Canvas item primitive."""
        if item_type == "line":
            return self._canvas.create_line(0, 0, 0, 0, state="hidden")
        elif item_type == "rectangle":
            return self._canvas.create_rectangle(0, 0, 0, 0, state="hidden")
        elif item_type == "polygon":
            return self._canvas.create_polygon(0, 0, 0, 0, state="hidden")
        elif item_type == "oval":
            return self._canvas.create_oval(0, 0, 0, 0, state="hidden")
        elif item_type == "text":
            return self._canvas.create_text(0, 0, text="", state="hidden")
        else:
            return self._canvas.create_line(0, 0, 0, 0, state="hidden")
