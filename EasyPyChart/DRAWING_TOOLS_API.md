# EasyPyChart Drawing Tools API - Implementation Summary

## Overview
Enhanced the EasyPyChart library with 5 drawing tools and a coordinate extraction API.

---

## New API Methods

### 1. **create_hline(price, color, label, plot_name, tags, width, dash)**
Creates a horizontal line at a specific price level.

**Use Case:** Support/Resistance levels

**Example:**
```python
chart.create_hline(102.5, color='#00FFFF', label='Support', width=2)
chart.create_hline(105.0, color='white', label='Ghost', width=1, dash=(4, 4))  # Dotted
```

---

### 2. **create_vline(dt, color, label, plot_name, tags, width, dash)**
Creates a vertical line at a specific datetime.

**Use Case:** Event markers, earnings dates

**Example:**
```python
chart.create_vline(datetime.now(), color='#FF00FF', label='Earnings', width=1)
```

---

### 3. **create_aline(dt1, price1, dt2, price2, color, label, ...)**
Creates an angled line between two points.

**Use Case:** Trendlines, channels

**Example:**
```python
chart.create_aline(dt1, 98.0, dt2, 105.0, color='#FFFF00', label='Uptrend', width=2)
```

---

### 4. **create_rectangle(dt1, price1, dt2, price2, fill_color, label, ...)**
Creates a rectangular zone.

**Use Case:** Consolidation zones, S/R areas

**Example:**
```python
chart.create_rectangle(dt1, 99.0, dt2, 101.0, 
                       fill_color='#00FF0040',  # Semi-transparent
                       outline_color='#00FF00')
```

---

### 5. **create_line(dt1, price1, dt2, price2, color, label, width, dash, ...)**
Updated base method now supports:
- **width**: Line thickness (default 2)
- **dash**: Tuple for dash pattern, e.g., `(4, 4)` for dotted, `None` for solid

**Ghost Line Example:**
```python
# Ghost preview (dotted white line)
chart.create_line(t1, price, t2, price, 
                  color='white', 
                  width=1, 
                  dash=(4, 4), 
                  tags='ghost_line')
```

---

## Coordinate Extraction API

### **get_area_xy(tag)**
Returns structured coordinate data for any shape.

**Returns:**
```python
{
    'tag': 'hline_123',
    'shape': 'hline' | 'vline' | 'aline' | 'rectangle' | 'text',
    'coordinates': [(dt1, price1), (dt2, price2)]  # For lines
                   [[(x1,y1), (x2,y1), (x2,y2), (x1,y2)]]  # For rectangles (closed polygon)
}
```

**Example:**
```python
tag = chart.create_hline(102.5)
coords = chart.get_area_xy(tag)

print(coords)
# Output:
# {
#     'tag': 'hline_1735021234567',
#     'shape': 'hline',
#     'coordinates': [(datetime(...), 102.5), (datetime(...), 102.5)]
# }
```

---

## Shape Type Detection

The `get_area_xy()` automatically classifies lines:
- **hline**: Both Y-coordinates are equal
- **vline**: Both X-coordinates (datetimes) are equal
- **aline**: Angled line (neither X nor Y are equal)

---

## Usage Pattern in form_screener.py

### Ghost Line Preview:
```python
def on_event(event_type, value):
    if drawing_state['mode'] == 'hline':
        if event_type == 'move':
            # Draw dotted ghost line
            chart.create_hline(
                value['y'], 
                color='white', 
                width=1, 
                dash=(4, 4),  # Dotted!
                tags='ghost_line'
            )
        elif event_type == 'click':
            chart.delete_shape('ghost_line')
            # Create permanent solid line
            chart.create_hline(
                value['y'], 
                color='#00FFFF', 
                width=2
            )
```

---

## Testing

Run the demo script:
```bash
cd c:\Users\RajaVani\Desktop\Intraday\easypychart
python test_drawing_tools.py
```

This will:
1. Create sample chart data
2. Draw HLine, VLine, Angled Line, Rectangle
3. Create a dotted ghost line
4. Print all shape coordinates via `get_area_xy()`

---

## Key Changes to easypychart/core.py

1. **Line 395-508**: New drawing methods with dash support
2. **Line 421-499**: `get_area_xy()` implementation
3. **Line 1148-1165**: Updated rendering to use `dash` and `width` from shape definition

---

## Notes

- **Dash Pattern**: Use tuples like `(4, 4)` for dotted, `(8, 2)` for dashed, `None` for solid
- **Width**: Default is 2 pixels
- **Color**: Supports hex with alpha channel (e.g., `'#00FF0040'` for semi-transparent green)
- **Tags**: Auto-generated with timestamp if not provided
- **Coordinates**: Always in (datetime, price) format, not canvas pixels

---

## Grouped Shapes (Complex Tools)

The library supports complex tools that manage multiple primitive shapes as a single logical unit.

### 1. **Long Position (`long_pos`)**
A two-phase tool that creates:
- **Red Rectangle**: Stop Loss zone.
- **Green Rectangle**: Target zone.
- **Text Labels**: Displays Price, Percentage Risk/Reward, and RR Ratio.

#### **Procedural Example: Creation & Deletion**

**A. Creation Flow (Interactive)**
The `long_pos` tool requires a specific sequence of user clicks managed by the `InteractionManager` state machine:

1.  **Initialize Tool**: 
    ```python
    interaction.set_tool("long_pos")
    ```
2.  **Phase 1 (Stop Loss)**: 
    - **Click 1**: Define **Entry Price** and **Start Time**.
    - **Click 2**: Define **Stop Loss Price** and **End Time** (Width).
    - *Result*: A red rectangle is created with a `PosUnit_{UID}_SL` tag.
3.  **Phase 2 (Target)**:
    - **Click 3**: Define the **Target Price** level.
    - *Result*: A green rectangle is created with a `PosUnit_{UID}_TGT` tag, along with auto-calculated RR labels.

**B. Deletion Flow**
Because the tool uses group-aware logic, deleting any component removes the entire unit.

- **Interactive**: Select any part of the position box (Red or Green) and press the `Delete` key.
- **Programmatic**:
    ```python
    # Deleting by any sub-tag removes the whole group
    uid = "1736000000" # Example timestamp UID
    layout.remove_drawing(f"PosUnit_{uid}_SL") 
    chart.render()
    ```

### 2. **Short Position (`short_pos`)**
Similar to Long Position, but with inverted logic (Red SL above Entry, Green Target below).

---

## Grouping Logic & Implementation

Complex tools are managed using a **Prefix-based Grouping** system in `InteractionManager`.

### **Group Identification**
Each group is assigned a `position_uid`. Sub-components are tagged with a specific naming convention:
- `PosUnit_{UID}_SL` (Rectangle)
- `PosUnit_{UID}_TGT` (Rectangle)
- `PosUnit_{UID}_Text_SL` (Text)
- `PosUnit_{UID}_Text_TGT` (Text)

### **Synchronized Management**
The `InteractionManager` provides three key behaviors for groups:

1.  **Group Selection**: Clicking any component of a `PosUnit` selects the entire group (using `_get_related_tags`).
2.  **Synchronized Dragging**: Moving one component applies the same (time, price) delta to all members of the group.
3.  **Atomic Deletion**: Deleting one component removes all related shapes in the unit.

### **Internal Helper: `_get_related_tags(tag)`**
```python
def _get_related_tags(self, tag):
    parts = tag.split("_")
    if parts[0] == "PosUnit":
        prefix = f"{parts[0]}_{parts[1]}"
        return [t for t in self.chart.drawings.keys() if t.startswith(prefix)]
    return [tag]
```

---

## Added Features Section
- **2026-04-23**: Added "Grouped Shapes" documentation and a procedural example for the Long Position tool (creation flow and deletion logic).
