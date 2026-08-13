# FinChart Layer 1.7 — Chart Input & Event Management Engine Documentation

## Problem Overview

FinChart requires a framework-independent, deterministic input normalization and hit-testing engine that handles raw pointer, wheel, touch, keyboard, focus, and container resize events without coupling domain logic to any specific GUI toolkit (such as Tkinter, PyQt, PySide, or web canvas).

## Key Classes and Architecture

### 1. `finchart/tradingview/input_events.py`
- **`ModifierState`**: Encapsulates Shift, Ctrl, Alt, and Meta key flags into immutable snapshots.
- **`HitTarget`**: Carries target metadata (`HitRegion`, `target_id`, `pane_id`, `handle_id`, `logical_index`, `price_position`).
- **`PointerEvent`**: Normalized pointer data including screen coordinates, previous positions, buttons, modifiers, and click type (`SINGLE`, `DOUBLE`, `CONTEXT`).
- **`WheelEvent`**: Preserves scroll deltas, coordinates, and modifier state for wheel routing.
- **`TouchEvent`**: Stores touch point lists, touch count, center math (`center_x`, `center_y`), and multi-touch pinch distance calculation.
- **`KeyboardEvent`**: Normalized keyboard event with key name, key code, repeat flag, and modifier state.
- **`FocusEvent`**: Standardized focus acquisition and focus loss event structures.
- **`ResizeEvent`**: Captures container dimensions update.
- **`ChartInputEvent`**: Envelope combining input event payload, target description, pane-local coordinates, and propagation state (`HANDLED`, `CANCELLED`).

### 2. `finchart/tradingview/hit_tester.py`
- **`HitTester`**: Resolves hit targets deterministically using FinChart strict priority order:
  1. Active drawing handle
  2. Selected drawing body
  3. Other drawing body
  4. Pane splitter
  5. Price scale
  6. Time scale
  7. Series / indicator
  8. Pane body
  9. Chart background

### 3. `finchart/tradingview/pointer_capture.py`
- **`PointerCaptureManager`**: Ensures drag/resize operations continue receiving pointer movements even when the pointer leaves chart boundaries during active press gestures. Releases capture upon `POINTER_UP` or `POINTER_CANCEL`.

### 4. `finchart/tradingview/focus_manager.py`
- **`FocusManager`**: Gates keyboard input dispatch to prevent external widget shortcut interference unless the chart explicitly holds focus.

### 5. `finchart/tradingview/input_adapter.py`
- **`InputAdapter`**: Abstract baseline class defining the contract for platform-specific event adapters.

### 6. `finchart/tradingview/input_engine.py`
- **`InputEngine`**: The central coordinator. Accepts raw platform inputs, normalizes them, queries `HitTester`, tracks drag threshold (`DEFAULT_DRAG_THRESHOLD_PX = 4.0`), enforces pointer capture, calculates touch pinch center/distance, gates keyboard events through `FocusManager`, and dispatches `ChartInputEvent` to downstream listeners.

## Architectural Guarantees

1. **Coordinate Authority**: Logical indices and prices are converted exclusively via `TimeScale` and `PriceScale`. The input engine does not calculate authoritative coordinates.
2. **No Direct Mutation**: `InputEngine` does not mutate `ChartState`, `ViewportState`, or drawings directly. It passes typed events downstream.
3. **No Workspace Dependency**: Built strictly for a single `Chart` instance, exposing clean interfaces so multiple `Chart` instances can be instantiated independently in the future.
4. **Performance Isolation**: Pointer movement alone does not trigger layout recalculations or render invalidation unless downstream state mutations occur.
