"""Layout Engine - Multi-pane subplot partitioning engine.

Splits vertical chart height among subplots (Main Candlestick Pane, Volume Pane, RSI Pane, etc.)
based on relative weight ratios.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..core.types import Viewport, Rect


@dataclass
class SubplotPane:
    """Subplot pane definition."""
    name: str
    weight: float = 1.0
    overlay_on: Optional[str] = None
    min_y: float = 0.0
    max_y: float = 100.0
    viewport: Viewport = field(default_factory=Viewport)


class LayoutEngine:
    """Manages vertical partitioning of chart height into subplots."""

    def __init__(self) -> None:
        self._panes: Dict[str, SubplotPane] = {}
        # Create default main candlestick pane
        self.add_pane("candlestick", weight=3.0)

    @property
    def panes(self) -> Dict[str, SubplotPane]:
        return self._panes

    def add_pane(self, name: str, weight: float = 1.0, overlay_on: Optional[str] = None) -> SubplotPane:
        """Add or update a subplot pane."""
        pane = SubplotPane(name=name, weight=weight, overlay_on=overlay_on)
        self._panes[name] = pane
        return pane

    def remove_pane(self, name: str) -> bool:
        """Remove a subplot pane (cannot remove main 'candlestick' pane)."""
        if name == "candlestick" or name not in self._panes:
            return False
        del self._panes[name]
        return True

    def reset(self) -> None:
        """Reset layout back to single main candlestick pane."""
        self._panes = {}
        self.add_pane("candlestick", weight=3.0)

    def calculate_layout(self, chart_vp: Viewport) -> Dict[str, Viewport]:
        """Partition chart_vp height across non-overlay subplots based on weight ratios."""
        main_panes = [p for p in self._panes.values() if p.overlay_on is None]
        total_weight = sum(p.weight for p in main_panes)
        if total_weight <= 0:
            total_weight = 1.0

        current_y = chart_vp.top
        total_h = chart_vp.height

        # Subtract axis margins from total height for chart area
        from ..rendering.grid import GridStyle
        axis_height = GridStyle().time_axis_height
        chart_area_h = total_h - axis_height  # Reserve space for time axis at bottom

        result: Dict[str, Viewport] = {}

        for pane in main_panes:
            h = (pane.weight / total_weight) * chart_area_h
            pane_vp = Viewport(
                x=chart_vp.left,
                y=current_y,
                width=chart_vp.width,
                height=h
            )
            pane.viewport = pane_vp
            result[pane.name] = pane_vp
            current_y += h

        # Map overlays to target pane viewport
        for pane in self._panes.values():
            if pane.overlay_on and pane.overlay_on in result:
                pane.viewport = result[pane.overlay_on]
                result[pane.name] = pane.viewport

        return result

    def get_pane_count(self) -> int:
        """Get number of non-overlay panes."""
        return len([p for p in self._panes.values() if p.overlay_on is None])
