"""
FinChart GUI demo for visual chart verification.

Loads sample OHLCV CSVs from ./data, renders a TradingView-like chart surface,
and lets you switch symbols/timeframes from the bundled files.
"""

from __future__ import annotations

import csv
import math
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple

import tkinter as tk
from tkinter import ttk

from finchart.tradingview.chart_api import Chart
from finchart.tradingview.enums import KeyboardEventType, TouchEventType
from finchart.tradingview.input_events import ModifierState, TouchPoint
from finchart.tradingview.price_scale import PriceScale
from finchart.tradingview.types import OHLCVBar


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
TIMEFRAME_ORDER = ["1m", "5m", "1d"]
TIMEFRAME_LABELS = {"1m": "1m", "5m": "5m", "1d": "1D"}
RESET_VIEW_MAX_BARS = 215
RESET_VIEW_RIGHT_OFFSET_BARS = 3.0


@dataclass
class ChartDataset:
    symbol: str
    timeframe: str
    bars: List[OHLCVBar]


def load_csv_bars(path: Path) -> List[OHLCVBar]:
    bars: List[OHLCVBar] = []
    with path.open("r", newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if not row:
                continue
            lower = {k.lower(): v for k, v in row.items() if k}
            raw_ts = lower.get("timestamp", lower.get("time", lower.get("datetime", 0.0))) or 0.0
            timestamp = _parse_timestamp(raw_ts)
            bars.append(
                OHLCVBar(
                    timestamp=timestamp,
                    open=float(lower.get("open", 0.0) or 0.0),
                    high=float(lower.get("high", 0.0) or 0.0),
                    low=float(lower.get("low", 0.0) or 0.0),
                    close=float(lower.get("close", 0.0) or 0.0),
                    volume=float(lower.get("volume", 0.0) or 0.0),
                )
            )
    return bars


def _parse_timestamp(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        pass
    try:
        iso_text = text.replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso_text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except ValueError:
        return 0.0


def discover_datasets() -> Dict[str, Dict[str, Path]]:
    datasets: Dict[str, Dict[str, Path]] = {}
    if not DATA_DIR.exists():
        return datasets
    for path in DATA_DIR.glob("*.csv"):
        stem = path.stem
        if "_" not in stem:
            continue
        symbol, tf = stem.rsplit("_", 1)
        tf = tf.lower()
        symbol_key = symbol.upper()
        datasets.setdefault(symbol_key, {})[tf] = path
    return datasets


def heikin_ashi_hint(bars: List[OHLCVBar]) -> Optional[Tuple[float, float, float]]:
    if len(bars) < 5:
        return None
    recent = bars[-20:]
    closes = [b.close for b in recent]
    opens = [b.open for b in recent]
    slope = closes[-1] - closes[0]
    body = mean(abs(c - o) for c, o in zip(closes, opens))
    return slope, body, mean(b.volume for b in recent)


class DemoApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("FinChart Demo GUI")
        self.geometry("1600x920")
        self.minsize(1200, 720)
        self.configure(bg="#ffffff")

        self.datasets = discover_datasets()
        if not self.datasets:
            raise RuntimeError("No CSV datasets found in ./data")

        self.symbol_var = tk.StringVar(value=sorted(self.datasets.keys())[0])
        self.timeframe_var = tk.StringVar(value=self._default_timeframe(self.symbol_var.get()))
        self.status_var = tk.StringVar(value="")

        self.chart = Chart(symbol=self.symbol_var.get(), interval=self.timeframe_var.get().upper(), options={"dimensions": {"width": 1200.0, "height": 700.0}})
        self.datasets_cache: Dict[Tuple[str, str], ChartDataset] = {}
        self.ma_cache: Dict[Tuple[str, str], List[float]] = {}
        self._crosshair_pos: Optional[Tuple[int, int]] = None
        self._active_pointer_id = 1

        # Tool mode state
        self._active_tool: Optional[str] = None
        self._tool_first_click: Optional[Tuple[float, float]] = None
        self._tool_ghost_drawing: Optional[Any] = None

        self._build_ui()
        self._bind_events()
        self.load_selection()

    def _default_timeframe(self, symbol: str) -> str:
        available = self.datasets.get(symbol, {})
        for tf in TIMEFRAME_ORDER:
            if tf in available:
                return tf
        return next(iter(available.keys()))

    def _build_ui(self) -> None:
        self.toolbar = tk.Frame(self, bg="#f7f7f7", height=56, bd=0, highlightthickness=1, highlightbackground="#e5e5e5")
        self.toolbar.pack(side=tk.TOP, fill=tk.X)

        brand = tk.Label(self.toolbar, text="FinChart", bg="#f7f7f7", fg="#111111", font=("Segoe UI", 14, "bold"))
        brand.pack(side=tk.LEFT, padx=(16, 10))

        ttk.Label(self.toolbar, text="Symbol").pack(side=tk.LEFT, padx=(16, 4))
        self.symbol_combo = ttk.Combobox(self.toolbar, textvariable=self.symbol_var, values=sorted(self.datasets.keys()), width=16, state="readonly")
        self.symbol_combo.pack(side=tk.LEFT)
        self.symbol_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_symbol_changed())

        for tf in TIMEFRAME_ORDER:
            btn = tk.Button(
                self.toolbar,
                text=TIMEFRAME_LABELS[tf],
                command=lambda t=tf: self.set_timeframe(t),
                relief=tk.FLAT,
                bg="#ececec",
                fg="#111111",
                activebackground="#d8d8d8",
                padx=12,
                pady=4,
            )
            btn.pack(side=tk.LEFT, padx=4)

        self.indicator_var = tk.BooleanVar(value=True)
        self.indicator_check = ttk.Checkbutton(self.toolbar, text="MA20", variable=self.indicator_var, command=self.redraw)
        self.indicator_check.pack(side=tk.LEFT, padx=(18, 6))

        self.auto_scale_var = tk.BooleanVar(value=True)
        self.auto_scale_check = ttk.Checkbutton(self.toolbar, text="Auto-scale", variable=self.auto_scale_var, command=self.redraw)
        self.auto_scale_check.pack(side=tk.LEFT, padx=6)

        self.save_btn = tk.Button(self.toolbar, text="Save Session", command=self.save_session_to_file, relief=tk.FLAT, bg="#ececec", padx=10, pady=4)
        self.save_btn.pack(side=tk.LEFT, padx=6)
        self.load_btn = tk.Button(self.toolbar, text="Load Session", command=self.load_session_from_file, relief=tk.FLAT, bg="#ececec", padx=10, pady=4)
        self.load_btn.pack(side=tk.LEFT, padx=6)

        self.draw_line_btn = tk.Button(self.toolbar, text="Trend Line", command=lambda: self._toggle_tool("trend_line"), relief=tk.FLAT, bg="#ececec", padx=10, pady=4)
        self.draw_line_btn.pack(side=tk.LEFT, padx=(18, 6))
        self.draw_box_btn = tk.Button(self.toolbar, text="Range Box", command=lambda: self._toggle_tool("range_box"), relief=tk.FLAT, bg="#ececec", padx=10, pady=4)
        self.draw_box_btn.pack(side=tk.LEFT, padx=6)
        self.clear_drawings_btn = tk.Button(self.toolbar, text="Clear Drawings", command=self.clear_drawings, relief=tk.FLAT, bg="#ececec", padx=10, pady=4)
        self.clear_drawings_btn.pack(side=tk.LEFT, padx=6)

        self.toolbar_spacer = tk.Frame(self.toolbar, bg="#f7f7f7")
        self.toolbar_spacer.pack(side=tk.LEFT, expand=True, fill=tk.X)

        self.canvas_frame = tk.Frame(self, bg="#ffffff")
        self.canvas_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(self.canvas_frame, bg="#ffffff", highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas.configure(takefocus=1, cursor="crosshair")

        self.right_panel = tk.Frame(self.canvas_frame, bg="#fafafa", width=220)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.Y)

        self.status = tk.Label(self.right_panel, textvariable=self.status_var, justify=tk.LEFT, anchor="nw", bg="#fafafa", fg="#222222", font=("Segoe UI", 10))
        self.status.pack(side=tk.TOP, fill=tk.X, padx=12, pady=12)

        self.help_text = tk.Label(
            self.right_panel,
            text="Mouse wheel pans.\nCtrl + wheel zooms.\nDrag inside chart to pan.\nSwitch symbol/timeframe from the toolbar.",
            justify=tk.LEFT,
            anchor="nw",
            bg="#fafafa",
            fg="#555555",
            font=("Segoe UI", 9),
        )
        self.help_text.pack(side=tk.TOP, fill=tk.X, padx=12, pady=(0, 12))

    def _bind_events(self) -> None:
        self.canvas.bind("<Configure>", lambda _e: self.redraw())
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Button-4>", self._on_mousewheel_linux)
        self.canvas.bind("<Button-5>", self._on_mousewheel_linux)
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Enter>", lambda _e: self.canvas.focus_set())
        self.canvas.bind("<Leave>", lambda _e: self._set_crosshair(None))
        self.bind_all("<KeyPress>", self._on_keypress)
        self.canvas.bind("<Alt-r>", lambda _e: self.reset_view_to_latest())
        self.canvas.bind("<Alt-R>", lambda _e: self.reset_view_to_latest())
        self.canvas.bind("<Escape>", lambda _e: self._cancel_tool())
        self.canvas.bind("<Button-3>", lambda _e: self._cancel_tool())

        self._drag_origin: Optional[Tuple[int, int]] = None
        self._dragging = False

    def _load_dataset(self, symbol: str, timeframe: str) -> ChartDataset:
        key = (symbol, timeframe)
        if key in self.datasets_cache:
            return self.datasets_cache[key]
        path = self.datasets[symbol][timeframe]
        dataset = ChartDataset(symbol=symbol, timeframe=timeframe, bars=load_csv_bars(path))
        self.datasets_cache[key] = dataset
        return dataset

    def load_selection(self) -> None:
        symbol = self.symbol_var.get().upper()
        timeframe = self.timeframe_var.get().lower()
        if symbol not in self.datasets:
            symbol = sorted(self.datasets.keys())[0]
            self.symbol_var.set(symbol)
        if timeframe not in self.datasets.get(symbol, {}):
            timeframe = self._default_timeframe(symbol)
            self.timeframe_var.set(timeframe)

        dataset = self._load_dataset(symbol, timeframe)
        self.chart = Chart(symbol=symbol, interval=timeframe.upper(), options={"dimensions": {"width": float(max(1, self.canvas.winfo_width())), "height": float(max(1, self.canvas.winfo_height()))}})
        self.chart.set_data(dataset.bars)
        if self.auto_scale_var.get():
            self.chart.autoscale_price("pane_main")

        hint = heikin_ashi_hint(dataset.bars)
        last = dataset.bars[-1] if dataset.bars else None
        if last:
            self.status_var.set(
                f"{symbol} {timeframe.upper()}\n"
                f"Bars: {len(dataset.bars)}\n"
                f"Last: O {last.open:.2f} H {last.high:.2f} L {last.low:.2f} C {last.close:.2f}\n"
                + (f"Trend hint: slope {hint[0]:.2f}, avg body {hint[1]:.2f}\n" if hint else "")
                + f"Volume: {last.volume:.0f}"
            )
        self.redraw()

    def set_timeframe(self, timeframe: str) -> None:
        self.timeframe_var.set(timeframe)
        self.load_selection()

    def _on_symbol_changed(self) -> None:
        self.timeframe_var.set(self._default_timeframe(self.symbol_var.get().upper()))
        self.load_selection()

    def _on_press(self, event: tk.Event) -> None:
        if self._active_tool:
            self._handle_tool_click(event)
            return
        self._drag_origin = (event.x, event.y)
        self._dragging = False
        chart_x, chart_y = self._chart_local_event_xy(event)
        self.chart.input_engine.on_pointer_down(screen_x=chart_x, screen_y=chart_y, pointer_id=self._active_pointer_id)

    def _on_drag(self, event: tk.Event) -> None:
        if self._active_tool and self._tool_first_click:
            self._update_tool_ghost(event)
            return
        if self._drag_origin is None:
            return
        dx = event.x - self._drag_origin[0]
        dy = event.y - self._drag_origin[1]
        if not self._dragging and math.hypot(dx, dy) > 4:
            self._dragging = True
        if self._dragging:
            chart_x, chart_y = self._chart_local_event_xy(event)
            self.chart.input_engine.on_pointer_move(
                screen_x=chart_x,
                screen_y=chart_y,
                buttons_down=1,
                pointer_id=self._active_pointer_id,
            )
            self.chart.time_scale.visible_start = self.chart.viewport.visible_start
            self.chart.time_scale.visible_end = self.chart.viewport.visible_end
            self.chart.viewport.follow_latest = False
            self._crosshair_pos = (event.x, event.y)
            self.redraw()
            self._drag_origin = (event.x, event.y)

    def _on_release(self, _event: tk.Event) -> None:
        chart_x, chart_y = self._chart_local_event_xy(_event)
        self.chart.input_engine.on_pointer_up(screen_x=chart_x, screen_y=chart_y, pointer_id=self._active_pointer_id)
        self._drag_origin = None
        self._dragging = False
        self.redraw()

    def _on_motion(self, event: tk.Event) -> None:
        self._crosshair_pos = (event.x, event.y)
        chart_x, chart_y = self._chart_local_event_xy(event)
        self.chart.input_engine.on_pointer_move(screen_x=chart_x, screen_y=chart_y, buttons_down=0, pointer_id=self._active_pointer_id)
        self.redraw()

    def _set_crosshair(self, pos: Optional[Tuple[int, int]]) -> None:
        self._crosshair_pos = pos
        self.redraw()

    def _on_mousewheel(self, event: tk.Event) -> None:
        chart_x, chart_y = self._chart_local_event_xy(event)
        self._handle_wheel_delta(float(event.delta), chart_x, chart_y, self._modifier_state(event))

    def _on_mousewheel_linux(self, event: tk.Event) -> None:
        delta = 120.0 if getattr(event, "num", 0) == 4 else -120.0
        chart_x, chart_y = self._chart_local_event_xy(event)
        self._handle_wheel_delta(delta, chart_x, chart_y, self._modifier_state(event))

    def _handle_wheel_delta(self, wheel_delta: float, chart_x: float, chart_y: float, modifiers: ModifierState) -> None:
        if modifiers.ctrl or modifiers.meta:
            self.chart.input_engine.on_wheel(
                delta_x=0.0,
                delta_y=-wheel_delta,
                screen_x=chart_x,
                screen_y=chart_y,
                modifiers=modifiers,
            )
        else:
            self._pan_by_wheel(wheel_delta)
        self.chart.time_scale.visible_start = self.chart.viewport.visible_start
        self.chart.time_scale.visible_end = self.chart.viewport.visible_end
        self.chart.viewport.follow_latest = False
        self.redraw()

    def _chart_local_event_xy(self, event: tk.Event) -> Tuple[float, float]:
        left, top, _right, _bottom = self._chart_rect()
        return float(event.x - left), float(event.y - top)

    def _pan_by_wheel(self, wheel_delta: float) -> None:
        bars_per_notch = max(3.0, min(24.0, 72.0 / max(1.0, self.chart.time_scale.bar_spacing)))
        delta_bars = -(wheel_delta / 120.0) * bars_per_notch
        self.chart.viewport.visible_start += delta_bars
        self.chart.viewport.visible_end += delta_bars
        self.chart.time_scale.visible_start = self.chart.viewport.visible_start
        self.chart.time_scale.visible_end = self.chart.viewport.visible_end

    def _on_keypress(self, event: tk.Event) -> None:
        key = getattr(event, "keysym", "") or getattr(event, "char", "")
        state = getattr(event, "state", 0)
        ctrl = bool(state & 0x0004)
        shift = bool(state & 0x0001)
        modifiers = ModifierState(shift=shift, ctrl=ctrl, meta=ctrl)
        if ctrl and key.lower() == "s":
            self.save_session_to_file()
            return
        if ctrl and key.lower() == "z":
            if shift:
                self.chart.redo()
            else:
                self.chart.undo()
            self.redraw()
            return
        if self._is_alt_pressed(state) and key.lower() == "r":
            self.reset_view_to_latest()
            return
        if key in ("Left", "Right"):
            delta = -5.0 if key == "Left" else 5.0
            self.chart.time_scale.zoom_at(self.canvas.winfo_width() // 2, delta / 10.0)
            self.redraw()
            return
        if key in ("Delete", "BackSpace"):
            self.clear_drawings()
            return
        self.chart.input_engine.on_key(KeyboardEventType.KEY_DOWN, key=key, modifiers=modifiers)

    def _modifier_state(self, event: tk.Event) -> ModifierState:
        state = getattr(event, "state", 0)
        return ModifierState(
            shift=bool(state & 0x0001),
            ctrl=bool(state & 0x0004),
            alt=self._is_alt_pressed(state),
            meta=bool(state & 0x0004),
        )

    def _is_alt_pressed(self, state: int) -> bool:
        return bool(state & 0x0008 or state & 0x0080 or state & 0x20000)

    def _chart_rect(self) -> Tuple[int, int, int, int]:
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        left = 24
        right = 96
        top = 12
        bottom = 96
        return left, top, width - right, height - bottom

    def _price_area(self, top: int, bottom: int) -> Tuple[int, int]:
        chart_h = max(1, bottom - top)
        volume_h = int(chart_h * 0.18)
        price_top = top + 4
        price_bottom = bottom - volume_h - 8
        return price_top, max(price_top + 1, price_bottom)

    def redraw(self) -> None:
        self.canvas.delete("all")
        if not self.chart:
            return
        bars = self._current_bars()
        if not bars:
            return

        left, top, right, bottom = self._chart_rect()
        chart_w = max(1, right - left)
        chart_h = max(1, bottom - top)
        price_top, price_bottom = self._price_area(top, bottom)
        price_scale = self.chart.price_scales["pane_main"]
        price_scale.pane_height = max(1, price_bottom - price_top)
        self.chart.time_scale.width = chart_w
        self.chart.resize(float(chart_w), float(chart_h + 30))
        price_scale.pane_height = max(1, price_bottom - price_top)
        visible_bars = self._visible_bars(bars)
        if self.auto_scale_var.get():
            price_scale.set_range_from_bars(visible_bars or bars)
            self.chart.viewport.set_pane_price_range("pane_main", price_scale.price_min, price_scale.price_max)

        # main grid
        self._draw_background(left, top, right, bottom)
        self._draw_volume(bars, left, top, right, bottom)
        self._draw_candles(bars, left, top, right, bottom, price_scale)
        self._draw_axes(left, top, right, bottom, price_scale)
        self._draw_header(left, top, bars, price_scale)
        self._draw_crosshair(left, top, right, bottom)
        self._draw_drawings(left, top, right, bottom, price_scale)

    def _current_bars(self) -> List[OHLCVBar]:
        symbol = self.symbol_var.get().upper()
        timeframe = self.timeframe_var.get().lower()
        return self._load_dataset(symbol, timeframe).bars

    def _visible_bars(self, bars: List[OHLCVBar], overscan: int = 2) -> List[OHLCVBar]:
        start = max(0, int(math.floor(self.chart.viewport.visible_start)) - overscan)
        end = min(len(bars), int(math.ceil(self.chart.viewport.visible_end)) + overscan)
        if end <= start:
            return []
        return bars[start:end]

    def _draw_background(self, left: int, top: int, right: int, bottom: int) -> None:
        self.canvas.create_rectangle(left, top, right, bottom, fill="#ffffff", outline="#f0f0f0")
        for i in range(0, 10):
            x = left + (right - left) * i / 9
            self.canvas.create_line(x, top, x, bottom, fill="#f3f3f3")
        for i in range(0, 8):
            y = top + (bottom - top) * i / 7
            self.canvas.create_line(left, y, right, y, fill="#f3f3f3")

    def _draw_header(self, left: int, top: int, bars: List[OHLCVBar], price_scale: PriceScale) -> None:
        last = bars[-1]
        prev = bars[-2] if len(bars) > 1 else last
        change = last.close - prev.close
        change_pct = (change / prev.close * 100.0) if prev.close else 0.0
        header = f"{self.symbol_var.get().upper()}  •  {self.timeframe_var.get().upper()}  •  O {last.open:.2f}  H {last.high:.2f}  L {last.low:.2f}  C {last.close:.2f}  {change:+.2f} ({change_pct:+.2f}%)"
        self.canvas.create_text(left + 6, top + 10, text=header, anchor="nw", fill="#0a6f5b", font=("Segoe UI", 11, "bold"))

    def _draw_axes(self, left: int, top: int, right: int, bottom: int, price_scale: PriceScale) -> None:
        price_ticks = 8
        for i in range(price_ticks + 1):
            price_top, price_bottom = self._price_area(top, bottom)
            y = price_top + (price_bottom - price_top) * i / price_ticks
            price = price_scale.y_to_price(y - price_top)
            self.canvas.create_text(right + 8, y, text=f"{price:,.1f}", anchor="w", fill="#444444", font=("Segoe UI", 9))

        bars = self._current_bars()
        if not bars:
            return
        visible_start = max(0, int(math.floor(self.chart.viewport.visible_start)))
        visible_end = min(len(bars) - 1, int(math.ceil(self.chart.viewport.visible_end)))
        visible_count = max(1, visible_end - visible_start + 1)
        step = max(1, visible_count // 6)
        for idx in range(visible_start, visible_end + 1, step):
            x = left + self.chart.time_scale.index_to_x(float(idx))
            if x < left - 20 or x > right + 20:
                continue
            label = str(int(bars[idx].timestamp))
            self.canvas.create_text(x, bottom + 8, text=label, anchor="n", fill="#555555", font=("Segoe UI", 8))

    def _draw_volume(self, bars: List[OHLCVBar], left: int, top: int, right: int, bottom: int) -> None:
        vol_h = int((bottom - top) * 0.18)
        vol_top = bottom - vol_h
        visible = self._visible_bars(bars)
        max_vol = max((b.volume for b in visible), default=1.0)
        for idx, bar in self._visible_bar_items(bars):
            x0, x1, _ = self._bar_bounds(idx, left, right)
            h = 0.0 if max_vol <= 0 else (bar.volume / max_vol) * (vol_h - 4)
            y0 = bottom - h
            color = "#13bfa5" if bar.close >= bar.open else "#ff5b5b"
            self.canvas.create_rectangle(x0, y0, x1, bottom, fill=color, outline="")
        self.canvas.create_line(left, vol_top, right, vol_top, fill="#dddddd")

    def _draw_candles(self, bars: List[OHLCVBar], left: int, top: int, right: int, bottom: int, price_scale: PriceScale) -> None:
        candle_top, _candle_bottom = self._price_area(top, bottom)
        for idx, bar in self._visible_bar_items(bars):
            x0, x1, xc = self._bar_bounds(idx, left, right)
            body_w = max(1.0, (x1 - x0) * 0.7)
            open_y = candle_top + price_scale.price_to_y(bar.open)
            close_y = candle_top + price_scale.price_to_y(bar.close)
            high_y = candle_top + price_scale.price_to_y(bar.high)
            low_y = candle_top + price_scale.price_to_y(bar.low)
            up = bar.close >= bar.open
            color = "#13bfa5" if up else "#ff5b5b"
            self.canvas.create_line(xc, high_y, xc, low_y, fill=color, width=1)
            self.canvas.create_rectangle(xc - body_w / 2, open_y, xc + body_w / 2, close_y, fill=color, outline=color)

        if self.indicator_var.get() and len(bars) >= 5:
            ma = self._moving_average_values(bars)
            points = []
            for idx, bar in self._visible_bar_items(bars):
                value = ma[idx]
                _, _, xc = self._bar_bounds(idx, left, right)
                y = candle_top + price_scale.price_to_y(value)
                points.extend([xc, y])
            if len(points) >= 4:
                self.canvas.create_line(*points, fill="#3b6cff", width=2, smooth=True)

        # current price marker
        last = bars[-1]
        y = candle_top + price_scale.price_to_y(last.close)
        self.canvas.create_line(left, y, right, y, fill="#37b8d7", dash=(2, 3))
        self.canvas.create_rectangle(right + 4, y - 14, right + 72, y + 14, fill="#10a37f", outline="")
        self.canvas.create_text(right + 38, y, text=f"{last.close:,.1f}", fill="white", font=("Segoe UI", 10, "bold"))

    def _visible_bar_items(self, bars: List[OHLCVBar]):
        start = max(0, int(math.floor(self.chart.viewport.visible_start)) - 2)
        end = min(len(bars), int(math.ceil(self.chart.viewport.visible_end)) + 2)
        for idx in range(start, end):
            yield idx, bars[idx]

    def _bar_bounds(self, idx: int, left: int, right: int) -> Tuple[float, float, float]:
        x = left + self.chart.time_scale.index_to_x(float(idx))
        bar_w = max(1.0, min(18.0, self.chart.time_scale.bar_spacing * 0.7))
        return x - bar_w / 2, x + bar_w / 2, x

    def _moving_average_values(self, bars: List[OHLCVBar], length: int = 20) -> List[float]:
        key = (self.symbol_var.get().upper(), self.timeframe_var.get().lower())
        cached = self.ma_cache.get(key)
        if cached is not None and len(cached) == len(bars):
            return cached

        values: List[float] = []
        rolling_sum = 0.0
        closes = [bar.close for bar in bars]
        for idx, close in enumerate(closes):
            rolling_sum += close
            if idx >= length:
                rolling_sum -= closes[idx - length]
            count = min(idx + 1, length)
            values.append(rolling_sum / count)
        self.ma_cache[key] = values
        return values

    def _draw_crosshair(self, left: int, top: int, right: int, bottom: int) -> None:
        if not self._crosshair_pos:
            return
        x, y = self._crosshair_pos
        if x < left or x > right or y < top or y > bottom:
            return
        self.canvas.create_line(left, y, right, y, fill="#7a7a7a", dash=(2, 4))
        self.canvas.create_line(x, top, x, bottom, fill="#7a7a7a", dash=(2, 4))

        bars = self._current_bars()
        if not bars:
            return
        idx = int(round(self.chart.time_scale.x_to_index(x - left)))
        idx = max(0, min(len(bars) - 1, idx))
        bar = bars[idx]
        price_scale = self.chart.price_scales["pane_main"]
        price_top, price_bottom = self._price_area(top, bottom)
        price_scale.pane_height = max(1, price_bottom - price_top)
        price = price_scale.y_to_price(y - price_top)
        label = f"Bar {idx}  O {bar.open:.2f}  H {bar.high:.2f}  L {bar.low:.2f}  C {bar.close:.2f}  Y {price:.2f}"
        self.canvas.create_rectangle(left + 10, bottom + 4, left + 520, bottom + 28, fill="#111111", outline="")
        self.canvas.create_text(left + 16, bottom + 16, text=label, anchor="w", fill="white", font=("Segoe UI", 9))

    def _draw_drawings(self, left: int, top: int, right: int, bottom: int, price_scale: PriceScale) -> None:
        for drawing in self.chart.get_drawings():
            pts = []
            for p in drawing.points:
                if "time" in p and "price" in p:
                    idx = float(p["time"])
                    x = self.chart.time_scale.index_to_x(idx) + left
                    price_top, _price_bottom = self._price_area(top, bottom)
                    y = price_top + price_scale.price_to_y(float(p["price"]))
                    pts.append((x, y))
                elif "logical_index" in p and "price" in p:
                    x = self.chart.time_scale.index_to_x(float(p["logical_index"])) + left
                    price_top, _price_bottom = self._price_area(top, bottom)
                    y = price_top + price_scale.price_to_y(float(p["price"]))
                    pts.append((x, y))
            if not pts:
                continue
            style = drawing.properties if hasattr(drawing, "properties") else {}
            fill = style.get("color", "#2f6cff")
            width = int(style.get("width", 2))
            is_ghost = getattr(drawing, "properties", {}).get("ghost", False)
            if len(pts) == 1:
                x, y = pts[0]
                self.canvas.create_oval(x - 4, y - 4, x + 4, y + 4, outline=fill, width=2)
            elif drawing.shape_type in ("rectangle", "range_box") and len(pts) >= 4:
                flat = [coord for pt in pts for coord in pt]
                fill_color = self._blend_fill(fill) if not is_ghost else ""
                if is_ghost:
                    self.canvas.create_polygon(*flat, outline=fill, fill=fill_color, width=width, dash=(4, 4))
                else:
                    self.canvas.create_polygon(*flat, outline=fill, fill=fill_color, width=width)
                # Only draw endpoint markers when ghost (drawing in progress) or when selected
                is_selected = getattr(drawing, "properties", {}).get("selected", False)
                if is_ghost or is_selected:
                    for x, y in pts:
                        self.canvas.create_oval(x - 4, y - 4, x + 4, y + 4, outline=fill, width=2)
            else:
                # Only draw endpoint markers when ghost (drawing in progress) or when selected
                is_selected = getattr(drawing, "properties", {}).get("selected", False)
                flat = [coord for pt in pts for coord in pt]
                if is_ghost or is_selected:
                    self.canvas.create_line(*flat, fill=fill, width=width)
                    for x, y in pts:
                        self.canvas.create_oval(x - 4, y - 4, x + 4, y + 4, outline=fill, width=2)
                else:
                    self.canvas.create_line(*flat, fill=fill, width=width)
                # Endpoint markers hidden when not ghost and not selected

        # Draw tool ghost preview if active
        if self._active_tool and self._tool_first_click and self._crosshair_pos:
            price_scale = self.chart.price_scales["pane_main"]
            price_top, _price_bottom = self._price_area(top, bottom)
            cx, cy = self._crosshair_pos
            if left <= cx <= right and top <= cy <= bottom:
                x1 = left + self.chart.time_scale.index_to_x(self._tool_first_click[0])
                y1 = price_top + price_scale.price_to_y(self._tool_first_click[1])
                x2 = cx
                y2 = cy
                fill = "#2f6cff"
                width = 2
                if self._active_tool == "trend_line":
                    self.canvas.create_line(x1, y1, x2, y2, fill=fill, width=width, dash=(4, 4))
                elif self._active_tool == "range_box":
                    coords = [x1, y1, x2, y1, x2, y2, x1, y2]
                    fill_color = self._blend_fill(fill)
                    self.canvas.create_polygon(*coords, outline=fill, fill=fill_color, width=width, dash=(4, 4))
                self.canvas.create_oval(x1 - 4, y1 - 4, x1 + 4, y1 + 4, outline=fill, width=2)

    def _toggle_tool(self, tool_type: str) -> None:
        if self._active_tool == tool_type:
            self._cancel_tool()
            return
        self._cancel_tool()
        self._active_tool = tool_type
        self._tool_first_click = None
        self._update_tool_button_styles()
        self.status_var.set(self.status_var.get() + f"\nTool: {tool_type.replace('_', ' ').title()} (click two points, Esc to cancel)")

    def _cancel_tool(self) -> None:
        if self._tool_ghost_drawing:
            try:
                self.chart.remove_drawing(self._tool_ghost_drawing.drawing_id)
            except Exception:
                pass
        self._active_tool = None
        self._tool_first_click = None
        self._tool_ghost_drawing = None
        self._update_tool_button_styles()
        self.redraw()

    def _blend_fill(self, hex_color: str) -> str:
        h = hex_color.lstrip("#")
        if len(h) == 6:
            r, g, b = (int(h[i:i+2], 16) for i in (0, 2, 4))
            return f"#{int(r*0.3 + 255*0.7):02x}{int(g*0.3 + 255*0.7):02x}{int(b*0.3 + 255*0.7):02x}"
        return hex_color

    def _update_tool_button_styles(self) -> None:
        line_bg = "#d8d8d8" if self._active_tool == "trend_line" else "#ececec"
        box_bg = "#d8d8d8" if self._active_tool == "range_box" else "#ececec"
        self.draw_line_btn.configure(bg=line_bg)
        self.draw_box_btn.configure(bg=box_bg)

    def _handle_tool_click(self, event: tk.Event) -> None:
        chart_x, chart_y = self._chart_local_event_xy(event)
        idx = self.chart.time_scale.x_to_index(chart_x)
        # Convert chart-local Y to pane-local Y before price conversion.
        # chart_y is relative to chart area top; price_top is in canvas coords.
        left, top, _right, _bottom = self._chart_rect()
        price_top, _price_bottom = self._price_area(top, _bottom)
        pane_local_y = chart_y + top - price_top
        price = self.chart.price_scales["pane_main"].y_to_price(pane_local_y)
        point = {"logical_index": float(idx), "price": float(price)}

        if self._tool_first_click is None:
            self._tool_first_click = (float(idx), float(price))
        else:
            if self._active_tool == "trend_line":
                p1 = {"logical_index": self._tool_first_click[0], "price": self._tool_first_click[1]}
                p2 = point
                drawing = self.chart.create_multipoint_shape([p1, p2], shape_type="trend_line")
            else:
                left_idx = min(self._tool_first_click[0], float(idx))
                right_idx = max(self._tool_first_click[0], float(idx))
                low = min(self._tool_first_click[1], float(price))
                high = max(self._tool_first_click[1], float(price))
                drawing = self.chart.create_multipoint_shape(
                    [
                        {"logical_index": left_idx, "price": low},
                        {"logical_index": right_idx, "price": low},
                        {"logical_index": right_idx, "price": high},
                        {"logical_index": left_idx, "price": high},
                    ],
                    shape_type="rectangle",
                )
            drawing.set_properties({"color": "#2f6cff", "width": 2})
            self._cancel_tool()
            self.redraw()

    def _update_tool_ghost(self, event: tk.Event) -> None:
        # Ghost preview is drawn directly in _draw_drawings using _tool_first_click and _crosshair_pos
        self._crosshair_pos = (event.x, event.y)
        self.redraw()

    def add_trend_line_demo(self) -> None:
        bars = self._current_bars()
        if len(bars) < 20:
            return
        start_idx, end_idx = self._visible_anchor_indices(len(bars), 0.25, 0.75)
        p1 = {"logical_index": float(start_idx), "price": float(bars[start_idx].close)}
        p2 = {"logical_index": float(end_idx), "price": float(bars[end_idx].close)}
        drawing = self.chart.create_multipoint_shape([p1, p2], shape_type="trend_line")
        drawing.set_properties({"color": "#2f6cff", "width": 2})
        self.chart.select(drawing.drawing_id)
        self.redraw()

    def reset_view_to_latest(self) -> None:
        bars = self._current_bars()
        if not bars:
            return

        left, top, right, bottom = self._chart_rect()
        chart_w = max(1.0, float(right - left))
        data_count = len(bars)
        right_offset = RESET_VIEW_RIGHT_OFFSET_BARS
        visible_start = max(0.0, float(data_count - RESET_VIEW_MAX_BARS))
        visible_end = float(max(0, data_count - 1)) + right_offset
        bar_spacing = chart_w / max(1.0, visible_end - visible_start)

        self.chart.time_scale.set_bar_spacing(bar_spacing)
        self.chart.viewport.bar_spacing = self.chart.time_scale.bar_spacing
        self.chart.viewport.right_offset = right_offset
        self.chart.time_scale.right_offset = right_offset
        self.chart.viewport.visible_start = visible_start
        self.chart.viewport.visible_end = visible_end
        self.chart.time_scale.visible_start = visible_start
        self.chart.time_scale.visible_end = visible_end
        self.chart.viewport.follow_latest = True

        price_top, price_bottom = self._price_area(top, bottom)
        price_scale = self.chart.price_scales["pane_main"]
        price_scale.pane_height = max(1, price_bottom - price_top)
        price_scale.set_range_from_bars(bars[int(visible_start):data_count], padding_factor=0.08)
        self.chart.viewport.set_pane_price_range("pane_main", price_scale.price_min, price_scale.price_max)
        self.redraw()

    def add_range_box_demo(self) -> None:
        bars = self._current_bars()
        if len(bars) < 20:
            return
        left_idx, right_idx = self._visible_anchor_indices(len(bars), 0.35, 0.65)
        box_bars = bars[left_idx:right_idx + 1]
        low = min(b.low for b in box_bars)
        high = max(b.high for b in box_bars)
        drawing = self.chart.create_multipoint_shape(
            [
                {"logical_index": float(left_idx), "price": low},
                {"logical_index": float(right_idx), "price": low},
                {"logical_index": float(right_idx), "price": high},
                {"logical_index": float(left_idx), "price": high},
            ],
            shape_type="rectangle",
        )
        drawing.set_properties({"color": "#ef476f", "width": 2})
        self.redraw()

    def _visible_anchor_indices(self, data_count: int, left_ratio: float, right_ratio: float) -> Tuple[int, int]:
        visible_start = max(0.0, self.chart.viewport.visible_start)
        visible_end = min(float(data_count - 1), self.chart.viewport.visible_end)
        if visible_end <= visible_start:
            visible_start = max(0.0, float(data_count - 40))
            visible_end = float(data_count - 1)
        span = max(1.0, visible_end - visible_start)
        left_idx = int(round(visible_start + span * left_ratio))
        right_idx = int(round(visible_start + span * right_ratio))
        left_idx = max(0, min(data_count - 2, left_idx))
        right_idx = max(left_idx + 1, min(data_count - 1, right_idx))
        return left_idx, right_idx

    def clear_drawings(self) -> None:
        for drawing in list(self.chart.get_drawings()):
            self.chart.remove_drawing(drawing.drawing_id)
        self.redraw()

    def save_session_to_file(self) -> None:
        path = ROOT / "demo_session.json"
        payload = self.chart.save_session()
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.status_var.set(self.status_var.get() + f"\nSaved session: {path.name}")

    def load_session_from_file(self) -> None:
        path = ROOT / "demo_session.json"
        if not path.exists():
            self.status_var.set(self.status_var.get() + "\nNo demo_session.json found")
            return
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.chart.load_session(payload)
        self.redraw()
        self.status_var.set(self.status_var.get() + f"\nLoaded session: {path.name}")


def main() -> None:
    app = DemoApp()
    app.mainloop()


if __name__ == "__main__":
    main()
