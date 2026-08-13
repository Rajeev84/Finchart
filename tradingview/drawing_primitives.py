"""
Drawing primitive contracts and basic operations for Layer 1.2.

Defines DrawingPoint, DrawingStyle, and DrawingObject with minimal
validation and geometry helper stubs used by renderers and commands.
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Tuple


@dataclass
class DrawingHitResult:
    """Categorized hit-test result for a drawing object.

    Attributes:
        drawing_id: The id of the drawing that was hit.
        region: One of "BODY", "HANDLE", or "ENDPOINT".
        handle_index: Index of the handle/endpoint that was hit (if region is HANDLE/ENDPOINT).
        handle_id: Semantic handle id (e.g. ``"handle_start"``) when region is HANDLE.
        handle_role: Semantic handle role value (e.g. ``"start"``) when region is HANDLE.
        distance: Pixel distance from the cursor to the hit element.
    """
    drawing_id: str
    region: str  # "BODY", "HANDLE", "ENDPOINT"
    handle_index: Optional[int] = None
    handle_id: Optional[str] = None
    handle_role: Optional[str] = None
    distance: float = 0.0


@dataclass
class DrawingPoint:
    logical_index: float
    price: float

    def to_dict(self) -> Dict[str, float]:
        return {"logical_index": self.logical_index, "price": self.price}


@dataclass
class DrawingStyle:
    stroke_color: str = "#2962FF"
    stroke_width: float = 2.0
    stroke_style: str = "SOLID"
    stroke_opacity: float = 1.0
    fill_enabled: bool = False
    fill_color: str = "#2962FF"
    fill_opacity: float = 0.1
    handle_radius: float = 4.0


@dataclass
class DrawingObject:
    drawing_id: str
    drawing_type: str
    anchors: List[DrawingPoint] = field(default_factory=list)
    style: DrawingStyle = field(default_factory=DrawingStyle)
    visible: bool = True
    locked: bool = False
    selected: bool = False
    z_order: int = 100
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.drawing_id:
            raise ValueError("drawing_id must be non-empty")
        if not isinstance(self.drawing_type, str) or not self.drawing_type:
            raise ValueError("drawing_type must be a non-empty string")
        if self.z_order is None:
            raise ValueError("z_order must be numeric")
        if self.style.stroke_width <= 0:
            raise ValueError("stroke_width must be > 0")

    def calculate_geometry(self, time_scale: Any, price_scale: Any) -> Dict[str, Any]:
        """Calculate screen-space geometry for rendering.

        This is a minimal implementation that converts anchors to pixel coords.
        """
        points = []
        for a in self.anchors:
            x = time_scale.index_to_x(a.logical_index)
            y = price_scale.price_to_y(a.price)
            points.append({"x": x, "y": y})
        return {"points": points}

    def _distance_to_segment(self, px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
        """Return the shortest distance from point (px, py) to the segment (x1,y1)-(x2,y2)."""
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0 and dy == 0:
            return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
        t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
        t = max(0.0, min(1.0, t))
        closest_x = x1 + t * dx
        closest_y = y1 + t * dy
        return ((px - closest_x) ** 2 + (py - closest_y) ** 2) ** 0.5

    def _point_in_rect(self, px: float, py: float, x1: float, y1: float, x2: float, y2: float, tolerance: float) -> bool:
        """Return True if point (px, py) is within the rect expanded by tolerance."""
        min_x = min(x1, x2) - tolerance
        max_x = max(x1, x2) + tolerance
        min_y = min(y1, y2) - tolerance
        max_y = max(y1, y2) + tolerance
        return min_x <= px <= max_x and min_y <= py <= max_y

    def hit_test(
        self,
        mouse_x: float,
        mouse_y: float,
        time_scale: Any,
        price_scale: Any,
        tolerance: float = 6.0,
        handle_tolerance: Optional[float] = None
    ) -> Optional[DrawingHitResult]:
        """Perform a categorized hit test against this drawing.

        Priority:
        1. Handles/endpoints (within handle_tolerance, defaults to style.handle_radius + tolerance)
        2. Body (within tolerance)

        Returns a DrawingHitResult or None if no hit.
        """
        if not self.visible:
            return None
        geom = self.calculate_geometry(time_scale, price_scale)
        points = geom["points"]
        if not points:
            return None

        if handle_tolerance is None:
            handle_tolerance = self.style.handle_radius + tolerance

        # 1. Check handles/endpoints first (higher priority) — via Handle Engine (1.7.5)
        from .handle_engine import HandleEngine
        handles = HandleEngine.compute_handles(self, time_scale, price_scale)
        hit_handle = HandleEngine.hit_test_handles(
            handles, mouse_x, mouse_y,
            tolerance=handle_tolerance, visible_only=True
        )
        if hit_handle is not None:
            return DrawingHitResult(
                drawing_id=self.drawing_id,
                region="HANDLE",
                handle_index=hit_handle.anchor_index,
                handle_id=hit_handle.handle_id,
                handle_role=hit_handle.role.value,
                distance=hit_handle.distance_to(mouse_x, mouse_y)
            )

        # 2. Check body
        if len(points) == 1:
            # Single-point drawing (e.g. text): treat as point body
            dx = points[0]["x"] - mouse_x
            dy = points[0]["y"] - mouse_y
            if (dx * dx + dy * dy) ** 0.5 <= tolerance:
                return DrawingHitResult(
                    drawing_id=self.drawing_id,
                    region="BODY",
                    distance=(dx * dx + dy * dy) ** 0.5
                )
        elif len(points) == 2:
            # Line-like: distance to segment
            dist = self._distance_to_segment(
                mouse_x, mouse_y,
                points[0]["x"], points[0]["y"],
                points[1]["x"], points[1]["y"]
            )
            if dist <= tolerance:
                return DrawingHitResult(
                    drawing_id=self.drawing_id,
                    region="BODY",
                    distance=dist
                )
        else:
            # Polygon/rect-like: check if point is inside the bounding box (expanded by tolerance)
            xs = [p["x"] for p in points]
            ys = [p["y"] for p in points]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            if self._point_in_rect(mouse_x, mouse_y, min_x, min_y, max_x, max_y, tolerance):
                return DrawingHitResult(
                    drawing_id=self.drawing_id,
                    region="BODY",
                    distance=0.0
                )

        return None

    def get_bounds(self, time_scale: Any, price_scale: Any) -> Tuple[float, float, float, float]:
        geom = self.calculate_geometry(time_scale, price_scale)
        xs = [p["x"] for p in geom["points"]]
        ys = [p["y"] for p in geom["points"]]
        if not xs or not ys:
            return (0.0, 0.0, 0.0, 0.0)
        return (min(xs), min(ys), max(xs), max(ys))

    def move_by(self, logical_delta: float, price_delta: float) -> None:
        for a in self.anchors:
            a.logical_index += logical_delta
            a.price += price_delta

    def move_anchor(self, anchor_index: int, logical_index: float, price: float) -> None:
        if 0 <= anchor_index < len(self.anchors):
            self.anchors[anchor_index].logical_index = logical_index
            self.anchors[anchor_index].price = price

    def serialize(self) -> Dict[str, Any]:
        return {
            "drawing_id": self.drawing_id,
            "drawing_type": self.drawing_type,
            "anchors": [a.to_dict() for a in self.anchors],
            "style": asdict(self.style),
            "visible": self.visible,
            "locked": self.locked,
            "selected": self.selected,
            "z_order": self.z_order,
            "metadata": dict(self.metadata)
        }

    def build_handles(self, time_scale: Any, price_scale: Any) -> List[Any]:
        """Build rich :class:`~finchart.tradingview.handle_engine.Handle`
        objects for this drawing (Layer 1.7 — handle geometry calculation).

        Delegates to :class:`HandleEngine` to compute screen-space geometry
        and semantic roles.  A lazy import avoids a circular dependency
        (``drawing_primitives`` ←→ ``handle_engine``).
        """
        from .handle_engine import HandleEngine
        return HandleEngine.compute_handles(self, time_scale, price_scale)

    def get_handles(self, time_scale: Any, price_scale: Any) -> List[Dict[str, float]]:
        """Return visible handle positions (pixel coords) for each anchor.

        Delegates to :meth:`build_handles` and serialises only visible
        handles so the count matches the legacy one-handle-per-anchor
        behaviour.
        """
        from .handle_engine import HandleEngine
        handles = HandleEngine.compute_handles(self, time_scale, price_scale)
        return HandleEngine.to_render_payload(handles, visible_only=True)

    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> "DrawingObject":
        anchors = [DrawingPoint(a.get("logical_index", 0.0), a.get("price", 0.0)) for a in data.get("anchors", [])]
        style_data = data.get("style", {})
        style = DrawingStyle(**style_data) if style_data else DrawingStyle()
        return cls(
            drawing_id=data.get("drawing_id", ""),
            drawing_type=data.get("drawing_type", ""),
            anchors=anchors,
            style=style,
            visible=data.get("visible", True),
            locked=data.get("locked", False),
            selected=data.get("selected", False),
            z_order=data.get("z_order", 100),
            metadata=data.get("metadata", {})
        )
"""Drawing primitives for candle geometry.

Provides deterministic functions for candle and wick sizes based on spacing.
"""
import math


def candle_width(spacing: float) -> int:
    """Calculate an integer candle body width for a given spacing.

    Rules:
    - If spacing within special range 2.5–4.0, return 3 px.
    - Otherwise, apply a smoothing coefficient for larger spacing and
      floor the result. Constrain to [1, floor(spacing)].
    """
    if 2.5 <= spacing <= 4.0:
        return 3

    base = max(spacing, 4.0)
    x = base - 4.0
    # normalized using atan to smooth growth
    normalized = math.atan(x) / (math.pi * 0.5)
    coeff = 1.0 - 0.2 * normalized
    width = math.floor(spacing * coeff)
    width = min(width, math.floor(spacing))
    return max(1, int(width))


def wick_width() -> int:
    """Return the canonical wick width in pixels."""
    return 1
