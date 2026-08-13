# FinChart Layer 1.9 — Interaction / Gesture Engine Documentation

## Problem Overview

FinChart requires a deterministic gesture interpretation layer that translates low-level input events (pointer presses, drags, releases, wheel scrolls, and touch pinches) into high-level chart navigation operations, coordinate updates, and pane resizing commands without violating architectural boundaries.

## Key Classes and Architecture

### 1. `finchart/tradingview/gesture_state.py`
- **`GestureState`**: Enum defining valid gesture states:
  `IDLE`, `PRESS_PENDING`, `DRAGGING_CHART`, `DRAGGING_PRICE_SCALE`, `DRAGGING_TIME_SCALE`, `ZOOMING_TIME`, `ZOOMING_PRICE`, `DRAGGING_SHAPE`, `RESIZING_SHAPE`, `RESIZING_PANE`, `KINETIC_SCROLL`.
- **`GestureContext`**: Tracks active gesture session data (press origin coordinates, initial target snapshot, active pane ID, initial scale/viewport ranges).

### 2. `finchart/tradingview/selection_manager.py`
- **`SelectionManager`**: Handles selection of chart entities (drawings, components) with single selection, multi-selection (`Ctrl` / `Cmd` + click), and deselection events.

### 3. `finchart/tradingview/gesture_engine.py`
- **`GestureEngine`**: Central gesture interpreter listening to `InputEngine`.
  - **Horizontal Panning**: Converts pixel delta $\Delta x$ to logical index delta ($\Delta \text{index} = -\Delta x / \text{bar\_spacing}$) and updates `ViewportState` visible range.
  - **Cursor-Anchored Wheel Zooming**: Calculates the logical index under the cursor before zoom, adjusts `bar_spacing`, and updates `visible_start` so the cursor anchor remains stationary.
  - **Price Scale Dragging**: Adjusts `PriceScale` min/max range based on vertical drag delta.
  - **Time Scale Dragging**: Adjusts `TimeScale` `bar_spacing` based on horizontal drag delta.
  - **Pane Splitter Dragging**: Resizes adjacent pane heights dynamically.
  - **Invalidation**: Requests coalesced renders through `InvalidationScheduler`.

## Architectural Guarantees

1. **Target Arbitration Priority**:
   Handle > Selected Drawing > Drawing Body > Pane Splitter > Price Scale > Time Scale > Pane Body > Chart Background.
2. **Coordinate Authority**: All pixel-to-logical index conversions are delegated to `TimeScale` and `PriceScale`.
3. **No Direct Renderer Coupling**: Commands update logical states and trigger invalidation flags.
