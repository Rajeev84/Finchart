
import os
import sys
import tkinter as tk
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Add parent directory to sys.path so we can import 'this' folder as a package
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Package name is current folder name
pkg_name = os.path.basename(current_dir)

try:
    # Import components using the package structure to allow relative imports inside the library
    EasyPyChart = __import__(f"{pkg_name}.core", fromlist=["EasyPyChart"]).EasyPyChart
    LayoutManager = __import__(f"{pkg_name}.layout_manager", fromlist=["LayoutManager"]).LayoutManager
except ImportError as e:
    print(f"Failed to import as package '{pkg_name}': {e}")
    # Fallback to local import if possible (might fail due to relative imports in core.py)
    try:
        from core import EasyPyChart
        from layout_manager import LayoutManager
    except Exception as e2:
        print(f"Fallback local import also failed: {e2}")
        sys.exit(1)

def generate_sample_data(symbol, count=100):
    start = datetime.now() - timedelta(minutes=count)
    dates = [start + timedelta(minutes=i) for i in range(count)]
    
    np.random.seed(sum(ord(c) for c in symbol))
    close = 100 + np.random.standard_normal(count).cumsum()
    open_p = close - np.random.standard_normal(count)
    high = np.maximum(open_p, close) + np.abs(np.random.standard_normal(count))
    low = np.minimum(open_p, close) - np.abs(np.random.standard_normal(count))
    
    df = pd.DataFrame({
        'Datetime': dates,
        'Open': open_p,
        'High': high,
        'Low': low,
        'Close': close,
        'Volume': np.random.randint(100, 1000, count)
    })
    return df

def run_demo():
    root = tk.Tk()
    root.title("Multi-Canvas Scenarios Demo")
    root.geometry("1400x800")

    # Layout: Top instructions
    tk.Label(root, text="Multi-Canvas Scenarios: (Left) Different Symbols | (Right) Same Symbol, Different Shapes", 
             font=("Arial", 12, "bold"), pady=10).pack(side="top")

    container = tk.Frame(root)
    container.pack(fill="both", expand=True)

    # --- Scenario 1 & 2 Setup ---
    df_btc = generate_sample_data("BTCUSDT")
    df_eth = generate_sample_data("ETHUSDT")

    # --- Canvas 1 (BTCUSDT) ---
    f1 = tk.Frame(container)
    f1.pack(side="left", fill="both", expand=True, padx=5, pady=5)
    tk.Label(f1, text="Canvas 1: BTCUSDT").pack()
    
    chart1 = EasyPyChart(f1)
    chart1.pack(fill="both", expand=True)
    layout1 = LayoutManager(chart1)
    layout1.data_store = {"BTCUSDT": {"1m": df_btc}}
    layout1.set_context("BTCUSDT", "1m")
    
    # Add unique drawings to Canvas 1
    chart1.create_hline(df_btc['Close'].mean(), color='red', label='BTC Resistance')
    chart1.create_text(df_btc['Datetime'].iloc[50], df_btc['High'].max(), "Analysis A", color="white", label="Note")

    # --- Canvas 2 (ETHUSDT or BTCUSDT) ---
    f2 = tk.Frame(container)
    f2.pack(side="right", fill="both", expand=True, padx=5, pady=5)
    label2 = tk.Label(f2, text="Canvas 2: ETHUSDT")
    label2.pack()
    
    chart2 = EasyPyChart(f2)
    chart2.pack(fill="both", expand=True)
    layout2 = LayoutManager(chart2)
    layout2.data_store = {"ETHUSDT": {"1m": df_eth}, "BTCUSDT": {"1m": df_btc}}
    layout2.set_context("ETHUSDT", "1m")
    
    # Add unique drawings to Canvas 2
    chart2.create_hline(df_eth['Close'].mean(), color='blue', label='ETH Support')

    def switch_to_scenario_2():
        """Changes Canvas 2 to show BTCUSDT but with different shapes."""
        label2.config(text="Canvas 2: BTCUSDT (Different Analysis)")
        layout2.set_context("BTCUSDT", "1m") # Swatch to BTC
        # Clear ETH drawings and add new BTC specific ones
        chart2.create_rectangle(df_btc['Datetime'].iloc[20], df_btc['High'].max(),
                               df_btc['Datetime'].iloc[40], df_btc['Low'].min(),
                               fill_color='#00FF0030', label='Buy Zone')
        print("Canvas 2 switched to BTCUSDT with different shapes.")

    # Control buttons
    btn_frame = tk.Frame(root)
    btn_frame.pack(side="bottom", pady=10)
    tk.Button(btn_frame, text="Switch Canvas 2 to BTC (Same Symbol, Different Shapes)", 
              command=switch_to_scenario_2).pack(side="left", padx=10)
    tk.Button(btn_frame, text="Save Both Sessions", 
              command=lambda: (layout1.save_session("session_btc_a.json"), 
                               layout2.save_session("session_btc_b.json"),
                               print("Sessions saved."))).pack(side="left", padx=10)

    root.mainloop()

if __name__ == "__main__":
    run_demo()
