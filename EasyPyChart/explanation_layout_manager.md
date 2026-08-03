# Explanation: LayoutManager

## Purpose
The `LayoutManager` is responsible for the persistence and organization of chart drawings. It ensures that when a user draws a line or a position unit on a specific symbol, those drawings are saved and correctly restored when the user returns to that symbol later.

## Core Concepts

### Symbol-Specific Storage
Drawings are stored in a dictionary keyed by the symbol name (`self.drawings = { symbol_name: [shapes] }`). This allows for:
- **Ticker Independence**: Drawings on "AAPL" don't appear on "TSLA".
- **Contextual Rendering**: The `render_symbol(symbol)` method clears the chart and re-draws only the shapes associated with that ticker.

### Drawing Abstraction: `add_drawing`
Instead of calling the chart's drawing methods directly, the application uses `layout.add_drawing(tag, type, points, **kwargs)`.
- **Tagging**: Each drawing has a unique tag (or group tag prefix).
- **Metadata**: All styling (color, width, stipple) is stored alongside the coordinates.

### Persistence (Serialization)
The manager handles saving and loading the state to/from a JSON file (`chart_state.json`).
- **`save_state`**: Serializes the `drawings` dictionary and current subplot configuration.
- **`load_state`**: Deserializes the data and restores the visual state of the chart.

## Interaction with Other Components
- **controller.py**: Sets the `current_symbol` on the `LayoutManager` during interaction events.
- **InteractionManager**: Calls `add_drawing` when a tool capture is finished to ensure the new shape is persistent.

---
**Last Updated**: 2026-04-23
**Keywords**: Persistence, Serialization, Symbol Context, Drawing Storage
