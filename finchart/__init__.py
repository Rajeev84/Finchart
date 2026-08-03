"""FinChart - Professional Pure-Python Financial Charting Library.

A TradingView-class charting library implemented entirely in Tkinter Canvas.

Usage:
    import tkinter as tk
    from finchart import ChartWidget, OHLCV
    from finchart.session.manager import SessionManager
    from finchart.indicators import SMA, EMA, RSI

    root = tk.Tk()
    chart = ChartWidget(root, width=1200, height=700)
    chart.pack(fill="both", expand=True)
    
    # Use SessionManager for indicator management
    session_manager = SessionManager()
    chart.set_session_manager(session_manager)
    
    # Set data and context
    session_manager.set_context("AAPL", "1m", bars)
    
    # Add indicators via SessionManager
    session_manager.add_indicator_config("SMA", {"period": 20}, "candlestick")
    chart.refresh()
    
    root.mainloop()
"""
from __future__ import annotations

__version__ = "0.2.0"
__author__ = "FinChart Engineering"

# Public API surface
from .api.widget import ChartWidget
from .core.types import OHLCV, Color, Viewport, Point, Rect, ChartType
from .core.events import EventBus, EventType, Event
from .core.store import DataStore
from .coordinates.engine import CoordinateEngine, TimeScale, PriceScale
from .layout.engine import LayoutEngine
from .rendering.pipeline import RenderingPipeline, DrawCommand, Layer
from .themes.style import Theme, DarkTheme, LightTheme
from .session.manager import SessionManager, SessionState
from .indicators import (
    BaseIndicator,
    INDICATOR_REGISTRY,
    register_indicator,
    auto_discover,
    get_indicator,
    list_indicators,
    SMA,
    EMA,
    RSI,
    MACD,
    BollingerBands,
    Volume,
)

__all__ = [
    # Widget
    "ChartWidget",
    # Core Types
    "OHLCV",
    "Color",
    "Viewport",
    "Point",
    "Rect",
    "ChartType",
    # Events
    "EventBus",
    "EventType",
    "Event",
    # Data
    "DataStore",
    # Coordinates
    "CoordinateEngine",
    "TimeScale",
    "PriceScale",
    # Layout
    "LayoutEngine",
    # Rendering
    "RenderingPipeline",
    "DrawCommand",
    "Layer",
    # Themes
    "Theme",
    "DarkTheme",
    "LightTheme",
    # Session Management
    "SessionManager",
    "SessionState",
    # Indicators (New Plugin System)
    "BaseIndicator",
    "INDICATOR_REGISTRY",
    "register_indicator",
    "auto_discover",
    "get_indicator",
    "list_indicators",
    "SMA",
    "EMA",
    "RSI",
    "MACD",
    "BollingerBands",
    "Volume",
]
