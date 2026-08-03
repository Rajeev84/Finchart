import tkinter as tk
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from easypychart import EasyPyChart

def generate_sample_data(n=500):
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
        'Time': dates,
        'Open': opens,
        'High': highs,
        'Low': lows,
        'Close': closes
    })
    return df

def compute_sma(df, column='Close', window=9):
    return df[column].rolling(window=window).mean()

def compute_rsi(df, column='Close', period=14):
    delta = df[column].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def on_event(event_type, value):
    pass
    # print(f"Event: {event_type} | Data: {value}")

def main():
    root = tk.Tk()
    root.title("EasyPyChart Test")
    root.geometry("1000x700")
    
    # Control Panel
    panel = tk.Frame(root)
    panel.pack(side='top', fill='x')
    
    btn_zi = tk.Button(panel, text="Zoom In", command=lambda: chart.zoom_in())
    btn_zi.pack(side='left')
    
    btn_zo = tk.Button(panel, text="Zoom Out", command=lambda: chart.zoom_out())
    btn_zo.pack(side='left')
    
    btn_rst = tk.Button(panel, text="Reset", command=lambda: chart.reset_zoom())
    btn_rst.pack(side='left')

    btn_pan = tk.Button(panel, text="Pan +10", command=lambda: chart.pan(10))
    btn_pan.pack(side='left')

    btn_save = tk.Button(panel, text="Save State", command=lambda: chart.save_state("TEST"))
    btn_save.pack(side='left')
    
    btn_load = tk.Button(panel, text="Load State", command=lambda: chart.load_state("TEST"))
    btn_load.pack(side='left')
    
    btn_clear = tk.Button(panel, text="Clear Drawings", command=lambda: [chart.drawings.clear(), chart.render()])
    btn_clear.pack(side='left')



    def check_persistence():
        print("Running Persistence Check...")
        # 1. Save
        chart.save_state("AUTO_TEST")
        # 2. Clear
        count_before = len(chart.drawings)
        chart.drawings = {}
        chart.render()
        print(f"Cleared. Count: {len(chart.drawings)}")
        # 3. Load
        chart.load_state("AUTO_TEST")
        count_after = len(chart.drawings)
        print(f"Restored. Count: {count_after}")
        
    # root.after(2000, check_persistence) # Disable auto-check for interactive testing

    # Chart
    def on_event(event_type, value):
        msg = f"Event: {event_type} | Plot: {value.get('sub_plot')} | Price: {value.get('y'):.2f}"
        if 'shape' in value: msg += f" | SHAPE: {value['shape']}"
        if 'series' in value: msg += f" | SERIES: {value['series']}"
        print(msg)
        
        # HLine Logic
        if drawing_state['mode'] == 'hline':
            # Cancel on Right Click or Escape
            if event_type == 'click' and value.get('button') == 'right':
                drawing_state['mode'] = None
                chart.delete_shape('ghost_line')
                chart.render()
                print("HLine Tool: CANCELLED")
                return
            
            # Key cancel (Escape) handled if we listen to key events and check keysym
            if event_type == 'key' and value.get('key') == 'Escape':
                drawing_state['mode'] = None
                chart.delete_shape('ghost_line')
                chart.render()
                print("HLine Tool: CANCELLED")
                return

            # Only work on candlestick plot
            if value.get('sub_plot') == 'candlestick':
                current_price = value['y']
                
                if event_type == 'move':
                    # Draw Ghost Line
                    if chart.data and not chart.data.df.empty:
                        t_start = chart.data.df['datetime'].iloc[0]
                        t_end = chart.data.df['datetime'].iloc[-1]
                        
                        chart.create_line(t_start, current_price, t_end, current_price, 
                                          color='white', width=1, label='Ghost', 
                                          plot_name='candlestick', tags='ghost_line')
                    
                elif event_type == 'click' and value.get('button') == 'left':
                    # Place Line
                    # Delete ghost
                    chart.delete_shape('ghost_line')
                    
                    # Create permanent
                    import time
                    uid = f"hline_{int(time.time()*1000)}"
                    if chart.data and not chart.data.df.empty:
                        t_start = chart.data.df['datetime'].iloc[0]
                        t_end = chart.data.df['datetime'].iloc[-1]
                        
                        chart.create_line(t_start, current_price, t_end, current_price, 
                                          color='#00FFFF', width=2, label=f"HLine {current_price:.2f}",
                                          plot_name='candlestick', tags=uid)
                    
                    print(f"HLine PLACED at {current_price:.2f}")
                    drawing_state['mode'] = None

    chart = EasyPyChart(root)
    chart.pack(fill='both', expand=True)
    
    # ---------------------------------------------------------
    # 1. Multi-Timeframe Data Generation
    # ---------------------------------------------------------
    # ---------------------------------------------------------
    # 1. Multi-Timeframe Data Generation
    # ---------------------------------------------------------
    def generate_mtf_data():
        # Generate 1m data
        # Increase dataset size to make 5m look decent
        n = 1000 
        dates = [datetime.now() - timedelta(minutes=n-i) for i in range(n)]
        
        opens = []
        highs = []
        lows = []
        closes = []
        volumes = []
        price = 100.0
        
        for _ in range(n):
            o = price + np.random.uniform(-0.5, 0.5)
            c = o + np.random.uniform(-0.5, 0.5)
            h = max(o, c) + np.random.uniform(0, 0.5)
            l = min(o, c) - np.random.uniform(0, 0.5)
            v = np.random.randint(100, 2000)
            
            opens.append(o)
            closes.append(c)
            highs.append(h)
            lows.append(l)
            volumes.append(v)
            
            price = c
            
        df_1m = pd.DataFrame({
            'Datetime': dates,
            'Open': opens,
            'High': highs,
            'Low': lows,
            'Close': closes,
            'Volume': volumes
        })
        
        # Resample to 5m
        # Set time as index for resampling
        df_temp = df_1m.set_index('Datetime')
        df_5m = df_temp.resample('5min').agg({
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }).dropna().reset_index()
        
        return df_1m, df_5m

    df_1m, df_5m = generate_mtf_data()
    print(f"Generated Data: 1m={len(df_1m)}, 5m={len(df_5m)}")
    
    # ... (Controls) ...
    
    # --- Real-time Logic ---
    def simulate_tick():
        # Generate new candle based on last 1m data
        last_time = df_1m.iloc[-1]['Datetime']
        last_close = df_1m.iloc[-1]['Close']
        
        new_time = last_time + timedelta(minutes=1)
        new_open = last_close
        new_close = new_open + np.random.uniform(-0.5, 0.5)
        new_high = max(new_open, new_close) + np.random.uniform(0, 0.2)
        new_low = min(new_open, new_close) - np.random.uniform(0, 0.2)
        new_vol = np.random.randint(100, 2000)
        
        new_row = pd.DataFrame([{
            'Datetime': new_time,
            'Open': new_open,
            'High': new_high,
            'Low': new_low,
            'Close': new_close,
            'Volume': new_vol
        }])
        
        # 1. Update Main Candle Data
        chart.plot('candlestick').update(new_row)
        
        # Recalculate indicators with FULL data from chart
        # NOTE: In a real app, you might optimize this to only calc latest, but here we re-calc on full series for accuracy
        current_df = chart.data.df
        
        # 2. Update SMA 9
        sma_val = compute_sma(df=current_df, column='close', window=9) # chart.data.df uses lowercase cols
        chart.plot('SMA 9').update(sma_val)

        # 3. Update RSI 14
        rsi_val = compute_rsi(df=current_df, column='close', period=14)
        chart.plot('RSI 14').update(rsi_val)
        
        print(f"Simulated Tick: {new_time} {new_close:.2f} | SMA: {sma_val.iloc[-1]:.2f}")

    # ... (HLine Logic references df['time']) ...
    # Need to verify if on_event uses df directly.
    # on_event uses 'value' from callback. 'value' has 'time' key which comes from data.py 'get_time_from_index'
    # data.py returns the timestamp.
    # But in HLine logic:
    # t_start = df['time'].iloc[0] -> needs to be df['Datetime'] logic.
    # Wait, 'on_event' in test_chart.py doesn't access 'df' global directly except in HLine code I wrote earlier?
    # Yes: t_start = df['time'].iloc[0] was in my code.
    # But now df is df_1m? Or 'chart.data.df'?
    # In 'on_event', I was using 'df' which was global.
    # I should change it to use 'chart.data.df' to be safe and use 'datetime' column (standardized by data.py).
    # Wait, data.py standardizes column to 'datetime' (lowercase) internally!
    # So `chart.data.df['datetime']` is correct regardless of input case.
    # The input DF has 'Datetime', data.py copies it to 'datetime'.
    
    # HOWEVER, my generate_mtf_data returns DF with 'Datetime'.
    # I should check where I access it.
    
    # In HLine logic:
    # t_start = chart.data.df['datetime'].iloc[0] is safer.
    
    # Let's see the previous 'on_event' implementation.


    btn_tick = tk.Button(panel, text="Tick +", command=simulate_tick)
    btn_tick.pack(side='left')

    # Crosshair Toggle
    def toggle_crosshair():
        state = not chart.config.get('crosshair_enabled', False)
        chart.config['crosshair_enabled'] = state
        print(f"Crosshair: {state}")
    
    btn_cross = tk.Button(panel, text="Crosshair", command=toggle_crosshair)
    btn_cross.pack(side='left')

    # Tool State
    # mode: None, 'hline', 'rect'
    # phase: 0 (start), 1 (drag)
    drawing_state = {'mode': None, 'phase': 0, 'start_point': None} 

    def start_hline():
        drawing_state['mode'] = 'hline'
        drawing_state['phase'] = 0
        print("Tool: HLine")

    def start_rect():
        drawing_state['mode'] = 'rect'
        drawing_state['phase'] = 0 # Waiting for first click
        drawing_state['start_point'] = None
        print("Tool: Rectangle (Phase 1: Click start point)")

    btn_hline = tk.Button(panel, text="HLine", command=start_hline)
    btn_hline.pack(side='left')
    
    btn_rect_tool = tk.Button(panel, text="Draw Rect", command=start_rect)
    btn_rect_tool.pack(side='left')
    
    # Load Initial Data
    chart.load_data(df_1m)

    # Initialize Indicators
    # SMA 9
    sma_9 = compute_sma(df=df_1m, column='Close', window=9)
    chart.create_series('candlestick', sma_9, color='#FF0000', label='SMA 9')

    # RSI 14
    chart.create_subplot('rsi', weight=0.3)
    rsi_14 = compute_rsi(df=df_1m, column='Close', period=14)
    chart.create_series('rsi', rsi_14, color='#00FF00', label='RSI 14')
    
    # ---------------------------------------------------------
    # 3. Interactive Logic
    # ---------------------------------------------------------
    def on_event(event_type, value):
        y_val = value.get('y')
        y_str = f"{y_val:.2f}" if y_val is not None else "N/A"
        msg = f"Event: {event_type} | Plot: {value.get('sub_plot')} | Price: {y_str}"
        if 'shape' in value: msg += f" | SHAPE: {value['shape']}"
        # print(msg) # Reduce spam
        
        # Global Cancel (Esc / Right Click)
        if (event_type == 'click' and value.get('button') == 'right') or \
           (event_type == 'key' and value.get('key') == 'Escape'):
            if drawing_state['mode']:
                print(f"Tool {drawing_state['mode']} CANCELLED")
                drawing_state['mode'] = None
                drawing_state['phase'] = 0
                chart.delete_shape('ghost_line')
                chart.delete_shape('ghost_rect')
                chart.render()
                return

        # --- HLine Tool ---
        if drawing_state['mode'] == 'hline':
            if value.get('sub_plot') == 'candlestick':
                current_price = value['y']
                
                if event_type == 'move':
                    t_start = chart.data.df['time'].iloc[0]
                    t_end = chart.data.df['time'].iloc[-1]
                    chart.create_line(t_start, current_price, t_end, current_price, 
                                      color='white', width=1, label='Ghost', 
                                      plot_name='candlestick', tags='ghost_line')
                    
                elif event_type == 'click' and value.get('button') == 'left':
                    chart.delete_shape('ghost_line')
                    import time
                    uid = f"hline_{int(time.time()*1000)}"
                    t_start = chart.data.df['time'].iloc[0]
                    t_end = chart.data.df['time'].iloc[-1]
                    chart.create_line(t_start, current_price, t_end, current_price, 
                                      color='#00FFFF', width=2, label=f"HLine",
                                      plot_name='candlestick', tags=uid)
                    print(f"HLine PLACED at {current_price:.2f}")
                    drawing_state['mode'] = None

        # --- Rectangle Tool ---
        elif drawing_state['mode'] == 'rect':
            if value.get('sub_plot') == 'candlestick':
                curr_t = value['time']
                curr_y = value['y']
                
                # Phase 0: Waiting for Start Point
                if drawing_state['phase'] == 0:
                     if event_type == 'click' and value.get('button') == 'left':
                         drawing_state['start_point'] = (curr_t, curr_y)
                         drawing_state['phase'] = 1
                         print("Rect Phase 2: Drag/Click to end point")
                
                # Phase 1: Dragging / Waiting for End Point
                elif drawing_state['phase'] == 1:
                    start_t, start_y = drawing_state['start_point']
                    
                    if event_type == 'move':
                        # Draw Ghost Rect
                        chart.create_rectangle(start_t, start_y, curr_t, curr_y,
                                               fill_color='#00FF00', label='Ghost',
                                               plot_name='candlestick', tags='ghost_rect')
                                               
                    elif event_type == 'click' and value.get('button') == 'left':
                        # Finalize
                        chart.delete_shape('ghost_rect')
                        import time
                        uid = f"rect_{int(time.time()*1000)}"
                        chart.create_rectangle(start_t, start_y, curr_t, curr_y,
                                               fill_color='#00FF00', label='Rect',
                                               plot_name='candlestick', tags=uid)
                        print("Rectangle PLACED")
                        drawing_state['mode'] = None
                        drawing_state['phase'] = 0

    chart.callback = on_event

    root.mainloop()

if __name__ == "__main__":
    main()
