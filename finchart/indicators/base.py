"""Indicator Base Specification - Abstract Indicator contract and calculation result model.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from ..core.types import OHLCV, Color
from ..coordinates.engine import CoordinateEngine
from ..rendering.pipeline import DrawCommand, Layer


@dataclass
class IndicatorResult:
    """Numerical outputs calculated by an indicator."""
    values: Dict[str, List[Optional[float]]] = field(default_factory=dict)


class Indicator(ABC):
    """Abstract base class for all technical indicator plugins."""

    def __init__(self, name: str, params: Optional[Dict[str, Any]] = None, pane: str = "candlestick") -> None:
        self.name = name
        self.params = params or {}
        self.pane = pane  # Which pane this indicator belongs to
        self._last_result: Optional[IndicatorResult] = None

    @abstractmethod
    def calculate(self, data: List[OHLCV]) -> IndicatorResult:
        """Calculate indicator outputs from input OHLCV bars."""
        pass

    @abstractmethod
    def render_commands(
        self,
        coord_engine: CoordinateEngine,
        start_idx: int,
        end_idx: int,
        viewport: Optional[Any] = None
    ) -> List[DrawCommand]:
        """Generate draw commands for visible bar range."""
        pass

    def update(self, data: List[OHLCV]) -> IndicatorResult:
        """Calculate and update internal cache."""
        self._last_result = self.calculate(data)
        return self._last_result
