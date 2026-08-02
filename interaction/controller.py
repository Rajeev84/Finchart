"""Interaction Controller - Mouse & Keyboard navigation controller.

Binds mouse wheel zoom around cursor, click-drag pan, crosshair move tracking,
and keyboard shortcuts onto Tkinter Canvas.
"""
from __future__ import annotations

import tkinter as tk
from typing import Optional, Callable, Any

from ..core.events import EventBus, EventType
from ..coordinates.engine import CoordinateEngine
from ..interaction.hit_test import is_point_near_handle
from ..interaction.tool_state import ToolState


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

        # Drawing tool integration
        self._widget: Optional[Any] = None  # ChartWidget reference

        self._bind_events()

    def set_widget(self, widget: Any) -> None:
        """Set reference to ChartWidget for drawing tool integration."""
        self._widget = widget

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
        c.bind("<Button-3>", self._on_right_click)  # Right-click cancel

        # Mouse wheel (Windows, macOS, Linux)
        c.bind("<MouseWheel>", self._on_mouse_wheel)
        c.bind("<Button-4>", self._on_mouse_wheel)
        c.bind("<Button-5>", self._on_mouse_wheel)

        # Keyboard shortcuts
        c.bind("<KeyPress>", self._on_key_press)

    def _on_mouse_down(self, event: tk.Event) -> None:
        """Handle mouse press: request canvas focus and initialize drag tracking."""
        self._canvas.focus_set()

        x, y = event.x, event.y
        index = self._coord.x_to_index(x)
        chart_vp = self._widget._grid_renderer.get_chart_viewport() if self._widget else self._coord.viewport
        price = self._coord.y_to_price(y, chart_vp)

        # Drawing tool integration
        if self._widget and self._widget._tool_context:
            ctx = self._widget._tool_context
            if ctx.state == ToolState.WAIT_FIRST_CLICK:
                # HLine and VLine are single-click tools
                if ctx.tool_type == "hline":
                    from ..drawing.base import DrawingState
                    from ..core.types import Color
                    import uuid
                    state = DrawingState(
                        id=uuid.uuid4().hex,
                        tool_type="hline",
                        points=[(None, price)],
                        color=Color(255, 165, 0),
                        width=2.0,
                        style="solid"
                    )
                    self._widget.add_drawing(state)
                    self._widget.deactivate_tool()
                    return
                elif ctx.tool_type == "vline":
                    from ..drawing.base import DrawingState
                    from ..core.types import Color
                    import uuid
                    state = DrawingState(
                        id=uuid.uuid4().hex,
                        tool_type="vline",
                        points=[(index, None)],
                        color=Color(255, 165, 0),
                        width=2.0,
                        style="solid"
                    )
                    self._widget.add_drawing(state)
                    self._widget.deactivate_tool()
                    return

                # Two-click tools (TrendLine, AngleLine, Rectangle)
                ctx.start_index = index
                ctx.start_price = price
                ctx.current_index = index
                ctx.current_price = price
                ctx.state = ToolState.PREVIEW
                # Create preview shape
                from ..drawing.base import DrawingState
                from ..core.types import Color
                import math

                points = []
                if ctx.tool_type == "angleline":
                    # For angleline, calculate second point based on 45-degree angle
                    # Use a fixed distance for preview
                    dx = 20.0  # index distance
                    dy = dx * math.tan(math.radians(45))  # price change at 45 degrees
                    # Invert dy because canvas Y increases downward
                    points = [(index, price), (index + dx, price - dy)]
                else:
                    points = [(index, price), (index, price)]  # Start and end same initially

                preview_state = DrawingState(
                    id="preview",
                    tool_type=ctx.tool_type,
                    points=points,
                    color=Color(255, 165, 0),
                    width=2.0,
                    style="solid",
                    visible=True
                )
                ctx.preview_shape = preview_state
                ctx.preview_tool = self._widget._create_tool(preview_state)
                self._widget._pipeline.force_full_redraw()
                self._widget._request_render()
                return
            elif ctx.state == ToolState.PREVIEW:
                # Finalize drawing
                from ..drawing.base import DrawingState
                from ..core.types import Color
                import uuid
                import math

                points = []
                if ctx.tool_type == "angleline":
                    # Calculate y2 based on 45-degree angle from first point
                    dx = index - ctx.start_index
                    dy = dx * math.tan(math.radians(45))
                    # Invert dy for canvas coordinates
                    points = [(ctx.start_index, ctx.start_price), (index, ctx.start_price - dy)]
                else:
                    points = [(ctx.start_index, ctx.start_price), (index, price)]

                state = DrawingState(
                    id=uuid.uuid4().hex,
                    tool_type=ctx.tool_type,
                    points=points,
                    color=Color(255, 165, 0),
                    width=2.0,
                    style="solid"
                )
                self._widget.add_drawing(state)
                self._widget.deactivate_tool()
                return

        # Normal mode: check for handle/line hit
        if self._widget and self._widget._selection_manager.selected_id:
            tool = self._widget._drawing_tools.get(self._widget._selection_manager.selected_id)
            if tool:
                handles = tool.get_handles(self._coord, chart_vp)
                for hx, hy, hid in handles:
                    if is_point_near_handle(x, y, hx, hy, size=8):
                        self._widget._selection_manager.start_drag("endpoint", hid, x, y, index, price)
                        return
                if tool.hit_test(x, y, self._coord, chart_vp):
                    self._widget._selection_manager.start_drag("whole", None, x, y, index, price)
                    return

        # Click on empty canvas: try to select a shape
        if self._widget and not self._widget._tool_context:
            clicked_id = None
            for sid, tool in reversed(list(self._widget._drawing_tools.items())):
                if tool.hit_test(x, y, self._coord, chart_vp):
                    clicked_id = sid
                    break

            if clicked_id:
                self._widget._selection_manager.select(clicked_id)
                # Don't start panning when selecting a shape
                self._is_dragging = False
                self._canvas.configure(cursor="")
                return
            else:
                self._widget._selection_manager.unselect()

        # Normal panning
        if self._panning_enabled:
            self._is_dragging = True
            self._drag_start_x = event.x
            self._drag_start_offset = self._coord.time_scale.offset
            self._canvas.configure(cursor="fleur")

        self._event_bus.emit_new(EventType.MOUSE_DOWN, self, x=event.x, y=event.y, num=getattr(event, "num", 1))

    def _on_mouse_drag(self, event: tk.Event) -> None:
        """Handle mouse motion while button 1 is pressed (Pan)."""
        x, y = event.x, event.y
        index = self._coord.x_to_index(x)
        chart_vp = self._widget._grid_renderer.get_chart_viewport() if self._widget else self._coord.viewport
        price = self._coord.y_to_price(y, chart_vp)

        # Drawing tool drag mode
        if self._widget and self._widget._selection_manager.drag_mode:
            delta = self._widget._selection_manager.update_drag(x, y, index, price)
            tool = self._widget._drawing_tools.get(self._widget._selection_manager.selected_id)
            if tool:
                if delta["mode"] == "endpoint":
                    tool.move_endpoint(delta["handle"], delta["new_index"], delta["new_price"])
                elif delta["mode"] == "whole":
                    # Convert pixel deltas to index/price deltas for smooth movement
                    chart_vp = self._widget._grid_renderer.get_chart_viewport()
                    d_index = delta["d_pixel_x"] / self._coord.time_scale.bar_spacing if self._coord.time_scale.bar_spacing > 0 else 0
                    
                    # Convert Y pixel delta to price delta using chart viewport
                    y1 = self._coord.y_to_price(self._widget._selection_manager._drag_start_y, chart_vp)
                    y2 = self._coord.y_to_price(self._widget._selection_manager._drag_start_y + delta["d_pixel_y"], chart_vp)
                    d_price = y2 - y1
                    
                    tool.move_whole(d_index, d_price)
                self._widget._pipeline.force_full_redraw()
                self._widget._request_render()
            self._event_bus.emit_new(EventType.MOUSE_MOVE, self, x=event.x, y=event.y, dragging=True)
            return

        # Normal panning
        if self._is_dragging and self._panning_enabled:
            delta_x = event.x - self._drag_start_x
            self._coord.time_scale.offset = self._drag_start_offset + delta_x
            self._event_bus.emit_new(EventType.SCALE_CHANGED, self, offset=self._coord.time_scale.offset)

        self._event_bus.emit_new(EventType.MOUSE_MOVE, self, x=event.x, y=event.y, dragging=True)

    def _on_mouse_up(self, event: tk.Event) -> None:
        """Handle mouse button release."""
        self._is_dragging = False
        self._canvas.configure(cursor="")

        # End drawing tool drag
        if self._widget and self._widget._selection_manager.drag_mode:
            self._widget._selection_manager.end_drag()

        self._event_bus.emit_new(EventType.MOUSE_UP, self, x=event.x, y=event.y)

    def _on_mouse_move(self, event: tk.Event) -> None:
        """Handle mouse motion across canvas."""
        x, y = event.x, event.y
        index = self._coord.x_to_index(x)
        chart_vp = self._widget._grid_renderer.get_chart_viewport() if self._widget else self._coord.viewport
        price = self._coord.y_to_price(y, chart_vp)

        # Update preview shape during drawing
        if self._widget and self._widget._tool_context and self._widget._tool_context.state == ToolState.PREVIEW:
            ctx = self._widget._tool_context
            ctx.current_index = index
            ctx.current_price = price

            if ctx.preview_tool and ctx.preview_shape:
                import math
                if ctx.tool_type == "hline":
                    ctx.preview_shape.points = [(None, price)]
                elif ctx.tool_type == "vline":
                    ctx.preview_shape.points = [(index, None)]
                elif ctx.tool_type == "angleline":
                    # For angleline, calculate second point based on 45-degree angle from first point
                    dx = index - ctx.start_index
                    dy = dx * math.tan(math.radians(45))
                    # Invert dy for canvas coordinates
                    ctx.preview_shape.points = [(ctx.start_index, ctx.start_price), (index, ctx.start_price - dy)]
                else:
                    ctx.preview_shape.points = [(ctx.start_index, ctx.start_price), (index, price)]

                self._widget._pipeline.force_full_redraw()
                self._widget._request_render()
                return

        if not self._is_dragging:
            self._event_bus.emit_new(EventType.MOUSE_MOVE, self, x=event.x, y=event.y, dragging=False)

    def _on_mouse_leave(self, event: tk.Event) -> None:
        """Handle mouse leaving canvas area."""
        self._is_dragging = False
        self._canvas.configure(cursor="")
        self._event_bus.emit_new(
            EventType.MOUSE_MOVE, self, x=-1.0, y=-1.0, dragging=False, leave=True
        )

    def _on_right_click(self, event: tk.Event) -> None:
        """Handle right-click to cancel drawing tool."""
        if self._widget and self._widget._tool_context:
            self._widget.deactivate_tool()

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
        keysym = event.keysym.lower()
        if keysym == "escape":
            # Cancel drawing tool if active
            if self._widget and self._widget._tool_context:
                self._widget.deactivate_tool()
            else:
                # Reset time scale offset
                self._coord.time_scale.offset = 0.0
                self._event_bus.emit_new(EventType.SCALE_CHANGED, self, offset=0.0)
        self._event_bus.emit_new(EventType.KEY_DOWN, self, keysym=keysym, char=getattr(event, "char", ""))
