import tkinter as tk
from easypychart import EasyPyChart
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def main():
    root = tk.Tk()
    root.title("EasyPyChart Real-time Empty Start")
    root.geometry("1000x800")
    
    # Chart with empty data (EasyPyChart defaults to empty if no data loaded loop?)
    # EasyPyChart logic: data initialized as None. load_data creates ChartData.
    # If we pass None to load_data?
    # EasyPyChart.load_data(None) calls ChartData(None) which is now safe.
    chart = EasyPyChart(root)
    chart.pack(fill='both', expand=True)
    chart.load_data(None) # Initialize Empty
    
    # State for generation
    gen_state = {
        'price': 100.0,
        'time': datetime.now(),
        'count': 0
    }
    
    def update_loop():
        # Generate 1 candle
        o = gen_state['price']
        c = o + np.random.uniform(-1, 1)
        h = max(o, c) + np.random.uniform(0, 0.5)
        l = min(o, c) - np.random.uniform(0, 0.5)
        
        # Advance time 1s? User said "update every 1 second".
        # If we use 1m interval labels, 1s updates will look weird on axis unless we zoom in?
        # Let's assume 1s interval.
        t = gen_state['time']
        
        df = pd.DataFrame([{
            'Datetime': t,
            'Open': o,
            'High': h,
            'Low': l,
            'Close': c,
            'Volume': np.random.randint(100, 1000)
        }])
        
        # Update Chart
        chart.plot('candlestick').update(df)
        
        # Update State
        gen_state['price'] = c
        gen_state['time'] = t + timedelta(seconds=1)
        gen_state['count'] += 1
        
        # Auto-scroll?
        # If data grows beyond view, we might want to pan.
        # Current logic: offset 0 means index 0 is at left.
        # As len grows, candles appear to the right.
        # If len > capacity, they go off screen to right.
        # To "autoscroll" to keep latest visible:
        # capacity = width / scale
        # if len > capacity: offset = len - capacity + buffer
        
        capacity = chart.config['width'] / chart.config['scale_x']
        current_len = chart.data.get_len()
        if current_len > capacity - 5: # Keep some buffer
             target_offset = current_len - (capacity - 10)
             if target_offset > chart.config['offset_x']:
                 chart.config['offset_x'] = target_offset
                 chart.render()
        
        # Schedule next
        root.after(1000, update_loop)

    # Start loop
    root.after(1000, update_loop)
    
    # Label
    lbl = tk.Label(root, text="Real-time updating 1 candle/sec starting from empty.")
    lbl.pack(side='top')

    root.mainloop()

if __name__ == "__main__":
    main()
