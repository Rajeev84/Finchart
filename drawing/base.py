"""Drawing Tools Base - Abstract DrawingTool ABC contract.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
import uuid

from ..core.types import Point, Color
from ..coordinates.engine import CoordinateEngine
from ..rendering.pipeline import DrawCommand, Layer


@dataclass
class DrawingState:
    """Rich state descriptor for a drawing shape."""
    # Identity
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    tool_type: str = ""
    label: str = ""

    # Geometry (normalized coordinates)
    # For lines: points = [(index1, price1), (index2, price2)]
    # For hline: points = [(None, price)]
    # For vline: points = [(index, None)]
    points: List[Tuple[Optional[float], Optional[float]]] = field(default_factory=list)
    # Semantic time anchors for x-coordinates.  Runtime ``points`` remain
    # index/price pairs for rendering; anchors are the stable source of truth
    # across symbol/timeframe changes.  ``None`` is used where a point has no
    # time component (for example an hline).
    anchor_timestamps: List[Optional[float]] = field(default_factory=list)

    # Appearance
    color: Color = field(default_factory=lambda: Color(255, 165, 0))
    width: float = 2.0
    style: str = "solid"  # "solid", "dashed", "dotted"
    fill: Optional[Color] = None  # Fill color for shapes like Rectangle

    # State flags
    visible: bool = True
    selected: bool = False
    hovered: bool = False
    locked: bool = False

    # Computed (transient, not serialized)
    angle: Optional[float] = None
    pane_name: str = "candlestick"

    # Position/trade data
    quantity: float = 1.0

    # Legacy compatibility
    @property
    def tag(self) -> str:
        """Legacy property for backward compatibility."""
        return self.id

    @property
    def dash(self) -> Optional[Tuple[int, ...]]:
        """Legacy property converting style to dash tuple."""
        style_map = {"solid": (), "dashed": (4, 4), "dotted": (2, 2)}
        return style_map.get(self.style, ())

    @property
    def is_selected(self) -> bool:
        """Legacy property for backward compatibility."""
        return self.selected

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tool_type": self.tool_type,
            "label": self.label,
            "points": self.points,
            "anchor_timestamps": self.anchor_timestamps,
            "color": self.color.to_hex(),
            "width": self.width,
            "style": self.style,
            "fill": self.fill.to_hex() if self.fill else None,
            "visible": self.visible,
            "selected": self.selected,
            "hovered": self.hovered,
            "locked": self.locked,
            "pane_name": self.pane_name,
            "quantity": self.quantity,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DrawingState":
        fill_hex = data.get("fill")
        return cls(
            id=data.get("id", uuid.uuid4().hex),
            tool_type=data.get("tool_type", ""),
            label=data.get("label", ""),
            points=[tuple(point) for point in data.get("points", [])],
            anchor_timestamps=[
                float(ts) if ts is not None else None
                for ts in data.get("anchor_timestamps", [])
            ],
            color=Color.from_hex(data.get("color", "#FFA500")),
            width=data.get("width", 2.0),
            style=data.get("style", "solid"),
            fill=Color.from_hex(fill_hex) if fill_hex else None,
            visible=data.get("visible", True),
            selected=data.get("selected", False),
            hovered=data.get("hovered", False),
            locked=data.get("locked", False),
            pane_name=data.get("pane_name", "candlestick"),
            quantity=data.get("quantity", 1.0),
        )


class DrawingTool(ABC):
    """Abstract base class for all interactive drawing tools."""

    def __init__(self, state: DrawingState) -> None:
        self.state = state

    @abstractmethod
    def hit_test(self, px: float, py: float, coord_engine: CoordinateEngine, viewport: Optional[Any] = None) -> bool:
        """Check if point (px, py) hits the drawing shape or handles."""
        pass

    @abstractmethod
    def render_commands(self, coord_engine: CoordinateEngine, viewport: Optional[Any] = None) -> List[DrawCommand]:
        """Generate draw commands for rendering shape."""
        pass

    @abstractmethod
    def get_handles(self, coord_engine: CoordinateEngine, viewport: Optional[Any] = None) -> List[Tuple[float, float, str]]:
        """Return list of (x, y, handle_id) for selection handles."""
        pass

    def compute_angle(self, coord_engine: CoordinateEngine) -> Optional[float]:
        """Return angle in degrees for trend/angle lines. None for hline/vline."""
        return None

    def move_endpoint(self, handle_id: str, new_index: float, new_price: float) -> None:
        """Update geometry when user drags a handle."""
        pass

    def move_whole(self, d_index: float, d_price: float) -> None:
        """Translate entire shape by delta."""
        pass
