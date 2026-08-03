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
        c.bind("<Double-Button-1>", self._on_double_click)

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

        ctrl = (event.state & 0x4) != 0

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
                snapped_index = round(index)  # Round to nearest bar for snapping
                ctx.start_index = snapped_index
                ctx.start_price = price
                ctx.current_index = snapped_index
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
                    points = [(snapped_index, price), (snapped_index + dx, price - dy)]
                elif ctx.tool_type == "longshort":
                    # LongShort is a three-click tool: entry -> width/target -> stop
                    # First click: entry point
                    points = [(snapped_index, price)]
                else:
                    points = [(snapped_index, price), (snapped_index, price)]  # Start and end same initially

                preview_state = DrawingState(
                    id="preview",
                    tool_type=ctx.tool_type,
                    points=points,
                    color=Color(255, 165, 0),
                    fill=Color(255, 165, 0, 0.3) if ctx.tool_type == "rectangle" else None,
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
                # Handle second click for multi-click tools
                from ..drawing.base import DrawingState
                from ..core.types import Color
                import uuid
                import math

                snapped_index = round(index)  # Round to nearest bar for snapping
                
                # LongShort is a three-click tool - move to third click state
                if ctx.tool_type == "longshort":
                    points = list(ctx.preview_shape.points)
                    points.append((snapped_index, price))  # Add target point
                    points.append((snapped_index, price))  # Placeholder for stop point
                    
                    ctx.preview_shape.points = points
                    ctx.preview_tool = self._widget._create_tool(ctx.preview_shape)
                    ctx.state = ToolState.PREVIEW_2  # Move to third click state
                    self._widget._pipeline.force_full_redraw()
                    self._widget._request_render()
                    return
                
                # Finalize two-click tools (TrendLine, AngleLine, Rectangle)
                points = []
                if ctx.tool_type == "angleline":
                    # Calculate y2 based on 45-degree angle from first point
                    dx = snapped_index - ctx.start_index
                    dy = dx * math.tan(math.radians(45))
                    # Invert dy for canvas coordinates
                    points = [(ctx.start_index, ctx.start_price), (snapped_index, ctx.start_price - dy)]
                else:
                    points = [(ctx.start_index, ctx.start_price), (snapped_index, price)]

                state = DrawingState(
                    id=uuid.uuid4().hex,
                    tool_type=ctx.tool_type,
                    points=points,
                    color=Color(255, 165, 0),
                    fill=Color(255, 165, 0, 0.3) if ctx.tool_type == "rectangle" else None,
                    width=2.0,
                    style="solid"
                )
                self._widget.add_drawing(state)
                self._widget.deactivate_tool()
                return
            elif ctx.state == ToolState.PREVIEW_2:
                # Third click: finalize LongShort
                if ctx.tool_type == "longshort":
                    snapped_index = round(index)  # Round to nearest bar for snapping
                    points = list(ctx.preview_shape.points)
                    points[2] = (snapped_index, price)  # Update stop point
                    
                    state = DrawingState(
                        id=uuid.uuid4().hex,
                        tool_type="longshort",
                        points=points,
                        color=Color(255, 165, 0),
                        width=2.0,
                        style="solid",
                        label="1.0"  # Default quantity
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
                        snapped_index = round(index)  # Round to nearest bar for snapping
                        self._widget._selection_manager.start_drag("endpoint", hid, x, y, snapped_index, price)
                        return
                if tool.hit_test(x, y, self._coord, chart_vp):
                    self._widget._selection_manager.start_drag("whole", None, x, y, index, price)
                    return

        # Click on empty canvas: try to select a shape
        if self._widget and not self._widget._tool_context:
            clicked_id = None
            for sid, tool in reversed(list(self._widget._drawing_tools.items())):
                pane_vp = chart_vp if tool.state.pane_name == "candlestick" else self._coord.get_pane_viewport(tool.state.pane_name)
                if tool.hit_test(x, y, self._coord, pane_vp):
                    clicked_id = sid
                    break

            if clicked_id:
                # Support Ctrl+toggle multi-select
                if ctrl:
                    self._widget._selection_manager.select(clicked_id, toggle=True, multi=True)
                else:
                    self._widget._selection_manager.select(clicked_id)

                # TradingView-style: select AND immediately start dragging in one motion
                clicked_tool = self._widget._drawing_tools.get(clicked_id)
                if clicked_tool:
                    handles = clicked_tool.get_handles(self._coord, chart_vp)
                    for hx, hy, hid in handles:
                        if is_point_near_handle(x, y, hx, hy, size=8):
                            snapped_index = round(index)  # Round to nearest bar for snapping
                            self._widget._selection_manager.start_drag("endpoint", hid, x, y, snapped_index, price)
                            return
                    if clicked_tool.hit_test(x, y, self._coord, chart_vp):
                        self._widget._selection_manager.start_drag("whole", None, x, y, index, price)
                        return
                return
            else:
                if not ctrl:
                    self._widget._selection_manager.unselect()

        # Normal panning
        if self._panning_enabled and not ctrl:
            self._is_dragging = True
            self._drag_start_x = event.x
            self._drag_start_offset = self._coord.time_scale.offset
            self._canvas.configure(cursor="fleur")

        self._event_bus.emit_new(EventType.MOUSE_DOWN, self, x=event.x, y=event.y, num=getattr(event, "num", 1), double=False)

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
                    # Incremental deltas from SelectionManager — no cumulative compounding
                    d_index = delta.get("d_index", 0.0)
                    d_price = delta.get("d_price", 0.0)
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
        if self._widget and self._widget._tool_context and self._widget._tool_context.state in (ToolState.PREVIEW, ToolState.PREVIEW_2):
            ctx = self._widget._tool_context
            snapped_index = round(index)  # Round to nearest bar for snapping
            ctx.current_index = snapped_index
            ctx.current_price = price

            if ctx.preview_tool and ctx.preview_shape:
                import math
                if ctx.tool_type == "hline":
                    ctx.preview_shape.points = [(None, price)]
                elif ctx.tool_type == "vline":
                    ctx.preview_shape.points = [(snapped_index, None)]
                elif ctx.tool_type == "angleline":
                    # For angleline, calculate second point based on 45-degree angle from first point
                    dx = snapped_index - ctx.start_index
                    dy = dx * math.tan(math.radians(45))
                    # Invert dy for canvas coordinates
                    ctx.preview_shape.points = [(ctx.start_index, ctx.start_price), (snapped_index, ctx.start_price - dy)]
                elif ctx.tool_type == "longshort":
                    # Handle LongShort preview updates
                    points = list(ctx.preview_shape.points)
                    if ctx.state == ToolState.PREVIEW:
                        # Second point (width/target) being set
                        if len(points) == 1:
                            points.append((snapped_index, price))
                            points.append((snapped_index, price))  # Placeholder for stop
                        else:
                            points[1] = (snapped_index, price)
                            points[2] = (snapped_index, price)
                    elif ctx.state == ToolState.PREVIEW_2:
                        # Third point (stop) being set
                        if len(points) >= 3:
                            points[2] = (snapped_index, price)
                    ctx.preview_shape.points = points
                else:
                    ctx.preview_shape.points = [(ctx.start_index, ctx.start_price), (snapped_index, price)]

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

    def _on_double_click(self, event: tk.Event) -> None:
        """Handle double-click."""
        self._event_bus.emit_new(EventType.MOUSE_DOWN, self, x=event.x, y=event.y, num=2, double=True)

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
        ctrl = (event.state & 0x4) != 0

        if keysym == "escape":
            # Cancel drawing tool if active
            if self._widget and self._widget._tool_context:
                self._widget.deactivate_tool()
            else:
                # Reset time scale offset
                self._coord.time_scale.offset = 0.0
                self._event_bus.emit_new(EventType.SCALE_CHANGED, self, offset=0.0)

        elif keysym == "delete":
            if self._widget:
                self._widget.delete_selected_drawings()

        elif ctrl and keysym == "a":
            if self._widget:
                self._widget.select_all_drawings()

        elif ctrl and keysym == "c":
            if self._widget:
                self._widget._copy_buffer = self._widget.copy_selected_drawings()

        elif ctrl and keysym == "v":
            if self._widget and self._widget._copy_buffer:
                self._widget.paste_drawings(self._widget._copy_buffer)

        self._event_bus.emit_new(EventType.KEY_DOWN, self, keysym=keysym, char=getattr(event, "char", ""))
