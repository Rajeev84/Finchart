import pandas as pd
import numpy as np


class ChartData:
    COLUMN_MAP = {
        'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume',
        'date': 'Datetime', 'time': 'Datetime', 'datetime': 'Datetime'
    }

    def __init__(self, df: pd.DataFrame):
        """
        Manages OHLCV data and coordinate mapping.
        Assumes df has a DatetimeIndex or a column named 'date'/'time'.
        """
        self.df = pd.DataFrame()  # Initialize empty
        if df is not None:
            self.df = df.copy()
            self._prepare_data()

    def update(self, new_data: pd.DataFrame):
        """
        Updates the internal DataFrame.
        - If new_data overlaps existing indices, it updates them.
        - If new_data has new indices, it appends them.
        - Requires re-sorting and re-indexing.
        """
        if new_data is None or new_data.empty:
            return

        temp_df = self._normalize_columns(new_data)
        temp_df = self._ensure_datetime_column(temp_df)

        if self.df.empty:
            self.df = temp_df
            self._prepare_data()
            return

        current = self.df.set_index('Datetime')
        incoming = temp_df.set_index('Datetime')

        # Upsert logic: drop rows that incoming replaces, then append the new data.
        current = current.drop(incoming.index, errors='ignore')
        combined = pd.concat([current, incoming])

        self.df = combined.reset_index()
        self._prepare_data()

    def _prepare_data(self):
        if self.df.empty:
            self.avg_interval = pd.Timedelta(minutes=1)  # Default
            return

        self.df = self._normalize_columns(self.df)
        self.df = self._ensure_datetime_column(self.df)
        self.df = self.df.sort_values('Datetime').reset_index(drop=True)

        # The internal X coordinate is the index of the dataframe.
        self.df['x_index'] = self.df.index

        if len(self.df) > 1:
            diffs = self.df['Datetime'].diff().dropna()
            self.avg_interval = diffs.median()
            if self.avg_interval == pd.Timedelta(0):
                self.avg_interval = pd.Timedelta(minutes=1)
        else:
            self.avg_interval = pd.Timedelta(minutes=1)

    def get_len(self):
        return len(self.df)

    def get_by_index(self, idx):
        """Returns row at integer index."""
        if 0 <= idx < len(self.df):
            return self.df.iloc[int(idx)]
        return None

    def get_index_from_time(self, time_val):
        """
        Finds nearest index for a given time.
        Uses searchsorted for performance.
        Supports projection for future dates.
        """
        if self.df.empty:
            return 0

        times = self.df['Datetime'].values

        try:
            target = pd.to_datetime(time_val).to_datetime64()
        except Exception:
            target = time_val

        last_time = times[-1]

        if target > last_time:
            diff_ns = (target - last_time).astype('timedelta64[ns]')
            interval_ns = self.avg_interval.value

            if interval_ns <= 0:
                interval_ns = 60 * 1e9  # Default 1 min

            steps = diff_ns.astype(float) / interval_ns
            return len(times) - 1 + steps

        idx = times.searchsorted(target)

        if 0 < idx < len(times):
            t_prev = times[idx - 1]
            t_curr = times[idx]
            try:
                total_diff = (t_curr - t_prev).astype('timedelta64[ns]').astype(float)
                partial_diff = (target - t_prev).astype('timedelta64[ns]').astype(float)
                if total_diff > 0:
                    return (idx - 1) + (partial_diff / total_diff)
            except Exception:
                pass

        if idx >= len(times):
            return float(len(times) - 1)
        if idx < 0:
            return 0.0

        return float(idx)

    def get_time_from_index(self, idx):
        if self.df.empty:
            return None

        if 0 <= idx < len(self.df):
            i_low = int(idx)
            frac = idx - i_low

            if frac == 0 or i_low >= len(self.df) - 1:
                return self.df.iloc[i_low]['Datetime']

            t_low = self.df.iloc[i_low]['Datetime']
            t_high = self.df.iloc[i_low + 1]['Datetime']
            return t_low + (t_high - t_low) * frac

        if idx >= len(self.df):
            over = idx - (len(self.df) - 1)
            last_dt = self.df.iloc[-1]['Datetime']
            return last_dt + (self.avg_interval * over)

        if idx < 0:
            start_dt = self.df.iloc[0]['Datetime']
            return start_dt + (self.avg_interval * idx)

        return None

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        normalized = df.copy()
        normalized.columns = [self.COLUMN_MAP.get(str(col).lower(), col) for col in normalized.columns]
        if normalized.columns.duplicated().any():
            normalized = normalized.loc[:, ~normalized.columns.duplicated(keep='last')]
        return normalized

    def _ensure_datetime_column(self, df: pd.DataFrame) -> pd.DataFrame:
        normalized = df.copy()

        if isinstance(normalized.index, pd.DatetimeIndex):
            normalized['Datetime'] = pd.to_datetime(normalized.index)
            return normalized

        cols_map = {str(c).lower(): c for c in normalized.columns}
        if 'datetime' not in cols_map:
            if len(normalized.columns) > 0:
                raise ValueError("DataFrame must have DatetimeIndex or 'date'/'time' column")
            normalized['Datetime'] = pd.Series(dtype='datetime64[ns]')
            return normalized

        datetime_col = cols_map['datetime']
        normalized['Datetime'] = pd.to_datetime(normalized[datetime_col])
        if datetime_col != 'Datetime':
            normalized = normalized.drop(columns=[datetime_col])
        return normalized
