EasyPyChart Library Documentation
=============================

**EasyPyChart** is a lightweight, high-performance financial charting library for Python, built on Tkinter. It is designed to mimic the tracking and drawing capabilities of professional trading platforms like TradingView.

Table of Contents
-----------------
1. `Overview <#overview>`_
2. `Initialization <#initialization>`_
3. `Data Management <#data-management>`_
4. `Plotting & Series <#plotting-series>`_
5. `Drawing Tools API <#drawing-tools-api>`_
6. `Interaction & Events <#interaction-events>`_
7. `Session & Layout Management <#session-layout-management>`_

Overview
--------

EasyPyChart provides a canvas-based interactive chart that supports:

*   OHLCV Candle plotting.
*   Multiple subplots (panes) for indicators.
*   Interactive drawing tools (Lines, rectangles, support/resistance levels).
*   Zooming, panning, and responsive scaling.
*   Session persistence (saving/loading analysis).

Initialization
--------------

The core class is ``EasyPyChart``. It can be embedded into any Tkinter application.

.. code-block:: python

    from easypychart.core import EasyPyChart

    # Config Dictionary
    config = {
        'width': 1200,            # Canvas width
        'height': 600,            # Canvas height
        'background': '#131722',  # Background color
        'candle_width': 0.6,      # Candle body width ratio (0-1)
        'scale_x': 12.0,          # X-axis zoom level
        'crosshair_enabled': True # Toggle crosshair
    }

    chart = EasyPyChart(
        master=root,              # Parent Tkinter widget
        config=config,
        callback=my_event_handler # Optional event callback
    )
    chart.pack(fill='both', expand=True)

Key Configuration Options
~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :widths: 20 15 15 50
   :header-rows: 1

   * - Key
     - Type
     - Default
     - Description
   * - ``width``
     - ``int``
     - ``800``
     - Initial canvas width.
   * - ``height``
     - ``int``
     - ``600``
     - Initial canvas height.
   * - ``background``
     - ``str``
     - ``'#131722'``
     - Hex color code for background.
   * - ``candle_width``
     - ``float``
     - ``0.6``
     - 0.0 to 1.0, relative width of candle body.
   * - ``scale_x``
     - ``float``
     - ``10.0``
     - Pixels per bar (Horizontal Zoom).
   * - ``watermark_text``
     - ``str``
     - ``None``
     - Text to display in background.

Data Management
---------------

EasyPyChart expects a standardized Pandas DataFrame.

load_data(df: pd.DataFrame)
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Loads new data into the chart. Clears existing drawings and global series.
**Required Columns:** ``Datetime`` (or labeled index), ``Open``, ``High``, ``Low``, ``Close``, ``Volume``.

.. code-block:: python

    import pandas as pd
    df = pd.read_csv('data.csv')
    chart.load_data(df)

LayoutManager.update_data(df: pd.DataFrame)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Updates the main chart data while preserving the current session (drawings and indicators).

.. code-block:: python

    # Real-time update
    chart.layout.update_data(new_candle_df)

Plotting & Series
-----------------

You can create multiple drawing areas (subplots) and add various series types to them.

create_subplot(name, weight=1.0)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Creates a new pane.

*   **name**: Unique ID for the subplot.
*   **weight**: Height ratio relative to other panes.

.. code-block:: python

    chart.create_subplot('rsi_pane', weight=1)

create_series(plot_name, data, ...)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Adds a data series to a specific subplot.

**Arguments:**

*   ``plot_name``: Target subplot name (``'candlestick'`` is the default main chart).
*   ``data``: List or Series of values (must match main data length).
*   ``color``: CSS/Hex color.
*   ``type``: ``'line'``, ``'histogram'``, ``'area'``.
*   ``label``: Legend label.

.. code-block:: python

    # Add SMA to main chart
    chart.create_series('candlestick', sma_values, color='#FFFF00', label='SMA 50')

    # Add RSI to separate pane
    chart.create_series('rsi_pane', rsi_values, color='purple', type='line', label='RSI')

plot(name).update(data)
~~~~~~~~~~~~~~~~~~~~~~~
Update an existing series efficiently.

.. code-block:: python

    chart.plot('SMA 50').update(new_sma_values)

Drawing Tools API
-----------------

Programmatic control over interactive drawings. Coordinates are consistent with chart data (Time/Price), not screen pixels.

Common Arguments
~~~~~~~~~~~~~~~~
*   ``dt``/``dt1``/``dt2``: Datetime objects (X-axis).
*   ``price``/``price1``/``price2``: Price values (Y-axis).
*   ``width``: Line thickness (pixels).
*   ``dash``: Tuple (e.g., ``(4, 4)``) for dotted lines, or ``None`` for solid.

Methods
~~~~~~~

1. Horizontal Line
^^^^^^^^^^^^^^^^^^

.. code-block:: python

    chart.create_hline(price=150.0, color='red', label='Resistance', width=2, dash=(4,4))

2. Vertical Line
^^^^^^^^^^^^^^^^

.. code-block:: python

    chart.create_vline(dt=datetime(2023,1,1), color='blue', label='Start Year')

3. Trend Line (Segment)
^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    chart.create_line(dt1, price1, dt2, price2, color='white', width=2)

4. Angled Line (Ray)
^^^^^^^^^^^^^^^^^^^^
Creates a line from a point extending infinitely.
**Note:** Uses screen pixel coordinates for origin ``x, y`` and ``angle``.

.. code-block:: python

    chart.create_angle_line(x=500, y=300, angle=45, color='yellow')

5. Rectangle
^^^^^^^^^^^^

.. code-block:: python

    chart.create_rectangle(dt1, price1, dt2, price2, 
                           fill_color='#00FF0020', # Semi-transparent
                           outline_color='#00FF00')

6. Text
^^^^^^^

.. code-block:: python

    chart.create_text(dt, price, text="Buy Signal", color="white")

Coordinate Extraction
~~~~~~~~~~~~~~~~~~~~~
Retrieve the data coordinates of any shape.

.. code-block:: python

    coords = chart.get_area_xy(tag='shape_id')
    # Returns: {'coordinates': [(dt1, p1), (dt2, p2)], 'shape': 'type'}

get_all_shapes()
~~~~~~~~~~~~~~~~

Returns a list of all active shapes with their coordinates.

.. code-block:: python

    shapes = chart.get_all_shapes()
    # Returns: [{'tag': '...', 'coordinates': ...}, ...]

Interaction & Events
--------------------
The InteractionManager class (defined in interaction_manager.py) is designed as a decoupled component. It must be manually instantiated and attached to the chart instance.
The demo script explicitly shows that the user is responsible for linking these components:
.. code-block:: python
  import EasyPyChart as ep
  import EasyPyChart.interaction_manager as InteractionManager
  import EasyPyChart.layout_manager as LayoutManager
  self.layout = LayoutManager(self.chart)
  self.interaction = InteractionManager(self.chart, self.layout)
  self.chart.layout = self.layout          # Manual attachment
  self.chart.interaction = self.interaction  # Manual attachment

Tool Mode
~~~~~~~~~
Switch the active mouse tool for user interaction.

.. code-block:: python
  

    # Enable drawing mode
    chart.interaction.set_tool('line') 
    # Available: 'line', 'horizontal_line', 'vertical_line', 'rectangle', 'text'

    # Reset to normal navigation (pan/zoom)
    chart.interaction.set_tool(None)
    self.layout = LayoutManager(self.chart)

  .. 'line' (This is the standard 2-point tool used for trend lines)
  .. 'rect'
  .. 'hline'
  .. 'vline'
  .. 'angle_line'
  .. 'long_pos'
  .. 'short_pos'



Event Callback
~~~~~~~~~~~~~~
Register a callback function to handle click and hover events.

.. code-block:: python

    def on_chart_event(bind_key, event_data, event_obj):
        print(f"Event: {event_data['event_type']}")
        print(f"Price: {event_data['price']}")
        
    chart = EasyPyChart(..., callback=on_chart_event)

**Event Data Structure:**

.. code-block:: json

    {
      "event_type": "click",         // Type: click, move, drag, release, scroll, key, hover
      "x": 50.5,                     // Logical Index (float)
      "y": 105.50,                   // Price Value (float)
      "time": "2023-10-15 09:30:00", // Datetime object or Timestamp string
      "sub_plot": "candlestick",     // ID of the subplot under cursor
      "button": "left",              // Mouse button: 'left', 'middle', 'right', 'scroll_up', 'scroll_down'
      "key": "A",                    // Key symbol (if event_type is 'key')
      "char": "a",                   // Key char (if event_type is 'key')
      
      // OHLCV Data (if hovering over a valid bar)
      "open": 100.0,
      "high": 110.0,
      "low": 98.0,
      "close": 105.0,
      "volume": 5000,
      
      // Hit Test Results
      "shape": "rect_123456",        // Tag of clicked/hovered shape
      "series": "SMA 50",            // Label of clicked/hovered series
      
      "original_event": "<Tkinter Event Object>" 
    }

Shape Interaction Events
~~~~~~~~~~~~~~~~~~~~~~~~

When using ``InteractionManager``, the following specific events are emitted:

.. list-table::
   :widths: 20 40 40
   :header-rows: 1

   * - Event Name
     - Description
     - Data Payload
   * - ``shape-create``
     - Fired when a new shape is finished drawing.
     - ``{'shape': 'tag_id', 'type': 'tool_type'}``
   * - ``shape-select``
     - Fired when a shape is clicked/selected.
     - ``{'shape': 'tag_id'}``
   * - ``shape-deselect``
     - Fired when the selection is cleared.
     - ``{}``
   * - ``shape-drop``
     - Fired when a shape is released after dragging.
     - ``{'shape': 'tag_id'}``
   * - ``shape-delete``
     - Fired when a selected shape is deleted.
     - ``{'shape': 'tag_id'}``

Session & Layout Management
---------------------------

The ``LayoutManager`` handles saving and loading the entire chart state, including drawings and indicator configurations.

save_session(filepath)
~~~~~~~~~~~~~~~~~~~~~~
Saves the current view (drawings, active indicators) to a JSON file.

.. code-block:: python

    chart.layout.save_session("analysis_session.json")

load_session(filepath)
~~~~~~~~~~~~~~~~~~~~~~
Restores a previously saved session.

.. code-block:: python

    chart.layout.load_session("analysis_session.json")

add_drawing(tag, shape_type, points, **kwargs)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Manually add a drawing to the layout manager (useful for restoring state).

remove_drawing(tag)
~~~~~~~~~~~~~~~~~~~
Deletes a drawing by its unique tag.

Features Needed
~~~~~~~~~~~~~~~~~~~
Market profile takes time when candle became wider.Move it to background,save precomputed calculations 

