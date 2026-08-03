"""
Demo 1: Interaction Manager Tutorial
====================================
This script serves as a living companion to README_INTERACTION.rst.
It walks through the evolution of interaction logic.
"""

import time
import pandas as pd
from core import EasyPyChart
from interaction_manager import InteractionManager
from layout_manager import LayoutManager

# 1. Setup minimal chart with dummy data
chart = EasyPyChart()
data = {
    'time': pd.date_range("2026-01-01", periods=100, freq="H"),
    'open': [100 + i for i in range(100)],
    'high': [105 + i for i in range(100)],
    'low': [95 + i for i in range(100)],
    'close': [102 + i for i in range(100)],
}
df = pd.DataFrame(data)
chart.set_data(df)

# 2. Initialize Managers
layout = LayoutManager(chart)
im = InteractionManager(chart, layout)

print("--- TUTORIAL STEP 1: EVENT LISTENING ---")
print("The chart is now capturing raw clicks. Check the console.")

def app_callback(event, data):
    if event == 'tool-start':
         print(f"\n[Tutorial] TOOL STARTED: Click {data['target']} times on the chart.")
    elif event == 'point-capture':
         print(f"[Tutorial] POINT RECEIVED: {data['captured']} of {data['target']} registered.")
    elif event == 'shape-create':
        print(f"\n[Tutorial] SUCCESS: Created {data['shape']} of type {data['type']}")
    elif event == 'shape-select':
        print(f"\n[Tutorial] SELECTION: You picked {data['shape']}. Now try dragging it!")
    elif event == 'shape-drop':
        print(f"\n[Tutorial] DRAG COMPLETE: Shape relocated.")
    elif event == 'capture-stop':
        print("\n[Tutorial] CANCELLED: Tool stopped by user.")
    elif event == 'click':
        # This is a raw event passed through by the manager
        print(f"Raw Click -> Time: {data['time']}, Price: {data.get('y', 'N/A')}")

# Connect our app logic to the manager's output
im._original_callback = app_callback

print("\n--- TUTORIAL STEP 2: SIMPLE TOOLS ---")
print("Press 'L' to activate the LINE tool (2 clicks).")
print("Press 'R' to activate the RECT tool (2 clicks).")
print("Press 'H' or 'V' for Horizontal/Vertical lines.")

# Simple Keyboard-to-Tool mapping for the demo
def on_key(event, data):
    key = data.get('key')
    if key == 'l': im.set_tool('line')
    elif key == 'r': im.set_tool('rect')
    elif key == 'h': im.set_tool('hline')
    elif key == 'v': im.set_tool('vline')
    elif key == 'p': im.set_tool('long_pos')
    elif key == 's': im.set_tool('short_pos')
    elif key == 'Escape': im.stop_capture()
    
# Hook key events
# We need to ensure InteractionManager doesn't swallow keys we want.
# Actually, InteractionManager already handles keys. We just check if they are tool shortcuts.
# In a real app, this would be a UI toolbar.

print("\n--- TUTORIAL STEP 3: THE PRO TOOLS ---")
print("Press 'P' for LONG POSITION (3 phases: Entry, Stop Loss, Target).")
print("Press 'S' for SHORT POSITION.")

# Overlay some instructions on the chart for the user
chart.create_text(df['time'].iloc[10], 150, text="Interaction Tutorial Mode\nL: Line | R: Rect | P: Position\nCheck Console for logs!", fill='white')

chart.show()

# --- Added Features ---
# 1. 2026-04-22: Created interactive tutorial demo tracking README_INTERACTION steps.
