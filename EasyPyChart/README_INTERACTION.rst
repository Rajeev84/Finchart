Building a Powerful Interaction Layer
======================================

Handling user input in a professional charting library can get messy quickly. This tutorial walks you through how we built the **Interaction Manager** from scratch—moving from simple clicks to complex multi-phase trading tools.

Step 1: The Single-Click Challenge
----------------------------------

Every interaction starts with a simple question: *"Where did the user click?"*

In a basic setup, we just listen for a ``click`` event and output the coordinates. But in a chart, we need **Context**: which subplot was clicked? what was the price? what was the time?

.. code-block:: python

    def handle_click(event, data):
        # Data contains: { 'time': ..., 'y': ..., 'sub_plot': ... }
        print(f"User clicked at {data['time']} on {data['y']}")

This is great for a "Price Label" tool, but falls apart for a "Trend Line".

Step 2: The Two-Point Tool (State Management)
---------------------------------------------

To draw a **Line**, we need two clicks. This introduces **State**. We need to store the first click and wait for the second.

We solve this using a **Capture State Machine**:

.. code-block:: python

    # simplified logic
    capture_state = { 'target': 2, 'points': [] }

    def on_event(event_type, data):
        if event_type == 'click':
            capture_state['points'].append( (data['time'], data['y']) )
            
            if len(capture_state['points']) == 2:
                finalize_line(capture_state['points'])
                stop_capture()

**The Design Secret**: By putting this logic in a central ``InteractionManager``, the core ``Chart`` doesn't have to worry about individual tool states.

Step 3: Adding "Ghosts" (Real-time Feedback)
--------------------------------------------

Waiting for a final click feels "blind". Professional tools use **Ghost Previews**. 

As the user moves their mouse between Click 1 and Click 2, we draw a temporary, dashed "ghost" line.

.. code-block:: python

    def on_move(data):
        if len(capture_state['points']) == 1:
            # Draw a temporary line from pt1 to current cursor
            chart.draw_line(capture_state['points'][0], (data['time'], data['y']), tags='ghost')

Step 4: Master Class - Multi-Phase Tools
----------------------------------------

What if a tool needs more than just two points? Or what if it needs different types of rectangles in sequence?

Take the **Risk/Reward Position Tool**:
1. **Phase 1**: Click twice to define the "Stop Loss" zone (Red rectangle).
2. **Phase 2**: Click once more to define the "Target" zone (Green rectangle).

The Interaction Manager handles this by chaining captures. When Phase 1 completes, it automatically starts a new single-point capture for Phase 2, passing the shared "Base Price" (Entry) along.

Step 5: The Final Level - Grouped Interaction
---------------------------------------------

A complex tool isn't just one shape; it's a collection (Rectangles, Text labels, Lines). 

**The Problem**: If the user moves the "Risk" box, the "Reward" box should follow.
**The Solution**: **Group IDs**. 

We tag every part of a tool with a unique ID (e.g., ``PosUnit_101_SL``, ``PosUnit_101_TGT``). When any part is dragged, the Interaction Manager:
1. Finds all shapes starting with ``PosUnit_101``.
2. Applies the movement delta to all of them at once.

Summary: The I/O Contract
-------------------------

By following this step-by-step approach, we've created a clean interaction contract:

+-----------------+-----------------------+-----------------------------+
| Feature Level   | Input (User Action)   | Output (System Action)      |
+=================+=======================+=============================+
| **Foundational**| Simple Click          | ``shape-select`` event      |
+-----------------+-----------------------+-----------------------------+
| **Intermediate**| Multi-point Capture   | ``shape-create`` event      |
+-----------------+-----------------------+-----------------------------+
| **Advanced**    | Mouse Drag            | Live Group Syncing          |
+-----------------+-----------------------+-----------------------------+
| **Pro**         | Right-Click / ESC     | Safe Capture Cancellation   |
+-----------------+-----------------------+-----------------------------+

Using the Manager in your App
-----------------------------

.. code-block:: python

    # 1. Initialize
    im = InteractionManager(chart, layout)

    # 2. Pick a tool
    im.set_tool('long_pos') # Starts the 2-phase tutorial flow!

    # 3. Handle the results
    def on_finalize(event, data):
         if event == 'shape-create':
             print(f"New tool ready: {data['shape']}")

Full Integration Case Study
---------------------------

In a real-world trading application, you typically want to bind the Interaction Manager to a UI toolbar and a status bar. Here is the "Complete" pattern:

.. code-block:: python

    from EasyPyChart.core import EasyPyChart
    from EasyPyChart.interaction_manager import InteractionManager
    from EasyPyChart.layout_manager import LayoutManager

    # 1. Standard Setup
    chart = EasyPyChart()
    layout = LayoutManager(chart)
    interaction = InteractionManager(chart, layout)

    # 2. Define a sophisticated callback
    def on_interaction(event, data):
        if event == 'tool-start':
            # Signals when a user picks a tool (e.g., 'line')
            print(f"Tool Active: Please select {data['target']} points.")
            
        elif event == 'point-capture':
            # Signals every time a click is recorded during capture
            print(f"Progress: {data['captured']} of {data['target']} points set.")
            
        elif event == 'shape-create':
            # Signals when the tool is finished and the shape is finalized
            print(f"Success: {data['shape']} created.")
            save_drawing_to_db(data['shape'], chart.drawings[data['shape']])
            
        elif event == 'capture-stop':
            # Signals if the user cancels via ESC or Right-click
            print("Interaction Cancelled by user.")

        elif event == 'shape-select':
            update_gui_properties(data['shape'])
            
        elif event == 'click':
            # Raw passthrough still works for general UI
            status_bar.set(f"Price: {data['y']:.2f}")

    # 3. Connect and Go!
    interaction._original_callback = on_interaction
    interaction.set_tool('rect') # User is now drawing a supply zone!

Added Features
--------------
- Completely refactored README into a step-by-step tutorial.
- Explained progression from single-click to complex grouped units.
- simplified I/O contract table.
- Added "Full Integration Case Study" code example.

The InteractionManager uses a "Middle-Man" (Proxy) Architecture to ensure you don't lose any of the chart's original event-listening power.

Here is exactly how it works and how you use it:

1. The Hooking Mechanism
    When you create the InteractionManager, it automatically "hijacks" the chart's callback. It saves whatever was there before and inserts itself into the stream:
        code-block:: python

            # What happens inside the library:
            self._original_callback = chart.callback  # 1. Save your previous logic
            chart.callback = self.process_event       # 2. Manager takes control
2. How to use it with on_interaction
    You have two ways to use your custom function on_interaction with the manager:

    Option A: The "Direct Attachment" (Recommended)
        You tell the manager: "Process the events first, and then send everything to my function."

        code-block:: python

            interaction = InteractionManager(chart, layout)
            # Re-route the manager's output to your custom function
            interaction._original_callback = on_interaction
    
    Option B: The "Chart-First" Setup
    If you set your callback on the chart before creating the manager, it handles the connection for you automatically:

        code-block:: python
            chart.callback = on_interaction  # Set logic on chart
            interaction = InteractionManager(chart, layout) # Manager saves it automatically!
    3. Why this is powerful
    Because the manager "wraps" your callback, your on_interaction function now receives Higher-Intelligence Events that the raw chart doesn't know about:

    Event Source	Type	What your on_interaction sees
    From Chart	Raw	click, move, key
    From Manager	Smart	tool-start, point-capture, shape-create