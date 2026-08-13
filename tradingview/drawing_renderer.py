"""
Minimal DrawingRenderer and DrawingResourcePool for Layer 1.2.

This renderer computes screen-space geometry for DrawingObject instances
and returns a lightweight render payload. It is intentionally decoupled
from any real Canvas so it is easy to test in unit tests.
"""
from typing import Dict, Any, List, Optional
from .drawing_primitives import DrawingObject
from .handle_engine import HandleEngine
from .canvas_adapter import CanvasAdapter

def _is_drawing_api(obj: Any) -> bool:
    # duck-typing: DrawingAPI exposes `points` list and a `_chart` reference
    return hasattr(obj, "points") and hasattr(obj, "_chart")


class DrawingResourcePool:
    """Simple pool tracking allocated rendering resources per drawing."""

    def __init__(self):
        self._resources: Dict[str, Dict[str, Any]] = {}

    def allocate(self, drawing_id: str, primitive_type: str) -> Dict[str, Any]:
        res = {"drawing_id": drawing_id, "primitive": primitive_type, "allocated": True}
        self._resources[drawing_id] = res
        return res

    def release(self, drawing_id: str) -> None:
        if drawing_id in self._resources:
            del self._resources[drawing_id]

    def get(self, drawing_id: str) -> Optional[Dict[str, Any]]:
        return self._resources.get(drawing_id)


class DrawingRenderer:
    def __init__(self, resource_pool: Optional[DrawingResourcePool] = None, canvas: Optional[CanvasAdapter] = None):
        self.pool = resource_pool or DrawingResourcePool()
        self.canvas = canvas

    def render_all(
        self,
        drawing_registry: Any,
        time_scale: Any,
        price_scales: Dict[str, Any],
        pane_order: Optional[Dict[str, int]] = None
    ) -> List[Dict[str, Any]]:
        """Compute render payloads for all visible drawings in the registry.

        Returns a list of dicts: {drawing_id, geometry, resource, pane_id}
        """
        out: List[Dict[str, Any]] = []

        # Collect render candidates with pane ordering, z-order, and creation index for stable sorting
        candidates: List[Dict[str, Any]] = []
        # Acquire creation order list if available
        creation_list = None
        if hasattr(drawing_registry, "_chart_state") and hasattr(drawing_registry._chart_state, "drawings"):
            creation_list = drawing_registry._chart_state.drawings

        for drawing_id, drawing in drawing_registry.items():
            # Determine pane and sort order for compositor grouping.
            pane_id = getattr(drawing, "pane_id", None)
            if pane_id is None and hasattr(drawing, "metadata") and isinstance(getattr(drawing, "metadata", None), dict):
                pane_id = drawing.metadata.get("pane_id", "pane_main")
            pane_id = pane_id or "pane_main"
            pane_index = pane_order.get(pane_id, 0) if pane_order is not None else 0

            # Internal DrawingObject: use its calculate_geometry
            if isinstance(drawing, DrawingObject):
                if not drawing.visible:
                    continue
                price_scale = price_scales.get(pane_id, price_scales.get("pane_main"))
                geom = drawing.calculate_geometry(time_scale, price_scale)
                z = getattr(drawing, "z_order", 100)
                # find creation index
                cidx = None
                if creation_list is not None:
                    for i, md in enumerate(creation_list):
                        if md.get("id") == drawing_id:
                            cidx = i
                            break
                candidates.append({
                    "drawing_id": drawing_id,
                    "geometry": geom,
                    "resource_type": drawing.drawing_type,
                    "z": z,
                    "pane_id": pane_id,
                    "pane_order": pane_index,
                    "creation_index": cidx if cidx is not None else 0,
                    "source": drawing
                })
                continue

            # DrawingAPI-like wrappers (duck-typed)
            if _is_drawing_api(drawing):
                # skip invisible
                if not getattr(drawing, "visible", True):
                    continue
                chart = getattr(drawing, "_chart", None)
                pane_id = getattr(drawing, "pane_id", "pane_main")
                pane_index = pane_order.get(pane_id, 0) if pane_order is not None else 0
                price_scale = price_scales.get(pane_id, price_scales.get("pane_main"))
                pts = []
                for p in getattr(drawing, "points", []) or []:
                    # p may be dict with logical_index/price, or x/y pixels, or x_percent/y_percent
                    if isinstance(p, dict) and "logical_index" in p and "price" in p:
                        x = time_scale.index_to_x(p["logical_index"])
                        y = price_scale.price_to_y(p["price"])
                    elif isinstance(p, dict) and "x" in p and "y" in p:
                        # pixel coords -> convert to logical/price where necessary
                        x = p["x"]
                        y = p["y"]
                    elif isinstance(p, dict) and "x_percent" in p and "y_percent" in p and chart is not None:
                        w = chart.options.dimensions.width
                        h = chart.options.dimensions.height
                        x = p["x_percent"] * w
                        y = p["y_percent"] * h
                    else:
                        # unknown format, skip
                        continue
                    pts.append({"x": x, "y": y})

                geom = {"points": pts}
                # determine z-order from drawing properties or metadata
                z = getattr(drawing, "z_order", None)
                if z is None and hasattr(drawing, "properties") and isinstance(drawing.properties, dict):
                    z = drawing.properties.get("z_order", 100)
                if z is None and creation_list is not None:
                    # attempt to find metadata z-order
                    for md in creation_list:
                        if md.get("id") == drawing_id:
                            z = md.get("z_order", 100)
                            break
                z = z if z is not None else 100
                # find creation index
                cidx = None
                if creation_list is not None:
                    for i, md in enumerate(creation_list):
                        if md.get("id") == drawing_id:
                            cidx = i
                            break
                candidates.append({
                    "drawing_id": drawing_id,
                    "geometry": geom,
                    "resource_type": getattr(drawing, "shape_type", "unknown"),
                    "z": z,
                    "pane_id": pane_id,
                    "pane_order": pane_index,
                    "creation_index": cidx if cidx is not None else 0,
                    "source": drawing
                })
                continue

        # Sort candidates by pane order, then z ascending, then creation_index ascending
        candidates.sort(key=lambda c: (c.get("pane_order", 0), c.get("z", 100), c.get("creation_index", 0)))

        # Clip against viewport and allocate resources for visible items
        w = getattr(time_scale, "width", None)
        for c in candidates:
            geom = c["geometry"]
            pts = geom.get("points", [])
            if not pts:
                continue
            xs = [p.get("x", 0.0) for p in pts]
            ys = [p.get("y", 0.0) for p in pts]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            pane_price_scale = price_scales.get(c.get("pane_id", "pane_main"), price_scales.get("pane_main"))
            pane_h = pane_price_scale.pane_height if pane_price_scale is not None else None

            outside = False
            if w is not None:
                if max_x < 0 or min_x > w:
                    outside = True
            if pane_h is not None:
                if max_y < 0 or min_y > pane_h:
                    outside = outside and True or outside or False
            if outside:
                continue

            resource = self.pool.allocate(c["drawing_id"], c.get("resource_type", "unknown"))
            # selection overlay and handles
            selection_overlay = None
            src = c.get("source")
            handles = None
            show_handles = False
            if isinstance(src, DrawingObject):
                if getattr(src, "selected", False):
                    show_handles = True
            else:
                # DrawingAPI-like object
                try:
                    chart = getattr(src, "_chart", None)
                    is_selected = chart and chart.selection_manager.is_selected(c["drawing_id"])
                    is_drawing = bool(getattr(src, "is_drawing", False))
                    points = getattr(src, "points", []) or []
                    if is_selected:
                        show_handles = True
                    elif is_drawing and len(points) == 2:
                        # Show endpoint handles during creation preview for 2-point shapes
                        show_handles = True
                except Exception:
                    show_handles = False

            if show_handles:
                # Handle Engine (1.7) — richer handles with semantic roles
                _pane_id = c.get("pane_id", "pane_main")
                _price_scale = price_scales.get(_pane_id, price_scales.get("pane_main"))
                if isinstance(src, DrawingObject):
                    _all_handles = src.build_handles(time_scale, _price_scale)
                else:
                    _all_handles = HandleEngine.compute_handles_from_points(
                        drawing_id=c["drawing_id"],
                        drawing_type=getattr(src, "shape_type", "trend_line"),
                        points=getattr(src, "points", []) or [],
                        time_scale=time_scale,
                        price_scale=_price_scale,
                    )
                handles = HandleEngine.to_render_payload(_all_handles, visible_only=True)
                selection_overlay = {"selected": bool(getattr(src, "selected", False)), "handles": handles}

            payload = {"drawing_id": c["drawing_id"], "geometry": geom, "resource": resource}
            if selection_overlay is not None:
                payload["selection"] = selection_overlay

            # Emit to canvas adapter if present
            if self.canvas is not None:
                # draw path
                style = {}
                src_obj = c.get("source")
                # prefer DrawingObject.style
                if isinstance(src_obj, DrawingObject):
                    style = {"stroke_color": src_obj.style.stroke_color, "stroke_width": src_obj.style.stroke_width}
                else:
                    style = getattr(src_obj, "properties", {}) or {}
                pts_for_canvas = geom.get("points", [])
                try:
                    self.canvas.draw_path(c["drawing_id"], pts_for_canvas, style)
                    if handles:
                        self.canvas.draw_handles(c["drawing_id"], handles)
                except Exception:
                    # canvas adapter errors should not break rendering pipeline
                    pass

            out.append(payload)

        return out


class RenderPipeline:
    """Composes drawing renderer output with overlay payloads such as crosshair."""

    def __init__(self, resource_pool: Optional[DrawingResourcePool] = None, canvas: Optional[CanvasAdapter] = None):
        self.renderer = DrawingRenderer(resource_pool=resource_pool, canvas=canvas)
        self.canvas = canvas

    def render(
        self,
        drawing_registry: Any,
        time_scale: Any,
        price_scales: Dict[str, Any],
        crosshair_state: Optional[Any] = None,
        pane_order: Optional[Dict[str, int]] = None
    ) -> List[Dict[str, Any]]:
        payloads = self.renderer.render_all(drawing_registry, time_scale, price_scales, pane_order=pane_order)

        if crosshair_state is None or not getattr(crosshair_state, "visible", False):
            return payloads

        payload = self._build_crosshair_payload(crosshair_state, time_scale, price_scales)
        if payload is not None:
            payloads.append(payload)

        return payloads

    def _build_crosshair_payload(self, crosshair_state: Any, time_scale: Any, price_scales: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        pane_id = getattr(crosshair_state, "pane_id", "pane_main")
        pane_price_scale = price_scales.get(pane_id)
        pane_height = getattr(pane_price_scale, "pane_height", 0.0) if pane_price_scale is not None else 0.0

        x = float(getattr(crosshair_state, "screen_x", 0.0))
        y = float(getattr(crosshair_state, "screen_y", 0.0))

        geometry = {
            "lines": [
                {"x1": 0.0, "y1": y, "x2": time_scale.width, "y2": y},
                {"x1": x, "y1": 0.0, "x2": x, "y2": pane_height}
            ]
        }

        style = {"stroke_color": "#4A4A4A", "stroke_width": 1.0, "dash": [4.0, 2.0], "render_type": "crosshair"}

        if self.canvas is not None:
            try:
                self.canvas.draw_path(f"crosshair_{pane_id}_h", [{"x": 0.0, "y": y}, {"x": time_scale.width, "y": y}], style)
                self.canvas.draw_path(f"crosshair_{pane_id}_v", [{"x": x, "y": 0.0}, {"x": x, "y": pane_height}], style)
            except Exception:
                pass

        return {
            "render_type": "crosshair",
            "pane_id": pane_id,
            "geometry": geometry,
            "style": style,
            "z": 1000
        }
