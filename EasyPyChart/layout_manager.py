"""
LayoutManager for EasyPyChart
Acts as a Session & State Manager, handling:
- Global Indicators (persist across symbols)
- Symbol-Specific Drawings
- Context Switching (Symbol/Timeframe)
"""

import json
import os
import copy
from datetime import datetime
import pandas as pd
import numpy as np


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, pd.Timestamp)):
            return obj.isoformat()
        if isinstance(obj, (pd.Index, pd.DatetimeIndex)):
            return [x.isoformat() for x in obj]
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


class LayoutManager:
    def __init__(self, chart):
        self.chart = chart

        # Session State
        self.global_indicators = (
            []
        )  # List of indicator dicts: {id, type, params, subplot, series_label}
        self.symbol_drawings = {}  # { 'SYMBOL': { 'tag': shape_data } }
        self.current_symbol = None
        self.current_timeframe = None

        # Subplot Configurations { 'name': { 'weight': 1, 'overlay_on': None, ... } }
        self.subplot_configs = {}

        # View State Store: { (symbol, timeframe): { 'scale_x': float, 'offset_from_end': float } }
        self.view_states = {}

        # Indicator Renderer Callback
        self.indicator_renderer = None

        # Initialize default main plot config
        self.subplot_configs["candlestick"] = {"weight": 3.0, "overlay_on": None}

        # Internal Data Store: { 'SYMBOL': { 'TF': df, ... } }
        self.data_store = {}

    def set_context(self, symbol, timeframe):
        """Switches the active symbol/timeframe context."""
        # Save current state (drawings)
        if self.current_symbol:
            # SAFE COPY: Do not use deepcopy (Tkinter objects issue)
            snapshot = {}
            for tag, shape in self.chart.drawings.items():
                snapshot[tag] = shape.copy()
                snapshot[tag]["points"] = list(shape["points"])
                if "kwargs" in shape:
                    snapshot[tag]["kwargs"] = shape["kwargs"].copy()

            self.symbol_drawings[self.current_symbol] = snapshot

            # Save View State
            try:
                if self.chart.data and self.chart.data.get_len() > 0:
                    curr_off = self.chart.config["offset_x"]
                    total = self.chart.data.get_len()
                    dist = total - curr_off  # Distance from end

                    key_tuple = (self.current_symbol, self.current_timeframe)
                    self.view_states[key_tuple] = {
                        "scale_x": self.chart.config["scale_x"],
                        "offset_from_end": dist,
                    }
            except:
                pass

        self.current_symbol = symbol
        self.current_timeframe = timeframe

        # 2. Reset Chart (Clear Data/Drawings)
        self.chart.clear()
        self.chart.reset_subplots()

        # 3. Restore Subplot Layout (Containers)
        self._restore_layout()

        # 4. Load Data (if available)
        # Note: chart.load_data() clears drawings/series, so we load data BEFORE restoring drawings
        # 4. Load Data (if available)
        # Note: chart.load_data() clears drawings/series, so we load data BEFORE restoring drawings
        if self.current_symbol in self.data_store:
            symbol_data = self.data_store[self.current_symbol]
            if self.current_timeframe in symbol_data:
                df = symbol_data[self.current_timeframe]
                print(
                    f"LayoutManager: Loading data for {symbol} {timeframe} (Rows: {len(df)})"
                )
                self.chart.load_data(df)

                # Restore View State
                self._restore_view_state(symbol, timeframe, len(df))
            else:
                print(
                    f"LayoutManager: No data found for {symbol} {timeframe} in store."
                )
        else:
            print(f"LayoutManager: No data entry for symbol {symbol} in store.")

        # 5. Restore Drawings
        self._restore_drawings()

    def _restore_view_state(self, symbol, timeframe, data_len):
        """Restores zoom and scroll position if saved state exists."""
        key = (symbol, timeframe)
        if key in self.view_states:
            state = self.view_states[key]
            try:
                # Restore Zoom
                self.chart.config["scale_x"] = state["scale_x"]

                # Restore Position (Relative to End)
                # offset = total - dist
                dist = state["offset_from_end"]
                new_offset = data_len - dist

                # Clamp?
                self.chart.config["offset_x"] = new_offset
                print(
                    f"LayoutManager: Restored view for {symbol} {timeframe} (Offset: {new_offset}, Scale: {state['scale_x']})"
                )

                # Force Render to apply changes
                self.chart.render()
            except Exception as e:
                print(f"Error restoring view: {e}")

    def load_data(self, data):
        """
        Loads data into the manager.
        Args:
            data: Can be a DataFrame (for simple update) OR a dict { 'timeframe': df }
        """
        if isinstance(data, dict):
            # User passed { '5m': df, '10m': df }
            if self.current_symbol:
                if self.current_symbol not in self.data_store:
                    self.data_store[self.current_symbol] = {}
                self.data_store[self.current_symbol].update(data)

                # If current timeframe is in this update, refresh chart
                if self.current_timeframe and self.current_timeframe in data:
                    self.update_data(data[self.current_timeframe])
            else:
                print("LayoutManager: Set context (Symbol) before loading data dict.")
        else:
            # Direct DF update
            if self.current_symbol and self.current_timeframe:
                if self.current_symbol not in self.data_store:
                    self.data_store[self.current_symbol] = {}
                self.data_store[self.current_symbol][self.current_timeframe] = data
            self.update_data(data)

    def update_data(self, df):
        """Passes new data to chart."""
        self.chart.load_data(df)

        # chart.load_data wipes drawings, so we must restore them
        self._restore_drawings()
        
        # Indicators need calculated data.
        self._restore_indicators(df)

    def add_drawing(self, tag, shape_type, points, **kwargs):
        """Adds a drawing to the current symbol's state."""
        if not self.current_symbol:
            print("LayoutManager: No symbol selected. Drawing ignored.")
            return

        if self.current_symbol not in self.symbol_drawings:
            self.symbol_drawings[self.current_symbol] = {}

        shape_data = {"type": shape_type, "points": points, "kwargs": kwargs}
        self.symbol_drawings[self.current_symbol][tag] = shape_data

        # Render immediately
        self._render_shape(tag, shape_data)

    def remove_drawing(self, tag):
        """Removes a drawing from both Chart and Storage."""
        # 1. Remove from Chart
        self.chart.delete_shape(tag)

        # 2. Remove from Store
        if self.current_symbol and self.current_symbol in self.symbol_drawings:
            if tag in self.symbol_drawings[self.current_symbol]:
                del self.symbol_drawings[self.current_symbol][tag]

    def clear_all_drawings(self):
        """Removes ALL drawings for the current symbol."""
        if not self.current_symbol:
            return

        # 1. Clear Chart
        self.chart.delete_shape("all")  # Assuming 'all' works or need loop?
        # EasyPyChart delete_shape typically takes a tag.
        # If 'all' is not supported, we must loop drawings.
        # Check EasyPyChart API? Assuming loop for safety.
        for tag in list(self.chart.drawings.keys()):
            self.chart.delete_shape(tag)

        # 2. Clear Store
        if self.current_symbol in self.symbol_drawings:
            self.symbol_drawings[self.current_symbol] = {}

    def get_drawings(self):
        if not self.current_symbol:
            return {}
        return self.symbol_drawings.get(self.current_symbol, {})

    def _sync_from_chart(self):
        """Pull latest drawings from chart to memory."""
        # self.chart.drawings contains {tag: shape}
        # We need to save this to symbol_drawings[current_symbol]
        if self.current_symbol:
            # SAFE COPY: Do not use deepcopy (Tkinter objects issue)
            snapshot = {}
            for tag, shape in self.chart.drawings.items():
                snapshot[tag] = shape.copy()
                snapshot[tag]["points"] = list(shape["points"])
                if "kwargs" in shape:
                    snapshot[tag]["kwargs"] = shape["kwargs"].copy()
            self.symbol_drawings[self.current_symbol] = snapshot

    def _position_group_prefix(self, tag):
        """Returns the shared PosUnit prefix for grouped position drawings."""
        if not isinstance(tag, str) or not tag.startswith("PosUnit_"):
            return None

        parts = tag.split("_", 2)
        if len(parts) < 3:
            return None

        return "_".join(parts[:2])

    def _time_to_index(self, time_value):
        """Converts a stored timestamp to the current chart index space."""
        data = getattr(self.chart, "data", None)
        if data is None or not hasattr(data, "get_index_from_time"):
            return None

        try:
            idx = float(data.get_index_from_time(time_value))
        except Exception:
            return None

        if np.isnan(idx):
            return None

        return idx

    def _position_group_width(self, drawings, group_prefix):
        """Measures the bar width of a grouped long/short position unit."""
        widths = []

        for tag, shape in drawings.items():
            if not isinstance(tag, str) or not tag.startswith(f"{group_prefix}_"):
                continue

            points = shape.get("points", [])
            if len(points) < 2:
                continue

            # Prefer rectangle spans, since labels are anchored to the same group.
            if shape.get("type") != "rect":
                continue

            idx1 = self._time_to_index(points[0][0])
            idx2 = self._time_to_index(points[1][0])
            if idx1 is None or idx2 is None:
                continue

            widths.append(abs(idx2 - idx1))

        if not widths:
            # Fallback for partially restored units where rect metadata is missing.
            xs = []
            for tag, shape in drawings.items():
                if not isinstance(tag, str) or not tag.startswith(f"{group_prefix}_"):
                    continue

                for point in shape.get("points", []):
                    if not point:
                        continue
                    idx = self._time_to_index(point[0])
                    if idx is not None:
                        xs.append(idx)

            if len(xs) >= 2:
                return max(xs) - min(xs)

            return None

        return max(widths)

    def _restore_layout(self):
        """Restores subplot configurations."""
        for name, cfg in self.subplot_configs.items():
            if name == "candlestick":
                continue  # Always exists
            self.chart.create_subplot(
                name, weight=cfg.get("weight", 1.0), overlay_on=cfg.get("overlay_on")
            )

    def _restore_drawings(self):
        """Restores drawings for current symbol."""
        drawings = self.symbol_drawings.get(self.current_symbol, {})
        position_width_cache = {}
        for tag, shape in drawings.items():
            group_prefix = self._position_group_prefix(tag)
            if group_prefix:
                if group_prefix not in position_width_cache:
                    position_width_cache[group_prefix] = self._position_group_width(
                        drawings, group_prefix
                    )

                group_width = position_width_cache[group_prefix]
                if group_width is not None and group_width <= 5:
                    # Narrow position units collapse into text on higher timeframes.
                    # Skip the whole unit so the stored labels do not reappear alone.
                    continue

            self._render_shape(tag, shape)

    def _rebuild_chart(self):
        """Full rebuild of the chart: Clear, Restore Layout, Reload Data, Restore Drawings, Restore Indicators."""
        # 1. Cleanup empty subplots first
        self._cleanup_subplots()

        # 2. Determine data to use
        df = None
        if self.current_symbol in self.data_store:
            symbol_data = self.data_store[self.current_symbol]
            if self.current_timeframe in symbol_data:
                df = symbol_data[self.current_timeframe]
        
        # If no data in store, try to preserve current chart data
        if df is None and self.chart.data:
            df = self.chart.data.df

        # 3. Reset Chart
        self.chart.clear()
        self.chart.reset_subplots()
        self._restore_layout()
        
        # 4. Reload Data
        if df is not None:
            self.chart.load_data(df)
                
        # 5. Restore Items
        self._restore_drawings()
        self._restore_indicators(df)

    def _cleanup_subplots(self):
        """Removes subplots that are no longer used by any indicator."""
        used_subplots = {ind['subplot'] for ind in self.global_indicators}
        used_subplots.add("candlestick")
        
        to_delete = [sp for sp in self.subplot_configs if sp not in used_subplots]
        for sp in to_delete:
            del self.subplot_configs[sp]

    def _restore_indicators(self, df):
        """Renders global indicators if a renderer is set."""
        if self.indicator_renderer and df is not None:
            for ind_config in self.global_indicators:
                try:
                    self.indicator_renderer(self, ind_config, df)
                except Exception as e:
                    print(f"LayoutManager: Error rendering indicator {ind_config.get('id')}: {e}")

    def add_indicator_config(self, ind_id, ind_type, params, subplot="candlestick", weight=1.0):
        """Registers an indicator metadata and ensures its layout exists."""
        config = {
            'id': ind_id,
            'type': ind_type,
            'params': params,
            'subplot': subplot
        }
        # Check for duplicates
        self.global_indicators = [i for i in self.global_indicators if i['id'] != ind_id]
        self.global_indicators.append(config)
        
        if subplot != "candlestick":
            if subplot not in self.subplot_configs:
                self.subplot_configs[subplot] = {'weight': weight, 'overlay_on': None}
        
        # Rebuild to apply changes
        self._rebuild_chart()

    def remove_indicator_config(self, ind_id):
        """Removes an indicator."""
        self.global_indicators = [i for i in self.global_indicators if i['id'] != ind_id]
        self._rebuild_chart()

    def set_indicator_renderer(self, callback):
        """Sets a callback function(indicator_config, data_df) to render series."""
        self.indicator_renderer = callback

    def _render_shape(self, tag, shape):
        t = shape["type"]
        pts = shape["points"]
        kw = shape.get("kwargs", {}).copy()  # Copy to avoid mutation
        plot_name = kw.pop("plot_name", shape.get("plot", "candlestick")) or "candlestick"

        # Merge top-level attributes from shape dict into kw if not present
        # EasyPyChart stores some args (fill, width, dash) at top level

        # Helper to strip alpha
        def fix_color(c):
            if isinstance(c, str) and c.startswith("#") and len(c) == 9:
                return c[:7]
            return c

        def get_prop(keys, default=None):
            # Try top-level shape dict first, then kw, then default
            for k in keys:
                if k in shape:
                    return shape[k]
                if k in kw:
                    return kw[k]
            return default

        if t == "line":
            # create_line(dt1, p1, dt2, p2, color, label, ...)
            color = get_prop(["fill", "color"], "#FFFFFF")
            color = fix_color(color)
            width = get_prop(["width"], 2)
            dash = get_prop(["dash"])
            label = get_prop(["label"], "Line")

            kw.pop("color", None)
            kw.pop("width", None)
            kw.pop("dash", None)
            kw.pop("label", None)

            self.chart.create_line(
                pts[0][0],
                pts[0][1],
                pts[1][0],
                pts[1][1],
                color,
                label,
                plot_name=plot_name,
                tags=tag,
                width=width,
                dash=dash,
                **kw,
            )

        elif t == "rect":
            fill = get_prop(["fill", "fill_color"], "")
            fill = fix_color(fill)
            label = get_prop(["label"], "Rect")

            kw.pop("fill_color", None)
            kw.pop("fill", None)
            kw.pop("label", None)

            self.chart.create_rectangle(
                pts[0][0], pts[0][1], pts[1][0], pts[1][1], fill, label, tags=tag, **kw
            )

        elif t == "hline":
            color = get_prop(["fill", "color"], "#00FFFF")
            color = fix_color(color)
            label = get_prop(["label"], "HLine")
            width = get_prop(["width"], 2)
            dash = get_prop(["dash"])

            kw.pop("color", None)
            kw.pop("width", None)
            kw.pop("dash", None)
            kw.pop("label", None)

            self.chart.create_hline(
                pts[0][1], color, label, tags=tag, width=width, dash=dash, **kw
            )

        elif t == "vline":
            color = get_prop(["fill", "color"], "#00FFFF")
            color = fix_color(color)
            label = get_prop(["label"], "VLine")
            width = get_prop(["width"], 2)
            dash = get_prop(["dash"])

            kw.pop("color", None)
            kw.pop("width", None)
            kw.pop("dash", None)
            kw.pop("label", None)

            self.chart.create_vline(
                pts[0][0], color, label, tags=tag, width=width, dash=dash, **kw
            )

        elif t == "text":
            color = get_prop(["fill", "color"], "#FFFFFF")
            color = fix_color(color)

            label = get_prop(["label"], "Text")
            text_content = get_prop(["text"], "")

            kw.pop("color", None)
            kw.pop("fill", None)
            kw.pop("label", None)
            kw.pop("text", None)

            self.chart.create_text(
                pts[0][0], pts[0][1], text_content, color, label, tags=tag, **kw
            )

    def save_session(self, filepath):
        """Saves the current session (Layout + All Drawings) to a JSON file."""
        print(f"LayoutManager: Saving session to {filepath}...")
        # 1. Sync current symbol's drawings from chart to store
        self._sync_from_chart()

        data = {
            "symbol_drawings": {},
            "current_context": {
                "symbol": self.current_symbol,
                "timeframe": self.current_timeframe,
            },
        }

        # Serialize Drawings (Datetime -> Str)
        for sym, shapes in self.symbol_drawings.items():
            serialized_shapes = {}
            for tag, shape in shapes.items():
                s_copy = copy.deepcopy(shape)
                # Convert points
                try:
                    s_copy["points"] = [
                        (
                            (
                                p[0].isoformat()
                                if hasattr(p[0], "isoformat")
                                else str(p[0])
                            ),
                            p[1],
                        )
                        for p in s_copy["points"]
                    ]
                except:
                    pass
                serialized_shapes[tag] = s_copy
            data["symbol_drawings"][sym] = serialized_shapes

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

    def load_session(self, filepath="chart_state.json"):
        if not os.path.exists(filepath):
            return

        with open(filepath, "r") as f:
            data = json.load(f)

        # Deserialize Drawings
        self.symbol_drawings = {}
        for sym, shapes in data.get('symbol_drawings', {}).items():
            deserialized = {}
            for tag, shape in shapes.items():
                # Convert back to datetime
                pts = []
                for p in shape['points']:
                    dt = pd.to_datetime(p[0])
                    pts.append((dt, p[1]))
                shape['points'] = pts
                deserialized[tag] = shape
            self.symbol_drawings[sym] = deserialized
            
        # Restore Context
        ctx = data.get('current_context', {})
        sym = ctx.get('symbol')
        tf = ctx.get('timeframe')
        
        if sym and tf:
            # SMART RESTORE: Only force a context switch if we aren't already on this symbol.
            # If we are already on the symbol, just rebuild to show drawings on CURRENT timeframe.
            if self.current_symbol == sym:
                self._rebuild_chart()
                print(f"LayoutManager: Session loaded for {sym} (Maintained current timeframe)")
            else:
                # Reset current_symbol to ensure set_context doesn't save empty state over loaded state
                self.current_symbol = None
                self.set_context(sym, tf)
                print(f"LayoutManager: Session loaded. Context set to {sym} {tf}")
        else:
            self._rebuild_chart() 
            print("LayoutManager: Session loaded (No context).")

    def load_symbol_session(self, symbol, filepath):
        """Loads drawings for a specific symbol from a session file into memory
        without triggering a context switch or affecting other symbols."""
        if not os.path.exists(filepath):
            return
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
        except Exception:
            return

        drawings = data.get("symbol_drawings", {}).get(symbol, {})
        deserialized = {}
        for tag, shape in drawings.items():
            pts = []
            for p in shape.get("points", []):
                try:
                    dt = pd.to_datetime(p[0])
                    pts.append((dt, p[1]))
                except Exception:
                    continue
            if pts:
                shape_copy = copy.deepcopy(shape)
                shape_copy["points"] = pts
                deserialized[tag] = shape_copy
        self.symbol_drawings[symbol] = deserialized

    def save_layout(self, filepath):
        """Saves only the global indicators and subplot configs (no drawings/context)."""
        print(f"LayoutManager: Saving layout to {filepath}...")
        
        # Sanitize Indicators (Remove non-serializable functions)
        clean_indicators = []
        for ind in self.global_indicators:
            clean_ind = copy.deepcopy(ind)
            if "params" in clean_ind and "func" in clean_ind["params"]:
                del clean_ind["params"]["func"]
            clean_indicators.append(clean_ind)

        data = {
            "global_indicators": clean_indicators,
            "subplot_configs": self.subplot_configs,
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

    def load_layout(self, filepath):
        """Loads only the global indicators and subplot configs."""
        if not os.path.exists(filepath):
            return

        print(f"LayoutManager: Loading layout from {filepath}...")
        with open(filepath, "r") as f:
            data = json.load(f)

        self.global_indicators = data.get("global_indicators", [])
        self.subplot_configs = data.get("subplot_configs", {})
        
        # Rebuild chart to apply the new indicators/subplots (preserves context and drawings)
        self._rebuild_chart()
