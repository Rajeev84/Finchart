"""Data Store - High-performance time-series buffer and query manager.

Normalizes pandas DataFrames or raw lists into immutable OHLCV bars.
Supports fast binary search timestamp lookups and fast price range queries.
"""
from __future__ import annotations

from typing import List, Tuple, Optional, Any, Dict, Union
import bisect
from datetime import datetime

from .types import OHLCV
from .events import EventBus, EventType


class DataStore:
    """Manages OHLCV bar array, timestamp indexing, and range price queries."""

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._data: List[OHLCV] = []
        self._timestamps: List[float] = []

    @property
    def data(self) -> List[OHLCV]:
        """Return the current bar list."""
        return self._data

    @property
    def count(self) -> int:
        """Total number of bars."""
        return len(self._data)

    @property
    def is_empty(self) -> bool:
        """True if store contains zero bars."""
        return len(self._data) == 0

    def set_data(self, data: Union[List[OHLCV], Any]) -> None:
        """Set or replace total bar dataset. Automatically normalizes DataFrame if passed."""
        normalized = self._normalize_input(data)
        self._data = normalized
        self._timestamps = [b.timestamp for b in self._data]
        self._event_bus.emit_new(EventType.DATA_CHANGED, self, count=len(self._data))

    def append(self, bar: Union[OHLCV, dict]) -> None:
        """Append a single new bar to the data store."""
        ohlcv_bar = self._normalize_single_bar(bar)
        self._data.append(ohlcv_bar)
        self._timestamps.append(ohlcv_bar.timestamp)
        self._event_bus.emit_new(EventType.DATA_CHANGED, self, count=len(self._data), action="append")

    def update_last(self, bar: Union[OHLCV, dict]) -> None:
        """Update the last bar in real-time streaming mode."""
        if not self._data:
            self.append(bar)
            return

        ohlcv_bar = self._normalize_single_bar(bar)
        self._data[-1] = ohlcv_bar
        self._timestamps[-1] = ohlcv_bar.timestamp
        self._event_bus.emit_new(EventType.DATA_CHANGED, self, count=len(self._data), action="update_last")

    def get_bar(self, index: int) -> Optional[OHLCV]:
        """Get OHLCV bar at index, or None if out of bounds."""
        if 0 <= index < len(self._data):
            return self._data[index]
        return None

    def get_price_range(self, start_idx: int, end_idx: int) -> Tuple[float, float]:
        """Calculate minimum low and maximum high across visible bar slice [start_idx, end_idx]."""
        if not self._data:
            return (0.0, 1.0)

        s_idx = max(0, start_idx)
        e_idx = min(len(self._data), end_idx)

        if s_idx >= e_idx:
            return (0.0, 1.0)

        slice_bars = self._data[s_idx:e_idx]
        min_p = min(b.low for b in slice_bars)
        max_p = max(b.high for b in slice_bars)

        if min_p == max_p:
            min_p -= 0.5
            max_p += 0.5

        return (min_p, max_p)

    def get_index_from_timestamp(self, timestamp: float) -> int:
        """Find bar index corresponding to a Unix timestamp using binary search."""
        if not self._timestamps:
            return 0
        idx = bisect.bisect_left(self._timestamps, timestamp)
        if idx >= len(self._timestamps):
            return len(self._timestamps) - 1
        return idx

    def get_timestamp_from_index(self, index: float) -> float:
        """Convert a float index to interpolated or exact Unix timestamp."""
        if not self._timestamps:
            return 0.0

        int_idx = int(round(index))
        clamped_idx = max(0, min(len(self._timestamps) - 1, int_idx))
        return self._timestamps[clamped_idx]

    # --- Internal Helpers ---
    def _normalize_input(self, raw_input: Any) -> List[OHLCV]:
        """Convert pandas DataFrame, list of dicts, or list of OHLCV to List[OHLCV]."""
        if not raw_input:
            return []

        # Check if pandas DataFrame
        if hasattr(raw_input, "columns") and hasattr(raw_input, "iloc"):
            return self._from_dataframe(raw_input)

        # Check if list of dicts or list of OHLCV
        if isinstance(raw_input, list):
            result = []
            for item in raw_input:
                result.append(self._normalize_single_bar(item))
            return result

        return []

    def _normalize_single_bar(self, item: Any) -> OHLCV:
        """Normalize dict or OHLCV into an OHLCV bar."""
        if isinstance(item, OHLCV):
            return item

        if isinstance(item, dict):
            # Parse timestamp
            ts = item.get("timestamp", item.get("time", item.get("date", 0)))
            if isinstance(ts, (datetime, str)):
                ts = self._parse_datetime(ts)

            op = float(item.get("open", item.get("Open", 0.0)))
            hi = float(item.get("high", item.get("High", 0.0)))
            lo = float(item.get("low", item.get("Low", 0.0)))
            cl = float(item.get("close", item.get("Close", 0.0)))
            vo = float(item.get("volume", item.get("Volume", 0.0)))
            return OHLCV(timestamp=float(ts), open=op, high=hi, low=lo, close=cl, volume=vo)

        return OHLCV(timestamp=0.0, open=0.0, high=0.0, low=0.0, close=0.0, volume=0.0)

    def _from_dataframe(self, df: Any) -> List[OHLCV]:
        """Convert pandas DataFrame to List[OHLCV]."""
        bars = []
        # Find column names flexibly
        cols = {col.lower(): col for col in df.columns}

        time_col = cols.get("datetime", cols.get("time", cols.get("date", None)))
        open_col = cols.get("open", "Open")
        high_col = cols.get("high", "High")
        low_col = cols.get("low", "Low")
        close_col = cols.get("close", "Close")
        vol_col = cols.get("volume", "Volume")

        for idx, row in df.iterrows():
            if time_col and time_col in row:
                t_val = row[time_col]
                ts = self._parse_datetime(t_val)
            else:
                # Use row index if integer or timestamp
                ts = self._parse_datetime(idx)

            op = float(row.get(open_col, 0.0))
            hi = float(row.get(high_col, 0.0))
            lo = float(row.get(low_col, 0.0))
            cl = float(row.get(close_col, 0.0))
            vo = float(row.get(vol_col, 0.0))
            bars.append(OHLCV(timestamp=float(ts), open=op, high=hi, low=lo, close=cl, volume=vo))

        return bars

    def _parse_datetime(self, val: Any) -> float:
        """Parse datetime object, string, or number into unix timestamp seconds."""
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, datetime):
            return val.timestamp()
        try:
            import pandas as pd
            dt = pd.to_datetime(val)
            return dt.timestamp()
        except Exception:
            return 0.0
