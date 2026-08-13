"""
Series abstractions for FinChart (Layer 1.12).
"""

from abc import ABC, abstractmethod
from typing import Any, List, Tuple


class Series(ABC):
    """Abstract base for a data series.
    Implementations must provide point management and length query.
    """

    @abstractmethod
    def add_point(self, point: Any) -> None:
        """Add a data point to the series."""

    @abstractmethod
    def remove_point(self, index: int) -> None:
        """Remove point at given index."""

    @abstractmethod
    def get_point(self, index: int) -> Any:
        """Retrieve point at index."""

    @abstractmethod
    def __len__(self) -> int:
        """Number of points in the series."""


class DerivedSeries(Series):
    """Series generated from computations on another series (e.g., indicator output)."""

    def __init__(self, source_series: Series, compute_func):
        self._source = source_series
        self._compute = compute_func
        self._cache: List[Any] = []
        self._recalculate()

    def _recalculate(self) -> None:
        self._cache = [self._compute(point) for point in self._source]

    def add_point(self, point: Any) -> None:
        self._source.add_point(point)
        self._cache.append(self._compute(point))

    def remove_point(self, index: int) -> None:
        self._source.remove_point(index)
        del self._cache[index]

    def get_point(self, index: int) -> Any:
        return self._cache[index]

    def __len__(self) -> int:
        return len(self._cache)

    def __iter__(self):
        return iter(self._cache)
