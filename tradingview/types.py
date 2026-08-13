"""
FinChart TradingView Types module.
Core dataclasses for market data, instruments, and logical positioning.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class OHLCVBar:
    timestamp: float
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass
class Instrument:
    symbol: str
    exchange: str
    session: str = "24x7"


@dataclass
class VisibleRange:
    start_index: float
    end_index: float

    @property
    def span(self) -> float:
        return self.end_index - self.start_index


@dataclass
class LogicalPosition:
    index: float
    timestamp: Optional[float] = None

# Added Features:
# - Added basic dataclasses for OHLCV, Instrument, VisibleRange, and LogicalPosition.
