"""
FinChart TradingView Input Adapter module (Layer 1.7).
Abstract baseline and helper utilities for normalizing framework-specific input events into FinChart events.
"""

from abc import ABC, abstractmethod
from typing import Any
from .input_events import PointerEvent, WheelEvent, KeyboardEvent, TouchEvent, FocusEvent, ResizeEvent


class InputAdapter(ABC):
    """Abstract interface for platform-specific raw event listeners."""

    @abstractmethod
    def bind(self, container_widget: Any) -> None:
        """Binds low-level toolkit events (Tk, Qt, Web, etc.) to normalized input engine callbacks."""
        pass

    @abstractmethod
    def unbind(self) -> None:
        """Detaches event listeners."""
        pass

# Added Features:
# - Abstract InputAdapter interface for framework-independent event binding.
