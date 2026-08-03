"""finchart.indicators - Technical indicator framework and built-in indicators."""
from .plugin import BaseIndicator
from .registry import INDICATOR_REGISTRY, register_indicator, auto_discover, get_indicator, list_indicators
from .adapter import ChartProxy, IndicatorAdapter
from .manager import IndicatorManager

# Import built-in indicators to register them
from .builtins import SMA, EMA, RSI, MACD, BollingerBands, Volume

__all__ = [
    "BaseIndicator",
    "INDICATOR_REGISTRY", 
    "register_indicator",
    "auto_discover",
    "get_indicator",
    "list_indicators",
    "ChartProxy",
    "IndicatorAdapter",
    "IndicatorManager",
    "SMA",
    "EMA", 
    "RSI",
    "MACD",
    "BollingerBands",
    "Volume"
]
