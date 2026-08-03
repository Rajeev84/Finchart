# Explanation: InteractionManager

## Purpose
The `InteractionManager` class provides a high-level abstraction for handling complex chart interactions. It sits between the raw chart events and the application logic, allowing for stateful tool behaviors like multi-click drawing sequences and grouped shape manipulation.

## Core Features

### Multi-Phase Tool Drawing
Tools like `long_pos` and `short_pos` require multiple clicks to define different boundaries (Entry, Stop Loss, Target). The `InteractionManager` manages these phases internally using:
- **`get_click_cords`**: A flexible method to capture a specific number of points with real-time "ghost" previews.
- **Phase Handlers**: Functions that transition the state from Phase 1 (e.g., Risk) to Phase 2 (e.g., Reward).

### Grouped Shape Management
Complex tools are created as groups of shapes.
- **Naming Convention**: Uses a unique `PosUnit_{timestamp}` prefix for all components (rectangles and text labels) within a group.
- **Synchronized Operations**: When a shape with a `PosUnit` prefix is selected, the manager automatically includes all other shapes in that group for dragging or deletion.

### Event Propagation
The manager wraps the original chart callback. It intercepts events it can handle (like clicks and drags) and forwards unhandled or high-level events (like `shape-create` or `shape-select`) back to the application.

## Methods

### `set_tool(tool_name)`
Initializes the capture sequence for a specific tool. It clears any previous state and sets up the `on_update` and `on_complete` callbacks.

### `_handle_capture(event, data)`
Processes raw mouse events to build up the point list required by the active tool. It emits `point-capture` events to notify the application of progress.

---
**Last Updated**: 2026-06-23
**Keywords**: State Machine, Multi-phase Capture, Ghost Preview, Grouped Shapes, Order Form Auto-fill, Distinct Ghost Tags

## Recent Changes (2026-06-23)

### Ghost Text Labels & Distinct Tags (Requirement 1 & 3)
During Long/Short drawing, ghost previews display descriptive text labels continuously based on pointer movement:
- **Phase 1** (entry → stop drag): Shows `"Entry: {price}"` at the first click point and `"Stop: {price} (Entry-SL: {range}, {pct}%)"` at the current cursor position (over the red SL rectangle). Before the first click, it shows `"Entry: {price}"` continuously following the mouse pointer.
- **Phase 2** (entry → target drag): Shows `"Entry: {price}"` pinned at the entry line, Stop Loss details pinned at the stop loss line, and `"Target: {price} (Entry-Tgt: {range}, {pct}%){RR}"` at the cursor (over the green Target rectangle).
- Resolved ghost visual overwrites by using distinct tags: `ghost_rect_sl`, `ghost_text_entry`, `ghost_text_sl`, `ghost_rect_tgt`, and `ghost_text_tgt`.
- Fixed the Python `TypeError` signature mismatch in `create_text` by explicitly passing the positional `label` argument.
- All ghost components are safely cleaned up in `stop_capture()`.

### Order Form Auto-fill (Requirement 2)
When the tool is fully completed (`shape-create` event):
- `entry_price`, `sl_price`, and `target_price` are now included in the event `data` dict.
- `controller.chart_handler` reads these values and writes them to `txt_entry_price`, `txt_sl_price`, and `txt_target_price` in the Order Placement tab of the Market Watch panel.
