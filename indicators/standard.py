"""Standard Technical Indicators - SMA, EMA, RSI, MACD, and Bollinger Bands.
"""
from __future__ import annotations

from typing import List, Optional, Dict, Any
import math

from ..core.types import OHLCV, Color
from ..coordinates.engine import CoordinateEngine
from ..rendering.pipeline import DrawCommand, Layer
from .base import Indicator, IndicatorResult


class SMA(Indicator):
    """Simple Moving Average (SMA) Indicator."""

    def __init__(self, period: int = 20, color: str = "#2196F3", width: float = 1.5) -> None:
        if not isinstance(period, int) or period < 1:
            raise ValueError("SMA period must be a positive integer")
        if width <= 0:
            raise ValueError("SMA width must be positive")
        super().__init__("SMA", {"period": period, "color": color, "width": width})
        self.period = period
        self.color = Color.from_hex(color)
        self.width = width
        self._sma_values: List[Optional[float]] = []

    def calculate(self, data: List[OHLCV]) -> IndicatorResult:
        closes = [b.close for b in data]
        self._sma_values = []
        for i in range(len(closes)):
            if i < self.period - 1:
                self._sma_values.append(None)
            else:
                window = closes[i - self.period + 1 : i + 1]
                self._sma_values.append(sum(window) / float(self.period))
        return IndicatorResult(values={"sma": self._sma_values})

    def render_commands(
        self,
        coord_engine: CoordinateEngine,
        start_idx: int,
        end_idx: int,
        viewport: Optional[Any] = None
    ) -> List[DrawCommand]:
        if not self._sma_values:
            return []

        vp = viewport or coord_engine.viewport
        points = []

        for i in range(start_idx, min(end_idx, len(self._sma_values))):
            val = self._sma_values[i]
            if val is not None:
                x = coord_engine.index_to_x(i)
                y = coord_engine.price_to_y(val, vp)
                points.extend([x, y])

        if len(points) < 4:
            return []

        return [
            DrawCommand(
                layer=Layer.INDICATORS,
                tag=f"sma_{self.period}",
                item_type="line",
                coords=tuple(points),
                options={"fill": self.color.to_hex(), "width": self.width},
                z_index=10
            )
        ]


class EMA(Indicator):
    """Exponential Moving Average (EMA) Indicator."""

    def __init__(self, period: int = 9, color: str = "#FF9800", width: float = 1.5) -> None:
        if not isinstance(period, int) or period < 1:
            raise ValueError("EMA period must be a positive integer")
        if width <= 0:
            raise ValueError("EMA width must be positive")
        super().__init__("EMA", {"period": period, "color": color, "width": width})
        self.period = period
        self.color = Color.from_hex(color)
        self.width = width
        self._ema_values: List[Optional[float]] = []

    def calculate(self, data: List[OHLCV]) -> IndicatorResult:
        closes = [b.close for b in data]
        self._ema_values = []
        if not closes:
            return IndicatorResult(values={"ema": []})

        multiplier = 2.0 / (self.period + 1.0)
        ema = None

        for i in range(len(closes)):
            if i < self.period - 1:
                self._ema_values.append(None)
            elif i == self.period - 1:
                ema = sum(closes[: self.period]) / float(self.period)
                self._ema_values.append(ema)
            else:
                ema = (closes[i] - ema) * multiplier + ema
                self._ema_values.append(ema)

        return IndicatorResult(values={"ema": self._ema_values})

    def render_commands(
        self,
        coord_engine: CoordinateEngine,
        start_idx: int,
        end_idx: int,
        viewport: Optional[Any] = None
    ) -> List[DrawCommand]:
        if not self._ema_values:
            return []

        vp = viewport or coord_engine.viewport
        points = []

        for i in range(start_idx, min(end_idx, len(self._ema_values))):
            val = self._ema_values[i]
            if val is not None:
                x = coord_engine.index_to_x(i)
                y = coord_engine.price_to_y(val, vp)
                points.extend([x, y])

        if len(points) < 4:
            return []

        return [
            DrawCommand(
                layer=Layer.INDICATORS,
                tag=f"ema_{self.period}",
                item_type="line",
                coords=tuple(points),
                options={"fill": self.color.to_hex(), "width": self.width},
                z_index=11
            )
        ]


class RSI(Indicator):
    """Relative Strength Index (RSI) Indicator."""

    def __init__(self, period: int = 14, color: str = "#E91E63", width: float = 1.5) -> None:
        if not isinstance(period, int) or period < 1:
            raise ValueError("RSI period must be a positive integer")
        if width <= 0:
            raise ValueError("RSI width must be positive")
        super().__init__("RSI", {"period": period, "color": color, "width": width}, pane="rsi")
        self.period = period
        self.color = Color.from_hex(color)
        self.width = width
        self._rsi_values: List[Optional[float]] = []

    def calculate(self, data: List[OHLCV]) -> IndicatorResult:
        closes = [b.close for b in data]
        self._rsi_values = [None] * len(closes)
        if len(closes) <= self.period:
            return IndicatorResult(values={"rsi": self._rsi_values})

        gains = []
        losses = []

        for i in range(1, len(closes)):
            diff = closes[i] - closes[i - 1]
            gains.append(max(0.0, diff))
            losses.append(max(0.0, -diff))

        avg_gain = sum(gains[: self.period]) / float(self.period)
        avg_loss = sum(losses[: self.period]) / float(self.period)

        if avg_loss == 0:
            self._rsi_values[self.period] = 100.0
        else:
            rs = avg_gain / avg_loss
            self._rsi_values[self.period] = 100.0 - (100.0 / (1.0 + rs))

        for i in range(self.period + 1, len(closes)):
            gain = gains[i - 1]
            loss = losses[i - 1]
            avg_gain = (avg_gain * (self.period - 1) + gain) / float(self.period)
            avg_loss = (avg_loss * (self.period - 1) + loss) / float(self.period)

            if avg_loss == 0:
                self._rsi_values[i] = 100.0
            else:
                rs = avg_gain / avg_loss
                self._rsi_values[i] = 100.0 - (100.0 / (1.0 + rs))

        return IndicatorResult(values={"rsi": self._rsi_values})

    def render_commands(
        self,
        coord_engine: CoordinateEngine,
        start_idx: int,
        end_idx: int,
        viewport: Optional[Any] = None
    ) -> List[DrawCommand]:
        if not self._rsi_values:
            return []

        vp = viewport or coord_engine.viewport
        points = []

        for i in range(start_idx, min(end_idx, len(self._rsi_values))):
            val = self._rsi_values[i]
            if val is not None:
                x = coord_engine.index_to_x(i)
                # Use the coordinate engine's price_to_y with the RSI pane
                y = coord_engine.price_to_y(val, vp, self.pane)
                points.extend([x, y])

        if len(points) < 4:
            return []

        return [
            DrawCommand(
                layer=Layer.INDICATORS,
                tag=f"rsi_{self.period}",
                item_type="line",
                coords=tuple(points),
                options={"fill": self.color.to_hex(), "width": self.width},
                z_index=12
            )
        ]


class MACD(Indicator):
    """Moving Average Convergence Divergence (MACD) Indicator.

    Computes MACD line, Signal line, and Histogram.
    """

    def __init__(
        self,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
        color_macd: str = "#2196F3",
        color_signal: str = "#FF9800",
        color_hist_bull: str = "#089981",
        color_hist_bear: str = "#F23645",
        width: float = 1.5,
    ) -> None:
        if not all(isinstance(v, int) and v >= 1 for v in (fast, slow, signal)):
            raise ValueError("MACD periods must be positive integers")
        if slow <= fast:
            raise ValueError("MACD slow period must be greater than fast period")
        if width <= 0:
            raise ValueError("MACD width must be positive")
        super().__init__("MACD", {"fast": fast, "slow": slow, "signal": signal, "color_macd": color_macd, "color_signal": color_signal, "color_hist_bull": color_hist_bull, "color_hist_bear": color_hist_bear, "width": width}, pane="macd")
        self.fast = fast
        self.slow = slow
        self.signal_period = signal
        self.color_macd = Color.from_hex(color_macd)
        self.color_signal = Color.from_hex(color_signal)
        self.color_hist_bull = Color.from_hex(color_hist_bull)
        self.color_hist_bear = Color.from_hex(color_hist_bear)
        self.width = width
        self._macd_line: List[Optional[float]] = []
        self._signal_line: List[Optional[float]] = []
        self._histogram: List[Optional[float]] = []

    def _calc_ema(self, values: List[float], period: int) -> List[Optional[float]]:
        result: List[Optional[float]] = []
        mult = 2.0 / (period + 1.0)
        ema: Optional[float] = None
        for i, v in enumerate(values):
            if i < period - 1:
                result.append(None)
            elif i == period - 1:
                ema = sum(values[:period]) / period
                result.append(ema)
            else:
                ema = (v - ema) * mult + ema  # type: ignore[operator]
                result.append(ema)
        return result

    def calculate(self, data: List[OHLCV]) -> IndicatorResult:
        closes = [b.close for b in data]
        n = len(closes)

        fast_ema = self._calc_ema(closes, self.fast)
        slow_ema = self._calc_ema(closes, self.slow)

        # MACD = fast EMA - slow EMA
        self._macd_line = []
        for i in range(n):
            f = fast_ema[i]
            s = slow_ema[i]
            if f is None or s is None:
                self._macd_line.append(None)
            else:
                self._macd_line.append(f - s)

        # Signal = EMA(MACD, signal_period)
        # Filter out None values, align indices
        macd_vals_only = [v for v in self._macd_line if v is not None]
        first_valid = next((i for i, v in enumerate(self._macd_line) if v is not None), n)
        signal_raw = self._calc_ema(macd_vals_only, self.signal_period)

        self._signal_line = [None] * n
        for j, sig in enumerate(signal_raw):
            self._signal_line[first_valid + j] = sig

        # Histogram = MACD - Signal
        self._histogram = []
        for i in range(n):
            m = self._macd_line[i]
            s = self._signal_line[i]
            if m is None or s is None:
                self._histogram.append(None)
            else:
                self._histogram.append(m - s)

        return IndicatorResult(values={
            "macd": self._macd_line,
            "signal": self._signal_line,
            "histogram": self._histogram,
        })

    def render_commands(
        self,
        coord_engine: CoordinateEngine,
        start_idx: int,
        end_idx: int,
        viewport: Optional[Any] = None
    ) -> List[DrawCommand]:
        if not self._macd_line:
            return []

        vp = viewport or coord_engine.viewport
        cmds: List[DrawCommand] = []

        # Use coordinate engine's price_to_y with the MACD pane
        zero_y = coord_engine.price_to_y(0.0, vp, self.pane)

        # MACD line
        macd_pts = []
        for i in range(start_idx, min(end_idx, len(self._macd_line))):
            v = self._macd_line[i]
            if v is not None:
                macd_pts.extend([coord_engine.index_to_x(i), coord_engine.price_to_y(v, vp, self.pane)])
        if len(macd_pts) >= 4:
            cmds.append(DrawCommand(
                layer=Layer.INDICATORS,
                tag="macd_line",
                item_type="line",
                coords=tuple(macd_pts),
                options={"fill": self.color_macd.to_hex(), "width": self.width},
                z_index=10
            ))

        # Signal line
        sig_pts = []
        for i in range(start_idx, min(end_idx, len(self._signal_line))):
            v = self._signal_line[i]
            if v is not None:
                sig_pts.extend([coord_engine.index_to_x(i), coord_engine.price_to_y(v, vp, self.pane)])
        if len(sig_pts) >= 4:
            cmds.append(DrawCommand(
                layer=Layer.INDICATORS,
                tag="macd_signal",
                item_type="line",
                coords=tuple(sig_pts),
                options={"fill": self.color_signal.to_hex(), "width": self.width},
                z_index=11
            ))

        # Histogram bars
        bar_w = max(1.0, coord_engine.get_bar_width() * 0.5)
        for i in range(start_idx, min(end_idx, len(self._histogram))):
            h = self._histogram[i]
            if h is None:
                continue
            x = coord_engine.index_to_x(i)
            y = coord_engine.price_to_y(h, vp, self.pane)
            color = self.color_hist_bull if h >= 0 else self.color_hist_bear
            cmds.append(DrawCommand(
                layer=Layer.INDICATORS,
                tag=f"macd_hist_{i}",
                item_type="rectangle",
                coords=(x - bar_w, min(y, zero_y), x + bar_w, max(y, zero_y)),
                options={"fill": color.to_hex(), "outline": ""},
                z_index=9
            ))

        return cmds


class Volume(Indicator):
    """Volume indicator with moving average overlay.

    Renders volume bars (green/red based on close vs open) and an SMA line
    in a dedicated 'volume' subplot pane.
    """

    def __init__(
        self,
        ma_period: int = 21,
        color_up: str = "#089981",
        color_down: str = "#F23645",
        color_ma: str = "#2196F3",
        width: float = 1.5,
    ) -> None:
        if not isinstance(ma_period, int) or ma_period < 1:
            raise ValueError("Volume MA period must be a positive integer")
        if width <= 0:
            raise ValueError("Volume width must be positive")
        super().__init__("Volume", {"ma_period": ma_period, "color_up": color_up, "color_down": color_down, "color_ma": color_ma, "width": width}, pane="volume")
        self.ma_period = ma_period
        self.color_up = Color.from_hex(color_up)
        self.color_down = Color.from_hex(color_down)
        self.color_ma = Color.from_hex(color_ma)
        self.width = width
        self._volumes: List[float] = []
        self._ma_values: List[Optional[float]] = []
        self._directions: List[bool] = []  # True if bullish (close >= open)

    def calculate(self, data: List[OHLCV]) -> IndicatorResult:
        self._volumes = [b.volume for b in data]
        self._directions = [b.close >= b.open for b in data]
        self._ma_values = []
        for i in range(len(data)):
            if i < self.ma_period - 1:
                self._ma_values.append(None)
            else:
                window = self._volumes[i - self.ma_period + 1: i + 1]
                self._ma_values.append(sum(window) / self.ma_period)
        return IndicatorResult(values={"volume": self._volumes, "ma": self._ma_values})

    def render_commands(
        self,
        coord_engine: CoordinateEngine,
        start_idx: int,
        end_idx: int,
        viewport: Optional[Any] = None
    ) -> List[DrawCommand]:
        if not self._volumes:
            return []

        vp = viewport or coord_engine.viewport
        cmds: List[DrawCommand] = []
        bar_w = max(1.0, coord_engine.get_bar_width() * 0.8)
        half_w = bar_w / 2.0

        # Volume bars — semi-transparent via stipple
        for i in range(start_idx, min(end_idx, len(self._volumes))):
            vol = self._volumes[i]
            x = coord_engine.index_to_x(i)
            if x + half_w < vp.left or x - half_w > vp.right:
                continue
            y = coord_engine.price_to_y(vol, vp, pane="volume")
            color = self.color_up if self._directions[i] else self.color_down
            cmds.append(DrawCommand(
                layer=Layer.INDICATORS,
                tag=f"vol_bar_{i}",
                item_type="rectangle",
                coords=(x - half_w, y, x + half_w, vp.bottom),
                options={"fill": color.to_hex(), "outline": "", "stipple": "gray50"},
                z_index=0
            ))

        # MA line
        points = []
        for i in range(start_idx, min(end_idx, len(self._ma_values))):
            val = self._ma_values[i]
            if val is not None:
                x = coord_engine.index_to_x(i)
                y = coord_engine.price_to_y(val, vp, pane="volume")
                points.extend([x, y])

        if len(points) >= 4:
            cmds.append(DrawCommand(
                layer=Layer.INDICATORS,
                tag=f"vol_ma_{self.ma_period}",
                item_type="line",
                coords=tuple(points),
                options={"fill": self.color_ma.to_hex(), "width": self.width},
                z_index=10
            ))

        return cmds


class BollingerBands(Indicator):
    """Bollinger Bands indicator: Middle SMA ± N standard deviations."""

    def __init__(
        self,
        period: int = 20,
        std_dev: float = 2.0,
        color_middle: str = "#9C27B0",
        color_upper: str = "#FF9800",
        color_lower: str = "#FF9800",
        width: float = 1.0,
    ) -> None:
        if not isinstance(period, int) or period < 1:
            raise ValueError("Bollinger Bands period must be a positive integer")
        if std_dev < 0:
            raise ValueError("Bollinger Bands standard deviation must be non-negative")
        if width <= 0:
            raise ValueError("Bollinger Bands width must be positive")
        super().__init__("BollingerBands", {"period": period, "std_dev": std_dev, "color_middle": color_middle, "color_upper": color_upper, "color_lower": color_lower, "width": width})
        self.period = period
        self.std_dev = std_dev
        self.color_middle = Color.from_hex(color_middle)
        self.color_upper = Color.from_hex(color_upper)
        self.color_lower = Color.from_hex(color_lower)
        self.width = width
        self._upper: List[Optional[float]] = []
        self._middle: List[Optional[float]] = []
        self._lower: List[Optional[float]] = []

    def calculate(self, data: List[OHLCV]) -> IndicatorResult:
        closes = [b.close for b in data]
        n = len(closes)
        self._upper = []
        self._middle = []
        self._lower = []

        for i in range(n):
            if i < self.period - 1:
                self._upper.append(None)
                self._middle.append(None)
                self._lower.append(None)
            else:
                window = closes[i - self.period + 1: i + 1]
                mean = sum(window) / self.period
                variance = sum((c - mean) ** 2 for c in window) / self.period
                sd = variance ** 0.5
                self._middle.append(mean)
                self._upper.append(mean + self.std_dev * sd)
                self._lower.append(mean - self.std_dev * sd)

        return IndicatorResult(values={
            "upper": self._upper,
            "middle": self._middle,
            "lower": self._lower,
        })

    def _band_points(
        self,
        values: List[Optional[float]],
        coord_engine: CoordinateEngine,
        start_idx: int,
        end_idx: int,
        vp: Any
    ) -> List[float]:
        pts: List[float] = []
        for i in range(start_idx, min(end_idx, len(values))):
            v = values[i]
            if v is not None:
                pts.extend([coord_engine.index_to_x(i), coord_engine.price_to_y(v, vp)])
        return pts

    def render_commands(
        self,
        coord_engine: CoordinateEngine,
        start_idx: int,
        end_idx: int,
        viewport: Optional[Any] = None
    ) -> List[DrawCommand]:
        if not self._middle:
            return []

        vp = viewport or coord_engine.viewport
        cmds: List[DrawCommand] = []

        for values, color, tag, z in [
            (self._upper, self.color_upper, "bb_upper", 10),
            (self._middle, self.color_middle, "bb_middle", 11),
            (self._lower, self.color_lower, "bb_lower", 10),
        ]:
            pts = self._band_points(values, coord_engine, start_idx, end_idx, vp)
            if len(pts) >= 4:
                cmds.append(DrawCommand(
                    layer=Layer.INDICATORS,
                    tag=tag,
                    item_type="line",
                    coords=tuple(pts),
                    options={"fill": color.to_hex(), "width": self.width},
                    z_index=z,
                ))

        return cmds
