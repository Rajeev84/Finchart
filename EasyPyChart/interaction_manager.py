"""
InteractionManager for EasyPyChart
Handles user input events, manages drawing tools, and implements the Tool State Machine.
"""

import time
import copy
from datetime import datetime


class InteractionManager:
    def __init__(self, chart, layout_manager):
        self.chart = chart
        self.layout = layout_manager

        # State
        self.mode = "NORMAL"  # NORMAL, DRAWING
        self.active_tool = None
        self.mode = "NORMAL"  # NORMAL, DRAWING
        self.active_tool = None
        self.selected_tag = None
        self.dragging_shape = None
        self.drag_start_data = None  # (time, price) tuple
        self.resizing_shape = None
        self.resize_handle = None
        self.resize_start_points = None
        self.resize_start_data = None

        # Capture State for get_click_cords
        self.capture_state = None
        # { 'target': N, 'points': [], 'render': fn, 'final': fn }
        self.active_angle = 45.0

        # Bind validation
        # self.connect() # Manually called by user? Or auto?
        # Ideally we wrap the chart's existing callback.
        self._original_callback = self.chart.callback
        self.chart.callback = self.process_event

    def process_event(self, event_type, data):
        """Main Event Dispatcher."""

        # 1. Capture Mode (Highest Priority)
        if self.capture_state:
            self._handle_capture(event_type, data)
            # Use return to consume event?
            # Or pass through? Usually capture consumes clicks.
            if event_type in ["click", "move"]:
                return

        # 2. Drawing Mode (Legacy / Simple Tools)
        # (If we use capture_state for everything, this might be redundant)

        # Pass through to original callback if needed (for UI logging etc)
        # USER REQUEST: Fire standard event BEFORE shape events ("first left click then a shape-select")
        if self._original_callback:
            self._original_callback(event_type, data)

        # 3. Normal Mode (Selection, Pan)
        if self.mode == "NORMAL":
            self._handle_normal(event_type, data)

    def _handle_capture(self, event_type, data):
        c = self.capture_state

        if event_type == "move":
            # Live Preview
            # Points = Captured + [Current Cursor]
            cursor_pt = (data["time"], data["y"])
            if cursor_pt[0] is None:
                return

            c["sub_plot"] = data.get("sub_plot")
            preview_points = c["points"] + [cursor_pt]

            # Call render callback
            if c["render"]:
                c["render"](preview_points)

        elif event_type == "click" and data.get("button") == "left":
            # Add Point
            pt = (data["time"], data["y"])
            if pt[0] is None:
                return

            c["sub_plot"] = data.get("sub_plot")
            c["points"].append(pt)

            # Signal point-capture
            if self._original_callback:
                self._original_callback(
                    "point-capture",
                    {
                        "captured": len(c["points"]),
                        "target": c["target"],
                        "points": c["points"],
                    },
                )

            # Check completion
            if len(c["points"]) >= c["target"]:
                # Finalize
                if c["final"]:
                    c["final"](c["points"])

                # Cleanup
                # Only stop capture if we haven't started a new one (chained capture)
                if self.capture_state == c:
                    self.stop_capture()

        elif event_type == "key" and data.get("key") in [
            "Escape",
            "BackSpace",
            "Delete",
        ]:
            self.stop_capture()
        elif event_type == "click" and data.get("button") == "right":
            self.stop_capture()

    def get_click_cords(
        self, num_points, on_update=None, on_complete=None, tool_name=None
    ):
        """
        Starts a point capture session.
        Args:
            num_points: Number of points to capture.
            on_update: fn(points) -> void (Draw ghost)
            on_complete: fn(points) -> void (Commit)
        """
        self.mode = "DRAWING"
        self.capture_state = {
            "target": num_points,
            "points": [],
            "render": on_update,
            "final": on_complete,
        }
        print(f"InteractionManager: Started capture for {num_points} points.")

        # Signal tool-start
        if self._original_callback:
            self._original_callback(
                "tool-start", {"target": num_points, "tool": tool_name}
            )

    def stop_capture(self):
        """Cancels any active capture."""
        self.capture_state = None
        self.mode = "NORMAL"
        # Clear all ghost shapes
        ghost_tags = [
            "ghost",
            "ghost_rect_sl",
            "ghost_text_entry",
            "ghost_text_sl",
            "ghost_rect_tgt",
            "ghost_text_tgt",
        ]
        any_deleted = False
        for tag in ghost_tags:
            if tag in self.chart.drawings:
                del self.chart.drawings[tag]
                any_deleted = True
        if any_deleted:
            self.chart.render()
        print("InteractionManager: Capture stopped.")

        # Signal capture-stop
        if self._original_callback:
            self._original_callback("capture-stop", {})

    def set_color(self, color):
        """Updates the active drawing color."""
        self.active_color = color
        print(f"InteractionManager: Color set to {color}")

    def _get_related_tags(self, tag):
        """Finds all tags related to the given tag based on Group ID conventions."""
        if not tag:
            return []

        parts = tag.split("_")
        if len(parts) >= 2:
            # Define prefixes that imply a grouped unit
            group_prefixes = ["PosUnit"]

            if parts[0] in group_prefixes:
                # Group Key is Prefix_UID (e.g. PosUnit_1736...)
                prefix_key = f"{parts[0]}_{parts[1]}"
                return [
                    t for t in self.chart.drawings.keys() if t.startswith(prefix_key)
                ]

        return [tag]

    def _event_point(self, data):
        """Returns the current chart-space point from an event payload."""
        dt = data.get("time")
        price = data.get("y")

        if dt is None and self.chart.data and data.get("x") is not None:
            try:
                dt = self.chart.data.get_time_from_index(data["x"])
            except Exception:
                dt = None

        return dt, price

    def _normalize_rect_shape_points(self, points):
        """Normalize rect points into left/top and right/bottom order."""
        if len(points) < 2:
            return points

        (dt1, price1), (dt2, price2) = points[:2]
        left_dt, right_dt = (dt1, dt2)

        if self.chart.data and hasattr(self.chart.data, "get_index_from_time"):
            try:
                idx1 = self.chart.data.get_index_from_time(dt1)
                idx2 = self.chart.data.get_index_from_time(dt2)
                if idx1 > idx2:
                    left_dt, right_dt = right_dt, left_dt
            except Exception:
                if dt1 > dt2:
                    left_dt, right_dt = right_dt, left_dt
        elif dt1 > dt2:
            left_dt, right_dt = dt2, dt1

        top_price = max(price1, price2)
        bottom_price = min(price1, price2)
        return [(left_dt, top_price), (right_dt, bottom_price)]

    def _resize_shape_points(self, tag, handle, original_points, data):
        """Calculate resized points for the active shape."""
        current_dt, current_price = self._event_point(data)
        if current_dt is None or current_price is None or len(original_points) < 2:
            return original_points

        shape = self.chart.drawings.get(tag, {})
        shape_type = shape.get("type")
        p0 = tuple(original_points[0])
        p1 = tuple(original_points[1])

        if shape_type == "line":
            if handle == "start":
                return [(current_dt, current_price), p1]
            if handle == "end":
                return [p0, (current_dt, current_price)]
            return original_points

        if shape_type == "rect":
            points = list(self._normalize_rect_shape_points(original_points))
            left_dt, top_price = points[0]
            right_dt, bottom_price = points[1]

            if isinstance(tag, str) and tag.startswith("PosUnit_"):
                if handle == "lt":
                    return [(current_dt, current_price), (right_dt, bottom_price)]
                if handle == "lm":
                    return [(current_dt, top_price), (right_dt, bottom_price)]
                if handle == "lb":
                    return [(current_dt, top_price), (right_dt, current_price)]
                return points

            if handle == "tl":
                return [(current_dt, current_price), (right_dt, bottom_price)]
            if handle == "br":
                return [(left_dt, top_price), (current_dt, current_price)]
            return points

        return original_points

    def _finish_resize(self):
        self.resizing_shape = None
        self.resize_handle = None
        self.resize_start_points = None
        self.resize_start_data = None
        self.chart.selected_handle_tag = None

    def _handle_normal(self, event_type, data):
        # 1. Release Logic
        if event_type == "release":
            if self.resizing_shape:
                print(f"InteractionManager: Resized {self.resizing_shape} via {self.resize_handle}")
                if self._original_callback:
                    self._original_callback(
                        "shape-drop",
                        {
                            "shape": self.resizing_shape,
                            "mode": "resize",
                            "handle": self.resize_handle,
                        },
                    )
                self._finish_resize()
                return
            if self.dragging_shape:
                print(f"InteractionManager: Dropped {self.dragging_shape}")
                # EMIT: shape-drop
                if self._original_callback:
                    # Provide shape tag and maybe new coords? The receiver can query coords.
                    self._original_callback(
                        "shape-drop", {"shape": self.dragging_shape}
                    )

                # Commit change to LayoutManager?
                # LayoutManager stores "Safe Copy" on set_context.
                # But it also relies on current chart.drawings for runtime.
                # So we just leave it modified on chart.
                # On next context switch, it will be saved.

                self.dragging_shape = None
                self.drag_start_data = None
            return

        # 2. Click Logic (Selection & Drag Start)
        if event_type == "click" and data.get("button") == "left":
            # Check for shape hit
            if data.get("shape_handle") and data.get("shape"):
                self.selected_tag = data["shape"]

                related = self._get_related_tags(self.selected_tag)
                self.chart.selected_tags = set(related)
                self.chart.selected_handle_tag = self.selected_tag

                self.resizing_shape = self.selected_tag
                self.resize_handle = data.get("shape_handle")
                self.resize_start_data = (data["time"], data["y"])
                shape = self.chart.drawings.get(self.selected_tag)
                self.resize_start_points = copy.deepcopy(shape["points"]) if shape else None
                self.dragging_shape = None
                self.drag_start_data = None

                self.chart.render()
                print(f"Selected resize handle: {self.selected_tag} ({self.resize_handle})")

                if self._original_callback:
                    self._original_callback(
                        "shape-select",
                        {"shape": self.selected_tag, "handle": self.resize_handle},
                    )

                self.chart.drag_start = None

            elif data.get("shape"):
                self.selected_tag = data["shape"]

                # Group Selection
                related = self._get_related_tags(self.selected_tag)
                self.chart.selected_tags = set(related)
                self.chart.selected_handle_tag = self.selected_tag

                self.chart.render()
                print(f"Selected: {self.selected_tag} (Group: {len(related)})")

                # EMIT: shape-select
                if self._original_callback:
                    self._original_callback(
                        "shape-select", {"shape": self.selected_tag}
                    )

                # Start Dragging
                self.dragging_shape = self.selected_tag
                self.drag_start_data = (data["time"], data["y"])
                self.resizing_shape = None
                self.resize_handle = None
                self.resize_start_points = None
                self.resize_start_data = None

                # CRITICAL: Stop Core Panning
                self.chart.drag_start = None

            else:
                if self.selected_tag:
                    self.selected_tag = None
                    self.chart.selected_tag = None
                    self.chart.selected_handle_tag = None
                    self.chart.render()
                    print("Deselected")
                    # EMIT: shape-deselect
                    if self._original_callback:
                        self._original_callback("shape-deselect", {})

        # 3. Drag/Move Logic
        elif event_type in ["move", "drag"]:
            if self.resizing_shape and self.resize_start_points:
                shape = self.chart.drawings.get(self.resizing_shape)
                if not shape:
                    return

                new_points = self._resize_shape_points(
                    self.resizing_shape,
                    self.resize_handle,
                    self.resize_start_points,
                    data,
                )
                shape["points"] = new_points
                self.chart.render()
                return

            if self.dragging_shape and self.drag_start_data:
                # Calculate Delta
                current_time = data["time"]
                current_price = data["y"]

                if current_time is None or current_price is None:
                    return

                start_time, start_price = self.drag_start_data

                # Check Subplot Constraint
                shape = self.chart.drawings.get(self.dragging_shape)
                if not shape:
                    return

                target_plot = shape.get("plot", "candlestick")
                current_plot = data.get("sub_plot")

                # Logic: If current mouse is in a different plot, IGNORE Y change.
                # Allow time change (horizontal drag across plots is fine).
                if current_plot != target_plot:
                    # Clamp Y: Treat price_delta as 0 (keep Y constant)
                    price_delta = 0
                else:
                    try:
                        price_delta = current_price - start_price
                    except:
                        price_delta = 0

                try:
                    time_delta = current_time - start_time
                except:
                    time_delta = pd.Timedelta(0)  # Should be valid

                # Apply to shape (and related group)
                if shape:
                    related = self._get_related_tags(self.dragging_shape)
                    for t_tag in related:
                        s = self.chart.drawings.get(t_tag)
                        if not s:
                            continue

                        updated_pts = []
                        for t, p in s["points"]:
                            updated_pts.append((t + time_delta, p + price_delta))
                        s["points"] = updated_pts

                    # Update start data for next delta.
                    # CRITICAL: If we clamped Y, we must NOT update start_price to current_price
                    # because current_price is in the wrong scale/plot!
                    # We should keep start_price as is? No, delta is relative to start.
                    # Best way: New Start = Old Start + Allowed Delta.

                    new_start_time = start_time + time_delta
                    new_start_price = start_price + price_delta

                    self.drag_start_data = (new_start_time, new_start_price)
                    self.chart.render()
                else:
                    # Shape might have been deleted while dragging?
                    self.dragging_shape = None

        elif event_type == "key" and data.get("key") == "Delete":
            if self.selected_tag:
                print(f"InteractionManager: Deleting {self.selected_tag}")

                # EMIT: shape-delete
                # Must emit BEFORE actual deletion if we want to pass info, or AFTER if we just pass tag.
                # Usually AFTER is fine for 'deleted'.
                deleted_tag = self.selected_tag

                # Group Deletion
                related = self._get_related_tags(self.selected_tag)
                for t in related:
                    self.layout.remove_drawing(t)

                self.selected_tag = None
                self.chart.selected_tags = set()
                self.chart.render()

                if self._original_callback:
                    self._original_callback("shape-delete", {"shape": deleted_tag})

    # --- Tool Presets ---
    def set_tool(self, tool_name):
        self.stop_capture()

        # Get active color (default to red if not set)
        active_color = getattr(self, "active_color", "#FF0000")

        if tool_name == "line":
            self.get_click_cords(
                num_points=2,
                on_update=lambda pts: self.chart.create_line(
                    pts[0][0],
                    pts[0][1],
                    pts[-1][0],
                    pts[-1][1],
                    color="blue",
                    label="Ghost",
                    tags="ghost",
                    dash=(4, 4),
                ),
                on_complete=lambda pts, ts=int(time.time()): (
                    self.layout.add_drawing(
                        f"line_{ts}",
                        "line",
                        pts,
                        color=active_color,
                        width=2,
                        label="Line",
                    ),
                    (
                        self._original_callback(
                            "shape-create", {"shape": f"line_{ts}", "type": "line"}
                        )
                        if self._original_callback
                        else None
                    ),
                ),
                tool_name=tool_name,
            )

        elif tool_name == "rect":
            self.get_click_cords(
                num_points=2,
                on_update=lambda pts: self.chart.create_rectangle(
                    pts[0][0],
                    pts[0][1],
                    pts[-1][0],
                    pts[-1][1],
                    fill_color=active_color,
                    label="GhostZone",
                    tags="ghost",
                    outline_color=active_color,
                    stipple="gray25",
                ),
                on_complete=lambda pts, ts=int(time.time()): (
                    self.layout.add_drawing(
                        f"rect_{ts}",
                        "rect",
                        pts,
                        fill_color=active_color,
                        outline_color=active_color,
                        label="Zone",
                        stipple="gray25",
                    ),
                    (
                        self._original_callback(
                            "shape-create", {"shape": f"rect_{ts}", "type": "rect"}
                        )
                        if self._original_callback
                        else None
                    ),
                ),
                tool_name=tool_name,
            )

        elif tool_name == "hline":
            # HLine needs 1 click (Price level)
            # But visual preview needs to show the line following Mouse Y
            self.get_click_cords(
                num_points=1,
                on_update=lambda pts: self.chart.create_hline(
                    pts[-1][1], color="white", label="Ghost", tags="ghost", dash=(4, 4)
                ),
                on_complete=lambda pts, ts=int(time.time()): (
                    self.layout.add_drawing(
                        f"hline_{ts}",
                        "hline",
                        pts,
                        color=active_color,
                        width=1,
                        label="Level",
                    ),
                    (
                        self._original_callback(
                            "shape-create", {"shape": f"hline_{ts}", "type": "hline"}
                        )
                        if self._original_callback
                        else None
                    ),
                ),
                tool_name=tool_name,
            )

        elif tool_name == "vline":
            self.get_click_cords(
                num_points=1,
                on_update=lambda pts: self.chart.create_vline(
                    pts[-1][0], color="white", label="Ghost", tags="ghost", dash=(4, 4)
                ),
                on_complete=lambda pts, ts=int(time.time()): (
                    self.layout.add_drawing(
                        f"vline_{ts}",
                        "vline",
                        pts,
                        color=active_color,
                        width=1,
                        label="Level",
                    ),
                    (
                        self._original_callback(
                            "shape-create", {"shape": f"vline_{ts}", "type": "vline"}
                        )
                        if self._original_callback
                        else None
                    ),
                ),
                tool_name=tool_name,
            )

        elif tool_name == "angle_line":
            self.active_angle = 45.0

            self.get_click_cords(
                num_points=1,  # One click to place
                on_update=self._draw_angle_ghost,
                on_complete=self._finish_angle_line,
                tool_name=tool_name,
            )

        elif tool_name == "long_pos":
            # Long position: Two-phase drawing
            # Phase 1: Draw red stop loss rectangle (below)
            # Phase 2: Draw green target rectangle (above) from same x1,y1
            self.position_mode = "long_pos_phase1"
            self.position_uid = int(time.time())
            self.position_start = None

            def finish_phase1_long(pts):
                """Phase 1 complete: Commit red SL rectangle + Entry/SL labels with range info."""
                self.position_start = pts[0]
                end_pt = pts[-1]

                # Constraint: SL must be BELOW Entry (Strictly)
                sl_price = end_pt[1]
                entry_price = self.position_start[1]
                if sl_price >= entry_price:
                    sl_price = entry_price - 0.05  # Force strictly below

                # Store SL Price
                self.position_sl_price = sl_price

                # Stats: risk range
                risk = abs(entry_price - sl_price)
                pct_sl = (risk / entry_price * 100) if entry_price else 0

                # 1. Committed: Red SL rectangle
                self.layout.add_drawing(
                    f"PosUnit_{self.position_uid}_SL",
                    "rect",
                    [
                        (self.position_start[0], self.position_start[1]),
                        (end_pt[0], sl_price),
                    ],
                    fill_color="#FF0000",
                    outline_color="#FF0000",
                    label="",
                    stipple="gray25",
                )

                # 2. Committed: Entry label at entry price (top of SL rect)
                self.layout.add_drawing(
                    f"PosUnit_{self.position_uid}_Text_Entry",
                    "text",
                    [(self.position_start[0], entry_price)],
                    text=f"Entry: {entry_price:.2f}",
                    fill="#FFFFFF",
                )

                # 3. Committed: SL label with range at bottom of SL rect
                self.layout.add_drawing(
                    f"PosUnit_{self.position_uid}_Text_SL",
                    "text",
                    [(self.position_start[0], sl_price)],
                    text=f"Stop: {sl_price:.2f} (Entry-SL: {risk:.2f}, {pct_sl:.1f}%)",
                    fill="#FFAAAA",
                )

                # Mode -> Phase 2 (Target)
                self.position_mode = "long_pos_phase2"
                self.position_phase1_pts = [
                    (self.position_start[0], self.position_start[1]),
                    (end_pt[0], sl_price),
                ]

                self.get_click_cords(
                    num_points=1,
                    on_update=lambda pts2: self._draw_phase2_ghost_long(pts2),
                    on_complete=lambda pts2: self._finish_phase2_long(pts2),
                    tool_name=tool_name,
                )

            def _ghost_phase1_long(pts):
                """Phase 1 ghost for long: red rect + Entry/Stop labels with range info.
                Shows info from first mouse move so trader sees values immediately."""
                entry_price = pts[0][1]

                if len(pts) > 1:
                    stop_price  = pts[-1][1]
                    # Range stats (live, may be negative direction before 2nd click)
                    risk = abs(entry_price - stop_price)
                    pct_sl = (risk / entry_price * 100) if entry_price else 0

                    # Red SL rectangle ghost
                    self.chart.create_rectangle(
                        pts[0][0], pts[0][1],
                        pts[-1][0], pts[-1][1],
                        fill_color="#FF0000",
                        label="",
                        tags="ghost_rect_sl",
                        outline_color="#FF0000",
                        stipple="gray25",
                    )
                    # Entry label at first click (top of SL rect)
                    self.chart.create_text(
                        pts[0][0], entry_price,
                        f"Entry: {entry_price:.2f}",
                        "#FFFFFF",
                        "Entry",
                        tags="ghost_text_entry",
                    )
                    # Stop label with range at cursor (bottom of SL rect)
                    self.chart.create_text(
                        pts[-1][0], stop_price,
                        f"Stop: {stop_price:.2f} (Entry-SL: {risk:.2f}, {pct_sl:.1f}%)",
                        "#FFAAAA",
                        "Stop",
                        tags="ghost_text_sl",
                    )
                else:
                    # Before first click, show Entry text at current mouse position
                    self.chart.create_text(
                        pts[0][0], entry_price,
                        f"Entry: {entry_price:.2f}",
                        "#FFFFFF",
                        "Entry",
                        tags="ghost_text_entry",
                    )

            self.get_click_cords(
                num_points=2,
                on_update=_ghost_phase1_long,
                on_complete=finish_phase1_long,
                tool_name=tool_name,
            )

        elif tool_name == "short_pos":
            # Short position: Two-phase drawing
            # Phase 1: Draw RED Stop Loss rectangle (ABOVE) - SWAPPED as per user request
            # Phase 2: Draw GREEN Target rectangle (BELOW)
            self.position_mode = "short_pos_phase1"
            self.position_uid = int(time.time())
            self.position_start = None

            def finish_phase1_short(pts):
                """Phase 1 complete: Commit red SL rectangle + Entry/SL labels with range info."""
                self.position_start = pts[0]
                end_pt = pts[-1]

                # Constraint: SL must be ABOVE Entry (Strictly)
                sl_price = end_pt[1]
                entry_price = self.position_start[1]
                if sl_price <= entry_price:
                    sl_price = entry_price + 0.05  # Force strictly above

                # Store SL Price
                self.position_sl_price = sl_price

                # Stats: risk range
                risk = abs(entry_price - sl_price)
                pct_sl = (risk / entry_price * 100) if entry_price else 0

                # 1. Committed: Red SL rectangle
                self.layout.add_drawing(
                    f"PosUnit_{self.position_uid}_SL",
                    "rect",
                    [
                        (self.position_start[0], self.position_start[1]),
                        (end_pt[0], sl_price),
                    ],
                    fill_color="#FF0000",
                    outline_color="#FF0000",
                    label="",
                    stipple="gray25",
                )

                # 2. Committed: Entry label at entry price (bottom of SL rect for short)
                self.layout.add_drawing(
                    f"PosUnit_{self.position_uid}_Text_Entry",
                    "text",
                    [(self.position_start[0], entry_price)],
                    text=f"Entry: {entry_price:.2f}",
                    fill="#FFFFFF",
                )

                # 3. Committed: SL label with range at top of SL rect
                self.layout.add_drawing(
                    f"PosUnit_{self.position_uid}_Text_SL",
                    "text",
                    [(self.position_start[0], sl_price)],
                    text=f"Stop: {sl_price:.2f} (Entry-SL: {risk:.2f}, {pct_sl:.1f}%)",
                    fill="#FFAAAA",
                )

                # Mode -> Phase 2 (Target - Green)
                self.position_mode = "short_pos_phase2"
                self.position_phase1_pts = [
                    (self.position_start[0], self.position_start[1]),
                    (end_pt[0], sl_price),
                ]

                # Start capturing for Green Target
                self.get_click_cords(
                    num_points=1,
                    on_update=lambda pts2: self._draw_phase2_ghost_short(pts2),
                    on_complete=lambda pts2: self._finish_phase2_short(pts2),
                    tool_name=tool_name,
                )

            def _ghost_phase1_short(pts):
                """Phase 1 ghost for short: red rect + Entry/Stop labels with range info.
                Shows info from first mouse move so trader sees values immediately."""
                entry_price = pts[0][1]

                if len(pts) > 1:
                    stop_price  = pts[-1][1]
                    # Range stats (live)
                    risk = abs(entry_price - stop_price)
                    pct_sl = (risk / entry_price * 100) if entry_price else 0

                    # Red SL rectangle ghost
                    self.chart.create_rectangle(
                        pts[0][0], pts[0][1],
                        pts[-1][0], pts[-1][1],
                        fill_color="#FF0000",
                        label="",
                        tags="ghost_rect_sl",
                        outline_color="#FF0000",
                        stipple="gray25",
                    )
                    # Entry label at first click (bottom of SL rect for short)
                    self.chart.create_text(
                        pts[0][0], entry_price,
                        f"Entry: {entry_price:.2f}",
                        "#FFFFFF",
                        "Entry",
                        tags="ghost_text_entry",
                    )
                    # Stop label with range at cursor (above entry)
                    self.chart.create_text(
                        pts[-1][0], stop_price,
                        f"Stop: {stop_price:.2f} (Entry-SL: {risk:.2f}, {pct_sl:.1f}%)",
                        "#FFAAAA",
                        "Stop",
                        tags="ghost_text_sl",
                    )
                else:
                    # Before first click, show Entry text at current mouse position
                    self.chart.create_text(
                        pts[0][0], entry_price,
                        f"Entry: {entry_price:.2f}",
                        "#FFFFFF",
                        "Entry",
                        tags="ghost_text_entry",
                    )

            # Phase 1: Capture Red SL (Short)
            self.get_click_cords(
                num_points=2,
                on_update=_ghost_phase1_short,
                on_complete=finish_phase1_short,
                tool_name=tool_name,
            )

    def _draw_angle_ghost(self, pts):
        """Helper to draw angle ghost."""
        if not pts:
            return

        start_pt = pts[-1]  # Current cursor or last point
        plot_name = self._capture_plot_name(start_pt)
        end_pt = self._angle_line_endpoint(start_pt, plot_name=plot_name)

        if end_pt:
            dt2, price2 = end_pt
            self.chart.create_aline(
                start_pt[0],
                start_pt[1],
                dt2,
                price2,
                color="white",
                label="Ghost",
                tags="ghost",
                dash=(4, 4),
                plot_name=plot_name,
            )

    def _finish_angle_line(self, pts):
        """Commit angle line."""
        start_pt = pts[0]
        timestamp_id = int(time.time())
        tag = f"aline_{timestamp_id}"

        plot_name = self._capture_plot_name(start_pt)
        end_pt = self._angle_line_endpoint(start_pt, plot_name=plot_name)
        if not end_pt:
            return

        dt2, price2 = end_pt
        active_color = getattr(self, "active_color", "#FF0000")

        self.layout.add_drawing(
            tag,
            "line",
            [(start_pt[0], start_pt[1]), (dt2, price2)],
            color=active_color,
            width=2,
            label="AngleLine",
            plot_name=plot_name,
        )
        if self._original_callback:
            self._original_callback(
                "shape-create", {"shape": tag, "type": "angle_line"}
            )

    def _capture_plot_name(self, fallback_pt=None):
        """Returns the active subplot for the current capture, if known."""
        if self.capture_state:
            plot_name = self.capture_state.get("sub_plot")
            if plot_name:
                return plot_name

        if fallback_pt and self.chart:
            try:
                y_guess = self.chart.transform_price_to_y(fallback_pt[1])
                plot_name = self.chart.get_plot_at_y(y_guess)
                if plot_name:
                    return plot_name
            except Exception:
                pass

        return "candlestick"

    def _angle_line_endpoint(self, start_pt, plot_name=None, max_pixels=240):
        """Returns a bounded endpoint for the angle ray at the current active angle."""
        if not start_pt or not self.chart or not getattr(self.chart, "data", None):
            return None

        try:
            eff_w, eff_h = self.chart.get_chart_area()
        except Exception:
            return None

        if eff_w <= 0 or eff_h <= 0:
            return None

        import math

        plot_name = plot_name or self._capture_plot_name(start_pt)
        subplot = None
        if hasattr(self.chart, "subplots"):
            subplot = self.chart.subplots.get(plot_name)
            if subplot and subplot.get("overlay_on"):
                plot_name = subplot["overlay_on"]
                subplot = self.chart.subplots.get(plot_name)

        angle_deg = getattr(self, "active_angle", 45.0) % 360
        rad = math.radians(angle_deg)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)

        idx1 = self.chart.data.get_index_from_time(start_pt[0])
        x1 = self.chart.transform_index_to_x(idx1)

        try:
            y1 = self.chart.transform_price_to_y(start_pt[1], plot_name=plot_name)
        except TypeError:
            y1 = self.chart.transform_price_to_y(start_pt[1])

        bounds = (0.0, 1.0)
        if subplot and "bounds" in subplot:
            bounds = subplot["bounds"]
        panel_top = bounds[0] * eff_h
        panel_bottom = bounds[1] * eff_h

        eps = 1e-9
        candidates = [float(max_pixels)]

        if cos_a > eps:
            candidates.append((eff_w - 1 - x1) / cos_a)
        elif cos_a < -eps:
            candidates.append((0 - x1) / cos_a)

        if sin_a > eps:
            candidates.append((y1 - panel_top) / sin_a)
        elif sin_a < -eps:
            candidates.append((panel_bottom - y1) / (-sin_a))

        usable = [c for c in candidates if c is not None and c > 0]
        if not usable:
            return None

        length = min(usable)
        x2 = x1 + cos_a * length
        y2 = y1 - sin_a * length

        # Safety clamp to stay inside the visible subplot area.
        x2 = max(0, min(eff_w - 1, x2))
        inset = 1e-6
        if panel_bottom - panel_top > inset * 2:
            y2 = max(panel_top + inset, min(panel_bottom - inset, y2))
        else:
            y2 = max(panel_top, min(panel_bottom, y2))

        idx2 = self.chart.inverse_transform_x(x2)
        price2 = self.chart.inverse_transform_y(y2)
        dt2 = self.chart.data.get_time_from_index(idx2)

        if dt2 is None:
            return None

        return dt2, price2

    # --- Phase 2 Helpers for Position Tools ---
    def _draw_phase2_ghost_long(self, pts):
        """Phase 2 ghost for long: green target rect + Entry/SL info re-drawn + Target with range+RR.
        All info is visible during drawing so trader sees the full picture before committing."""
        if not pts or not hasattr(self, "position_start"):
            return

        cursor_pt = pts[0]
        start_pt = self.position_start
        entry_price = start_pt[1]
        sl_price = getattr(self, "position_sl_price", None)

        # Constraint: Target must be ABOVE Entry (Strictly)
        target_price = cursor_pt[1]
        if target_price <= entry_price:
            target_price = entry_price + 0.05

        # --- Reward / Risk stats ---
        reward = abs(target_price - entry_price)
        pct_tgt = (reward / entry_price * 100) if entry_price else 0
        rr_str = ""
        if sl_price is not None:
            risk = abs(entry_price - sl_price)
            if risk > 0:
                rr = reward / risk
                rr_str = f"  RR: {rr:.2f}"

        # Re-draw committed SL rect ghost so trader sees the full shape (phase 1 already committed)
        if sl_price is not None:
            sl_risk = abs(entry_price - sl_price)
            sl_pct  = (sl_risk / entry_price * 100) if entry_price else 0
            self.chart.create_rectangle(
                start_pt[0], entry_price,
                cursor_pt[0], sl_price,
                fill_color="#FF0000",
                label="",
                tags="ghost_rect_sl",
                outline_color="#FF0000",
                stipple="gray25",
            )
            # SL ghost label
            self.chart.create_text(
                start_pt[0], sl_price,
                f"Stop: {sl_price:.2f} (Entry-SL: {sl_risk:.2f}, {sl_pct:.1f}%)",
                "#FFAAAA",
                "Stop",
                tags="ghost_text_sl",
            )

        # Green target ghost rectangle (entry → target)
        self.chart.create_rectangle(
            start_pt[0], entry_price,
            cursor_pt[0], target_price,
            fill_color="#00B341",
            label="",
            tags="ghost_rect_tgt",
            outline_color="#00B341",
            stipple="gray25",
        )
        # Entry label at entry price (boundary between red and green)
        self.chart.create_text(
            start_pt[0], entry_price,
            f"Entry: {entry_price:.2f}",
            "#FFFFFF",
            "Entry",
            tags="ghost_text_entry",
        )
        # Target label with range + RR at cursor
        self.chart.create_text(
            cursor_pt[0], target_price,
            f"Target: {target_price:.2f} (Entry-Tgt: {reward:.2f}, {pct_tgt:.1f}%){rr_str}",
            "#AAFFAA",
            "Target",
            tags="ghost_text_tgt",
        )

    def _finish_phase2_long(self, pts):
        """Finish phase 2 of long position - commit green target rect + Target label with range+RR."""
        if not hasattr(self, "position_start") or not hasattr(self, "position_uid"):
            return

        end_pt = pts[0]
        start_pt = self.position_start

        # Constraint: Target must be ABOVE Entry (Strictly)
        target_price = end_pt[1]
        entry_price = start_pt[1]
        if target_price <= entry_price:
            target_price = entry_price + 0.05

        # Calculate stats
        reward = abs(target_price - entry_price)
        pct_tgt = (reward / entry_price * 100) if entry_price else 0

        sl_price = getattr(self, "position_sl_price", None)
        rr_str = ""
        if sl_price is not None:
            risk = abs(entry_price - sl_price)
            if risk > 0:
                rr = reward / risk
                rr_str = f"  RR: {rr:.2f}"

        # 1. Committed: Green target rectangle
        self.layout.add_drawing(
            f"PosUnit_{self.position_uid}_TGT",
            "rect",
            [(start_pt[0], start_pt[1]), (end_pt[0], target_price)],
            fill_color="#00B341",
            outline_color="#00B341",
            label="",
            stipple="gray25",
        )

        # 2. Committed: Target label with range + RR at target price (top of green rect)
        self.layout.add_drawing(
            f"PosUnit_{self.position_uid}_Text_TGT",
            "text",
            [(start_pt[0], target_price)],
            text=f"Target: {target_price:.2f} (Entry-Tgt: {reward:.2f}, {pct_tgt:.1f}%){rr_str}",
            fill="#AAFFAA",
        )

        self.position_mode = None
        print(f"Long position complete: Unit ID PosUnit_{self.position_uid}")

        # EMIT: shape-create with entry/sl/target prices for order form population
        if self._original_callback:
            self._original_callback(
                "shape-create",
                {
                    "shape": f"PosUnit_{self.position_uid}",
                    "type": "long_pos",
                    "entry_price": entry_price,
                    "sl_price": sl_price,
                    "target_price": target_price,
                },
            )

    def _draw_phase2_ghost_short(self, pts):
        """Phase 2 ghost for short: green target rect + Entry/SL info re-drawn + Target with range+RR.
        All info is visible during drawing so trader sees the full picture before committing."""
        if not pts or not hasattr(self, "position_start"):
            return

        cursor_pt = pts[0]
        start_pt = self.position_start
        entry_price = start_pt[1]
        sl_price = getattr(self, "position_sl_price", None)

        # Constraint: Target must be BELOW Entry (Strictly) for Short
        target_price = cursor_pt[1]
        if target_price >= entry_price:
            target_price = entry_price - 0.05

        # --- Reward / Risk stats ---
        reward = abs(entry_price - target_price)
        pct_tgt = (reward / entry_price * 100) if entry_price else 0
        rr_str = ""
        if sl_price is not None:
            risk = abs(entry_price - sl_price)
            if risk > 0:
                rr = reward / risk
                rr_str = f"  RR: {rr:.2f}"

        # Re-draw committed SL rect ghost so trader sees the full shape during phase 2
        if sl_price is not None:
            sl_risk = abs(entry_price - sl_price)
            sl_pct  = (sl_risk / entry_price * 100) if entry_price else 0
            self.chart.create_rectangle(
                start_pt[0], entry_price,
                cursor_pt[0], sl_price,
                fill_color="#FF0000",
                label="",
                tags="ghost_rect_sl",
                outline_color="#FF0000",
                stipple="gray25",
            )
            # SL ghost label
            self.chart.create_text(
                start_pt[0], sl_price,
                f"Stop: {sl_price:.2f} (Entry-SL: {sl_risk:.2f}, {sl_pct:.1f}%)",
                "#FFAAAA",
                "Stop",
                tags="ghost_text_sl",
            )

        # Green target ghost rectangle (entry → target, below entry for short)
        self.chart.create_rectangle(
            start_pt[0], entry_price,
            cursor_pt[0], target_price,
            fill_color="#00B341",
            label="",
            tags="ghost_rect_tgt",
            outline_color="#00B341",
            stipple="gray25",
        )
        # Entry label at entry price (boundary between red and green)
        self.chart.create_text(
            start_pt[0], entry_price,
            f"Entry: {entry_price:.2f}",
            "#FFFFFF",
            "Entry",
            tags="ghost_text_entry",
        )
        # Target label with range + RR at cursor (below entry for short)
        self.chart.create_text(
            cursor_pt[0], target_price,
            f"Target: {target_price:.2f} (Entry-Tgt: {reward:.2f}, {pct_tgt:.1f}%){rr_str}",
            "#AAFFAA",
            "Target",
            tags="ghost_text_tgt",
        )

    def _finish_phase2_short(self, pts):
        """Finish phase 2 of short position - commit green target rect + Target label with range+RR."""
        if not hasattr(self, "position_start") or not hasattr(self, "position_uid"):
            return

        end_pt = pts[0]
        start_pt = self.position_start

        # Constraint: Target must be BELOW Entry (Strictly)
        target_price = end_pt[1]
        entry_price = start_pt[1]
        if target_price >= entry_price:
            target_price = entry_price - 0.05

        # Calc stats
        reward = abs(entry_price - target_price)
        pct_tgt = (reward / entry_price * 100) if entry_price else 0

        sl_price = getattr(self, "position_sl_price", None)
        rr_str = ""
        if sl_price is not None:
            risk = abs(entry_price - sl_price)
            if risk > 0:
                rr = reward / risk
                rr_str = f"  RR: {rr:.2f}"

        # 1. Committed: Green target rectangle
        self.layout.add_drawing(
            f"PosUnit_{self.position_uid}_TGT",
            "rect",
            [(start_pt[0], start_pt[1]), (end_pt[0], target_price)],
            fill_color="#00B341",
            outline_color="#00B341",
            label="",
            stipple="gray25",
        )

        # 2. Committed: Target label with range + RR at target price (bottom of green rect for short)
        self.layout.add_drawing(
            f"PosUnit_{self.position_uid}_Text_TGT",
            "text",
            [(start_pt[0], target_price)],
            text=f"Target: {target_price:.2f} (Entry-Tgt: {reward:.2f}, {pct_tgt:.1f}%){rr_str}",
            fill="#AAFFAA",
        )

        self.position_mode = None
        print(f"Short position complete: Unit ID PosUnit_{self.position_uid}")

        # EMIT: shape-create with entry/sl/target prices for order form population
        if self._original_callback:
            self._original_callback(
                "shape-create",
                {
                    "shape": f"PosUnit_{self.position_uid}",
                    "type": "short_pos",
                    "entry_price": entry_price,
                    "sl_price": sl_price,
                    "target_price": target_price,
                },
            )


# --- Added Features ---
# 1. 2026-04-22: Integrated with LayoutManager for persistent shape storage.
# 2. 2026-04-22: Added multi-phase gesture support for Long/Short position tools.
# 3. 2026-04-22: Implemented Group Interaction logic for complex units.
# 4. 2026-04-22: Added standard app-level event signals (shape-create, shape-select, etc).
# 5. 2026-06-23: Ghost shows Entry/Stop with range in phase 1; Entry/Target+RR in phase 2 (both phases).
# 6. 2026-06-23: shape-create carries entry_price, sl_price, target_price for order form auto-fill.
# 7. 2026-06-23: Committed shape now includes Entry label text node in addition to SL and Target labels.
# 8. 2026-06-23: All labels (SL, Target) include price range (distance + %) and RR in committed and ghost.
# 9. 2026-06-23: Solved ghost visual overwrites by using distinct tags and fixed create_text missing label argument.
# 10. 2026-06-23: Continuous Entry tracking at mouse move before the first click.
# 11. 2026-06-23: Refined text description formatting to use "Entry-SL" and "Entry-Tgt".
