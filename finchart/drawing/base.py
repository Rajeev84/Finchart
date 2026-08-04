"""Drawing Tools Base - Abstract DrawingTool ABC contract.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

from ..core.types import Point, Color
from ..coordinates.engine import CoordinateEngine
from ..rendering.pipeline import DrawCommand, Layer


@dataclass
class DrawingState:
    """State descriptor for a drawing shape."""
    tag: str
    tool_type: str
    points: List[Tuple[Any, float]]  # (timestamp or dt, price)
    color: Color = field(default_factory=lambda: Color(255, 159, 28))
    width: float = 2.0
    dash: Optional[Tuple[int, ...]] = None
    is_selected: bool = False
    pane_name: str = "candlestick"


class DrawingTool(ABC):
    """Abstract base class for all interactive drawing tools."""

    def __init__(self, state: DrawingState) -> None:
        self.state = state

    @abstractmethod
    def hit_test(self, px: float, py: float, coord_engine: CoordinateEngine) -> bool:
        """Check if point (px, py) hits the drawing shape or handles."""
        pass

    @abstractmethod
    def render_commands(self, coord_engine: CoordinateEngine, viewport: Optional[Any] = None) -> List[DrawCommand]:
        """Generate draw commands for rendering shape."""
        pass
