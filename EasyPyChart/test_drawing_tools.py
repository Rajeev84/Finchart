"""
Demo script for new EasyPyChart drawing tools API
Tests: hline, vline, aline, rectangle, and get_area_xy()
"""
import tkinter as tk
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from easypychart import EasyPyChart

def generate_sample_data(n=200):
    dates = [datetime.now() - timedelta(minutes=n-i) for i in range(n)]
    
    opens = []
    highs = []
    lows = []
    closes = []
    price = 100.0
    
    for _ in range(n):
        o = price + np.random.uniform(-1, 1)
        c = o + np.random.uniform(-1, 1)
        h = max(o, c) + np.random.uniform(0, 1)
        l = min(o, c) - np.random.uniform(0, 1)
        
        opens.append(o)
        closes.append(c)
        highs.append(h)
        lows.append(l)
        
        price = c
        
    df = pd.DataFrame({
        'Datetime': dates,
        'Open': opens,
        'High': highs,
        'Low': lows,
        'Close': closes,
        'Volume': [1000] * n
    })
    return df

def main():
    root = tk.Tk()
    root.title("EasyPyChart Drawing Tools Demo")
    root.geometry("1200x700")
    
    # Control Panel
    panel = tk.Frame(root, bg='#1E222D')
    panel.pack(side='top', fill='x', padx=5, pady=5)
    
    # Chart
    chart = EasyPyChart(root, config={'width': 1200, 'height': 650})
    chart.pack(fill='both', expand=True)
    
    # Load data
    df = generate_sample_data()
    chart.load_data(df)
    
    # Demo: Create various drawing tools
    created_shapes = []
    
    def demo_hline():
        """Create horizontal line (support/resistance)"""
        price = 102.5
        tag = chart.create_hline(price, color='#00FFFF', label='Support', width=2)
        created_shapes.append(tag)
        print(f"✓ Created HLine at {price}")
        
        # Get coordinates
        coords = chart.get_area_xy(tag)
        print(f"  Coordinates: {coords}")
    
    def demo_vline():
        """Create vertical line (event marker)"""
        dt = df.iloc[len(df)//2]['Datetime']
        tag = chart.create_vline(dt, color='#FF00FF', label='Event', width=1, dash=(4, 4))
        created_shapes.append(tag)
        print(f"✓ Created VLine at {dt}")
        
        coords = chart.get_area_xy(tag)
        print(f"  Coordinates: {coords}")
    
    def demo_aline():
        """Create angled trendline"""
        dt1 = df.iloc[20]['Datetime']
        dt2 = df.iloc[150]['Datetime']
        p1 = 98.0
        p2 = 105.0
        
        tag = chart.create_aline(dt1, p1, dt2, p2, color='#FFFF00', label='Trendline', width=2)
        created_shapes.append(tag)
        print(f"✓ Created Angled Line from ({dt1}, {p1}) to ({dt2}, {p2})")
        
        coords = chart.get_area_xy(tag)
        print(f"  Coordinates: {coords}")
    
    def demo_rectangle():
        """Create zone/channel"""
        dt1 = df.iloc[50]['Datetime']
        dt2 = df.iloc[120]['Datetime']
        p1 = 99.0
        p2 = 101.0
        
        tag = chart.create_rectangle(dt1, p1, dt2, p2, 
                                     fill_color='#00FF0040',  # Semi-transparent green
                                     label='Zone',
                                     outline_color='#00FF00')
        created_shapes.append(tag)
        print(f"✓ Created Rectangle from ({dt1}, {p1}) to ({dt2}, {p2})")
        
        coords = chart.get_area_xy(tag)
        print(f"  Coordinates: {coords}")
    
    def demo_ghost_line():
        """Create dotted ghost line (preview)"""
        price = 104.0
        tag = chart.create_hline(price, color='white', label='Ghost', width=1, dash=(4, 4), tags='ghost_preview')
        print(f"✓ Created Ghost Line at {price} (dotted)")
    
    def clear_all():
        """Clear all drawings"""
        for tag in created_shapes:
            chart.delete_shape(tag)
        chart.delete_shape('ghost_preview')
        created_shapes.clear()
        print("✓ Cleared all drawings")
    
    def list_all_shapes():
        """List all current shapes with coordinates"""
        print("\n=== Current Shapes ===")
        for tag in chart.drawings.keys():
            coords = chart.get_area_xy(tag)
            if coords:
                print(f"{tag}: {coords['shape']}")
                print(f"  → {coords['coordinates']}")
        print("======================\n")
    
    # Buttons
    tk.Button(panel, text="HLine (Support)", command=demo_hline, bg='#00FFFF', fg='black').pack(side='left', padx=2)
    tk.Button(panel, text="VLine (Event)", command=demo_vline, bg='#FF00FF', fg='black').pack(side='left', padx=2)
    tk.Button(panel, text="Angled Line", command=demo_aline, bg='#FFFF00', fg='black').pack(side='left', padx=2)
    tk.Button(panel, text="Rectangle (Zone)", command=demo_rectangle, bg='#00FF00', fg='black').pack(side='left', padx=2)
    tk.Button(panel, text="Ghost Line (Dotted)", command=demo_ghost_line, bg='white', fg='black').pack(side='left', padx=2)
    tk.Button(panel, text="Clear All", command=clear_all, bg='#F23645', fg='white').pack(side='left', padx=2)
    tk.Button(panel, text="List Shapes", command=list_all_shapes, bg='#363A45', fg='white').pack(side='left', padx=2)
    
    # Auto-create demo shapes on start
    root.after(500, demo_hline)
    root.after(700, demo_vline)
    root.after(900, demo_aline)
    root.after(1100, demo_rectangle)
    root.after(1300, demo_ghost_line)
    root.after(1500, list_all_shapes)
    
    root.mainloop()

if __name__ == "__main__":
    main()
