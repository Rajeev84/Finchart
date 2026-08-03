"""
demo_group.py - Grouped Shapes Demo for EasyPyChart
Demonstrates Long/Short Position tools with synchronized grouping.
"""
import os
import sys
import tkinter as tk
from tkinter import ttk
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Ensure local easypychart is in path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from core import EasyPyChart
from interaction_manager import InteractionManager
from layout_manager import LayoutManager

def generate_sample_data(bars=200):
    start = datetime(2026, 1, 1, 9, 30)
    dates = [start + timedelta(minutes=i) for i in range(bars)]
    prices = 100 + np.cumsum(np.random.randn(bars) * 0.5)
    return pd.DataFrame({
        "Datetime": dates,
        "Open": prices,
        "High": prices + 0.5,
        "Low": prices - 0.5,
        "Close": prices + 0.1,
        "Volume": np.random.randint(100, 1000, bars)
    })

class GroupDemoApp:
    def __init__(self, root):
        self.root = root
        self.root.title("EasyPyChart - Grouped Tools Demo")
        self.root.geometry("1200x800")
        self.root.configure(bg="#161A23")

        # UI Layout
        ctrl_bar = tk.Frame(self.root, bg="#1C2330", pady=10)
        ctrl_bar.pack(side="top", fill="x")

        self._btn(ctrl_bar, "Long Pos", lambda: self.interaction.set_tool("long_pos"))
        self._btn(ctrl_bar, "Short Pos", lambda: self.interaction.set_tool("short_pos"))
        self._btn(ctrl_bar, "Select/Pan", lambda: self.interaction.set_tool(None))
        self._btn(ctrl_bar, "Clear All", self.clear_all)
        self._btn(ctrl_bar, "List Tags", self.list_tags)

        # Chart
        self.chart_frame = tk.Frame(self.root, bg="#10141C")
        self.chart_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.chart = EasyPyChart(self.chart_frame, callback=self.on_event)
        self.chart.pack(fill="both", expand=True)

        # Managers
        self.layout = LayoutManager(self.chart)
        self.interaction = InteractionManager(self.chart, self.layout)
        self.chart.layout = self.layout
        self.chart.interaction = self.interaction

        # Load Data
        df = generate_sample_data()
        self.datasets = {"DEMO": {"1m": df}}
        self.layout.data_store = self.datasets
        self.layout.set_context("DEMO", "1m")
        
        # Log area
        self.log_text = tk.Text(self.root, height=6, bg="#0A0D12", fg="#C7D0E0", font=("Consolas", 10))
        self.log_text.pack(fill="x", side="bottom", padx=10, pady=(0, 10))
        self.log("Demo started. Select 'Long Pos' or 'Short Pos' to test grouping.")
        self.log("Instruction: Click 1 (Entry), Click 2 (SL/Width), Click 3 (Target).")

    def _btn(self, parent, text, cmd):
        btn = tk.Button(parent, text=text, command=cmd, bg="#273246", fg="white", relief="flat", padx=10)
        btn.pack(side="left", padx=5)
        return btn

    def log(self, msg):
        self.log_text.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        self.log_text.see("end")

    def on_event(self, event_type, data):
        if event_type == "move" or event_type == "hover":
            return
        
        # Log significant events
        msg = f"Event: {event_type}"
        if "shape" in data:
            msg += f" | Shape: {data['shape']}"
        if "type" in data:
            msg += f" | Tool: {data['type']}"
        
        self.log(msg)

        # Handle deletion sync visualization
        if event_type == "shape-delete":
            self.log(f"Cleanup: All shapes in group {data['shape']} removed.")

    def clear_all(self):
        self.chart.drawings = {}
        if self.layout.current_symbol:
            self.layout.symbol_drawings[self.layout.current_symbol] = {}
        self.chart.render()
        self.log("All drawings cleared.")

    def list_tags(self):
        self.log("Current Drawing Tags:")
        if not self.chart.drawings:
            self.log(" - None")
            return
        for tag in sorted(self.chart.drawings.keys()):
            self.log(f" - {tag}")

if __name__ == "__main__":
    root = tk.Tk()
    app = GroupDemoApp(root)
    root.mainloop()

# --- Added Features Section ---
# 2026-04-23: Created demo_group.py to showcase Long/Short position tool grouping logic.
