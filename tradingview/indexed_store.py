"""
Indexed data store for mapping timestamps to logical indices.

Provides fast lookup of bar index by timestamp and utilities to query
bars by timestamp ranges. Designed to be lightweight and keep ordering.
"""
from bisect import bisect_left, bisect_right
from typing import List, Optional, Tuple
from .types import OHLCVBar


class IndexedDataStore:
    def __init__(self, bars: Optional[List[OHLCVBar]] = None):
        self._timestamps: List[float] = []
        self._bars: List[OHLCVBar] = []
        if bars:
            self.build_from_bars(bars)

    def build_from_bars(self, bars: List[OHLCVBar]) -> None:
        # Ensure bars are sorted by timestamp
        sorted_bars = sorted(bars, key=lambda b: b.timestamp)
        self._bars = list(sorted_bars)
        self._timestamps = [b.timestamp for b in self._bars]

    def insert_bar(self, bar: OHLCVBar) -> int:
        """Insert a bar while maintaining timestamp order.

        Returns the integer logical index where the bar was inserted.
        If the timestamp equals an existing timestamp, the new bar is
        appended after existing ones with the same timestamp.
        """
        if not self._timestamps or bar.timestamp >= self._timestamps[-1]:
            self._bars.append(bar)
            self._timestamps.append(bar.timestamp)
            return len(self._bars) - 1

        pos = bisect_right(self._timestamps, bar.timestamp)
        self._timestamps.insert(pos, bar.timestamp)
        self._bars.insert(pos, bar)
        return pos

    def index_of_timestamp(self, timestamp: float, nearest: bool = True) -> Optional[int]:
        """Return integer index for given timestamp.

        If `nearest` is True returns nearest index when an exact match
        is not found. Otherwise returns None for missing timestamps.
        """
        if not self._timestamps:
            return None
        pos = bisect_left(self._timestamps, timestamp)
        if pos < len(self._timestamps) and self._timestamps[pos] == timestamp:
            return pos
        if not nearest:
            return None

        # choose nearest of pos-1 and pos
        left = max(0, pos - 1)
        right = min(len(self._timestamps) - 1, pos)
        if abs(self._timestamps[left] - timestamp) <= abs(self._timestamps[right] - timestamp):
            return left
        return right

    def get_bars_in_time_range(self, start_ts: float, end_ts: float) -> List[OHLCVBar]:
        if not self._timestamps:
            return []
        s = bisect_left(self._timestamps, start_ts)
        e = bisect_right(self._timestamps, end_ts)
        return list(self._bars[s:e])

    def __len__(self) -> int:
        return len(self._bars)
