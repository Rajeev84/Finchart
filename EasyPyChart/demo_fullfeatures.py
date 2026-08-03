"""
Full-featured EasyPyChart demo app.

This script exercises the parts of the library that are actually implemented in
the local codebase:
- candlestick rendering
- multiple subplots and indicator series
- drawing tools via InteractionManager
- symbol/timeframe context switching via LayoutManager
- chart state and session persistence
- event logging, shape inspection, and view inspection
- optional market profile overlay
- synthetic real-time updates
"""
from __future__ import annotations

import os
import sys
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta

import numpy as np
import pandas as pd


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from easypychart import EasyPyChart
from easypychart.interaction_manager import InteractionManager
from easypychart.layout_manager import LayoutManager


DEMO_CHART_STATE = os.path.join(PROJECT_ROOT, "easypychart_demo_chart_state.json")
DEMO_SESSION_STATE = os.path.join(PROJECT_ROOT, "easypychart_demo_session.json")


def build_symbol_dataset(symbol: str, bars: int = 900) -> dict[str, pd.DataFrame]:
    seed = sum(ord(ch) for ch in symbol)
    rng = np.random.default_rng(seed)

    start = datetime(2026, 1, 5, 9, 15)
    dates = [start + timedelta(minutes=i) for i in range(bars)]

    base_price = 62000.0 if "BTC" in symbol else 3100.0
    drift = 0.12 if "BTC" in symbol else 0.05
    wave = np.sin(np.linspace(0, 18, bars)) * (130 if "BTC" in symbol else 11)

    opens = []
    highs = []
    lows = []
    closes = []
    volumes = []
    price = base_price

    for i in range(bars):
        move = rng.normal(drift, 18 if "BTC" in symbol else 1.8) + wave[i] * 0.04
        open_price = price
        close_price = max(1.0, open_price + move)
        wick_up = abs(rng.normal(10 if "BTC" in symbol else 0.8, 4 if "BTC" in symbol else 0.3))
        wick_down = abs(rng.normal(10 if "BTC" in symbol else 0.8, 4 if "BTC" in symbol else 0.3))
        high_price = max(open_price, close_price) + wick_up
        low_price = min(open_price, close_price) - wick_down
        volume = int(abs(rng.normal(1800 if "BTC" in symbol else 7000, 500 if "BTC" in symbol else 1800)))

        opens.append(round(open_price, 2))
        highs.append(round(high_price, 2))
        lows.append(round(low_price, 2))
        closes.append(round(close_price, 2))
        volumes.append(volume)
        price = close_price

    one_min = pd.DataFrame(
        {
            "Datetime": dates,
            "Open": opens,
            "High": highs,
            "Low": lows,
            "Close": closes,
            "Volume": volumes,
        }
    )

    return {
        "1m": one_min,
        "5m": resample_ohlcv(one_min, "5min"),
        "15m": resample_ohlcv(one_min, "15min"),
    }


def resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    return (
        df.set_index("Datetime")
        .resample(rule)
        .agg(
            {
                "Open": "first",
                "High": "max",
                "Low": "min",
                "Close": "last",
                "Volume": "sum",
            }
        )
        .dropna()
        .reset_index()
    )


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


class DemoApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("EasyPyChart Full Features Demo")
        self.root.geometry("1500x920")
        self.root.configure(bg="#161A23")

        self.datasets = {
            "BTCUSDT": build_symbol_dataset("BTCUSDT"),
            "ETHUSDT": build_symbol_dataset("ETHUSDT"),
        }

        self.symbol_var = tk.StringVar(value="BTCUSDT")
        self.timeframe_var = tk.StringVar(value="5m")
        self.market_profile_var = tk.BooleanVar(value=False)
        self.sma_var = tk.BooleanVar(value=True)
        self.ema_var = tk.BooleanVar(value=True)
        self.rsi_var = tk.BooleanVar(value=True)
        self.volume_var = tk.BooleanVar(value=True)

        self.realtime_enabled = False
        self.realtime_job = None
        self.seeded_contexts: set[tuple[str, str]] = set()

        self._build_ui()

        self.chart = EasyPyChart(
            self.chart_host,
            callback=self.on_chart_event,
            config={
                "background": "#10141C",
                "width": 1400,
                "height": 780,
                "scale_x": 12.0,
                "crosshair_enabled": True,
                "crosshair_color": "#8A93A6",
                "padding_right": 78,
                "padding_bottom": 34,
            },
        )
        self.chart.pack(fill="both", expand=True, padx=8, pady=8)

        self.layout = LayoutManager(self.chart)
        self.interaction = InteractionManager(self.chart, self.layout)
        self.chart.layout = self.layout
        self.chart.interaction = self.interaction

        self.layout.subplot_configs.update(
            {
                "rsi": {"weight": 1.0, "overlay_on": None},
                "volume": {"weight": 1.0, "overlay_on": None},
            }
        )
        self.layout.data_store = self.datasets

        self.symbol_var.trace_add("write", self._on_context_change)
        self.timeframe_var.trace_add("write", self._on_context_change)

        self.apply_context(seed_demo=True)

    def _build_ui(self) -> None:
        top = tk.Frame(self.root, bg="#1C2330")
        top.pack(side="top", fill="x")

        ctx_bar = tk.Frame(top, bg="#1C2330")
        ctx_bar.pack(side="top", fill="x", padx=8, pady=(8, 4))

        tk.Label(ctx_bar, text="Symbol", bg="#1C2330", fg="#E7ECF6").pack(side="left")
        ttk.Combobox(
            ctx_bar,
            textvariable=self.symbol_var,
            values=["BTCUSDT", "ETHUSDT"],
            width=10,
            state="readonly",
        ).pack(side="left", padx=(6, 14))

        tk.Label(ctx_bar, text="Timeframe", bg="#1C2330", fg="#E7ECF6").pack(side="left")
        ttk.Combobox(
            ctx_bar,
            textvariable=self.timeframe_var,
            values=["1m", "5m", "15m"],
            width=7,
            state="readonly",
        ).pack(side="left", padx=(6, 14))

        ttk.Checkbutton(
            ctx_bar,
            text="Market Profile",
            variable=self.market_profile_var,
            command=self.refresh_overlays,
        ).pack(side="left", padx=(0, 12))
        ttk.Checkbutton(ctx_bar, text="SMA 20", variable=self.sma_var, command=self.refresh_overlays).pack(side="left")
        ttk.Checkbutton(ctx_bar, text="EMA 50", variable=self.ema_var, command=self.refresh_overlays).pack(side="left")
        ttk.Checkbutton(ctx_bar, text="RSI 14", variable=self.rsi_var, command=self.refresh_overlays).pack(side="left")
        ttk.Checkbutton(ctx_bar, text="Volume MA", variable=self.volume_var, command=self.refresh_overlays).pack(side="left")

        nav_bar = tk.Frame(top, bg="#1C2330")
        nav_bar.pack(side="top", fill="x", padx=8, pady=4)

        self._button(nav_bar, "Reset", self.chart_reset_view)
        self._button(nav_bar, "Zoom In", lambda: self.chart.zoom_in())
        self._button(nav_bar, "Zoom Out", lambda: self.chart.zoom_out())
        self._button(nav_bar, "Pan Left", lambda: self.chart.pan(-20))
        self._button(nav_bar, "Pan Right", lambda: self.chart.pan(20))
        self._button(nav_bar, "View Coords", self.show_view_coordinates)
        self._button(nav_bar, "List Shapes", self.list_shapes)
        self._button(nav_bar, "Seed Drawings", self.seed_demo_drawings)
        self._button(nav_bar, "Clear Drawings", self.clear_drawings)

        tool_bar = tk.Frame(top, bg="#1C2330")
        tool_bar.pack(side="top", fill="x", padx=8, pady=4)

        for label, tool in [
            ("Select", None),
            ("Line", "line"),
            ("Rect", "rect"),
            ("HLine", "hline"),
            ("VLine", "vline"),
            ("Angle", "angle_line"),
            ("Long Pos", "long_pos"),
            ("Short Pos", "short_pos"),
        ]:
            self._button(tool_bar, label, lambda name=tool: self.set_tool(name))

        self._button(tool_bar, "Blue", lambda: self.set_color("#4AA3FF"))
        self._button(tool_bar, "Gold", lambda: self.set_color("#FFCC33"))
        self._button(tool_bar, "Mint", lambda: self.set_color("#35D6A6"))
        self._button(tool_bar, "Angle 45", lambda: self.set_angle(45))
        self._button(tool_bar, "Angle 135", lambda: self.set_angle(135))

        state_bar = tk.Frame(top, bg="#1C2330")
        state_bar.pack(side="top", fill="x", padx=8, pady=(4, 8))

        self._button(state_bar, "Save Chart State", self.save_chart_state)
        self._button(state_bar, "Load Chart State", self.load_chart_state)
        self._button(state_bar, "Save Session", self.save_session)
        self._button(state_bar, "Load Session", self.load_session)
        self._button(state_bar, "Tick Once", self.advance_one_tick)
        self._button(state_bar, "Realtime On/Off", self.toggle_realtime)

        main = tk.PanedWindow(self.root, orient="vertical", sashrelief="flat", bg="#161A23")
        main.pack(fill="both", expand=True)

        self.chart_host = tk.Frame(main, bg="#11151D")
        main.add(self.chart_host, stretch="always", minsize=600)

        log_host = tk.Frame(main, bg="#0E1218", height=160)
        main.add(log_host, minsize=120)

        self.status_var = tk.StringVar(value="Ready")
        tk.Label(
            log_host,
            textvariable=self.status_var,
            anchor="w",
            bg="#0E1218",
            fg="#DCE3F1",
            padx=10,
            pady=6,
        ).pack(fill="x")

        self.log_box = tk.Text(
            log_host,
            height=8,
            bg="#0A0D12",
            fg="#C7D0E0",
            insertbackground="#FFFFFF",
            relief="flat",
        )
        self.log_box.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _button(self, parent: tk.Widget, text: str, command) -> tk.Button:
        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg="#273246",
            fg="#F4F7FC",
            activebackground="#31405A",
            activeforeground="#FFFFFF",
            relief="flat",
            padx=8,
            pady=4,
        )
        button.pack(side="left", padx=2)
        return button

    def log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_box.insert("end", f"[{timestamp}] {message}\n")
        self.log_box.see("end")
        self.status_var.set(message)

    def current_df(self) -> pd.DataFrame:
        return self.datasets[self.symbol_var.get()][self.timeframe_var.get()]

    def _on_context_change(self, *_args) -> None:
        self.apply_context(seed_demo=False)

    def apply_context(self, seed_demo: bool = False) -> None:
        symbol = self.symbol_var.get()
        timeframe = self.timeframe_var.get()
        self.layout.set_context(symbol, timeframe)
        self.refresh_overlays()

        context_key = (symbol, timeframe)
        if seed_demo and context_key not in self.seeded_contexts:
            self.seed_demo_drawings()
            self.seeded_contexts.add(context_key)

        self.log(f"Context loaded: {symbol} {timeframe} with {len(self.current_df())} bars")

    def refresh_overlays(self) -> None:
        df = self.current_df()
        self.chart.config["market_profile_enabled"] = self.market_profile_var.get()
        self.chart.mp_source_data = self.datasets[self.symbol_var.get()]["1m"]

        for subplot in self.chart.subplots.values():
            subplot["series"] = []

        close = df["Close"]
        volume = df["Volume"]

        if self.sma_var.get():
            sma20 = close.rolling(20).mean()
            self.chart.create_series("candlestick", sma20, color="#FFCC33", thickness=2, label="SMA 20")

        if self.ema_var.get():
            ema50 = close.ewm(span=50, adjust=False).mean()
            self.chart.create_series("candlestick", ema50, color="#4AA3FF", thickness=2, label="EMA 50")

        if self.rsi_var.get():
            rsi14 = compute_rsi(close)
            self.chart.create_series("rsi", rsi14, color="#35D6A6", thickness=2, label="RSI 14")

        if self.volume_var.get():
            volume_ma = volume.rolling(20).mean()
            self.chart.create_series("volume", volume_ma, color="#B685FF", thickness=2, label="Volume MA 20")

        self.chart.render()

    def seed_demo_drawings(self) -> None:
        if self.layout.current_symbol is None:
            return

        df = self.current_df()
        if len(df) < 150:
            return

        self.clear_drawings(log_change=False)

        dt_a = df.iloc[40]["Datetime"]
        dt_b = df.iloc[110]["Datetime"]
        dt_c = df.iloc[70]["Datetime"]
        close_a = float(df.iloc[40]["Close"])
        close_b = float(df.iloc[110]["Close"])
        low_mid = float(df.iloc[85]["Low"])
        high_mid = float(df.iloc[85]["High"])

        self.layout.add_drawing(
            "demo_trend",
            "line",
            [(dt_a, close_a - (close_a * 0.01)), (dt_b, close_b + (close_b * 0.008))],
            color="#4AA3FF",
            width=2,
            label="Trend",
        )
        self.layout.add_drawing(
            "demo_zone",
            "rect",
            [(df.iloc[60]["Datetime"], low_mid), (df.iloc[120]["Datetime"], high_mid)],
            fill_color="#35D6A6",
            outline_color="#35D6A6",
            alpha=0.35,
            label="Demand Zone",
        )
        self.layout.add_drawing(
            "demo_level",
            "hline",
            [(dt_c, float(df.iloc[70]["Close"]))],
            color="#FFCC33",
            width=2,
            dash=(6, 3),
            label="Level",
        )
        self.layout.add_drawing(
            "demo_marker",
            "vline",
            [(df.iloc[95]["Datetime"], float(df.iloc[95]["Close"]))],
            color="#FF7B72",
            width=1,
            dash=(4, 4),
            label="Event",
        )
        self.layout.add_drawing(
            "demo_note",
            "text",
            [(df.iloc[125]["Datetime"], float(df.iloc[125]["High"]))],
            text="Breakout area",
            fill="#FFFFFF",
            label="Note",
        )
        self.log("Seeded demo drawings for the active context")

    def clear_drawings(self, log_change: bool = True) -> None:
        self.chart.drawings = {}
        if self.layout.current_symbol:
            self.layout.symbol_drawings[self.layout.current_symbol] = {}
        self.chart.render()
        if log_change:
            self.log("Cleared drawings in the active context")

    def set_tool(self, name: str | None) -> None:
        self.interaction.set_tool(name)
        label = "select/pan" if name is None else name
        self.log(f"Tool selected: {label}")

    def set_color(self, color: str) -> None:
        self.interaction.set_color(color)
        self.log(f"Drawing color set to {color}")

    def set_angle(self, angle: int) -> None:
        self.interaction.active_angle = angle
        self.log(f"Angle tool set to {angle} degrees")

    def chart_reset_view(self) -> None:
        self.chart.reset_zoom()
        self.log("Chart view reset")

    def show_view_coordinates(self) -> None:
        left, right, low, high = self.chart.get_view_coordinates()
        self.log(f"View range: {left} -> {right} | low={low:.2f} high={high:.2f}")

    def list_shapes(self) -> None:
        if not self.chart.drawings:
            self.log("No active shapes")
            return

        for tag in sorted(self.chart.drawings):
            details = self.chart.get_area_xy(tag)
            self.log(f"{tag}: {details}")

    def save_chart_state(self) -> None:
        self.chart.save_state(self.symbol_var.get(), filepath=DEMO_CHART_STATE)
        self.log(f"Chart state saved to {DEMO_CHART_STATE}")

    def load_chart_state(self) -> None:
        self.chart.load_state(self.symbol_var.get(), filepath=DEMO_CHART_STATE)
        self.log(f"Chart state loaded from {DEMO_CHART_STATE}")

    def save_session(self) -> None:
        self.layout.save_session(DEMO_SESSION_STATE)
        self.log(f"Session saved to {DEMO_SESSION_STATE}")

    def load_session(self) -> None:
        self.layout.load_session(DEMO_SESSION_STATE)
        if self.layout.current_symbol:
            self.symbol_var.set(self.layout.current_symbol)
        if self.layout.current_timeframe:
            self.timeframe_var.set(self.layout.current_timeframe)
        self.refresh_overlays()
        self.log(f"Session loaded from {DEMO_SESSION_STATE}")

    def advance_one_tick(self) -> None:
        symbol = self.symbol_var.get()
        base_df = self.datasets[symbol]["1m"]

        rng = np.random.default_rng(int(base_df["Close"].iloc[-1] * 100) % 100000)
        last = base_df.iloc[-1]
        next_dt = last["Datetime"] + timedelta(minutes=1)
        open_price = float(last["Close"])
        close_price = max(1.0, open_price + rng.normal(0.0, 12 if "BTC" in symbol else 1.2))
        high_price = max(open_price, close_price) + abs(rng.normal(4 if "BTC" in symbol else 0.4, 1.5))
        low_price = min(open_price, close_price) - abs(rng.normal(4 if "BTC" in symbol else 0.4, 1.5))
        volume = int(abs(rng.normal(2000 if "BTC" in symbol else 7600, 450)))

        new_row = pd.DataFrame(
            [
                {
                    "Datetime": next_dt,
                    "Open": round(open_price, 2),
                    "High": round(high_price, 2),
                    "Low": round(low_price, 2),
                    "Close": round(close_price, 2),
                    "Volume": volume,
                }
            ]
        )

        updated_1m = pd.concat([base_df, new_row], ignore_index=True)
        self.datasets[symbol] = {
            "1m": updated_1m,
            "5m": resample_ohlcv(updated_1m, "5min"),
            "15m": resample_ohlcv(updated_1m, "15min"),
        }
        self.layout.data_store = self.datasets

        if self.layout.current_symbol == symbol:
            self.layout.set_context(symbol, self.timeframe_var.get())
            self.refresh_overlays()

        self.log(f"Appended one synthetic tick for {symbol} at {next_dt}")

    def toggle_realtime(self) -> None:
        self.realtime_enabled = not self.realtime_enabled
        if self.realtime_enabled:
            self.log("Realtime simulation enabled")
            self._schedule_next_tick()
        else:
            if self.realtime_job is not None:
                self.root.after_cancel(self.realtime_job)
                self.realtime_job = None
            self.log("Realtime simulation disabled")

    def _schedule_next_tick(self) -> None:
        if not self.realtime_enabled:
            return
        self.advance_one_tick()
        self.realtime_job = self.root.after(1500, self._schedule_next_tick)

    def on_chart_event(self, event_type: str, payload: dict) -> None:
        if event_type == "move":
            return

        if event_type == "hover":
            dt = payload.get("Datetime")
            close = payload.get("Close")
            if dt is not None and close is not None:
                self.status_var.set(f"Hover {dt} | Close {close}")
            return

        parts = [event_type]
        if payload.get("sub_plot"):
            parts.append(f"plot={payload['sub_plot']}")
        if payload.get("shape"):
            parts.append(f"shape={payload['shape']}")
        if payload.get("series"):
            parts.append(f"series={payload['series']}")
        if payload.get("button"):
            parts.append(f"button={payload['button']}")
        if payload.get("key"):
            parts.append(f"key={payload['key']}")
        if payload.get("time") is not None and payload.get("y") is not None:
            parts.append(f"time={payload['time']}")
            parts.append(f"price={payload['y']:.2f}")
        self.log(" | ".join(parts))


def main() -> None:
    root = tk.Tk()
    app = DemoApp(root)
    app.log("EasyPyChart full-feature demo ready")
    root.mainloop()


if __name__ == "__main__":
    main()
