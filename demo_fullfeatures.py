"""demo_fullfeatures.py - Full Features Demo for FinChart.

Demonstrates:
  - All 5 indicators: SMA, EMA, RSI, MACD, BollingerBands
  - All 4 chart types: Candlestick, Line, Area, Histogram
  - Dark and Light themes
  - Session save/load
  - Large dataset (1000 bars) for performance testing
  - Real-time streaming simulation

Run:
    python demo_fullfeatures.py
"""
import tkinter as tk
from tkinter import ttk
import math
import random
from datetime import datetime, timedelta
import threading
import time
import os

from finchart import ChartWidget, OHLCV, DarkTheme, LightTheme
from finchart.core.types import ChartType
from finchart.indicators import SMA, EMA, RSI, MACD, BollingerBands, Volume


SESSION_FILE = "demo_session.json"


# ---------------------------------------------------------------------------
# Synthetic Data Generator
# ---------------------------------------------------------------------------
def generate_price_data(n: int = 500, seed: int = 99) -> list:
    """Generate realistic OHLCV candlestick data with trends and volatility."""
    random.seed(seed)
    bars = []
    price = 45000.0  # BTC-like price
    base_ts = datetime(2024, 1, 1, 0, 0)

    volatility = 0.012
    trend = 0.0002

    for i in range(n):
        # Slow trend reversal every ~100 bars
        if i % 100 == 50:
            trend = -trend

        open_ = price
        change = random.gauss(trend * price, volatility * price)
        close = max(1.0, price + change)
        high  = max(open_, close) * (1.0 + abs(random.gauss(0.0, 0.004)))
        low   = min(open_, close) * (1.0 - abs(random.gauss(0.0, 0.004)))
        vol   = random.uniform(10_000_000, 100_000_000)

        ts = (base_ts + timedelta(hours=i)).timestamp()
        bars.append(OHLCV(timestamp=ts, open=open_, high=high, low=low, close=close, volume=vol))
        price = close

    return bars


# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------
def main():
    root = tk.Tk()
    root.title("FinChart — Full Feature Demo")
    root.geometry("1440x860")
    root.configure(bg="#0D1117")

    # ---- Top Toolbar ----
    toolbar = tk.Frame(root, bg="#161B22", height=44)
    toolbar.pack(side="top", fill="x")
    toolbar.pack_propagate(False)

    btn_style = {"bg": "#21262D", "fg": "#C9D1D9", "font": ("Segoe UI", 9),
                 "relief": "flat", "padx": 10, "pady": 6, "cursor": "hand2",
                 "activebackground": "#30363D", "activeforeground": "#FFFFFF",
                 "borderwidth": 0}

    def make_btn(parent, text, command):
        b = tk.Button(parent, text=text, command=command, **btn_style)
        b.pack(side="left", padx=2, pady=6)
        return b

    # ---- Hover Info Bar ----
    info_var = tk.StringVar(value="  Hover over a bar to see OHLCV data")
    info_bar = tk.Label(
        root, textvariable=info_var,
        bg="#0D1117", fg="#8B949E",
        font=("Segoe UI", 9), anchor="w"
    )
    info_bar.pack(side="bottom", fill="x", ipady=3)

    # ---- Status Bar ----
    status_var = tk.StringVar(value="  FinChart v0.1.0 | 500 bars loaded")
    status_bar = tk.Label(
        root, textvariable=status_var,
        bg="#161B22", fg="#6E7681",
        font=("Segoe UI", 8), anchor="w"
    )
    status_bar.pack(side="bottom", fill="x", ipady=2)

    def on_hover(event_type: str, data: dict):
        if event_type == "hover" and data.get("bar"):
            b = data["bar"]
            dt = datetime.fromtimestamp(b.timestamp).strftime("%Y-%m-%d %H:%M")
            chg = b.close - b.open
            pct = (chg / b.open) * 100
            arrow = "▲" if chg >= 0 else "▼"
            info_var.set(
                f"  {dt}   O {b.open:,.2f}   H {b.high:,.2f}   "
                f"L {b.low:,.2f}   C {b.close:,.2f}   "
                f"{arrow} {abs(chg):,.2f} ({abs(pct):.2f}%)   Vol {b.volume/1e6:.2f}M"
            )

    # ---- Chart Widget ----
    chart = ChartWidget(
        root,
        width=1440, height=780,
        theme=DarkTheme(),
        callback=on_hover,
    )
    chart.pack(fill="both", expand=True)

    # ---- Load Data ----
    bars = generate_price_data(500)
    chart.set_data(bars)

    # ---- Active Indicators ----
    _indicators = {}

    def toggle_indicator(name: str, factory):
        if name in _indicators:
            chart.remove_indicator(_indicators.pop(name))
            status_var.set(f"  {name} removed")
        else:
            ind = chart.add_indicator(factory())
            _indicators[name] = ind
            status_var.set(f"  {name} added")

    # ---- Add Volume subplot with 21MA by default ----
    toggle_indicator("Volume", lambda: Volume(ma_period=21))

    # ---- Toolbar Buttons ----
    make_btn(toolbar, "Candlestick", lambda: chart.set_chart_type(ChartType.CANDLESTICK))
    make_btn(toolbar, "Line",        lambda: chart.set_chart_type(ChartType.LINE))
    make_btn(toolbar, "Area",        lambda: chart.set_chart_type(ChartType.AREA))
    make_btn(toolbar, "Histogram",   lambda: chart.set_chart_type(ChartType.HISTOGRAM))

    sep = tk.Label(toolbar, text="│", bg="#161B22", fg="#30363D", font=("Segoe UI", 12))
    sep.pack(side="left", padx=4)

    make_btn(toolbar, "SMA(20)",     lambda: toggle_indicator("SMA", lambda: SMA(20, "#2196F3")))
    make_btn(toolbar, "EMA(9)",      lambda: toggle_indicator("EMA", lambda: EMA(9, "#FF9800")))
    make_btn(toolbar, "BB(20)",      lambda: toggle_indicator("BB",  lambda: BollingerBands(20)))
    make_btn(toolbar, "RSI(14)",     lambda: toggle_indicator("RSI", lambda: RSI(14)))
    make_btn(toolbar, "MACD",        lambda: toggle_indicator("MACD", lambda: MACD()))
    make_btn(toolbar, "Vol+21MA",   lambda: toggle_indicator("Volume", lambda: Volume(ma_period=21)))

    sep2 = tk.Label(toolbar, text="│", bg="#161B22", fg="#30363D", font=("Segoe UI", 12))
    sep2.pack(side="left", padx=4)

    _dark = [True]
    def toggle_theme():
        if _dark[0]:
            chart.set_theme(LightTheme())
            root.configure(bg="#FFFFFF")
            toolbar.configure(bg="#F6F8FA")
            info_bar.configure(bg="#FFFFFF", fg="#444444")
            status_bar.configure(bg="#F6F8FA", fg="#666666")
        else:
            chart.set_theme(DarkTheme())
            root.configure(bg="#0D1117")
            toolbar.configure(bg="#161B22")
            info_bar.configure(bg="#0D1117", fg="#8B949E")
            status_bar.configure(bg="#161B22", fg="#6E7681")
        _dark[0] = not _dark[0]

    make_btn(toolbar, "☀ / ☾ Theme", toggle_theme)
    make_btn(toolbar, "Fit [F]",     lambda: chart.fit_content())
    make_btn(toolbar, "Zoom +",      lambda: chart.zoom(1.2))
    make_btn(toolbar, "Zoom -",      lambda: chart.zoom(0.83))

    sep3 = tk.Label(toolbar, text="│", bg="#161B22", fg="#30363D", font=("Segoe UI", 12))
    sep3.pack(side="left", padx=4)

    make_btn(toolbar, "💾 Save",     lambda: (chart.save_session(SESSION_FILE),
                                               status_var.set(f"  Session saved → {SESSION_FILE}")))
    make_btn(toolbar, "📂 Load",     lambda: (chart.load_session(SESSION_FILE),
                                               status_var.set(f"  Session loaded ← {SESSION_FILE}")))

    # ---- Dataset Size Switcher ----
    sep4 = tk.Label(toolbar, text="│", bg="#161B22", fg="#30363D", font=("Segoe UI", 12))
    sep4.pack(side="left", padx=4)

    def load_n_bars(n: int):
        nonlocal bars
        _indicators.clear()
        bars = generate_price_data(n)
        chart.clear_indicators()
        chart.set_data(bars)
        status_var.set(f"  {n} bars loaded")

    make_btn(toolbar, "100 bars",  lambda: load_n_bars(100))
    make_btn(toolbar, "500 bars",  lambda: load_n_bars(500))
    make_btn(toolbar, "2000 bars", lambda: load_n_bars(2000))

    # ---- Streaming Simulation ----
    _streaming = [False]
    _stream_thread = [None]

    def stream_tick():
        """Append one bar every 200ms to simulate real-time streaming."""
        while _streaming[0]:
            last = bars[-1]
            new_price = last.close * (1.0 + random.gauss(0.0, 0.005))
            new_bar = OHLCV(
                timestamp=last.timestamp + 3600,
                open=last.close,
                high=max(last.close, new_price) * (1 + abs(random.gauss(0.0, 0.003))),
                low=min(last.close, new_price) * (1 - abs(random.gauss(0.0, 0.003))),
                close=new_price,
                volume=random.uniform(5_000_000, 50_000_000),
            )
            bars.append(new_bar)
            root.after(0, lambda b=new_bar: chart.append(b))
            time.sleep(0.3)

    def toggle_stream():
        if _streaming[0]:
            _streaming[0] = False
            status_var.set("  Streaming stopped")
        else:
            _streaming[0] = True
            t = threading.Thread(target=stream_tick, daemon=True)
            _stream_thread[0] = t
            t.start()
            status_var.set("  ▶ Streaming live data...")

    make_btn(toolbar, "▶ Stream", toggle_stream)

    # ---- Keyboard Shortcuts ----
    root.bind("<f>", lambda e: chart.fit_content())
    root.bind("<F>", lambda e: chart.fit_content())
    root.bind("<equal>", lambda e: chart.zoom(1.2))
    root.bind("<minus>",  lambda e: chart.zoom(0.83))
    root.bind("<t>", lambda e: toggle_theme())
    root.bind("<T>", lambda e: toggle_theme())

    print("Starting mainloop...")
    root.mainloop()
    print("Mainloop ended")
    _streaming[0] = False


if __name__ == "__main__":
    print("Starting main...")
    try:
        main()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
