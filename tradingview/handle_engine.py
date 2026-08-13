"""
FinChart Drawing Handle Engine (Layer 1.7).

Formalizes interactive handles for drawing objects.  A *handle* is the
small interactive control point shown around a selected (or
in-progress) drawing that lets the user resize, move, or rotate it.

The engine is the single source of truth for:

* **Handle definition**          (1.7.1) — ``Handle`` data model + ``HandleRole`` enum
* **Handle geometry calculation** (1.7.2) — screen-space positions for every handle
* **Handle rendering**            (1.7.3) — serialisation to a renderer payload
* **Handle visibility**           (1.7.4) — deciding *which* handles to show
* **Handle hit testing**          (1.7.5) — fast nearest-handle queries
* **Handle semantic roles**       (1.7.6) — role assignment per drawing type

Architecture notes
------------------
* ``HandleEngine`` is intentionally stateless — every public method is a
  ``classmethod`` so it can be used without instantiation and shared
  freely across ``DrawingObject``, ``DrawingHitTester`` and
  ``DrawingRenderer``.
* To avoid a circular import (``drawing_primitives`` must not import
  ``handle_engine`` at module load time because the reverse dependency
  exists), ``DrawingObject.build_handles`` performs a *lazy* import.
"""
from __future__ import annotations

import math
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple


# ---------------------------------------------------------------------------
# 1.7.1  Handle definition
# ---------------------------------------------------------------------------

class HandleRole(Enum):
    """Semantic roles a handle can play on a drawing object.

    * ``START`` / ``END``  — endpoints of a line, ray or arrow (resize).
    * ``CORNER``           — corners of a rectangle / box (resize).
    * ``EDGE``             — edge midpoints of a rectangle / box (resize).
    * ``MIDDLE``           — midpoint of a line segment (translation).
    * ``CENTER``           — centre of a rectangle / box (translation).
    * ``ROTATE``           — dedicated rotation pivot handle.
    * ``ANCHOR``           — generic anchor when no semantic role applies.
    """
    START = "start"
    END = "end"
    CORNER = "corner"
    EDGE = "edge"
    MIDDLE = "middle"
    CENTER = "center"
    ROTATE = "rotate"
    ANCHOR = "anchor"


@dataclass
class Handle:
    """A single interactive handle belonging to a drawing object.

    Attributes:
        handle_id:    Stable, *semantic* identifier (e.g. ``"handle_start"``).
        drawing_id:   Id of the owning drawing.
        role:         The :class:`HandleRole` describing this handle's meaning.
        anchor_index: Index into the drawing's ``anchors`` list (``-1`` for
                      synthetic handles such as ``MIDDLE`` / ``CENTER``).
        x / y:        Screen-space pixel coordinates of the handle centre.
        radius:       Visual radius **and** default hit tolerance in pixels.
        logical_index / price:  Underlying data coordinates (``None`` for
                                synthetic handles).
        visible:      Whether the handle should be rendered.
    """
    handle_id: str
    drawing_id: str
    role: HandleRole
    anchor_index: int
    x: float = 0.0
    y: float = 0.0
    radius: float = 4.0
    logical_index: Optional[float] = None
    price: Optional[float] = None
    visible: bool = True

    def distance_to(self, px: float, py: float) -> float:
        """Pixel distance from this handle's centre to *(px, py)*."""
        return math.hypot(self.x - px, self.y - py)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a render-payload dict (role included)."""
        return {
            "x": self.x,
            "y": self.y,
            "radius": self.radius,
            "handle_id": self.handle_id,
            "role": self.role.value,
            "anchor_index": self.anchor_index,
        }


# ---------------------------------------------------------------------------
# HandleEngine
# ---------------------------------------------------------------------------

class HandleEngine:
    """Stateless coordinator for computing, hit-testing, filtering and
    serialising interactive drawing handles."""

    # Drawing types whose two real anchors are semantic endpoints.
    LINE_TYPES = frozenset({
        "line", "trend_line", "ray", "ray_line", "arrow",
        "trend_line_channel", "horizontal_ray", "vertical_line",
    })

    # Drawing types whose anchors are rectangle corners.
    RECT_TYPES = frozenset({
        "rectangle", "box", "rect", "recticle", "price_channel",
        "equilateral_triangle", " triangle",
    })

    #: Default handle radius (px) when the drawing style does not specify one.
    DEFAULT_RADIUS = 4.0

    # ------------------------------------------------------------------ #
    # 1.7.2  Handle geometry calculation
    # ------------------------------------------------------------------ #

    @classmethod
    def compute_handles(
        cls,
        drawing: Any,
        time_scale: Any,
        price_scale: Any,
        default_radius: Optional[float] = None,
    ) -> List[Handle]:
        """Calculate every handle for *drawing* with geometry and roles.

        ``drawing`` is duck-typed — it must expose ``anchors`` (list of
        ``DrawingPoint``-like objects with ``logical_index`` / ``price``),
        ``drawing_id``, ``drawing_type`` and optionally ``style`` (with a
        ``handle_radius`` attribute).
        """
        anchors = getattr(drawing, "anchors", []) or []
        drawing_id = getattr(drawing, "drawing_id", "")
        drawing_type = getattr(drawing, "drawing_type", "") or ""
        style = getattr(drawing, "style", None)
        radius = cls._resolve_radius(style, default_radius)

        handles: List[Handle] = []
        for i, anchor in enumerate(anchors):
            x = time_scale.index_to_x(anchor.logical_index)
            y = price_scale.price_to_y(anchor.price)
            role = cls._role_for_anchor(drawing_type, i, len(anchors))
            handles.append(Handle(
                handle_id=cls._handle_id(role, i),
                drawing_id=drawing_id,
                role=role,
                anchor_index=i,
                x=x,
                y=y,
                radius=radius,
                logical_index=anchor.logical_index,
                price=anchor.price,
            ))

        # Optional synthetic handles (move / centre) --------------------------------
        if drawing_type in cls.LINE_TYPES and len(anchors) == 2:
            handles.append(cls._midpoint_handle(drawing, handles, radius))
        elif drawing_type in cls.RECT_TYPES and len(anchors) == 4:
            handles.extend(cls._rect_extra_handles(drawing, handles, radius))

        return handles

    # ------------------------------------------------------------------ #
    # 1.7.6  Handle semantic roles
    # ------------------------------------------------------------------ #

    @classmethod
    def _role_for_anchor(cls, drawing_type: str, index: int, count: int) -> HandleRole:
        """Assign a semantic role to an anchor based on drawing type & position."""
        dt = (drawing_type or "").strip().lower()

        if dt in cls.LINE_TYPES:
            if count >= 2:
                if index == 0:
                    return HandleRole.START
                if index == count - 1:
                    return HandleRole.END
            return HandleRole.ANCHOR

        if dt in cls.RECT_TYPES:
            # Every anchor on a rectangle is a corner.
            return HandleRole.CORNER

        return HandleRole.ANCHOR

    @classmethod
    def _handle_id(cls, role: HandleRole, index: int) -> str:
        """Render a stable, human-readable handle id from role + index."""
        if role in (HandleRole.START, HandleRole.END, HandleRole.MIDDLE,
                    HandleRole.CENTER, HandleRole.ROTATE):
            return f"handle_{role.value}"
        return f"handle_{role.value}_{index}"

    # ------------------------------------------------------------------ #
    # 1.7.3  Handle rendering payload
    # ------------------------------------------------------------------ #

    @classmethod
    def to_render_payload(
        cls, handles: List[Handle], visible_only: bool = True
    ) -> List[Dict[str, Any]]:
        """Serialise handles into the dict format consumed by
        :meth:`CanvasAdapter.draw_handles`."""
        out: List[Dict[str, Any]] = []
        for h in handles:
            if visible_only and not h.visible:
                continue
            out.append(h.to_dict())
        return out

    # ------------------------------------------------------------------ #
    # 1.7.4  Handle visibility
    # ------------------------------------------------------------------ #

    @classmethod
    def filter_visible(
        cls,
        handles: List[Handle],
        *,
        selected: bool = False,
        is_drawing: bool = False,
        locked: bool = False,
    ) -> List[Handle]:
        """Return the subset of handles that should be rendered.

        Handles are shown when the owning drawing is **selected** or is
        currently being **created** (``is_drawing``).  A **locked** drawing
        never shows handles.  Within a visible set each handle's own
        ``visible`` flag is respected.
        """
        if locked:
            return []
        if not (selected or is_drawing):
            return []
        return [h for h in handles if h.visible]

    # ------------------------------------------------------------------ #
    # 1.7.5  Handle hit testing
    # ------------------------------------------------------------------ #

    @classmethod
    def hit_test_handles(
        cls,
        handles: List[Handle],
        x: float,
        y: float,
        tolerance: Optional[float] = None,
        visible_only: bool = True,
    ) -> Optional[Handle]:
        """Return the nearest handle within *tolerance* of *(x, y)*.

        ``tolerance`` defaults to each handle's own ``radius`` when ``None``.
        When ``visible_only`` is ``True`` (the default) handles whose
        ``visible`` flag is ``False`` — e.g. synthetic *MIDDLE* / *CENTER*
        handles that are not currently shown — are skipped so that a
        click on empty space falls through to the body hit-test.
        """
        best: Optional[Handle] = None
        best_dist: float = float("inf")

        for h in handles:
            if visible_only and not h.visible:
                continue
            tol = h.radius if tolerance is None else max(tolerance, h.radius)
            dist = h.distance_to(x, y)
            if dist <= tol and dist < best_dist:
                best = h
                best_dist = dist

        return best

    # ------------------------------------------------------------------ #
    # helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _resolve_radius(style: Any, default_radius: Optional[float]) -> float:
        # An explicit *default_radius* parameter always wins; otherwise fall
        # back to the drawing style's handle_radius, then the engine default.
        if default_radius is not None:
            return float(default_radius)
        if style is not None:
            r = getattr(style, "handle_radius", None)
            if r is not None and r > 0:
                return float(r)
        return HandleEngine.DEFAULT_RADIUS

    @classmethod
    def _midpoint_handle(
        cls, drawing: Any, handles: List[Handle], radius: float
    ) -> Handle:
        """Build the synthetic MIDDLE (translation) handle for a 2-point line."""
        start, end = handles[0], handles[1]
        mx = (start.x + end.x) / 2.0
        my = (start.y + end.y) / 2.0
        mli = (start.logical_index + end.logical_index) / 2.0
        mpr = (start.price + end.price) / 2.0
        return Handle(
            handle_id="handle_middle",
            drawing_id=drawing.drawing_id,
            role=HandleRole.MIDDLE,
            anchor_index=-1,
            x=mx,
            y=my,
            radius=radius,
            logical_index=mli,
            price=mpr,
            visible=False,  # hidden by default; shown only for certain interactions
        )

    @classmethod
    def _rect_extra_handles(
        cls, drawing: Any, handles: List[Handle], radius: float
    ) -> List[Handle]:
        """Build synthetic CENTER + EDGE handles for a 4-corner rectangle."""
        xs = [h.x for h in handles]
        ys = [h.y for h in handles]
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0

        # CENTER (translation)
        center = Handle(
            handle_id="handle_center",
            drawing_id=drawing.drawing_id,
            role=HandleRole.CENTER,
            anchor_index=-1,
            x=cx,
            y=cy,
            radius=radius,
            logical_index=getattr(handles[0], "logical_index", None),
            price=getattr(handles[0], "price", None),
            visible=False,
        )

        # Four EDGE handles (midpoints of each side)
        edges: List[Handle] = []
        edge_specs: List[Tuple[str, float, float]] = [
            ("left",   x0, cy),
            ("right",  x1, cy),
            ("top",    cx, y0),
            ("bottom", cx, y1),
        ]
        for name, ex, ey in edge_specs:
            edges.append(Handle(
                handle_id=f"handle_edge_{name}",
                drawing_id=drawing.drawing_id,
                role=HandleRole.EDGE,
                anchor_index=-1,
                x=ex,
                y=ey,
                radius=radius,
                logical_index=None,
                price=None,
                visible=False,
            ))

        return [center, *edges]

    # ------------------------------------------------------------------ #
    # Convenience: build handles for a raw list of point dicts
    # ------------------------------------------------------------------ #

    @classmethod
    def compute_handles_from_points(
        cls,
        drawing_id: str,
        drawing_type: str,
        points: List[Dict[str, Any]],
        time_scale: Any,
        price_scale: Any,
        default_radius: Optional[float] = None,
    ) -> List[Handle]:
        """Fallback handle computation for objects that only expose raw
        ``points`` dicts (e.g. legacy ``DrawingAPI`` wrappers)."""
        radius = default_radius if default_radius is not None else cls.DEFAULT_RADIUS
        handles: List[Handle] = []
        for i, p in enumerate(points):
            if "logical_index" in p and "price" in p:
                x = time_scale.index_to_x(float(p["logical_index"]))
                y = price_scale.price_to_y(float(p["price"]))
            elif "x" in p and "y" in p:
                x, y = float(p["x"]), float(p["y"])
            else:
                continue
            role = cls._role_for_anchor(drawing_type, i, len(points))
            handles.append(Handle(
                handle_id=cls._handle_id(role, i),
                drawing_id=drawing_id,
                role=role,
                anchor_index=i,
                x=x,
                y=y,
                radius=radius,
                logical_index=float(p.get("logical_index", 0.0)),
                price=float(p.get("price", 0.0)),
            ))
        return handles


# Added Features:
# - HandleRole enum with semantic roles (START, END, CORNER, EDGE, MIDDLE, CENTER, ROTATE, ANCHOR)
# - Handle dataclass carrying id, role, geometry, and data-coordinate mirrors
# - HandleEngine: stateless classmethods for compute, render-payload, visibility filter, and hit testing
