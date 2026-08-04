"""Interaction Controller - Mouse & Keyboard navigation controller.

Binds mouse wheel zoom around cursor, click-drag pan, crosshair move tracking,
and keyboard shortcuts onto Tkinter Canvas.
"""
from __future__ import annotations

import tkinter as tk
from typing import Optional, Callable, Any

from ..core.events import EventBus, EventType
from ..coordinates.engine import CoordinateEngine


class InteractionController:
    """Manages mouse drag panning, wheel zooming, and focus bindings for Tkinter Canvas."""

    def __init__(self, canvas: tk.Canvas, coord_engine: CoordinateEngine, event_bus: EventBus) -> None:
        self._canvas = canvas
        self._coord = coord_engine
        self._event_bus = event_bus

        self._is_dragging = False
        self._drag_start_x = 0.0
        self._drag_start_offset = 0.0
        self._panning_enabled = True

        self._bind_events()

    @property
    def panning_enabled(self) -> bool:
        return self._panning_enabled

    @panning_enabled.setter
    def panning_enabled(self, enabled: bool) -> None:
        self._panning_enabled = enabled

    def _bind_events(self) -> None:
        """Bind mouse button, motion, wheel, and key events onto canvas."""
        c = self._canvas
        c.bind("<Button-1>", self._on_mouse_down)
        c.bind("<B1-Motion>", self._on_mouse_drag)
        c.bind("<ButtonRelease-1>", self._on_mouse_up)
        c.bind("<Motion>", self._on_mouse_move)
        c.bind("<Leave>", self._on_mouse_leave)

        # Mouse wheel (Windows, macOS, Linux)
        c.bind("<MouseWheel>", self._on_mouse_wheel)
        c.bind("<Button-4>", self._on_mouse_wheel)
        c.bind("<Button-5>", self._on_mouse_wheel)

        # Keyboard shortcuts
        c.bind("<KeyPress>", self._on_key_press)

    def _on_mouse_down(self, event: tk.Event) -> None:
        """Handle mouse press: request canvas focus and initialize drag tracking."""
        self._canvas.focus_set()
        if self._panning_enabled:
            self._is_dragging = True
            self._drag_start_x = event.x
            self._drag_start_offset = self._coord.time_scale.offset
            self._canvas.configure(cursor="fleur")

        self._event_bus.emit_new(EventType.MOUSE_DOWN, self, x=event.x, y=event.y, num=getattr(event, "num", 1))

    def _on_mouse_drag(self, event: tk.Event) -> None:
        """Handle mouse motion while button 1 is pressed (Pan)."""
        if self._is_dragging and self._panning_enabled:
            delta_x = event.x - self._drag_start_x
            self._coord.time_scale.offset = self._drag_start_offset + delta_x
            self._event_bus.emit_new(EventType.SCALE_CHANGED, self, offset=self._coord.time_scale.offset)

        self._event_bus.emit_new(EventType.MOUSE_MOVE, self, x=event.x, y=event.y, dragging=True)

    def _on_mouse_up(self, event: tk.Event) -> None:
        """Handle mouse button release."""
        self._is_dragging = False
        self._canvas.configure(cursor="")
        self._event_bus.emit_new(EventType.MOUSE_UP, self, x=event.x, y=event.y)

    def _on_mouse_move(self, event: tk.Event) -> None:
        """Handle mouse motion across canvas."""
        if not self._is_dragging:
            self._event_bus.emit_new(EventType.MOUSE_MOVE, self, x=event.x, y=event.y, dragging=False)

    def _on_mouse_leave(self, event: tk.Event) -> None:
        """Handle mouse leaving canvas area."""
        self._is_dragging = False
        self._canvas.configure(cursor="")
        self._event_bus.emit_new(
            EventType.MOUSE_MOVE, self, x=-1.0, y=-1.0, dragging=False, leave=True
        )

    def _on_mouse_wheel(self, event: tk.Event) -> None:
        """Handle mouse wheel zoom centered around mouse cursor X position."""
        factor = 1.0
        if getattr(event, "num", 0) == 4 or (hasattr(event, "delta") and event.delta > 0):
            factor = 1.15  # Zoom in
        elif getattr(event, "num", 0) == 5 or (hasattr(event, "delta") and event.delta < 0):
            factor = 0.85  # Zoom out

        if factor != 1.0:
            self._coord.zoom(factor, anchor_x=event.x)

        self._event_bus.emit_new(EventType.MOUSE_WHEEL, self, x=event.x, y=event.y, factor=factor)

    def _on_key_press(self, event: tk.Event) -> None:
        """Handle keyboard shortcuts."""
        keysym = getattr(event, "keysym", "")
        self._event_bus.emit_new(EventType.KEY_DOWN, self, keysym=keysym, char=getattr(event, "char", ""))
