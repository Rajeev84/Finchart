EasyPyChart Charting Library
========================

This is a custom Tkinter-based financial charting library.

Features
--------
*   Candlestick charts
*   Zooming and Panning (Mouse centered)
*   Crosshairs with Price and Date labels
*   Support for multiple subplots
*   Drawing API (Lines, Rectangles, Text)
*   Data Callback (Hover)

Usage
-----

.. code-block:: python

    from easypychart.core import EasyPyChart
    import pandas as pd

    # Initialize
    chart = EasyPyChart(master=root)
    chart.pack(fill='both', expand=True)

    # Load Data
    df = pd.read_csv('data.csv') # Must have 'date', 'open', 'high', 'low', 'close', 'volume'
    chart.load_data(df)

Configuration
-------------
Pass a dictionary to the `config` argument in `__init__`.

*   `width`: Canvas width
*   `height`: Canvas height
*   `background`: Background color (Hex)
*   `crosshair_enabled`: Boolean
*   `crosshair_color`: Hex color
*   `padding_right`: Right margin in pixels (for Price Axis) - Default 60
*   `padding_bottom`: Bottom margin in pixels (for Date Axis) - Default 30

API
---

`get_view_coordinates()`
~~~~~~~~~~~~~~~~~~~~~~~~
Returns the current visible bounds of the chart.

.. code-block:: python

    dt_left, dt_right, lowest_low, highest_high = chart.get_view_coordinates()

    print(f"Time Range: {dt_left} to {dt_right}")
    print(f"Price Range: {lowest_low} to {highest_high}")

Callbacks
---------
Pass a `callback` function to `__init__`.

.. code-block:: python

    def on_event(event_type, data):
        if event_type == 'hover':
            print(data) # {'time': ..., 'open': ..., 'close': ...}

    chart = EasyPyChart(callback=on_event)


EasyPyChart Multi-Canvas Support Report
---------

Overview
EasyPyChart supports multi-canvas (multi-widget) scenarios naturally due to its object-oriented architecture built on Tkinter's Frame and Canvas system. Each chart instance is an independent widget that maintains its own state, drawing collection, and configuration.

    1. Multiple Canvases with Different Symbols
    To display different symbols on separate canvases, you should instantiate an EasyPyChart and a corresponding LayoutManager for each symbolic view.

    Implementation Architecture
    Canvas A: EasyPyChart (Instance 1) + LayoutManager (Instance 1) -> Set context to "BTCUSDT"
    Canvas B: EasyPyChart (Instance 2) + LayoutManager (Instance 2) -> Set context to "ETHUSDT"
    Why it works:
    LayoutManager stores the data_store and current_symbol per instance.
    EasyPyChart renders only the data loaded via its own load_data() method (or via its manager's set_context()).
    The drawings dictionary is local to each EasyPyChart instance.
    2. Same Symbol with Different Shapes
    This scenario is useful for comparing different technical analyses on the same asset (e.g., one chart with Elliott Waves, another with Supply/Demand zones).

    Implementation Architecture
    Canvas A: EasyPyChart (Instance 1) + LayoutManager (Instance 1) -> Context: "BTCUSDT"
    Canvas B: EasyPyChart (Instance 2) + LayoutManager (Instance 2) -> Context: "BTCUSDT"
    Why it works:
    Even though they share the same symbol name, the memory-resident states of the two EasyPyChart instances are completely isolated.

    chart1.create_line(...) adds a shape only to Instance 1.
    chart2.create_rectangle(...) adds a shape only to Instance 2.
    Session Persistence Note:
    If you save sessions to the same file, they might overwrite each other because the session storage is currently keyed by symbol.

    IMPORTANT

    To preserve different shapes for the same symbol across sessions, you must save each canvas to a unique session file (e.g., chart1_session.json and chart2_session.json).

    3. Demonstration Code
    Below is a simplified structural example of how to implement the multi-canvas setup.

    .. code-block:: python
        import tkinter as tk
        from easypychart import EasyPyChart
        from easypychart.layout_manager import LayoutManager

        root = tk.Tk()

        # Initialize Canvas 1
        chart1 = EasyPyChart(root)
        layout1 = LayoutManager(chart1)
        layout1.data_store = {"BTCUSDT": {"1m": btc_df}}
        layout1.set_context("BTCUSDT", "1m")
        chart1.create_hline(60000, color='red', label='Resistance') # Drawing specific to Canvas 1

        # Initialize Canvas 2
        chart2 = EasyPyChart(root)
        layout2 = LayoutManager(chart2)
        layout2.data_store = {"BTCUSDT": {"1m": btc_df}}
        layout2.set_context("BTCUSDT", "1m")
        chart2.create_rectangle(dt1, p1, dt2, p2, fill_color='green') # Drawing specific to Canvas 2

        chart1.pack(side="left", fill="both", expand=True)
        chart2.pack(side="right", fill="both", expand=True)

        root.mainloop()

    Summary of Findings
    Requirement	                    Supported	Mechanism
    Different Symbols	             ✅Independent LayoutManager instances via set_context.
    Same Symbol, Different Shapes	 ✅Instance-local drawings dictionary in EasyPyChart.
    Session Saving	                 ✅Pass unique filepaths to save_session to avoid symbol-key collisions.