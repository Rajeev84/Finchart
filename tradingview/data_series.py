"""
FinChart TradingView Data Series module (Layer 1.1 Foundation).
Manages OHLCV data series indexed by logical sequence.
"""

from typing import List, Optional
from .types import OHLCVBar
from .indexed_store import IndexedDataStore


class OHLCVSeries:
    """Stores sequential OHLCV bars and maps integer logical indices to bars."""
    def __init__(self, symbol: str, bars: Optional[List[OHLCVBar]] = None):
        self.symbol = symbol
        self._bars: List[OHLCVBar] = bars or []
        # maintain an indexed store for timestamp->index mapping
        self._index = IndexedDataStore(self._bars)

    def add_bar(self, bar: OHLCVBar) -> None:
        self._validate_bar(bar)
        idx = self._index.insert_bar(bar)
        # keep list in sync
        if idx >= len(self._bars):
            self._bars.append(bar)
        else:
            self._bars.insert(idx, bar)

    def update_bar(self, index: int, bar: OHLCVBar) -> None:
        """Update an existing bar at `index`. Raises IndexError for invalid index."""
        if index < 0 or index >= len(self._bars):
            raise IndexError("Bar index out of range")
        self._validate_bar(bar)
        # update bar in place; timestamps may change so rebuild index
        self._bars[index] = bar
        self._index.build_from_bars(self._bars)

    def get_bars_in_range(self, start_index: int, end_index: int) -> List[OHLCVBar]:
        """Return bars between start_index and end_index inclusive.

        Indices are clamped to available bounds.
        """
        n = len(self._bars)
        if n == 0:
            return []
        s = max(0, start_index)
        e = min(n - 1, end_index)
        if s > e:
            return []
        return list(self._bars[s:e + 1])

    def _validate_bar(self, bar: OHLCVBar) -> None:
        """Basic validation for OHLCV values to avoid corrupt data."""
        if not (bar.high >= bar.low):
            raise ValueError("Bar high must be >= low")
        if not all(isinstance(v, (int, float)) for v in (bar.open, bar.high, bar.low, bar.close)):
            raise ValueError("Bar OHLC values must be numeric")

    def get_bar(self, index: int) -> Optional[OHLCVBar]:
        if 0 <= index < len(self._bars):
            return self._bars[index]
        return None

    def index_of_timestamp(self, timestamp: float, nearest: bool = True) -> Optional[int]:
        return self._index.index_of_timestamp(timestamp, nearest=nearest)

    def __len__(self) -> int:
        return len(self._bars)

# Added Features:
# - OHLCV series storage and lookup by logical index.
