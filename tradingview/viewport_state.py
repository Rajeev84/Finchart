"""
FinChart TradingView Viewport State module (Layer 1.4 Foundation).
Manages viewport navigation bounds and per-pane price ranges.
"""

from typing import Dict, Tuple, Optional
from .constants import DEFAULT_BAR_SPACING, MIN_BAR_SPACING, MAX_BAR_SPACING, DEFAULT_RIGHT_OFFSET


class ViewportState:
    """Stores active viewport state separately from layout and persistent chart configuration."""
    def __init__(self):
        self.visible_start: float = 0.0
        self.visible_end: float = 100.0
        self.bar_spacing: float = DEFAULT_BAR_SPACING
        self.min_bar_spacing: float = MIN_BAR_SPACING
        self.max_bar_spacing: float = MAX_BAR_SPACING
        self.right_offset: float = DEFAULT_RIGHT_OFFSET
        self.follow_latest: bool = True
        self.fix_left_edge: bool = False
        self.fix_right_edge: bool = False
        self.pane_price_ranges: Dict[str, Tuple[float, float]] = {}

    def set_pane_price_range(self, pane_id: str, p_min: float, p_max: float) -> None:
        self.pane_price_ranges[pane_id] = (p_min, p_max)

    def get_pane_price_range(self, pane_id: str) -> Tuple[float, float]:
        return self.pane_price_ranges.get(pane_id, (0.0, 100.0))

    def get_visible_start(self) -> float:
        return self.visible_start

    def get_visible_end(self) -> float:
        return self.visible_end

    def get_visible_range(self) -> Tuple[float, float]:
        return self.visible_start, self.visible_end

    def get_bar_spacing(self) -> float:
        return self.bar_spacing

    def get_right_offset(self) -> float:
        return self.right_offset

    def get_follow_latest(self) -> bool:
        return self.follow_latest

    def set_visible_range(self, visible_start: float, visible_end: float) -> None:
        if visible_end <= visible_start:
            raise ValueError("visible_end must be greater than visible_start")
        self.visible_start = visible_start
        self.visible_end = visible_end

    def set_bar_spacing(self, spacing: float) -> None:
        if spacing <= 0:
            raise ValueError("bar_spacing must be greater than zero")
        if self.max_bar_spacing > 0.0:
            spacing = min(spacing, self.max_bar_spacing)
        self.bar_spacing = max(spacing, self.min_bar_spacing)

    def visible_count(self, chart_width: float) -> float:
        """Calculate how many logical bars fit in the given chart width."""
        if self.bar_spacing <= 0:
            return 0.0
        return chart_width / self.bar_spacing

    def pan_by_bars(self, delta_bars: float) -> None:
        """Pan the viewport horizontally by a number of logical bars.

        Positive delta_bars moves the content to the right (visible window shifts left),
        matching the convention used by `GestureEngine` which computes delta from pixel drag.
        """
        self.visible_start -= delta_bars
        self.visible_end -= delta_bars
        self.follow_latest = False

    def render_start(self, overscan: int = 20) -> int:
        """Return the first integer index to render, applying overscan and clamping at 0."""
        first = int(self.visible_start // 1) - overscan
        return max(0, first)

    def render_end(self, overscan: int = 20, data_count: Optional[int] = None) -> int:
        """Return the last integer index to render, applying overscan and optional data_count clamp."""
        last = int(-(-self.visible_end // 1)) + overscan  # ceil visible_end
        if data_count is not None and data_count >= 0:
            last = min(last, max(0, data_count - 1))
        return last

    def visible_range_object(self, chart_width: float, overscan: int = 20, data_count: Optional[int] = None) -> Dict[str, float]:
        """Return a dict with visible_from, visible_to, render_first, render_last."""
        visible_from = self.visible_start
        visible_to = self.visible_end
        render_first = self.render_start(overscan)
        render_last = self.render_end(overscan, data_count)
        return {
            "visible_from": visible_from,
            "visible_to": visible_to,
            "render_first": render_first,
            "render_last": render_last,
        }

# Added Features:
# - ViewportState holding bar spacing, visible start/end indices, and per-pane price bounds.
