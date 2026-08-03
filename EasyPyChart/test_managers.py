"""
Test Script for LayoutManager and InteractionManager
Tests Multi-Symbol / Multi-Timeframe alignment and persistence.
"""
import tkinter as tk
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Ensure we can import from parent directory if running directly
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from easypychart.core import EasyPyChart
from easypychart.layout_manager import LayoutManager
from easypychart.interaction_manager import InteractionManager

# --- Data Generation ---
def generate_aligned_data(symbol, n_5m=500):
    """
    Generates 5m data and aggregates to 10m data.
    Ensures alignment.
    """
    # Deterministic seed based on symbol name length for variety but consistency
    np.random.seed(len(symbol))
    
    start_time = datetime(2025, 1, 1, 9, 30)
    dates_5m = [start_time + timedelta(minutes=5*i) for i in range(n_5m)]
    
    # Base Price
    price = 1000.0 if symbol.startswith('ETH') else 50000.0
    
    opens, highs, lows, closes, vols = [], [], [], [], []
    
    for _ in range(n_5m):
        change = np.random.uniform(-0.002, 0.002)
        o = price
        c = price * (1 + change)
        h = max(o, c) * (1 + np.random.uniform(0, 0.001))
        l = min(o, c) * (1 - np.random.uniform(0, 0.001))
        v = int(np.random.uniform(100, 5000))
        
        opens.append(o); closes.append(c); highs.append(h); lows.append(l); vols.append(v)
        price = c
        
    df_5m = pd.DataFrame({
        'Datetime': dates_5m, 'Open': opens, 'High': highs, 'Low': lows, 'Close': closes, 'Volume': vols
    })
    
    # Resample to 10m
    df_temp = df_5m.set_index('Datetime')
    df_10m = df_temp.resample('10min').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }).dropna().reset_index()
    
    return df_5m, df_10m

# --- Main App ---
def main():
    root = tk.Tk()
    root.title("EasyPyChart Manager Test: Multi-Symbol/TF")
    root.geometry("1400x800")
    
    # 1. Setup UI
    toolbar = tk.Frame(root, bg='#2B2E39')
    toolbar.pack(side='top', fill='x')
    
    # 2. Setup Chart
    print("DEBUG: Setting up Chart...")
    chart = EasyPyChart(root)
    chart.pack(fill='both', expand=True)
    
    # 3. Setup Managers
    print("DEBUG: Setting up Managers...")
    layout = LayoutManager(chart)
    interaction = InteractionManager(chart, layout)
    
    # 4. Global Indicators (Should persist)
    print("DEBUG: Configuring Global Indicators...")
    # Add RSI pane (LayoutManager ensures it exists)
    # Add RSI pane (LayoutManager ensures it exists)
    layout.add_indicator_config('rsi_14', 'RSI 14', 'rsi_pane') 
    
    # 5. Data Store
    print("DEBUG: Generating Aligned Data...")
    btc_data = {
        '5m': generate_aligned_data('BTCUSDT')[0],
        '10m': generate_aligned_data('BTCUSDT')[1]
    }
    eth_data = {
        '5m': generate_aligned_data('ETHUSDT')[0],
        '10m': generate_aligned_data('ETHUSDT')[1]
    }
    
    # Pre-load data into LayoutManager (User logic simulation)
    # We need to set context first to bind data to symbol?
    # Test Script Workflow:
    # 1. Set Context BTC
    # 2. Load Data for BTC (All TFs)
    # 3. Set Context ETH
    # 4. Load Data for ETH (All TFs)
    
    print("DEBUG: Loading Data into LayoutManager...")
    layout.set_context('BTCUSDT', '5m')
    layout.load_data(btc_data)
    
    layout.set_context('ETHUSDT', '5m')
    layout.load_data(eth_data)
    
    def switch_context(symbol, tf):
        print(f"\n--- Switching to {symbol} {tf} ---")
        layout.set_context(symbol, tf)
        # Data is auto-loaded by manager now!
        
        # Calculate & Update Global Indicators manually (Simulation of App Logic)
        # App logic needs to get CURRENT data to recalc
        # We can fetch it availability from chart.data.df or manager store?
        # Simulation:
        if layout.chart.data is None:
             print("DEBUG: Chart Data is None")
             return
        df = layout.chart.data.df
        if df is None or df.empty: return

        # RSI 14
        # RSI 14 - CHECK IF ENABLED
        rsi_active = any(i['id'] == 'rsi_14' for i in layout.global_indicators)
        if rsi_active:
             delta = df['close'].diff()
             gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
             loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
             rs = gain / loss
             rsi = 100 - (100 / (1 + rs))
             
             chart.create_series('rsi_pane', rsi, color='#00FF00', label='RSI')
             print(f"Loaded {len(df)} bars. RSI updated.")
        else:
             print(f"Loaded {len(df)} bars. RSI skipped (disabled).")

    # 6. Buttons
    def set_tool(t): interaction.set_tool(t)
    
    # Tool Buttons
    tk.Label(toolbar, text="Tools:", bg='#2B2E39', fg='white').pack(side='left', padx=5)
    tk.Button(toolbar, text="Line", command=lambda: set_tool('line'), bg='#444').pack(side='left', padx=2)
    tk.Button(toolbar, text="Rect", command=lambda: set_tool('rect'), bg='#444').pack(side='left', padx=2)
    
    # Context Switching
    switch_frame = tk.Frame(toolbar, bg='#2B2E39')
    switch_frame.pack(side='left', padx=10)
    
    tk.Label(switch_frame, text="Context:", bg='#2B2E39', fg='white').pack(side='left')
    
    contexts = [
        ('BTC 5m', 'BTCUSDT', '5m'),
        ('BTC 10m', 'BTCUSDT', '10m'),
        ('ETH 5m', 'ETHUSDT', '5m'),
        ('ETH 10m', 'ETHUSDT', '10m'),
    ]
    
    for label, sym, tf in contexts:
        tk.Button(switch_frame, text=label, 
                  command=lambda s=sym, t=tf: switch_context(s, t)).pack(side='left', padx=2)
                  
    # Session Persistence
    session_frame = tk.Frame(toolbar, bg='#2B2E39')
    session_frame.pack(side='left', padx=10)
    tk.Label(session_frame, text="Session:", bg='#2B2E39', fg='white').pack(side='left')
    
    def on_save():
        layout.save_session("session_snapshot.json")
        print("DEBUG: GUI Save Triggered")
        
    def on_load():
        layout.load_session("session_snapshot.json")
        print("DEBUG: GUI Load Triggered")
        
        # REFRESH APP LOGIC (RSI)
        # The Manager restored the layout/drawings, but the App (this script)
        # needs to re-calculate and plot the RSI series data for the new context.
        if layout.current_symbol and layout.current_timeframe:
            print(f"DEBUG: Refreshing App State for {layout.current_symbol} {layout.current_timeframe}")
            switch_context(layout.current_symbol, layout.current_timeframe)
        else:
             print("DEBUG: No context loaded.")
        
    tk.Button(session_frame, text="Save Snapshot", command=on_save, bg='#004488', fg='white').pack(side='left', padx=2)
    tk.Button(session_frame, text="Load Snapshot", command=on_load, bg='#003366', fg='white').pack(side='left', padx=2)
    
    # Debug / Maintenance
    maint_frame = tk.Frame(toolbar, bg='#2B2E39')
    maint_frame.pack(side='left', padx=10)
    tk.Label(maint_frame, text="Debug:", bg='#2B2E39', fg='white').pack(side='left')
    
    tk.Button(maint_frame, text="Print Drawings", command=lambda: print(layout.get_drawings()), bg='#666').pack(side='left', padx=2)
    
    def remove_rsi():
        layout.remove_indicator_config("rsi_14")
        # Trigger reload to reflect changes (rebuild_chart or just set_context)
        # Setting context will rebuild layout.
        if layout.current_symbol:
            layout.set_context(layout.current_symbol, layout.current_timeframe)
            
    tk.Button(maint_frame, text="Del RSI", command=remove_rsi, bg='#882222', fg='white').pack(side='left', padx=2)

    # Initial Load
    switch_context('BTCUSDT', '5m')
    
    print("DEBUG: Starting Mainloop...")
    root.mainloop()

if __name__ == "__main__":
    print("DEBUG: Script Started")
    try:
        main()
    except Exception as e:
        import traceback
        traceback.print_exc()
        input("Press Enter to Exit...")
