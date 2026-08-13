# FinChart Layer 1.8 — Chart Public API & Adapter Contract Engine Documentation

## Problem Overview

FinChart requires a clean, stable, application-facing root `Chart` facade object that exposes all single-chart operations (data binding, resolution, series, indicators, panes, drawings, tool selection, event subscriptions, persistence) without exposing internal engine implementation details or canvas/renderer handles. It also requires compatibility adapters for EasyPyChart legacy usage and TradingView lightweight-charts syntax.

## Key Classes and Architecture

### 1. `finchart/tradingview/errors.py`
- Defines deterministic exception hierarchy inheriting from `FinChartError`:
  `ChartRemovedError`, `EntityNotFoundError`, `InvalidSymbolError`, `InvalidResolutionError`, `InvalidChartTypeError`, `InvalidSeriesTypeError`, `InvalidIndicatorError`, `InvalidDrawingError`, `InvalidCoordinateError`, `InvalidPaneError`, `UnsupportedOperationError`.

### 2. `finchart/tradingview/options.py`
- Structured option groups: `DimensionsOptions`, `ThemeOptions`, `TimeScaleOptions`, `PriceScaleOptions`, `CrosshairOptions`, `InteractionOptions`.
- `ChartOptions`: Provides `apply_partial()` to safely merge dictionary option updates without overwriting unspecified options.

### 3. `finchart/tradingview/event_subscription.py`
- `Subscription`: Active handle object with `.unsubscribe()`.
- `EventRegistry`: Subscriber registry supporting event names (`symbol_changed`, `resolution_changed`, `layout_changed`, etc.). Enforces subscriber exception isolation so errors in one callback do not disrupt other subscribers or the chart engine.

### 4. `finchart/tradingview/api_entities.py`
- Public entity wrappers delegating operations back to `Chart` facade:
  - `SeriesAPI` (`set_data`, `update`, `apply_options`, `show`, `hide`, `remove`)
  - `IndicatorAPI` (`set_input`, `set_options`, `show`, `hide`, `remove`)
  - `DrawingAPI` (`set_properties`, `set_points`, `show`, `hide`, `remove`)
  - `PaneAPI` (`resize`, `collapse`, `expand`, `remove`)
  - `TimeScaleAPI` (`fit_content`, `reset_view`, `set_options`, `scroll`, `zoom`)
  - `PriceScaleAPI` (`set_mode`, `set_range`)

### 5. `finchart/tradingview/chart_api.py`
- **`Chart`**: Primary single-chart facade. Manages lifecycle (`CREATED`, `ACTIVE`, `REMOVED`). Guarantees operations on `REMOVED` instances raise `ChartRemovedError`. Integrates `ChartState`, `ChartLayout`, `ViewportState`, `TimeScale`, `PriceScale`, `InputEngine`, and `InvalidationScheduler`.

### 6. `finchart/tradingview/adapters.py`
- **`EasyPyChartAdapter`**: Pythonic legacy adapter mapping `load_data`, `create_subplot`, `create_series`, `create_line`, `create_hline`, `create_vline`, `create_rectangle`, `create_text`, `save_session`, `load_session`.
- **`TradingViewAdapter`**: TV Lightweight-Charts style adapter mapping `addSeries`, `createShape`, `createMultipointShape`, `createAnchoredShape`, `getAllShapes`, `removeEntity`, `removeAllShapes`, `subscribe`, `unsubscribe`.

## Architectural Guarantees

1. **Workspace Independence**: Built strictly as a single-chart object without Workspace assumptions.
2. **Lifecycle Enforcement**: Methods check active state before proceeding.
3. **Event Subscriber Isolation**: Subscriber errors are logged without interrupting execution.
