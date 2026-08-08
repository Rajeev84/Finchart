"""Data Store - High-performance time-series buffer and query manager.

Normalizes pandas DataFrames or raw lists into immutable OHLCV bars.
Supports fast binary search timestamp lookups and fast price range queries.
"""
from __future__ import annotations

from typing import List, Tuple, Optional, Any, Dict, Union
import bisect
import math
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
        for bar in normalized:
            self._validate_bar(bar)
        if any(bar.timestamp < normalized[i - 1].timestamp for i, bar in enumerate(normalized) if i > 0):
            raise ValueError("Data timestamps must be sorted ascending")
        self._data = normalized
        self._timestamps = [b.timestamp for b in self._data]
        self._event_bus.emit_new(EventType.DATA_CHANGED, self, count=len(self._data))

    def append(self, bar: Union[OHLCV, dict]) -> None:
        """Append a single new bar, preserving the sorted-timestamp invariant."""
        ohlcv_bar = self._normalize_single_bar(bar)
        if self._timestamps and ohlcv_bar.timestamp < self._timestamps[-1]:
            raise ValueError("Appended bar timestamp must be >= the last stored timestamp")
        self._data.append(ohlcv_bar)
        self._timestamps.append(ohlcv_bar.timestamp)
        self._event_bus.emit_new(EventType.DATA_CHANGED, self, count=len(self._data), action="append")

    def update_last(self, bar: Union[OHLCV, dict]) -> None:
        """Update the last bar in real-time streaming mode."""
        if not self._data:
            self.append(bar)
            return

        ohlcv_bar = self._normalize_single_bar(bar)
        if ohlcv_bar.timestamp != self._timestamps[-1]:
            raise ValueError("Updated bar timestamp must equal the last stored timestamp; use append() for a new bar")
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
        """Return the bar containing/at-or-before ``timestamp``.

        For cross-timeframe drawings this is intentionally a floor lookup: an
        intraday anchor such as 09:30 resolves to the daily candle containing
        that instant instead of jumping to a later candle.
        """
        if not self._timestamps:
            return 0
        idx = bisect.bisect_right(self._timestamps, float(timestamp)) - 1
        return max(0, min(len(self._timestamps) - 1, idx))

    def get_timestamp_from_index(self, index: float) -> float:
        """Convert a float bar index to a linearly interpolated timestamp."""
        if not self._timestamps:
            return 0.0
        if len(self._timestamps) == 1:
            return self._timestamps[0]
        i = max(0.0, min(float(len(self._timestamps) - 1), float(index)))
        lo = int(math.floor(i))
        hi = min(len(self._timestamps) - 1, lo + 1)
        frac = i - lo
        return self._timestamps[lo] + (self._timestamps[hi] - self._timestamps[lo]) * frac

    # --- Internal Helpers ---
    def _normalize_input(self, raw_input: Any) -> List[OHLCV]:
        """Convert a DataFrame or sequence of bars into validated OHLCV values."""
        if raw_input is None:
            return []

        if hasattr(raw_input, "columns") and hasattr(raw_input, "iloc"):
            return self._from_dataframe(raw_input)

        if isinstance(raw_input, (list, tuple)):
            return [self._normalize_single_bar(item) for item in raw_input]

        raise TypeError("data must be a pandas DataFrame or a sequence of OHLCV/dict bars")

    def _normalize_single_bar(self, item: Any) -> OHLCV:
        """Normalize dict or OHLCV into an OHLCV bar."""
        if isinstance(item, OHLCV):
            self._validate_bar(item)
            return item

        if isinstance(item, dict):
            ts = item.get("timestamp", item.get("time", item.get("date")))
            if ts is None:
                raise ValueError("OHLCV bar is missing timestamp/time/date")
            ts = self._parse_datetime(ts)

            required = {
                "open": ("open", "Open"),
                "high": ("high", "High"),
                "low": ("low", "Low"),
                "close": ("close", "Close"),
            }
            values = {}
            for canonical, aliases in required.items():
                value = next((item[k] for k in aliases if k in item), None)
                if value is None:
                    raise ValueError(f"OHLCV bar is missing {canonical}")
                values[canonical] = float(value)
            volume = item.get("volume", item.get("Volume", 0.0))
            bar = OHLCV(timestamp=ts, open=values["open"], high=values["high"],
                        low=values["low"], close=values["close"], volume=float(volume))
            self._validate_bar(bar)
            return bar

        raise TypeError(f"Unsupported OHLCV bar type: {type(item).__name__}")

    def _from_dataframe(self, df: Any) -> List[OHLCV]:
        """Convert pandas DataFrame to List[OHLCV]."""
        bars = []
        # Find column names flexibly
        cols = {col.lower(): col for col in df.columns}

        time_col = cols.get("datetime", cols.get("timestamp", cols.get("time", cols.get("date", None))))
        required = {name: cols.get(name) for name in ("open", "high", "low", "close")}
        missing = [name for name, col in required.items() if col is None]
        if missing:
            raise ValueError(f"DataFrame is missing required OHLC columns: {', '.join(missing)}")
        open_col, high_col, low_col, close_col = (required[name] for name in ("open", "high", "low", "close"))
        vol_col = cols.get("volume")

        for idx, row in df.iterrows():
            if time_col and time_col in row:
                t_val = row[time_col]
                ts = self._parse_datetime(t_val)
            else:
                # Use row index if integer or timestamp
                ts = self._parse_datetime(idx)

            op = float(row[open_col])
            hi = float(row[high_col])
            lo = float(row[low_col])
            cl = float(row[close_col])
            vo = float(row[vol_col]) if vol_col is not None else 0.0
            bars.append(OHLCV(timestamp=float(ts), open=op, high=hi, low=lo, close=cl, volume=vo))

        for bar in bars:
            self._validate_bar(bar)
        if any(b.timestamp < bars[i - 1].timestamp for i, b in enumerate(bars) if i > 0):
            raise ValueError("DataFrame timestamps must be sorted ascending")
        return bars

    @staticmethod
    def _validate_bar(bar: OHLCV) -> None:
        values = (bar.timestamp, bar.open, bar.high, bar.low, bar.close, bar.volume)
        if not all(math.isfinite(float(v)) for v in values):
            raise ValueError("OHLCV values must be finite numbers")
        if bar.high < max(bar.open, bar.close) or bar.low > min(bar.open, bar.close):
            raise ValueError("OHLCV high/low values are inconsistent with open/close")
        if bar.high < bar.low:
            raise ValueError("OHLCV high must be >= low")
        if bar.volume < 0:
            raise ValueError("OHLCV volume cannot be negative")

    def _parse_datetime(self, val: Any) -> float:
        """Parse datetime object, string, or number into unix timestamp seconds."""
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, datetime):
            return val.timestamp()
        try:
            import pandas as pd
            dt = pd.to_datetime(val)
            if hasattr(dt, "to_pydatetime"):
                dt = dt.to_pydatetime()
            return float(dt.timestamp())
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"Invalid datetime value: {val!r}") from exc
