"""Coordinate Engine - Data to Pixel transformations and viewport scaling.

Maps between bar indices / price levels and Canvas pixel coordinates.
Supports time scale panning/zooming around anchor points and price auto/log-scaling.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple, List
import math

from ..core.types import OHLCV, Viewport, VisibleRange, Point
from ..core.events import EventBus, EventType


@dataclass(slots=True)
class TimeScale:
    """Time scale state and spacing metrics."""
    bar_spacing: float = 8.0  # Pixels per bar centerline
    offset: float = 0.0      # Pixel offset for panning
    min_bar_spacing: float = 1.0
    max_bar_spacing: float = 200.0


@dataclass(slots=True)
class PriceScale:
    """Price scale state and range bounds."""
    min_price: float = 0.0
    max_price: float = 1.0
    top_padding: float = 0.08    # 8% top margin
    bottom_padding: float = 0.08 # 8% bottom margin
    is_log: bool = False
    is_auto: bool = True
    fixed_range: bool = False  # For indicators with fixed ranges like RSI (0-100)

    @property
    def price_range(self) -> float:
        return max(1e-6, self.max_price - self.min_price)


class CoordinateEngine:
    """Bi-directional coordinate transformation engine."""

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._time_scale = TimeScale()
        self._price_scale = PriceScale()
        self._price_scales: Dict[str, PriceScale] = {"candlestick": self._price_scale}  # Per-pane price scales
        self._viewports: Dict[str, Viewport] = {}  # Per-pane viewports
        self._viewport = Viewport()
        self._visible_range = VisibleRange()

    @property
    def time_scale(self) -> TimeScale:
        return self._time_scale

    @property
    def price_scale(self) -> PriceScale:
        return self._price_scale

    @property
    def viewport(self) -> Viewport:
        return self._viewport

    @property
    def visible_range(self) -> VisibleRange:
        return self._visible_range

    def set_viewport(self, viewport: Viewport) -> None:
        """Set pixel viewport bounds for chart area."""
        self._viewport = viewport
        # Update main candlestick viewport
        self._viewports["candlestick"] = viewport

    def set_pane_viewport(self, pane_name: str, viewport: Viewport) -> None:
        """Set viewport for a specific pane."""
        self._viewports[pane_name] = viewport

    def get_pane_viewport(self, pane_name: str) -> Viewport:
        """Get viewport for a specific pane."""
        return self._viewports.get(pane_name, self._viewport)

    def set_pane_price_scale(self, pane_name: str, min_price: float, max_price: float, emit_event: bool = False) -> None:
        """Set price range for a specific pane."""
        if pane_name not in self._price_scales:
            self._price_scales[pane_name] = PriceScale()
        ps = self._price_scales[pane_name]

        rng = max_price - min_price
        if rng <= 0:
            rng = 1.0

        # Apply visual padding so lines don't sit flush against pane edges.
        # fixed_range panes (e.g. RSI 0-100) use the same padding logic; the
        # flag's purpose is only to prevent the auto-scaler from overwriting
        # the range later (see _update_price_scale in widget.py).
        top_pad = rng * ps.top_padding
        bot_pad = rng * ps.bottom_padding
        new_min = min_price - bot_pad
        new_max = max_price + top_pad

        # Check if the values actually changed to prevent infinite feedback loops
        if (abs(ps.min_price - new_min) < 1e-9 and
                abs(ps.max_price - new_max) < 1e-9):
            return

        ps.min_price = new_min
        ps.max_price = new_max

        # Only emit event if requested (not during normal rendering)
        if emit_event:
            self._event_bus.emit_new(
                EventType.SCALE_CHANGED,
                self,
                min_price=ps.min_price,
                max_price=ps.max_price
            )

        # Only emit event if requested (not during normal rendering)
        if emit_event:
            self._event_bus.emit_new(
                EventType.SCALE_CHANGED,
                self,
                min_price=ps.min_price,
                max_price=ps.max_price
            )

    def get_pane_price_scale(self, pane_name: str) -> PriceScale:
        """Get price scale for a specific pane."""
        return self._price_scales.get(pane_name, self._price_scale)

    def set_visible_range(self, start_idx: int, end_idx: int, total_bars: int) -> None:
        """Update visible bar index window."""
        self._visible_range.start_index = max(0, start_idx)
        self._visible_range.end_index = min(total_bars, end_idx)
        self._visible_range.bar_count = total_bars

    def set_price_range(self, min_price: float, max_price: float, emit_event: bool = False) -> None:
        """Set price range with top and bottom percentage margins."""
        rng = max_price - min_price
        if rng <= 0:
            rng = 1.0

        top_pad = rng * self._price_scale.top_padding
        bot_pad = rng * self._price_scale.bottom_padding

        new_min = min_price - bot_pad
        new_max = max_price + top_pad

        # Check if the values actually changed to prevent infinite feedback loops
        if (abs(self._price_scale.min_price - new_min) < 1e-9 and 
            abs(self._price_scale.max_price - new_max) < 1e-9):
            return

        self._price_scale.min_price = new_min
        self._price_scale.max_price = new_max

        # Only emit event if requested (not during normal rendering)
        if emit_event:
            self._event_bus.emit_new(
                EventType.SCALE_CHANGED,
                self,
                min_price=self._price_scale.min_price,
                max_price=self._price_scale.max_price
            )

    # --- Conversions ---
    def index_to_x(self, index: float) -> float:
        """Convert bar index (float/int) to Canvas X pixel coordinate."""
        return self._viewport.left + self._time_scale.offset + index * self._time_scale.bar_spacing

    def x_to_index(self, x: float) -> float:
        """Convert Canvas X pixel coordinate to bar index (float for sub-bar accuracy)."""
        if self._time_scale.bar_spacing <= 0:
            return 0.0
        return (x - self._viewport.left - self._time_scale.offset) / self._time_scale.bar_spacing

    def price_to_y(self, price: float, viewport: Optional[Viewport] = None, pane: str = "candlestick", clip: bool = False) -> float:
        """Convert price to Canvas Y pixel coordinate inside given or default viewport.

        Args:
            price: The value to convert.
            viewport: Pane viewport to use; defaults to the main chart viewport.
            pane: Which pane's price scale to use for the conversion.
            clip: When True, clamp the result to [vp.top, vp.bottom] so that
                  out-of-range values never escape the pane boundary.  Pass
                  clip=True for all subplot (non-candlestick) indicator
                  rendering to get the general overflow-protection behaviour.
        """
        vp = viewport or self._viewport
        ps = self.get_pane_price_scale(pane)

        if vp.height <= 0:
            return vp.bottom

        price_range = ps.price_range
        if ps.is_log and price > 0 and ps.min_price > 0:
            log_min = math.log10(ps.min_price)
            log_max = math.log10(ps.max_price)
            log_p = math.log10(price)
            ratio = (log_p - log_min) / max(1e-6, (log_max - log_min))
        else:
            ratio = (price - ps.min_price) / price_range

        y = vp.bottom - ratio * vp.height
        if clip:
            y = max(vp.top, min(vp.bottom, y))
        return y

    def y_to_price(self, y: float, viewport: Optional[Viewport] = None, pane: str = "candlestick") -> float:
        """Convert Canvas Y pixel coordinate to price."""
        vp = viewport or self._viewport
        ps = self.get_pane_price_scale(pane)

        if vp.height <= 0:
            return ps.min_price

        ratio = (vp.bottom - y) / vp.height
        price_range = ps.price_range

        if ps.is_log and ps.min_price > 0:
            log_min = math.log10(ps.min_price)
            log_max = math.log10(ps.max_price)
            log_p = log_min + ratio * (log_max - log_min)
            return 10 ** log_p
        else:
            return ps.min_price + ratio * price_range

    def get_bar_width(self) -> float:
        """Bar body width in pixels (80% of spacing)."""
        return max(1.0, self._time_scale.bar_spacing * 0.8)

    def get_wick_width(self) -> float:
        """Wick line width in pixels."""
        return max(1.0, math.floor(self._time_scale.bar_spacing * 0.1))

    # --- Pan & Zoom ---
    def zoom(self, factor: float, anchor_x: Optional[float] = None) -> None:
        """Zoom time scale by factor around anchor_x pixel coordinate."""
        old_spacing = self._time_scale.bar_spacing
        new_spacing = max(
            self._time_scale.min_bar_spacing,
            min(self._time_scale.max_bar_spacing, old_spacing * factor)
        )

        if anchor_x is not None:
            anchor_idx = self.x_to_index(anchor_x)
            self._time_scale.offset = anchor_x - self._viewport.left - anchor_idx * new_spacing

        self._time_scale.bar_spacing = new_spacing
        self._event_bus.emit_new(EventType.SCALE_CHANGED, self, bar_spacing=new_spacing)

    def pan(self, delta_x: float) -> None:
        """Pan time scale by delta pixels."""
        self._time_scale.offset += delta_x
        self._event_bus.emit_new(EventType.SCALE_CHANGED, self, offset=self._time_scale.offset)

    def fit_range(self, start_idx: int, end_idx: int) -> None:
        """Fit visible range to show bars from start_idx to end_idx."""
        count = end_idx - start_idx
        if count <= 0 or self._viewport.width <= 0:
            return
        self._time_scale.bar_spacing = self._viewport.width / count
        self._time_scale.offset = -start_idx * self._time_scale.bar_spacing
        self._event_bus.emit_new(EventType.SCALE_CHANGED, self)


class ClippingCoordinateProxy:
    """Transparent proxy around CoordinateEngine that clips price_to_y output.

    When an indicator calls ``price_to_y(val, vp, pane)`` through this proxy
    the returned Y value is guaranteed to lie within ``[vp.top, vp.bottom]``.
    This prevents any subplot indicator — present or future — from painting
    outside its pane boundary regardless of scale mismatches or edge cases.

    All other CoordinateEngine attributes and methods are forwarded unchanged
    via ``__getattr__``, so indicators cannot tell the difference.
    """

    def __init__(self, engine: CoordinateEngine, pane_viewport: Viewport) -> None:
        # Store under mangled names so __getattr__ doesn't recurse on them.
        self.__dict__["_engine"] = engine
        self.__dict__["_pane_vp"] = pane_viewport

    # Override only the one method that needs clipping.
    def price_to_y(self, price: float, viewport: Optional[Viewport] = None, pane: str = "candlestick", clip: bool = False) -> float:  # noqa: D401
        """Delegate to the real engine with clip=True enforced."""
        return self._engine.price_to_y(price, viewport, pane, clip=True)

    def __getattr__(self, name: str):  # type: ignore[return]
        """Forward every other attribute/method to the wrapped engine."""
        return getattr(self._engine, name)
