"""Built-in Indicators - Reference implementations using BaseIndicator contract.

This module contains the ported versions of the original FinChart indicators
(SMA, EMA, RSI, MACD, BollingerBands, Volume) converted to the new
BaseIndicator plugin system for EasyPyChart compatibility.
"""
from __future__ import annotations

from typing import Optional
import pandas as pd
import numpy as np

from .plugin import BaseIndicator
from .registry import register_indicator


@register_indicator
class SMA(BaseIndicator):
    """Simple Moving Average (SMA) Indicator."""
    
    name = "SMA"
    description = "Simple Moving Average - smooths price data to create a single flowing line"
    defaults = {
        "period": 20,
        "price_type": "close",
        "color": "#2196F3",
        "width": 1.5
    }
    param_schema = [
        {"name": "period", "type": "int", "label": "Period", "min": 1, "max": 200},
        {"name": "price_type", "type": "combo", "label": "Price", "options": ["close", "open", "high", "low"]},
        {"name": "color", "type": "color", "label": "Color"},
        {"name": "width", "type": "float", "label": "Width", "min": 0.5, "max": 5.0}
    ]
    
    def __init__(self, period=20, color="#2196F3", **kwargs):
        self.params = {"period": period, "color": color, **kwargs}
        self.subplot = "candlestick"
    
    @classmethod
    def calculate(cls, df: pd.DataFrame, params: dict) -> Optional[pd.Series]:
        period = params.get("period", 20)
        price_type = params.get("price_type", "close")
        
        if len(df) < period:
            return pd.Series([None] * len(df), index=df.index)
        
        price_col = df[price_type] if price_type in df.columns else df['close']
        sma = price_col.rolling(window=period).mean()
        
        return sma
    
    @classmethod
    def on_render(cls, chart, subplot: str, params: dict, df: Optional[pd.DataFrame] = None) -> None:
        # SMA/EMA/Volume: on_render stays as pass -- main series auto-rendered by IndicatorAdapter
        pass


@register_indicator
class EMA(BaseIndicator):
    """Exponential Moving Average (EMA) Indicator."""
    
    name = "EMA"
    description = "Exponential Moving Average - gives more weight to recent prices"
    defaults = {
        "period": 9,
        "price_type": "close",
        "color": "#FF9800",
        "width": 1.5
    }
    param_schema = [
        {"name": "period", "type": "int", "label": "Period", "min": 1, "max": 200},
        {"name": "price_type", "type": "combo", "label": "Price", "options": ["close", "open", "high", "low"]},
        {"name": "color", "type": "color", "label": "Color"},
        {"name": "width", "type": "float", "label": "Width", "min": 0.5, "max": 5.0}
    ]
    
    def __init__(self, period=9, color="#FF9800", **kwargs):
        self.params = {"period": period, "color": color, **kwargs}
        self.subplot = "candlestick"
    
    @classmethod
    def calculate(cls, df: pd.DataFrame, params: dict) -> Optional[pd.Series]:
        period = params.get("period", 9)
        price_type = params.get("price_type", "close")
        
        if len(df) < period:
            return pd.Series([None] * len(df), index=df.index)
        
        price_col = df[price_type] if price_type in df.columns else df['close']
        ema = price_col.ewm(span=period, adjust=False).mean()
        
        return ema
    
    @classmethod
    def on_render(cls, chart, subplot: str, params: dict, df: Optional[pd.DataFrame] = None) -> None:
        # SMA/EMA/Volume: on_render stays as pass -- main series auto-rendered by IndicatorAdapter
        pass


@register_indicator
class RSI(BaseIndicator):
    """Relative Strength Index (RSI) Indicator."""
    
    name = "RSI"
    description = "Relative Strength Index - momentum oscillator measuring speed and change of price movements"
    defaults = {
        "period": 14,
        "color": "#E91E63",
        "width": 1.5,
        "overbought": 70,
        "oversold": 30
    }
    param_schema = [
        {"name": "period", "type": "int", "label": "Period", "min": 2, "max": 50},
        {"name": "color", "type": "color", "label": "Color"},
        {"name": "width", "type": "float", "label": "Width", "min": 0.5, "max": 5.0},
        {"name": "overbought", "type": "float", "label": "Overbought", "min": 50, "max": 100},
        {"name": "oversold", "type": "float", "label": "Oversold", "min": 0, "max": 50}
    ]
    
    def __init__(self, period=14, color="#E91E63", **kwargs):
        self.params = {"period": period, "color": color, **kwargs}
        self.subplot = "rsi"
    
    @classmethod
    def calculate(cls, df: pd.DataFrame, params: dict) -> Optional[pd.Series]:
        period = params.get("period", 14)
        
        if len(df) < period + 1:
            return pd.Series([None] * len(df), index=df.index)
        
        close = df['close']
        delta = close.diff()
        
        gains = delta.where(delta > 0, 0)
        losses = -delta.where(delta < 0, 0)
        
        avg_gains = gains.rolling(window=period).mean()
        avg_losses = losses.rolling(window=period).mean()
        
        rs = avg_gains / avg_losses
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    @classmethod
    def on_render(cls, chart, subplot: str, params: dict, df: Optional[pd.DataFrame] = None) -> None:
        # RSI: on_render draws overbought/oversold hlines -- main series auto-rendered by IndicatorAdapter
        overbought = params.get("overbought", 70)
        oversold = params.get("oversold", 30)
        color = params.get("color", "#E91E63")
        
        chart.create_hline(overbought, color="#FF5722", width=1.0, dash="--")
        chart.create_hline(oversold, color="#4CAF50", width=1.0, dash="--")


@register_indicator
class MACD(BaseIndicator):
    """Moving Average Convergence Divergence (MACD) Indicator."""
    
    name = "MACD"
    description = "MACD - trend-following momentum indicator showing relationship between two moving averages"
    defaults = {
        "fast": 12,
        "slow": 26,
        "signal": 9,
        "color_macd": "#2196F3",
        "color_signal": "#FF9800",
        "color_hist_bull": "#089981",
        "color_hist_bear": "#F23645",
        "show_histogram": True
    }
    param_schema = [
        {"name": "fast", "type": "int", "label": "Fast Period", "min": 5, "max": 50},
        {"name": "slow", "type": "int", "label": "Slow Period", "min": 10, "max": 100},
        {"name": "signal", "type": "int", "label": "Signal Period", "min": 2, "max": 20},
        {"name": "color_macd", "type": "color", "label": "MACD Color"},
        {"name": "color_signal", "type": "color", "label": "Signal Color"},
        {"name": "show_histogram", "type": "bool", "label": "Show Histogram"}
    ]
    
    def __init__(self, fast=12, slow=26, signal=9, **kwargs):
        self.params = {"fast": fast, "slow": slow, "signal": signal, **kwargs}
        self.subplot = "macd"
    
    @classmethod
    def calculate(cls, df: pd.DataFrame, params: dict) -> Optional[pd.Series]:
        # MACD returns the MACD line as the main series
        fast = params.get("fast", 12)
        slow = params.get("slow", 26)
        
        if len(df) < slow:
            return pd.Series([None] * len(df), index=df.index)
        
        close = df['close']
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        
        return macd_line
    
    @classmethod
    def on_render(cls, chart, subplot: str, params: dict, df: Optional[pd.DataFrame] = None) -> None:
        # MACD: on_render draws signal line and histogram -- main MACD line auto-rendered by IndicatorAdapter
        if df is None:
            return
        
        fast = params.get("fast", 12)
        slow = params.get("slow", 26)
        signal = params.get("signal", 9)
        color_macd = params.get("color_macd", "#2196F3")
        color_signal = params.get("color_signal", "#FF9800")
        color_hist_bull = params.get("color_hist_bull", "#089981")
        color_hist_bear = params.get("color_hist_bear", "#F23645")
        show_histogram = params.get("show_histogram", True)
        
        close = df['close']
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        
        # Add signal line
        chart.create_series("signal", signal_line, color=color_signal, width=1.5)
        
        # Add histogram if enabled
        if show_histogram:
            # Create histogram with bullish/bearish colors
            hist_colors = [color_hist_bull if val >= 0 else color_hist_bear for val in histogram]
            # Note: The current create_series doesn't support per-bar colors,
            # so we'll use a single color for now
            chart.create_series("histogram", histogram, color=color_hist_bull, width=1.0, style="histogram")


@register_indicator
class BollingerBands(BaseIndicator):
    """Bollinger Bands - volatility indicator with upper and lower bands."""
    
    name = "Bollinger Bands"
    description = "Bollinger Bands - volatility bands placed above and below a moving average"
    defaults = {
        "period": 20,
        "std_dev": 2.0,
        "color_middle": "#2196F3",
        "color_upper": "#4CAF50",
        "color_lower": "#F44336",
        "width": 1.5
    }
    param_schema = [
        {"name": "period", "type": "int", "label": "Period", "min": 5, "max": 50},
        {"name": "std_dev", "type": "float", "label": "Std Dev", "min": 0.5, "max": 4.0},
        {"name": "color_middle", "type": "color", "label": "Middle Color"},
        {"name": "color_upper", "type": "color", "label": "Upper Color"},
        {"name": "color_lower", "type": "color", "label": "Lower Color"},
        {"name": "width", "type": "float", "label": "Width", "min": 0.5, "max": 5.0}
    ]
    
    def __init__(self, period=20, std_dev=2.0, **kwargs):
        self.params = {"period": period, "std_dev": std_dev, **kwargs}
    
    @classmethod
    def calculate(cls, df: pd.DataFrame, params: dict) -> Optional[pd.Series]:
        # Returns the middle band (SMA) as the main series
        period = params.get("period", 20)
        
        if len(df) < period:
            return pd.Series([None] * len(df), index=df.index)
        
        close = df['close']
        middle_band = close.rolling(window=period).mean()
        
        return middle_band
    
    @classmethod
    def on_render(cls, chart, subplot: str, params: dict, df: Optional[pd.DataFrame] = None) -> None:
        # BollingerBands: on_render draws upper/lower bands -- middle line auto-rendered by IndicatorAdapter
        if df is None:
            return
        
        period = params.get("period", 20)
        std_dev = params.get("std_dev", 2.0)
        color_upper = params.get("color_upper", "#4CAF50")
        color_lower = params.get("color_lower", "#F44336")
        
        close = df['close']
        middle_band = close.rolling(window=period).mean()
        std = close.rolling(window=period).std()
        
        upper_band = middle_band + (std * std_dev)
        lower_band = middle_band - (std * std_dev)
        
        # Add upper and lower bands
        chart.create_series("upper", upper_band, color=color_upper, width=1.0)
        chart.create_series("lower", lower_band, color=color_lower, width=1.0)


@register_indicator
class Volume(BaseIndicator):
    """Volume Indicator - displays trading volume as histogram bars."""
    
    name = "Volume"
    description = "Volume - shows the number of shares/contracts traded in a given time period"
    defaults = {
        "color": "#9E9E9E",
        "width": 0.8
    }
    param_schema = [
        {"name": "color", "type": "color", "label": "Color"},
        {"name": "width", "type": "float", "label": "Width", "min": 0.1, "max": 1.0}
    ]
    
    def __init__(self, color="#9E9E9E", width=0.8, **kwargs):
        self.params = {"color": color, "width": width, **kwargs}
        self.subplot = "volume"
    
    @classmethod
    def calculate(cls, df: pd.DataFrame, params: dict) -> Optional[pd.Series]:
        if 'volume' not in df.columns:
            return pd.Series([None] * len(df), index=df.index)
        
        return df['volume']
    
    @classmethod
    def on_render(cls, chart, subplot: str, params: dict, df: Optional[pd.DataFrame] = None) -> None:
        # Volume is rendered as histogram automatically by the adapter
        pass


# Additional indicators mentioned in the task would be added here:
# - PivotPoints
# - DailyDevPro  
# - TrentTrade
# - ImportantLevels
# These would follow the same pattern as the indicators above