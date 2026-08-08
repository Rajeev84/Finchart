"""Core type definitions and data models for FinChart.

Defines immutable OHLCV candles, 2D geometry primitives (Point, Rect, Viewport),
RGBA Color models, chart type enums, and visible range indicators.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Any
import math
import time


class ChartType(Enum):
    """Supported main series chart rendering types."""
    CANDLESTICK = auto()
    OHLC = auto()
    LINE = auto()
    AREA = auto()
    HISTOGRAM = auto()
    BASELINE = auto()
    STEP = auto()
    HEIKIN_ASHI = auto()


class ScaleMode(Enum):
    """Price axis scale calculation modes."""
    AUTO = auto()
    MANUAL = auto()
    LOG = auto()
    PERCENTAGE = auto()


class PriceSource(Enum):
    """Price calculation source for technical indicators."""
    CLOSE = auto()
    OPEN = auto()
    HIGH = auto()
    LOW = auto()
    HL2 = auto()
    HLC3 = auto()
    OHLC4 = auto()


@dataclass(frozen=True, slots=True)
class OHLCV:
    """Immutable candlestick/bar data point.
    
    Attributes:
        timestamp: Unix timestamp in seconds (float).
        open: Opening price.
        high: Highest price during period.
        low: Lowest price during period.
        close: Closing price.
        volume: Traded volume.
    """
    timestamp: float
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    @property
    def time(self) -> float:
        """Alias for timestamp."""
        return self.timestamp

    @property
    def body_top(self) -> float:
        """Highest price between open and close."""
        return max(self.open, self.close)

    @property
    def body_bottom(self) -> float:
        """Lowest price between open and close."""
        return min(self.open, self.close)

    @property
    def is_bullish(self) -> bool:
        """True if close >= open (green candle)."""
        return self.close >= self.open

    @property
    def is_bearish(self) -> bool:
        """True if close < open (red candle)."""
        return self.close < self.open

    @property
    def range(self) -> float:
        """Total price range (high - low)."""
        return self.high - self.low

    @property
    def body_size(self) -> float:
        """Absolute body size |close - open|."""
        return abs(self.close - self.open)

    @property
    def upper_wick(self) -> float:
        """Upper wick size (high - body_top)."""
        return self.high - self.body_top

    @property
    def lower_wick(self) -> float:
        """Lower wick size (body_bottom - low)."""
        return self.body_bottom - self.low


@dataclass(slots=True)
class VisibleRange:
    """Visible bar index range in current viewport."""
    start_index: int = 0
    end_index: int = 0
    bar_count: int = 0

    @property
    def count(self) -> int:
        """Number of visible bars."""
        return max(0, self.end_index - self.start_index)


@dataclass(slots=True)
class Viewport:
    """2D rectangular viewport in pixel space."""
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0

    @property
    def left(self) -> float:
        return self.x

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def top(self) -> float:
        return self.y

    @property
    def bottom(self) -> float:
        return self.y + self.height

    @property
    def center_x(self) -> float:
        return self.x + self.width / 2.0

    @property
    def center_y(self) -> float:
        return self.y + self.height / 2.0

    def contains(self, px: float, py: float) -> bool:
        """Check if point (px, py) is inside viewport bounds."""
        return (self.left <= px <= self.right and self.top <= py <= self.bottom)

    def inset(self, dx: float, dy: float) -> Viewport:
        """Return a new Viewport inset by dx and dy."""
        return Viewport(
            x=self.x + dx,
            y=self.y + dy,
            width=max(0.0, self.width - 2.0 * dx),
            height=max(0.0, self.height - 2.0 * dy)
        )


@dataclass(slots=True)
class Point:
    """2D coordinate point."""
    x: float = 0.0
    y: float = 0.0

    def __add__(self, other: Point) -> Point:
        return Point(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Point) -> Point:
        return Point(self.x - other.x, self.y - other.y)


@dataclass(slots=True)
class Color:
    """RGBA Color representation."""
    r: int = 0
    g: int = 0
    b: int = 0
    a: float = 1.0

    def to_hex(self) -> str:
        """Convert color to #RRGGBB hex string."""
        return f"#{self.r:02x}{self.g:02x}{self.b:02x}"

    def to_rgba(self) -> str:
        """Convert color to rgba(r,g,b,a) CSS string."""
        return f"rgba({self.r},{self.g},{self.b},{self.a})"

    @classmethod
    def from_hex(cls, hex_str: str, alpha: float = 1.0) -> Color:
        """Construct Color from hex string (e.g. '#089981' or '089981')."""
        clean_hex = hex_str.lstrip("#")
        if len(clean_hex) == 6:
            r = int(clean_hex[0:2], 16)
            g = int(clean_hex[2:4], 16)
            b = int(clean_hex[4:6], 16)
            return cls(r=r, g=g, b=b, a=alpha)
        elif len(clean_hex) == 8:
            r = int(clean_hex[0:2], 16)
            g = int(clean_hex[2:4], 16)
            b = int(clean_hex[4:6], 16)
            a = int(clean_hex[6:8], 16) / 255.0
            return cls(r=r, g=g, b=b, a=a)
        raise ValueError(f"Invalid hex color: {hex_str!r}")


@dataclass(slots=True)
class Rect:
    """Bounding rectangle."""
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0

    @property
    def left(self) -> float:
        return self.x

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def top(self) -> float:
        return self.y

    @property
    def bottom(self) -> float:
        return self.y + self.height

    def contains(self, px: float, py: float) -> bool:
        return (self.left <= px <= self.right and self.top <= py <= self.bottom)
