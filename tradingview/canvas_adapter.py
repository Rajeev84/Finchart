from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class CanvasAdapter(ABC):
    @abstractmethod
    def draw_path(self, drawing_id: str, points: List[Dict[str, float]], style: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def draw_handles(self, drawing_id: str, handles: List[Dict[str, float]]) -> None:
        pass

    @abstractmethod
    def clear(self) -> None:
        pass


class StubCanvas(CanvasAdapter):
    """Test stub that records drawing commands for verification."""

    def __init__(self):
        self.commands: List[Any] = []

    def draw_path(self, drawing_id: str, points: List[Dict[str, float]], style: Dict[str, Any]) -> None:
        self.commands.append(("path", drawing_id, points, style))

    def draw_handles(self, drawing_id: str, handles: List[Dict[str, float]]) -> None:
        self.commands.append(("handles", drawing_id, handles))

    def clear(self) -> None:
        self.commands.append(("clear",))
