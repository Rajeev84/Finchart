import tkinter as tk
from tkinter import ttk
from .data import ChartData
import pandas as pd
import numpy as np
import json
import os
import copy
from datetime import datetime

class EasyPyChart(tk.Frame):
    def __init__(self, master=None, canvas=None, callback=None, config=None, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        
        # Configuration
        self.config = {
            'width': 800,
            'height': 600,
            'background': '#131722', # TradingView dark theme default
            'candle_width': 0.6,
            'scale_x': 10, # pixels per bar
            'scale_y': 1.0,
            'offset_x': 0, # Index offset
            'offset_y': 0,
            'crosshair_enabled': True,
            'crosshair_color': '#9598A1',
            'padding_right': 60,
            'padding_bottom': 30,
            'panning_enabled': True,
        }
        if config:
            self.config.update(config)

        # Callbacks
        self.callback = callback

        # UI Setup
        self._setup_ui(canvas)
        
        # Data
        self.data: ChartData = None
        
        # Subplots
        self.subplots = {}
        self.create_subplot('candlestick', weight=0.6)
        
        # State
        self.objects = {} # tag -> object info
        self.drawings = {}
        self.drag_start = None
        self.last_x = 0
        self.last_min_y = 0
        self.last_max_y = 100.0
        self.selected_tags = set()
        self.selected_handle_tag = None
        self.handle_hitboxes = []
        
        # Bindings
        self._bind_events()

    @property
    def selected_tag(self):
        """Backward compatibility for single selection."""
        return next(iter(self.selected_tags)) if self.selected_tags else None
        
    @selected_tag.setter
    def selected_tag(self, value):
        if value:
            self.selected_tags = {value}
        else:
            self.selected_tags = set()

    def _normalize_rect_points(self, points):
        """Return rectangle points as (left/top) and (right/bottom) pairs."""
        if len(points) < 2:
            return points

        (dt1, price1), (dt2, price2) = points[:2]
        if self.data and hasattr(self.data, "get_index_from_time"):
            try:
                idx1 = self.data.get_index_from_time(dt1)
                idx2 = self.data.get_index_from_time(dt2)
                left_pt, right_pt = ((dt1, price1), (dt2, price2)) if idx1 <= idx2 else ((dt2, price2), (dt1, price1))
            except Exception:
                left_pt, right_pt = ((dt1, price1), (dt2, price2)) if dt1 <= dt2 else ((dt2, price2), (dt1, price1))
        else:
            left_pt, right_pt = ((dt1, price1), (dt2, price2)) if dt1 <= dt2 else ((dt2, price2), (dt1, price1))

        left_dt = left_pt[0]
        right_dt = right_pt[0]
        top_price = max(price1, price2)
        bottom_price = min(price1, price2)
        return [(left_dt, top_price), (right_dt, bottom_price)]

    def _register_handle_hitbox(self, tag, handle_name, x, y, size):
        self.handle_hitboxes.append({
            "tag": tag,
            "handle": handle_name,
            "bbox": (x - size, y - size, x + size, y + size),
        })

    def _draw_handle(self, tag, handle_name, x, y, fill="#FFFFFF", outline="#000000", size=4):
        self.canvas.create_oval(
            x - size,
            y - size,
            x + size,
            y + size,
            fill=fill,
            outline=outline,
            width=1,
            tags=("shape_handle", f"handle_{tag}_{handle_name}"),
        )
        self._register_handle_hitbox(tag, handle_name, x, y, size)

    def _draw_selection_handles(self, tag, shape, canvas_points):
        """Draw resize handles for the currently selected shape."""
        if not canvas_points:
            return

        handle_fill = "#FFD166"
        handle_outline = "#1A1A1A"
        handle_size = 4
        shape_type = shape.get("type")

        if shape_type == "line" and len(canvas_points) >= 2:
            (x1, y1), (x2, y2) = canvas_points[:2]
            self._draw_handle(tag, "start", x1, y1, fill=handle_fill, outline=handle_outline, size=handle_size)
            self._draw_handle(tag, "end", x2, y2, fill=handle_fill, outline=handle_outline, size=handle_size)
            return

        if shape_type != "rect" or len(canvas_points) < 2:
            return

        x1, y1 = canvas_points[0]
        x2, y2 = canvas_points[1]
        left_x, right_x = sorted([x1, x2])
        top_y, bottom_y = sorted([y1, y2])

        if isinstance(tag, str) and tag.startswith("PosUnit_"):
            mid_y = (top_y + bottom_y) / 2
            self._draw_handle(tag, "lt", left_x, top_y, fill=handle_fill, outline=handle_outline, size=handle_size)
            self._draw_handle(tag, "lm", left_x, mid_y, fill=handle_fill, outline=handle_outline, size=handle_size)
            self._draw_handle(tag, "lb", left_x, bottom_y, fill=handle_fill, outline=handle_outline, size=handle_size)
            return

        self._draw_handle(tag, "tl", left_x, top_y, fill=handle_fill, outline=handle_outline, size=handle_size)
        self._draw_handle(tag, "br", right_x, bottom_y, fill=handle_fill, outline=handle_outline, size=handle_size)

    def _setup_ui(self, canvas):
        # We assume we are the container Frame
        # User request: "border around canvas to know the widget cordinates"
        # We apply border to the Frame itself
        self.configure(highlightthickness=2, highlightbackground='#FF0000') # Red border as requested
        
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        if canvas:
            self.canvas = canvas
            if self.canvas.master != self:
                pass 
        else:
            self.canvas = tk.Canvas(self, 
                                    width=self.config['width'], 
                                    height=self.config['height'],
                                    bg=self.config['background'],
                                    highlightthickness=0)
            self.canvas.grid(row=0, column=0, sticky='nsew')

    # --- Plot API ---
    class PlotHandle:
        def __init__(self, chart, target_type, target_name):
            self.chart = chart
            self.type = target_type # 'data', 'series'
            self.name = target_name # label or subplot name

        def update(self, data):
            if self.type == 'data':
                # Update ChartData
                if self.chart.data:
                    self.chart.data.update(data)
                    self.chart.render()
                else:
                    self.chart.load_data(data)
            elif self.type == 'series':
                # Find series and update
                # Name is label. We search all subplots.
                found = False
                for sp_name, sp in self.chart.subplots.items():
                    if 'series' in sp:
                        for s in sp['series']:
                            if s['label'] == self.name:
                                # Update data
                                # If data is Series, we might need a way to merge?
                                # For simplicity, we REPLAce the data or APPEND?
                                # User said "df['sma_9']", which is a full series usually.
                                # But if "realtime", we want append.
                                # Series data is currently just a list or Series.
                                # We can try to concat if it's pandas.
                                if isinstance(s['data'], (pd.Series, pd.DataFrame)) and isinstance(data, (pd.Series, pd.DataFrame)):
                                    # Very naive append for now
                                    s['data'] = pd.concat([s['data'], data])
                                    # Ensure unique index? Series usually relies on position matching main DF.
                                    # If main DF grew, Series must grow.
                                else:
                                    # List append or replace?
                                    # If data is scalar, append. If list, extend.
                                    if np.isscalar(data):
                                        pass # Not supported yet
                                    else:
                                        # Replace is safer for now unless we structure Series better
                                        s['data'] = data
                                found = True
                
                if found:
                    self.chart.render()
        
        def delete(self):
            if self.type == 'series':
                # Remove series
                 for sp_name, sp in self.chart.subplots.items():
                    if 'series' in sp:
                         sp['series'] = [s for s in sp['series'] if s['label'] != self.name]
                 self.chart.render()
            elif self.type == 'data':
                self.chart.data = None
                self.chart.render()

    def plot(self, name):
        """
        Returns a handle to manipulate a plot/series.
        Usage: chart.plot('candlestick').update(df)
               chart.plot('sma_9').update(series)
        """
        # If 'candlestick', return data wrapper
        if name == 'candlestick':
            return self.PlotHandle(self, 'data', name)
        
        # Else assume it is a series label
        return self.PlotHandle(self, 'series', name)

    def reset_subplots(self):
        """Resets subplots to default state (only candlestick)."""
        self.subplots = {}
        self.create_subplot('candlestick', weight=0.6)
        self.render()

    def clear(self):
        """Clears the chart data and canvas."""
        self.data = None
        self.drawings = {}
        self.objects = {}
        self.render()

    def load_data(self, df: pd.DataFrame):
        self.data = ChartData(df)
        
        # Auto-Pan to End (Latest Data)
        try:
            eff_w, _ = self.get_chart_area()
            scale = self.config['scale_x']
            
            if not self.data.df.empty:
                total_bars = len(self.data.df)
                visible_bars = eff_w / scale
                # Align end of data to right side with some padding (5 bars)
                target_offset = total_bars - visible_bars + 5
                
                # If data fits entirely on screen, center or start at 0?
                # Start at 0 is safer.
                if target_offset < 0: target_offset = 0
                
                self.config['offset_x'] = target_offset
            else:
                self.config['offset_x'] = 0
        except:
            self.config['offset_x'] = 0
            
        # Clear drawings and objects on new data load
        self.drawings = {}
        self.objects = {}
        
        # Clear series from all subplots to avoid duplication
        for sp in self.subplots.values():
            if 'series' in sp:
                sp['series'] = []
                
        self.render()

    def _bind_events(self):
        # Mouse
        self.canvas.bind('<Button-1>', self._on_mouse_down)
        self.canvas.bind('<Button-2>', self._on_mouse_down) # Middle
        self.canvas.bind('<Button-3>', self._on_mouse_down) # Right
        
        self.canvas.bind('<B1-Motion>', self._on_mouse_drag)
        self.canvas.bind('<B2-Motion>', self._on_mouse_drag)
        self.canvas.bind('<B3-Motion>', self._on_mouse_drag)
        
        self.canvas.bind('<ButtonRelease-1>', self._on_mouse_up)
        self.canvas.bind('<ButtonRelease-2>', self._on_mouse_up)
        self.canvas.bind('<ButtonRelease-3>', self._on_mouse_up)
        
        self.canvas.bind('<Motion>', self._on_mouse_move)
        
        # Scroll/Zoom
        # Linux uses Button-4/5, Windows/Mac uses MouseWheel
        self.canvas.bind('<MouseWheel>', self._on_scroll)
        self.canvas.bind('<Button-4>', self._on_scroll)
        self.canvas.bind('<Button-5>', self._on_scroll)
        
        # Keyboard (requires focus)
        self.canvas.focus_set()
        self.canvas.bind('<KeyPress>', self._on_key_press)
        
        self.canvas.bind('<Configure>', self._on_resize)
        
    def _on_resize(self, event):
        self.config['width'] = event.width
        self.config['height'] = event.height
        self.render()
        
        
    def _on_mouse_down(self, event):
        self.canvas.focus_set() # Enable keyboard events
        self.drag_start = event.x
        self.last_x = event.x
        self._dispatch('click', event)
        
    def _on_mouse_drag(self, event):
        if self.drag_start is not None and self.config.get('panning_enabled', True):
             # print(f"DEBUG: Panning Active. Enabled={self.config.get('panning_enabled', True)}")
             delta = event.x - self.last_x
             # Dragging right moves view left (offset decreases), so we subtract delta converted to index
             # One pixel = 1/scale_x units
             # But offset is in Units (Index). 
             # pixel_delta / scale_x = unit_delta
             unit_delta = delta / self.config['scale_x']
             self.pan(unit_delta)
             self.last_x = event.x
             # print(f"DEBUG: Panning delta={unit_delta}") # Too noisy?

        self._draw_crosshair(event.x, event.y)
        self._dispatch('drag', event)

    def _on_mouse_up(self, event):
        self.drag_start = None
        self._dispatch('release', event)

    def _draw_crosshair(self, x, y):
        self.canvas.delete('crosshair')
        if not self.config.get('crosshair_enabled'):
            return

        w = self.config['width']
        h = self.config['height']
        eff_w, eff_h = self.get_chart_area()
        
        # Only draw if inside chart area
        if x > eff_w or y > eff_h: return

        color = self.config.get('crosshair_color', '#9598A1')
        
        # Lines (Dashed, stops at axis limit)
        self.canvas.create_line(x, 0, x, eff_h, fill=color, dash=(4, 4), tag='crosshair')
        self.canvas.create_line(0, y, eff_w, y, fill=color, dash=(4, 4), tag='crosshair')
        
        # Extensions to Axis (Sold Lines connecting to labels)
        self.canvas.create_line(eff_w, y, w, y, fill=color, tag='crosshair') # Price Tick line
        self.canvas.create_line(x, eff_h, x, h, fill=color, tag='crosshair') # Date Tick line
        
        # Labels
        # Price Label (Right Margin)
        if self.data:
            try:
                price = self.inverse_transform_y(y)
                price_text = f"{price:.2f}"
                
                # Label Box in Right Margin
                rect_y1 = y - 10
                rect_y2 = y + 10
                pad_start = eff_w
                
                self.canvas.create_rectangle(pad_start, rect_y1, w, rect_y2, fill='#363A45', outline=color, tag='crosshair')
                self.canvas.create_text((pad_start + w)/2, y, text=price_text, fill='white', font=('Helvetica', 8), tag='crosshair')
            except: pass
            
            # Date Label (Bottom Margin)
            try:
                raw_idx = self.inverse_transform_x(x)
                # Snap to nearest candle (integer index) so label shows
                # the candle's open time, not an interpolated sub-candle timestamp.
                idx = max(0, min(round(raw_idx), self.data.get_len() - 1))
                # Get the candle's actual Datetime directly from the dataframe row
                d_val = self.data.df.iloc[idx]['Datetime']
                
                if d_val is not None:
                    try: 
                        if isinstance(d_val, (pd.Timestamp, datetime, np.datetime64)):
                            d_str = pd.to_datetime(d_val).strftime("%Y-%m-%d %H:%M")
                        else:
                            d_str = str(d_val)
                    except: d_str = str(d_val)
                    
                    # Label Box in Bottom Margin
                    th = 20
                    rect_y1 = eff_h
                    rect_y2 = eff_h + th
                    
                    tw = len(d_str) * 7 + 10
                    rect_x1 = x - tw/2
                    rect_x2 = x + tw/2
                    
                    # Clamp
                    if rect_x1 < 0: 
                        diff = -rect_x1; rect_x1 += diff; rect_x2 += diff
                    if rect_x2 > w:
                        diff = rect_x2 - w; rect_x1 -= diff; rect_x2 -= diff
                         
                    self.canvas.create_rectangle(rect_x1, rect_y1, rect_x2, rect_y2, fill='#363A45', outline=color, tag='crosshair')
                    self.canvas.create_text((rect_x1 + rect_x2)/2, (rect_y1+rect_y2)/2, text=d_str, fill='white', font=('Helvetica', 8), tag='crosshair')
            except: pass

    def _on_mouse_move(self, event):
        if self.drag_start is not None:
             delta = event.x - self.last_x
             unit_delta = delta / self.config['scale_x']
             # Dragging right moves view left -> decrease offset
             self.pan(unit_delta)
             self.last_x = event.x

        self._draw_crosshair(event.x, event.y)
        
        # Hover Data Callback
        if self.data and self.callback:
            idx = int(round(self.inverse_transform_x(event.x)))
            if 0 <= idx < self.data.get_len():
                # Extract row as dict
                row = self.data.df.iloc[idx]
                data_dict = row.to_dict()
                # Ensure date string format if needed, or let receiver handle
                self.callback('hover', data_dict)
                
        self._dispatch('move', event)

    def _on_scroll(self, event):
        # Windows: event.delta (120 or -120 usually)
        # Linux: Button-4 up, Button-5 down
        direction = 0
        if event.num == 4 or (hasattr(event, 'delta') and event.delta > 0):
            direction = 1
        elif event.num == 5 or (hasattr(event, 'delta') and event.delta < 0):
            direction = -1
            
        if direction == 1:
            self.zoom_in(event.x)
        elif direction == -1:
            self.zoom_out(event.x)
            
        self._dispatch('scroll', event)
    
    # --- Interaction API ---
    def zoom_in(self, x=None):
        if x is None: x = self.config['width'] / 2
        
        old_scale = self.config['scale_x']
        new_scale = old_scale * 1.1
        
        self.config['scale_x'] = new_scale
        
        # Adjust offset to anchor zoom at x
        # new_offset = old_offset + x * (1/old_scale - 1/new_scale)
        self.config['offset_x'] += x * (1/old_scale - 1/new_scale)
        
        self.render()
        
    def zoom_out(self, x=None):
        if x is None: x = self.config['width'] / 2
        
        old_scale = self.config['scale_x']
        new_scale = old_scale * 0.9
        if new_scale < 0.1: new_scale = 0.1
        
        self.config['scale_x'] = new_scale
        
        self.config['offset_x'] += x * (1/old_scale - 1/new_scale)
        
        self.render()

    def reset_zoom(self):
        self.config['scale_x'] = 10
        self.config['offset_x'] = 0
        self.render()

    def pan(self, delta_index):
        """
        Pans the chart by delta_index units.
        Returns the first and last candle indexes currently in view.
        """
        self.config['offset_x'] -= delta_index
        # Clamp? Maybe not, allow infinite pan for now, or clamp to data logic later
        self.render()
        
        # Return the visible range
        return self.calculate_visible_range()

    def _on_key_press(self, event):
        self._dispatch('key', event)

    # --- Drawing API ---
    def create_rectangle(self, dt1, price1, dt2, price2, fill_color, label, plot_name='candlestick', tags=None, **kwargs):
        """Creates a rectangle shape."""
        if tags is None: tags = f"shape_{len(self.drawings)}"
        
        self.drawings[tags] = {
            'type': 'rect',
            'points': [(dt1, price1), (dt2, price2)],
            'fill': fill_color,
            'label': label,
            'plot': plot_name,
            'kwargs': kwargs
        }
        self.render()
        return tags

    def create_line(self, dt1, price1, dt2, price2, color, label, plot_name='candlestick', tags=None, width=2, dash=None, **kwargs):
        """Creates a line shape.
        
        Args:
            dt1, price1: Start point (datetime, price)
            dt2, price2: End point (datetime, price)
            color: Line color
            label: Shape label
            plot_name: Target subplot
            tags: Unique identifier
            width: Line thickness (default 2)
            dash: Tuple for dash pattern, e.g., (4, 4) for dotted. None for solid.
        """
        if tags is None: tags = f"shape_{len(self.drawings)}"
        
        self.drawings[tags] = {
            'type': 'line',
            'points': [(dt1, price1), (dt2, price2)],
            'fill': color,
            'label': label,
            'plot': plot_name,
            'width': width,
            'dash': dash,
            'kwargs': kwargs
        }
        self.render()
        return tags

    def create_hline(self, price, color='#00FFFF', label='HLine', plot_name='candlestick', tags=None, width=2, dash=None, **kwargs):
        if tags is None:
            import time
            tags = f"hline_{int(time.time()*1000)}"

        # Use a dummy time from current offset or data start
        dt = None
        if self.data and not self.data.df.empty:
            dt = self.data.df['Datetime'].iloc[0]

        shape = {
            'type': 'hline',
            'points': [(dt, price)],
            'fill': color,
            'label': label,
            'plot': plot_name,
            'width': width,
            'dash': dash,
        }
        if kwargs:
            shape.update(kwargs)

        self.drawings[tags] = shape
        self.render()
        return tags

    def create_vline(self, dt, color='#00FFFF', label='VLine', plot_name='candlestick', tags=None, width=2, dash=None, **kwargs):
        if tags is None:
            import time
            tags = f"vline_{int(time.time()*1000)}"

        shape = {
            'type': 'vline',
            'points': [(dt, 0)],
            'fill': color,
            'label': label,
            'plot': plot_name,
            'width': width,
            'dash': dash,
        }
        if kwargs:
            shape.update(kwargs)

        self.drawings[tags] = shape
        self.render()
        return tags

    def create_aline(self, dt1, price1, dt2, price2, color='#FFFF00', label='Line', plot_name='candlestick', tags=None, width=2, dash=None):
        """Creates an angled line between two points (alias for create_line with default params).
        
        Args:
            dt1, price1: Start point
            dt2, price2: End point
            color: Line color
            label: Shape label
            plot_name: Target subplot
            tags: Unique identifier
            width: Line thickness
            dash: Tuple for dash pattern
        """
        if tags is None:
            import time
            tags = f"aline_{int(time.time()*1000)}"
        
        return self.create_line(dt1, price1, dt2, price2, color, label, plot_name, tags, width, dash)

    def create_rectangle(self, dt1, price1, dt2, price2, fill_color, label, plot_name='candlestick', tags=None, outline_color=None, alpha=None, **kwargs):
        """Creates a rectangle shape.
        
        Args:
            dt1, price1: Top-left corner
            dt2, price2: Bottom-right corner
            fill_color: Fill color (use alpha channel for transparency, e.g., '#00FF0040')
            label: Shape label
            plot_name: Target subplot
            tags: Unique identifier
            outline_color: Border color (optional)
            alpha: Transparency (0.0 - 1.0). Maps to stipple pattern.
        """
        # print(f"DEBUG: create_rectangle passed tags={tags}")
        if tags is None: 
            import time
            tags = f"rect_{int(time.time()*1000)}"
        
        self.drawings[tags] = {
            'type': 'rect',
            'points': [(dt1, price1), (dt2, price2)],
            'fill': fill_color,
            'outline': outline_color,
            'label': label,
            'plot': plot_name,
            'alpha': alpha,
            'kwargs': kwargs
        }
        self.render()
        return tags

    def create_text(self, dt, price, text, color, label, plot_name='candlestick', tags=None, **kwargs):
        """Creates a text shape."""
        if tags is None: tags = f"shape_{len(self.drawings)}"
        
        self.drawings[tags] = {
            'type': 'text',
            'points': [(dt, price)],
            'text': text,
            'fill': color,
            'label': label,
            'plot': plot_name,
            'kwargs': kwargs
        }
        self.render()
        return tags

    def get_area_xy(self, tag):
        """Returns the coordinates of a shape in a structured format.
        
        Args:
            tag: Shape identifier
            
        Returns:
            dict: {
                'tag': str,
                'shape': str,  # 'line', 'hline', 'vline', 'aline', 'rect'
                'coordinates': list of tuples or nested list
            }
            
        For lines (hline, vline, line, aline):
            coordinates: [(dt1, price1), (dt2, price2)]
            
        For rectangles:
            coordinates: [[(x1, y1), (x2, y1), (x2, y2), (x1, y2)]]  # Closed polygon
        """
        if tag not in self.drawings:
            return None
        
        shape = self.drawings[tag]
        shape_type = shape['type']
        points = shape['points']
        
        # Determine specific subtype
        if shape_type == 'line':
            dt1, price1 = points[0]
            dt2, price2 = points[1]
            
            # Classify line type
            if dt1 == dt2:
                subtype = 'vline'
            elif price1 == price2:
                subtype = 'hline'
            else:
                subtype = 'aline'
            
            return {
                'tag': tag,
                'shape': subtype,
                'coordinates': [(dt1, price1), (dt2, price2)]
            }
        
        elif shape_type == 'rect':
            dt1, price1 = points[0]
            dt2, price2 = points[1]
            
            # Return as closed polygon (4 corners in order: TL, TR, BR, BL)
            polygon = [
                (dt1, price1),  # Top-left
                (dt2, price1),  # Top-right
                (dt2, price2),  # Bottom-right
                (dt1, price2)   # Bottom-left
            ]
            
            return {
                'tag': tag,
                'shape': 'rectangle',
                'coordinates': [polygon]  # Nested list for potential multi-polygon support
            }
        
        elif shape_type == 'text':
            return {
                'tag': tag,
                'shape': 'text',
                'coordinates': points,
                'text': shape.get('text', '')
            }
        
        return None

    def delete_shape(self, tag):
        if tag in self.drawings:
            del self.drawings[tag]
            self.render()

    def move_shape(self, tag, dx, dy):
        """
        Translates a shape by dx (index units) and dy (price units).
        """
        if tag not in self.drawings:
            return
        
        shape = self.drawings[tag]
        new_points = []
        
        for dt, price in shape['points']:
            try:
                # 1. Convert dt to index
                idx = self.data.get_index_from_time(dt)
                # 2. Add dx
                new_idx = idx + dx
                # 3. Convert back to dt
                new_dt = self.data.get_time_from_index(new_idx)
                # 4. Add dy
                new_price = price + dy
                new_points.append((new_dt, new_price))
            except:
                # Fallback if index conversion fails (e.g. out of bounds)
                new_points.append((dt, price + dy))
        
        shape['points'] = new_points
        self.render()

    # --- Persistence ---
    def save_state(self, symbol_name, filepath="chart_state.json"):
        """Saves current layout and drawings for a symbol."""
        # 1. Serialize Drawings
        serializable_drawings = {}
        for tag, shape in self.drawings.items():
            # Deep copy to modify
            s_copy = copy.deepcopy(shape)
            # Convert datetime points to iso format
            s_copy['points'] = [(p[0].isoformat() if isinstance(p[0], (datetime, pd.Timestamp)) else str(p[0]), p[1]) for p in s_copy['points']]
            serializable_drawings[tag] = s_copy
            
        # 2. Serialize Subplots
        # We need to save weight, type, params. 
        # 'series' might contain objects? Currently list.
        serializable_subplots = copy.deepcopy(self.subplots)
        for k, v in serializable_subplots.items():
             if 'bounds' in v: del v['bounds'] # Recalculated on load
             if 'min_y' in v: del v['min_y']
             if 'max_y' in v: del v['max_y']
             
             # Sanitize Series Data (Indicators)
             if 'series' in v:
                 for s in v['series']:
                     if 'data' in s:
                         d = s['data']
                         # Convert Pandas/Numpy to list
                         if isinstance(d, (pd.Series, np.ndarray, pd.Index)):
                             s['data'] = d.tolist()
                         elif isinstance(d, list):
                             pass
                         else:
                             # Try list conversion or str fallback
                             try:
                                 s['data'] = list(d)
                             except:
                                 s['data'] = str(d) # Fallback

        state = {
            'drawings': serializable_drawings,
            'subplots': serializable_subplots
        }
        
        # 3. Load existing file
        full_data = {}
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    full_data = json.load(f)
            except:
                pass # Corrupt or empty
                
        full_data[symbol_name] = state
        
        with open(filepath, 'w') as f:
            json.dump(full_data, f, indent=2)

    def load_state(self, symbol_name, filepath="chart_state.json"):
        """Loads layout and drawings for a symbol."""
        if not os.path.exists(filepath):
            return
            
        try:
            with open(filepath, 'r') as f:
                full_data = json.load(f)
        except:
            return
            
        if symbol_name not in full_data:
            return
            
        state = full_data[symbol_name]
        
        # Restore Subplots
        saved_subplots = state.get('subplots', {})
        # We merge/replace. 
        # CAUTION: If we blindly replace, we might lose 'series' objects if they were not serialized properly?
        # But 'series' are usually strings (indicator names). 
        # For now, let's assume they are safe.
        self.subplots = saved_subplots
        # Add default bounds/min/max keys if missing (handled by create_subplot/recalc usually, but we need to init them)
        for k, v in self.subplots.items():
            if 'bounds' not in v: v['bounds'] = (0, 1)
            if 'min_y' not in v: v['min_y'] = 0
            if 'max_y' not in v: v['max_y'] = 100
            
        self._recalculate_layout()
        
        # Restore Drawings
        saved_drawings = state.get('drawings', {})
        self.drawings = {}
        for tag, shape in saved_drawings.items():
            s_copy = copy.deepcopy(shape)
            # Convert ISO strings back to datetime
            # We use pd.to_datetime for robustness
            coords = []
            for pt in s_copy['points']:
                 dt = pd.to_datetime(pt[0])
                 coords.append((dt, pt[1]))
            s_copy['points'] = coords
            self.drawings[tag] = s_copy
            
        self.render()

    # --- Subplot Management ---
    def create_subplot(self, name, weight=1.0, overlay_on=None):
        """Creates or updates a subplot definition."""
        if overlay_on:
            # Check validity
            if overlay_on not in self.subplots:
                raise ValueError(f"Overlay target {overlay_on} does not exist.")
            # Overlays share the parent's config roughly, or just tracking
            # Actually, overlays are just series added to a plot.
            # But if we want a logical 'subplot' that renders on top..
            # For now, let's treat overlays as just drawing into the target's bbox.
            self.subplots[name] = {'overlay_on': overlay_on, 'series': []}
        else:
            self.subplots[name] = {
                'weight': weight, 
                'overlay_on': None,
                'series': [],
                'min_y': 0, 
                'max_y': 100,
                'bounds': (0, 1) # Normalized coordinates (0 is top, 1 is bottom)
            }
        self._recalculate_layout()

    def reset_subplots(self):
        """Resets existing subplots to default state (only candlestick)."""
        self.subplots = {}
        # Re-create default
        self.create_subplot('candlestick', weight=3.0) 
        self._recalculate_layout()

    def create_series(self, plot_name, data, color='#FFFF00', thickness=1, label=None):
        """
        Adds a data series (e.g., indicator) to a subplot.
        data: list or pd.Series/array aligned with the main DataFrame.
        """
        if plot_name not in self.subplots:
            print(f"Warning: Plot {plot_name} not found.")
            return

        series_def = {
            'data': data,
            'color': color,
            'thickness': thickness,
            'label': label
        }
        self.subplots[plot_name]['series'].append(series_def)
        self.render()

    def _recalculate_layout(self):
        """Calculates normalized Y-bounds for each separate panel."""
        panels = [k for k, v in self.subplots.items() if v['overlay_on'] is None]
        total_weight = sum(self.subplots[p]['weight'] for p in panels)
        
        current_y = 0.0
        for p in panels:
            w = self.subplots[p]['weight']
            normalized_h = w / total_weight
            self.subplots[p]['bounds'] = (current_y, current_y + normalized_h)
            current_y += normalized_h

    # --- Coordinate System ---
    def get_chart_area(self):
        w = self.config['width']
        h = self.config['height']
        pr = self.config['padding_right']
        pb = self.config['padding_bottom']
        return w - pr, h - pb

    def transform_index_to_x(self, index):
        """Converts logical index to Canvas X."""
        return (index - self.config['offset_x']) * self.config['scale_x']

    def transform_price_to_y(self, price, plot_name='candlestick'):
        """Converts Price to Canvas Y within a specific subplot."""
        sp = self.subplots.get(plot_name)
        if not sp: return 0
        if sp['overlay_on']: sp = self.subplots.get(sp['overlay_on'])
             
        min_y = sp.get('min_y', 0)
        max_y = sp.get('max_y', 100)
        bounds = sp.get('bounds', (0, 1)) # Top, Bottom (0..1)
        
        price_range = max_y - min_y
        if price_range == 0: price_range = 1
        
        # Effective Chart Height
        eff_w, eff_h = self.get_chart_area()
        
        # Subplot Pixel Extents relative to Effective Height
        sp_top = bounds[0] * eff_h
        sp_bottom = bounds[1] * eff_h
        sp_height = sp_bottom - sp_top
        
        # Normalize price 0..1 relative to range
        try:
             norm_p = (float(price) - min_y) / price_range
        except:
             norm_p = 0
        
        # Y is inverted (0 is top of subplot)
        return sp_bottom - (norm_p * sp_height)

    def inverse_transform_x(self, x):
        """Canvas X -> Index"""
        return (x / self.config['scale_x']) + self.config['offset_x']

    def inverse_transform_y(self, y):
        """Canvas Y -> Price."""
        eff_w, eff_h = self.get_chart_area()
        norm_y = y / eff_h
        
        # Find panel
        target_panel = None
        for name, sp in self.subplots.items():
            if sp.get('overlay_on'): continue
            b = sp['bounds']
            if b[0] <= norm_y <= b[1]:
                target_panel = sp
                break
        
        if not target_panel: return 0 
            
        min_y = target_panel['min_y']
        max_y = target_panel['max_y']
        
        b = target_panel['bounds']
        sp_top = b[0] * eff_h
        sp_bottom = b[1] * eff_h
        sp_height = sp_bottom - sp_top
        
        norm_p = (sp_bottom - y) / sp_height
        return min_y + (norm_p * (max_y - min_y))

    def get_plot_at_y(self, y):
        """Identifies which subplot is at pixel Y."""
        eff_w, eff_h = self.get_chart_area()
        norm_y = y / eff_h
        for name, sp in self.subplots.items():
            if sp.get('overlay_on'): continue
            b = sp['bounds']
            if b[0] <= norm_y <= b[1]:
                return name
        return None

    # --- Geometry Helpers ---


    # --- Geometry Helpers ---
    def _clip_line(self, x1, y1, x2, y2, min_x, min_y, max_x, max_y):
        """Cohen-Sutherland Line Clipping Algorithm."""
        INSIDE, LEFT, RIGHT, BOTTOM, TOP = 0, 1, 2, 4, 8

        def compute_out_code(x, y):
            code = INSIDE
            if x < min_x: code |= LEFT
            elif x > max_x: code |= RIGHT
            if y < min_y: code |= BOTTOM
            elif y > max_y: code |= TOP
            return code

        code1, code2 = compute_out_code(x1, y1), compute_out_code(x2, y2)
        accept = False

        while True:
            if (code1 | code2) == 0:
                accept = True; break
            elif (code1 & code2) != 0:
                break
            else:
                x, y = 0.0, 0.0
                code_out = code1 if code1 else code2
                if code_out & TOP:
                    x = x1 + (x2 - x1) * (max_y - y1) / (y2 - y1); y = max_y
                elif code_out & BOTTOM:
                    x = x1 + (x2 - x1) * (min_y - y1) / (y2 - y1); y = min_y
                elif code_out & RIGHT:
                    y = y1 + (y2 - y1) * (max_x - x1) / (x2 - x1); x = max_x
                elif code_out & LEFT:
                    y = y1 + (y2 - y1) * (min_x - x1) / (x2 - x1); x = min_x

                if code_out == code1:
                    x1, y1 = x, y
                    code1 = compute_out_code(x1, y1)
                else:
                    x2, y2 = x, y
                    code2 = compute_out_code(x2, y2)

        return ((x1, y1), (x2, y2)) if accept else None

    # --- Rendering ---
    def calculate_visible_range(self):
        """Determines which indices are visible."""
        start_pixel = 0
        end_pixel = self.config['width'] - self.config['padding_right'] # Use effective width
        
        start_idx = int(self.inverse_transform_x(start_pixel)) - 1
        end_idx = int(self.inverse_transform_x(end_pixel)) + 1
        
        start_idx = max(0, start_idx)
        end_idx = min(self.data.get_len(), end_idx)
        
        return start_idx, end_idx

    def calculate_price_range(self, start_idx, end_idx, series_key='close'):
        """Auto-scale Y based on visible data for a specific series/columns."""
        # For simplicity, main plot uses High/Low
        # For simplicity, main plot uses High/Low
        subset = self.data.df.iloc[start_idx:end_idx]
        if subset.empty:
            # Fallback to last known good range to prevent wild scale jumps
            return self.last_min_y, self.last_max_y
        
        highs = subset['High']
        lows = subset['Low']
        
        min_p = lows.min()
        max_p = highs.max()
        
        # Add padding (5%)
        pad = (max_p - min_p) * 0.05
        if pad == 0: pad = 1.0
        
        # Update last known state
        self.last_min_y = min_p - pad
        self.last_max_y = max_p + pad
        
        return self.last_min_y, self.last_max_y

    def get_view_coordinates(self):
        """
        Returns the min and max bounds of the current view.
        Returns: (DatetimeLeft, DatetimeRight, LowestLow, HighestHigh)
        """
        try:
            if not self.data or self.data.get_len() == 0:
                # Double check to prevent accessing None
                return None, None, None, None

            start_idx, end_idx = self.calculate_visible_range()
            
            # Datetimes
            dt_left = self.data.get_time_from_index(start_idx)
            
            # end_idx is exclusive usually, but for time range we want the last visible bar time
            # or the projected time at the right edge
            eff_w, _ = self.get_chart_area()
            right_idx = self.inverse_transform_x(eff_w)
            dt_right = self.data.get_time_from_index(right_idx)
            
            # Price Range (High/Low of visible bars)
            sp = self.subplots.get('candlestick')
            if sp:
                min_y = sp.get('min_y', 0)
                max_y = sp.get('max_y', 100)
                return dt_left, dt_right, min_y, max_y
                
            return dt_left, dt_right, 0, 0
        except Exception as e:
            # print(f"Error getting view coords: {e}")
            return None, None, None, None
        
        # Update last known state
        self.last_min_y = min_p - pad
        self.last_max_y = max_p + pad
        
        return self.last_min_y, self.last_max_y

    def render(self):
        self.canvas.delete('all')
        self.canvas.delete('crosshair') # Clear crosshair explicitly 
        
        w = self.config['width']
        h = self.config['height']
        
        # Redraw crosshair at last known position if valid
        if hasattr(self, '_last_px') and hasattr(self, '_last_py'):
            self._draw_crosshair(self._last_px, self._last_py)
        eff_w, eff_h = self.get_chart_area()
        
        # Draw Axis Backgrounds
        self.canvas.create_rectangle(eff_w, 0, w, h, fill=self.config['background'], outline='#2B2E39', tags='axis_bg') # Right
        self.canvas.create_line(eff_w, 0, eff_w, h, fill='#2B2E39')
        
        self.canvas.create_rectangle(0, eff_h, w, h, fill=self.config['background'], outline='#2B2E39', tags='axis_bg') # Bottom
        self.canvas.create_line(0, eff_h, w, eff_h, fill='#2B2E39')

        if not self.data or self.data.get_len() == 0:
            return

        # 1. Calc Visible X Range (based on EFF width)
        # Note: inverse_transform_x uses effective width? No, it uses scale/offset. 
        # But end_pixel should be eff_w
        start_idx = int(self.inverse_transform_x(0)) - 1
        end_idx = int(self.inverse_transform_x(eff_w)) + 1
        start_idx = max(0, start_idx)
        end_idx = min(self.data.get_len(), end_idx)
        
        # 2. Subplots Layout & scaling
        self._recalculate_layout() 
        
        # ... (Rendering Loop logic same, but use updated transform_price_to_y) ...
        # Copied logic:
        tx = self.transform_index_to_x
        create_line = self.canvas.create_line
        create_rect = self.canvas.create_rectangle
        
        for name, sp in self.subplots.items():
            if sp.get('overlay_on'): continue
            
            # Auto-scale Y Axis
            y_min = float('inf')
            y_max = float('-inf')
            has_data_range = False

            # 1. Candlestick Main Data
            if name == 'candlestick':
                 c_min, c_max = self.calculate_price_range(start_idx, end_idx)
                 if c_max > c_min:
                    y_min = min(y_min, c_min)
                    y_max = max(y_max, c_max)
                    has_data_range = True
            
            # 2. Series Data (Indicators)
            if 'series' in sp:
                for s in sp['series']:
                    # Extract visible slice
                    data = s['data']
                    # Handle Series vs List
                    vals = data if isinstance(data, (list, np.ndarray)) else data.values
                    
                    # Safe Slice
                    s_s = max(0, start_idx)
                    s_e = min(len(vals), end_idx)
                    
                    if s_s < s_e:
                        subset = vals[s_s:s_e]
                        # Clean Update
                        try: 
                             # Filter NaNs
                             valid = subset[~np.isnan(subset)] if hasattr(subset, 'dtype') else [v for v in subset if v is not None]
                             if len(valid) > 0:
                                 s_min = np.min(valid)
                                 s_max = np.max(valid)
                                 y_min = min(y_min, s_min)
                                 y_max = max(y_max, s_max)
                                 has_data_range = True
                        except: pass
            
            if has_data_range:
                # Apply 5% Padding if pure series (Candlestick already padded in calc function)
                # If mixed, we might double pad but safer than clipping.
                if name != 'candlestick':
                    pad = (y_max - y_min) * 0.05
                    if pad == 0: pad = 1.0
                    y_min -= pad
                    y_max += pad
                
                sp['min_y'] = y_min
                sp['max_y'] = y_max
            
            def ty(p): return self.transform_price_to_y(p, plot_name=name)

            # Draw Candles
            if name == 'candlestick':
                subset = self.data.df.iloc[start_idx:end_idx]
                candle_w = self.config['scale_x'] * self.config['candle_width']
                half_w = candle_w / 2
                up_color = '#089981'; down_color = '#F23645'
                
                for i, row in subset.iterrows():
                    # Optimization: Don't draw if x > eff_w
                    x_center = tx(row['x_index'])
                    if x_center < -half_w or x_center > eff_w + half_w: continue
                    
                    y_open = ty(row['Open']); y_close = ty(row['Close'])
                    y_high = ty(row['High']); y_low = ty(row['Low'])
                    color = up_color if row['Close'] >= row['Open'] else down_color
                    create_line(x_center, y_high, x_center, y_low, fill=color, tags='candle')
                    if abs(y_close - y_open) < 1: y_close = y_open + 1 if row['Close'] >= row['Open'] else y_open - 1
                    create_rect(x_center - half_w, y_open, x_center + half_w, y_close, fill=color, outline=color, tags='candle')

            # --- Draw Y-Axis Ticks for this subplot ---
            # Simple grid lines and text
            # Range: sp['min_y'] to sp['max_y']
            # Steps: ~5-8 ticks
            mn, mx = sp['min_y'], sp['max_y']
            if mx > mn:
                step = (mx - mn) / 6
                for i in range(7):
                    p = mn + i*step
                    y_pos = ty(p)
                    # Text in margin
                    self.canvas.create_text(eff_w + 5, y_pos, text=f"{p:.2f}", anchor='w', fill='#B2B5BE', font=('Helvetica', 7), tags='axis')
                    # Grid line?
                    create_line(0, y_pos, eff_w, y_pos, fill='#2B2E39', dash=(1, 4), tags='grid')

            # --- Draw Extra Series (Indicators) ---
            # Using the same transform context
            if 'series' in sp:
                for s in sp['series']:
                    series_data = s['data']
                    # Slice data to visible range
                    # Should handle both list and series. 
                    # We need to map index -> x, value -> y
                    
                    # Ensure series_data is indexable by integer (0..N)
                    # If it's a pandas series with index, we ignore index and rely on position matching main df
                    vals = series_data if isinstance(series_data, (list, np.ndarray)) else series_data.values
                    
                    # We iterate only visible indices
                    # Clamping start/end to data bounds
                    s_idx = max(0, start_idx)
                    e_idx = min(len(vals), end_idx)
                    
                    if s_idx >= e_idx: continue

                    # Break into chunks separated by None/NaN
                    current_chunk = []
                    
                    for idx in range(s_idx, e_idx):
                        val = vals[idx]
                        is_valid = val is not None and not (isinstance(val, float) and np.isnan(val))
                        
                        if is_valid:
                            x = tx(idx)
                            y = ty(val)
                            # We Clamp Y for series as strict clipping is expensive for polyline
                            y = max(-5000, min(self.config['height']+5000, y))
                            current_chunk.extend([x, y])
                        else:
                            if len(current_chunk) >= 4:
                                create_line(current_chunk, fill=s['color'], width=s['thickness'], tags=(name, 'series', s.get('label', 'series_val')))
                            current_chunk = []
                    
                    # Draw the last chunk
                    if len(current_chunk) >= 4:
                        create_line(current_chunk, fill=s['color'], width=s['thickness'], tags=(name, 'series', s.get('label', 'series_val')))

        # --- Draw X-Axis Ticks ---
        # Draw dynamic dates
        # Visible range: start_idx to end_idx
        # Draw every Nth candle based on width
        px_per_bar = self.config['scale_x']
        # Try to space labels by ~100px
        step_idx = int(100 / px_per_bar) if px_per_bar > 0 else 10
        if step_idx < 1: step_idx = 1
        
        for i in range(start_idx, end_idx, step_idx):
            x = tx(i)
            # Read Datetime column correctly (column is 'Datetime', not 'date' or 'timestamp')
            row = self.data.df.iloc[i]
            d_val = row.get('Datetime', row.get('date', row.get('timestamp', '')))
            d_str = str(d_val)
            try:
                dt = pd.to_datetime(d_val)
                if px_per_bar > 5:
                    d_str = dt.strftime("%H:%M")   # zoomed in: show HH:MM
                else:
                    d_str = dt.strftime("%d-%b")   # zoomed out: show day+month
            except:
                pass

            self.canvas.create_text(x, eff_h + 10, text=d_str, fill='#B2B5BE', font=('Helvetica', 7), tags='axis')
            create_line(x, 0, x, eff_h, fill='#2B2E39', dash=(1, 4), tags='grid')

        if self.config.get('market_profile_enabled', False):
            self.render_market_profile(start_idx, end_idx)

        # 4. Draw User Shapes
        create_text = self.canvas.create_text
        self.handle_hitboxes = []
        
        # Viewport for clipping
        vp_min_x, vp_min_y = -1000, -1000
        vp_max_x, vp_max_y = eff_w + 1000, eff_h + 1000 # Use effective width/height for clipping
        
        for tag, shape in self.drawings.items():
            plot = shape['plot']
            if plot not in self.subplots: continue
            
            # Transform Points
            canvas_points = []
            
            def ty(p): return self.transform_price_to_y(p, plot_name=plot)
            
            for dt, price in shape['points']:
                 idx = self.data.get_index_from_time(dt)
                 x = tx(idx)
                 y = ty(price)
                 canvas_points.append((x, y))
            
            if shape['type'] == 'rect':
                x1, y1 = canvas_points[0]
                x2, y2 = canvas_points[1]
                # Simple clamping for Rect
                x1 = max(vp_min_x, min(vp_max_x, x1))
                y1 = max(vp_min_y, min(vp_max_y, y1))
                x2 = max(vp_min_x, min(vp_max_x, x2))
                y2 = max(vp_min_y, min(vp_max_y, y2))
                
                color = shape['fill']
                outline = shape.get('outline', color)
                if tag in self.selected_tags:
                    outline = '#FFA500' # Orange Highlight
                    color = '#FFA500'   # USER REQUEST: Change fill color matches selection
                
                # Alpha Logic
                stipple = 'gray25' # Default legacy style
                alpha = shape.get('alpha', shape.get('kwargs', {}).get('alpha'))
                kwargs = shape.get('kwargs', {})
                if 'outline_color' in kwargs and outline == color:
                     outline = kwargs['outline_color']
                
                if alpha is not None:
                    if alpha < 0.1: stipple = 'gray12'
                    elif alpha < 0.4: stipple = 'gray25'
                    elif alpha < 0.7: stipple = 'gray50' 
                    elif alpha < 0.95: stipple = 'gray75'
                    else: stipple = '' # Solid (None is tricky in direct kwargs sometimes, '' works for no stipple in some tk versions, or check)
                
                # Safe Solid Handling
                if stipple == '':
                     create_rect(x1, y1, x2, y2, fill=color, outline=outline, tags=(tag, 'shape', plot))
                else:
                     create_rect(x1, y1, x2, y2, fill=color, outline=outline, stipple=stipple, tags=(tag, 'shape', plot))
                if tag == self.selected_handle_tag:
                    self._draw_selection_handles(tag, shape, canvas_points)
                
            elif shape['type'] == 'line':
                # Critical: Use Clipping for Lines to preserve slope
                p1 = canvas_points[0]
                p2 = canvas_points[1]
                
                clipped = self._clip_line(p1[0], p1[1], p2[0], p2[1], vp_min_x, vp_min_y, vp_max_x, vp_max_y)
                
                if clipped:
                    (cx1, cy1), (cx2, cy2) = clipped
                    # Get width and dash from shape definition
                    line_width = shape.get('width', 2)
                    line_dash = shape.get('dash', None)
                    
                    color = shape['fill']
                    if tag in self.selected_tags:
                        color = '#FFA500' # Orange Highlight
                        line_width += 1

                    # Create line with optional dash pattern
                    if line_dash:
                        create_line(cx1, cy1, cx2, cy2, fill=color, width=line_width, dash=line_dash, tags=(tag, 'shape', plot))
                    else:
                        create_line(cx1, cy1, cx2, cy2, fill=color, width=line_width, tags=(tag, 'shape', plot))
                    if tag == self.selected_handle_tag:
                        self._draw_selection_handles(tag, shape, [(cx1, cy1), (cx2, cy2)])
                
            elif shape['type'] == 'hline':
                _, price = shape['points'][0]
                y = ty(price)
                
                line_width = shape.get('width', 1)
                line_dash = shape.get('dash', None)
                color = shape['fill']
                if tag in self.selected_tags:
                    color = '#FFA500'
                    line_width += 1

                # Draw from 0 to effective width (Infinite Horizontal)
                create_line(0, y, eff_w, y, fill=color, width=line_width, dash=line_dash, tags=(tag, 'shape', plot))

            elif shape['type'] == 'vline':
                dt, _ = shape['points'][0]
                idx = self.data.get_index_from_time(dt)
                x = tx(idx)
                
                line_width = shape.get('width', 1)
                line_dash = shape.get('dash', None)
                color = shape['fill']
                if tag in self.selected_tags:
                    color = '#FFA500'
                    line_width += 1

                # Draw from top of chart to bottom (Infinite Vertical)
                create_line(x, 0, x, self.config['height'], fill=color, width=line_width, dash=line_dash, tags=(tag, 'shape', plot))

            elif shape['type'] == 'text':
                x, y = canvas_points[0]
                # Check against effective width for text visibility
                if 0 <= x <= eff_w: 
                    create_text(x, y, text=shape['text'], fill=shape['fill'], anchor='sw', tags=(tag, 'shape', plot))

    def _dispatch(self, event_type, event):
        """
        Packaging the raw event into our standardized dict
        """
        if self.callback:
            x = getattr(event, 'x', 0)
            y = getattr(event, 'y', 0)
            
            # Store for persistence across renders
            self._last_px = x
            self._last_py = y
            
            # Inverse transform might return huge values if we claimed huge x from event (unlikely)
            idx = self.inverse_transform_x(x)
            
            # Safety for price transform?
            try:
                price = self.inverse_transform_y(y)
            except:
                price = 0
            
            dt = None
            try:
                dt = self.data.get_time_from_index(idx)
            except:
                pass
            
            plot = self.get_plot_at_y(y)
            
            value = {
                'x': idx,
                'y': price,
                'time': dt,
                'sub_plot': plot,
                'original_event': event,
                'shape': None,
                'series': None
            }
            
            # Enrich with OHLC if available
            if self.data:
                bar_idx = int(round(idx))
                if 0 <= bar_idx < self.data.get_len():
                    row = self.data.df.iloc[bar_idx]
                    for col in ['open', 'high', 'low', 'close', 'Close', 'volume']:
                        if col in row:
                             value[col] = row[col]
            
            # Enrich with Button Info
            if event_type in ['click', 'release', 'scroll']:
                if hasattr(event, 'num'):
                    # num is 1 (Left), 2 (Middle), 3 (Right), 4/5 (Scroll)
                    btn_map = {1: 'left', 2: 'middle', 3: 'right', 4:'scroll_up', 5:'scroll_down'}
                    value['button'] = btn_map.get(event.num, str(event.num))
            elif event_type == 'drag':
                # Attempt to infer button from state
                state = getattr(event, 'state', 0)
                # Standard Tkinter Masks (approximate)
                if state & 0x0100: value['button'] = 'left'     # Button 1
                elif state & 0x0200: value['button'] = 'middle' # Button 2
                elif state & 0x0400: value['button'] = 'right'  # Button 3
                # Fallback: if we are dragging, and no state matches, assume left?
                # Or leave empty. Form_Screener should handle empty.
            
            # Enrich with Key Info
            if event_type == 'key':
                keysym = getattr(event, 'keysym', '')
                value['key'] = keysym
                value['char'] = getattr(event, 'char', '')
                # Normalize common keys
                if keysym in ['Escape', 'Return', 'BackSpace', 'Delete']:
                    value['key'] = keysym
            
            # Add DataFrame coordinates (Requested by User)
            # dataframe_x = idx
            # dataframe_Y = price
            value['dataframe_x'] = int(round(idx))
            value['dataframe_Y'] = price

            try:
                found_handle = None
                # Find overlapping items in expanded radius (5px) for easier line selection
                items = self.canvas.find_overlapping(x-5, y-5, x+5, y+5)
                found_shape = None
                found_series = None

                for hb in self.handle_hitboxes:
                    x1, y1, x2, y2 = hb["bbox"]
                    if x1 <= x <= x2 and y1 <= y <= y2:
                        found_handle = hb
                        found_shape = hb["tag"]
                        break
                 
                # Check for candle hit if we have data
                # We do this manually because candles might be many objects or just lines/rects
                # But 'find_overlapping' returns tags.
                # If we clicked a candle, we expect 'candle' tag.
                
                is_candle_hit = False
                for item in items:
                    tags = self.canvas.gettags(item)
                    if 'candle' in tags:
                        is_candle_hit = True

                    if 'series' in tags:
                        # Identify which series. Tags usually: (plot_name, 'series', label)
                        # We need to find the label.
                        # Exclude 'series' and plot_name
                        for t in tags:
                            if t != 'series' and t not in self.subplots:
                                # This must be the label
                                found_series = t
                                # Also store plot if needed, but 'series' key in value needs label for deletion
                        
                        # Fallback: if we only found plot name (legacy), keep it
                        if not found_series:
                            for t in tags:
                                if t in self.subplots:
                                    found_series = t
                    
                    # Check for shapes
                    for t in tags:
                        if t in self.drawings:
                            found_shape = t

                    # Prioritize Shape over Series if both found in same cluster?
                    # Usually Shapes are on top.
                    if found_handle:
                        found_shape = found_handle["tag"]

                if found_shape:
                    value['shape'] = found_shape
                    if found_handle:
                        value['shape_handle'] = found_handle["handle"]
                        value['resize_handle'] = found_handle["handle"]
                elif found_series:
                    value['series'] = found_series # Or should this be 'shape'? User asked for 'sma_24' in return
                    # Maybe map series label to shape for consistency if desired?
                    # But 'series' is distinct key in existing logic.
                    # User asked "it returns subplot... but not shapes like candle_1 or sma_24"
                    # If we return series: 'sma_24', that fits.
                    pass
                elif is_candle_hit:
                    # If we hit a candle locally (by canvas tag), lets confirm we are actually over the bar range?
                    # Tag check is usually precise enough if canvas objects are well defined.
                    # Add candle shape id
                    # Format: candle_{index}
                    bar_idx = int(round(idx))
                    value['shape'] = f"candle_{bar_idx}"

            except Exception as e:
                print(f"HitTest Error: {e}")

            self.callback(event_type, value)

    # --- Market Profile (TPO) ---
    def calculate_tpo_profile(self, data_slice):
        """Calculates TPO profile for data slice."""
        if data_slice.empty: return {}
        
        tick_size = 0.05 
        session_start = data_slice['Datetime'].iloc[0]
        session_end = data_slice['Datetime'].iloc[-1]
        
        profile = {} 
        
        # User Request: "Use 30 minute tpos from active timeframe"
        # Our logic `elapsed // 1800` handles this regardless of input timeframe (1m, 5m, etc)
        # as long as we iterate rows.
        
        # We need Open/Close of the session/slice
        # Assuming slice is the session
        open_price = data_slice['Open'].iloc[0]
        close_price = data_slice['Close'].iloc[-1]
        
        import string
        letters = string.ascii_uppercase + string.ascii_lowercase
        
        for _, row in data_slice.iterrows():
            curr_time = row['Datetime']
            elapsed = (curr_time - session_start).total_seconds()
            bracket_idx = int(elapsed // 1800) # 30 mins
            
            if bracket_idx < 0: bracket_idx = 0
            if bracket_idx >= len(letters): bracket_idx = len(letters) - 1
            char = letters[bracket_idx]
            
            low = row['Low']
            high = row['High']
            
            curr_p = (np.floor(low / tick_size) * tick_size)
            end_p = (np.ceil(high / tick_size) * tick_size)
            
            while curr_p <= end_p + 0.00001:
                p_key = round(curr_p, 2)
                if p_key not in profile: profile[p_key] = []
                if not profile[p_key] or profile[p_key][-1] != char:
                     profile[p_key].append(char)
                curr_p += tick_size
        return profile

    def render_market_profile(self, start_idx, end_idx):
        """Renders the Market Profile overlay."""
        # Determine Time Range from current visible subset
        subset = self.data.df.iloc[start_idx:end_idx]
        if subset.empty: return
        
        start_time = subset['Datetime'].iloc[0]
        end_time = subset['Datetime'].iloc[-1]
        
        # High Resolution Data Source Check
        if hasattr(self, 'mp_source_data') and self.mp_source_data is not None:
             # Use the high-res data provided
             # Filter by visible time range
             # Assuming mp_source_data has 'datetime' column and is a dataframe
             try:
                 profile_source = self.mp_source_data.copy()
                 if 'Datetime' in profile_source.columns:
                     profile_source['Datetime'] = pd.to_datetime(profile_source['Datetime'])
                 profile_source = profile_source.sort_values('Datetime')
                 # Optimization: Ensure datetime is index or sorted for speed?
                 # For now, standard filter
                 mask = (profile_source['Datetime'] >= start_time) & (profile_source['Datetime'] <= end_time)
                 profile_subset = profile_source.loc[mask]
                 if profile_subset.empty:
                     # Fallback if no matching high-res data found
                     profile_subset = subset
             except Exception as e:
                 print(f"Error filtering high-res TPO data: {e}")
                 profile_subset = subset
        else:
             profile_subset = subset

        profile = self.calculate_tpo_profile(profile_subset)
        if not profile: return
        
        eff_w, eff_h = self.get_chart_area()
        panel_width = eff_w * 0.32
        base_x = 14
        font_size = 8
        row_height = 14
        panel_right = panel_width
        panel_fill = '#0C1017'
        panel_border = '#253041'
        value_area_fill = '#152031'
        poc_fill = '#2A1E10'

        # Give the profile a dedicated panel so it is easy to see in the demo.
        self.canvas.create_rectangle(
            0,
            0,
            panel_right,
            eff_h,
            fill=panel_fill,
            outline=panel_border,
            tags='market_profile'
        )
        self.canvas.create_text(
            base_x,
            14,
            text='MARKET PROFILE',
            anchor='w',
            fill='#7D8CA3',
            font=('Helvetica', 9, 'bold'),
            tags='market_profile'
        )
        self.canvas.create_text(
            panel_right - 12,
            14,
            text=f"{start_time:%d %b %H:%M} - {end_time:%H:%M}",
            anchor='e',
            fill='#5F6D82',
            font=('Helvetica', 8),
            tags='market_profile'
        )
        self.canvas.create_line(0, 28, panel_right, 28, fill=panel_border, tags='market_profile')
        
        # Calculate dynamic char width if needed or clamp
        # Find POC Max Length
        max_len = 0
        poc_price = 0
        for p, chars in profile.items():
            if len(chars) > max_len:
                max_len = len(chars)
                poc_price = p
        
        # Target: Max 40% of width
        max_allowed_w = max(80, panel_width - 24)
        if max_len > 0:
            char_w = min(6, max_allowed_w / max_len)
        else:
            char_w = 6
        # font_size could also scale?? For now just spacing.
        
        # Draw
        ty = lambda p: self.transform_price_to_y(p, 'candlestick')
        create_line = self.canvas.create_line
        create_text = self.canvas.create_text
        
        # Calculate Value Area (70%)
        # 1. Total TPOs
        # flatten profile to list of (price, count)
        price_counts = []
        total_tpo = 0
        for p, chars in profile.items():
            c = len(chars)
            price_counts.append((p, c))
            total_tpo += c
            
        # 2. Start at POC
        # Sort by price to find neighbors easily
        price_counts.sort(key=lambda x: x[0])
        
        # Find POC index in sorted list
        poc_idx = -1
        for i, (p, c) in enumerate(price_counts):
            if p == poc_price:
                poc_idx = i
                break
        
        if poc_idx == -1: return # Should not happen
        
        # VA Algorithm
        va_tpo = price_counts[poc_idx][1]
        va_target = total_tpo * 0.70
        up_idx = poc_idx
        dn_idx = poc_idx
        
        while va_tpo < va_target:
            # Check up
            next_up_c = 0
            if up_idx + 1 < len(price_counts):
                next_up_c = price_counts[up_idx+1][1]
            
            # Check down
            next_dn_c = 0
            if dn_idx - 1 >= 0:
                next_dn_c = price_counts[dn_idx-1][1]
                
            # If both 0, break (all done)
            if next_up_c == 0 and next_dn_c == 0: break
            
            # Add larger
            if next_up_c >= next_dn_c:
                va_tpo += next_up_c
                up_idx += 1
                if up_idx < len(price_counts) and next_up_c == next_dn_c: 
                     # If equal, Dual Auction rules often take both? Simplified here: take strictly larger or top preference
                     # The standard TPO rule is complex with 'singles'. simplified greedy is ok.
                     pass 
            else:
                va_tpo += next_dn_c
                dn_idx -= 1
        
        val_price = price_counts[dn_idx][0]
        vah_price = price_counts[up_idx][0]
        
        # Draw Profile Letters
        for price, chars in profile.items():
            text_str = "".join(chars)
            y = ty(price)
            if y < 0 or y > eff_h: continue # Clip vertical
            
            # Option 2: Clip String
            approx_w = len(text_str) * 6 # assuming fixed 6px font
            if approx_w > max_allowed_w:
                keep_chars = int(max_allowed_w / 6)
                if keep_chars < 1: keep_chars = 1
                text_str = text_str[:keep_chars]
            
            if val_price <= price <= vah_price:
                row_fill = value_area_fill
                color = '#DCE7F7'
            else:
                row_fill = panel_fill
                color = '#97A7BF'

            if price == poc_price:
                row_fill = poc_fill
                color = '#FFD089'

            self.canvas.create_rectangle(
                4,
                y - (row_height / 2),
                panel_right - 4,
                y + (row_height / 2),
                fill=row_fill,
                outline='',
                tags='market_profile'
            )
            create_text(
                base_x,
                y,
                text=text_str,
                anchor='w',
                fill=color,
                font=('Courier', font_size),
                tags='market_profile'
            )
            create_text(
                panel_right - 10,
                y,
                text=f"{price:.2f}",
                anchor='e',
                fill='#6F8097' if price != poc_price else '#FFB14A',
                font=('Helvetica', 7),
                tags='market_profile'
            )
            
        # Draw Lines (Open, Close, POC, VAH, VAL)
        # Using extended lines as per image
        
        # Determine labels x position (right side or near profile?) 
        # Image shows labels near the lines, right aligned or center.
        # Let's put them at the end.
        
        def draw_level(price, color, text, dashed=None):
            y = ty(price)
            if 0 <= y <= eff_h:
                # Line
                # Start line from the profile edge or full width?
                # User image: Lines seem to extend from profile or be full width?
                # Image: "Value Area High" line starts from profile edge.
                # Let's start from max_len * char_w
                row_w = len(profile.get(price, [])) * 6
                # But we clipped it.
                row_w = min(row_w, max_allowed_w)
                
                sx = base_x + row_w + 5
                
                create_line(sx, y, eff_w, y, fill=color, dash=dashed, width=1, tags='market_profile')
                self.canvas.create_rectangle(
                    sx + 4,
                    y - 10,
                    sx + 108,
                    y + 2,
                    fill='#111923',
                    outline='',
                    tags='market_profile'
                )
                create_text(sx + 8, y - 4, text=text, anchor='w', fill=color, font=('Helvetica', 8, 'bold'), tags='market_profile')

        # POC (Orange)
        draw_level(poc_price, '#FF9F1C', "POC")
        
        # VAH (Gray/White)
        draw_level(vah_price, '#A8B3C2', "VAH", dashed=(4, 3))
        
        # VAL (Gray/White)
        draw_level(val_price, '#A8B3C2', "VAL", dashed=(4, 3))
        
        # Open (Green)
        # Open Arrow logic? Image shows "Open" with arrow pointing to letter 'A'?
        # Let's just draw a line for now or text marker
        op = subset['Open'].iloc[0]
        oy = ty(op)
        create_line(panel_right - 56, oy, eff_w, oy, fill='#35D07F', dash=(2, 3), tags='market_profile')
        create_text(panel_right - 60, oy - 4, text="OPEN", fill='#35D07F', anchor='e', font=('Helvetica', 8, 'bold'), tags='market_profile')
        
        # Close (Red)
        cp = subset['Close'].iloc[-1]
        cy = ty(cp)
        create_line(panel_right - 56, cy, eff_w, cy, fill='#FF6B6B', dash=(2, 3), tags='market_profile')
        create_text(panel_right - 60, cy - 4, text="CLOSE", fill='#FF6B6B', anchor='e', font=('Helvetica', 8, 'bold'), tags='market_profile')

    # --- Deletion Methods ---
    def delete_series(self, label):
        updated = False
        subplots_to_delete = []
        
        for name, sp in self.subplots.items():
            if 'series' in sp:
                original_len = len(sp['series'])
                sp['series'] = [s for s in sp['series'] if s.get('label') != label]
                if len(sp['series']) < original_len:
                    updated = True
                    # Check if subplot is now empty and not the main candlestick
                    if len(sp['series']) == 0 and name != 'candlestick' and not sp.get('overlay_on'):
                        subplots_to_delete.append(name)
        
        # Delete empty subplots
        for subplot_name in subplots_to_delete:
            if subplot_name in self.subplots:
                del self.subplots[subplot_name]
                print(f"Deleted empty subplot: {subplot_name}")
        
        if updated or subplots_to_delete:
            self._recalculate_layout()
            self.render()
            return True
        return False

    def delete_subplot(self, name):
        if name == 'candlestick': return False
        if name in self.subplots:
            del self.subplots[name]
            self._recalculate_layout()
            self.render()
            return True
        return False


# Backward-compatible alias for older imports.
TvChart = EasyPyChart
