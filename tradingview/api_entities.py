"""
FinChart TradingView API Entities module (Layer 1.8).
Public object wrappers delegating entity operations to underlying engine components.
"""

from typing import List, Dict, Any, Optional
from .types import OHLCVBar
from .enums import ScalePolicy
from .errors import InvalidIndicatorError
from .drawing_primitives import DrawingObject, DrawingPoint, DrawingStyle, DrawingHitResult


class SeriesAPI:
    """Public wrapper object for manipulating a single chart Series."""

    def __init__(self, series_id: str, series_type: str, pane_id: str, chart: Any):
        self.series_id = series_id
        self.series_type = series_type
        self.pane_id = pane_id
        self._chart = chart
        self.visible: bool = True
        self.options: Dict[str, Any] = {}

    def set_data(self, bars: List[OHLCVBar]) -> None:
        self._chart._verify_active()
        self._chart._set_series_data(self.series_id, bars)

    def update(self, bar: OHLCVBar) -> None:
        self._chart._verify_active()
        self._chart._update_series_bar(self.series_id, bar)

    def apply_options(self, opts: Dict[str, Any]) -> None:
        self._chart._verify_active()
        self.options.update(opts)

    def show(self) -> None:
        self._chart._verify_active()
        self.visible = True

    def hide(self) -> None:
        self._chart._verify_active()
        self.visible = False

    def remove(self) -> None:
        self._chart._verify_active()
        self._chart.remove_series(self.series_id)


class IndicatorAPI:
    """Public wrapper object for manipulating a single Indicator."""

    def __init__(self, indicator_id: str, name: str, pane_id: str, chart: Any):
        self.indicator_id = indicator_id
        self.name = name
        self.pane_id = pane_id
        self._chart = chart
        self.visible: bool = True
        self.inputs: Dict[str, Any] = {}
        self.options: Dict[str, Any] = {}
        self._output: List[float] = []

    def set_input(self, key: str, value: Any) -> None:
        self._chart._verify_active()
        self.inputs[key] = value

    def set_options(self, opts: Dict[str, Any]) -> None:
        self._chart._verify_active()
        self.options.update(opts)

    def show(self) -> None:
        self._chart._verify_active()
        self.visible = True

    def hide(self) -> None:
        self._chart._verify_active()
        self.visible = False

    def remove(self) -> None:
        self._chart._verify_active()
        self._chart.remove_indicator(self.indicator_id)

    def get_output(self) -> List[float]:
        self._chart._verify_active()
        return self._chart._calculate_indicator_output(self.indicator_id)


class DrawingAPI:
    """Public wrapper object for manipulating a Drawing shape."""

    def __init__(self, drawing_id: str, shape_type: str, points: List[Dict[str, float]], pane_id: str, chart: Any):
        self.drawing_id = drawing_id
        self.shape_type = shape_type
        self.points = points
        self.pane_id = pane_id
        self._chart = chart
        self.visible: bool = True
        self.properties: Dict[str, Any] = {}
        self._is_drawing: bool = False  # True during creation, False after completion

    @property
    def is_drawing(self) -> bool:
        """Return True if the drawing is currently being created (preview state)."""
        return self._is_drawing

    @is_drawing.setter
    def is_drawing(self, value: bool) -> None:
        self._is_drawing = bool(value)

    @property
    def drawing_type(self) -> str:
        """Alias for ``shape_type`` so DrawingAPI is compatible with
        HandleEngine.compute_handles and other engine internals."""
        return self.shape_type

    @property
    def anchors(self) -> List[Any]:
        """Derive DrawingPoint anchors from ``points`` dicts for handle
        computation and hit testing.  Only logical_index/price points are
        convertible; percent-based points are skipped."""
        from .drawing_primitives import DrawingPoint
        anchors = []
        for p in self.points or []:
            if "logical_index" in p and "price" in p:
                anchors.append(DrawingPoint(
                    float(p["logical_index"]), float(p["price"])
                ))
        return anchors

    @property
    def style(self) -> Any:
        """Return a default DrawingStyle so HandleEngine can resolve
        handle_radius without special-casing DrawingAPI objects."""
        from .drawing_primitives import DrawingStyle
        if not hasattr(self, "_style_cache"):
            self._style_cache = DrawingStyle()
        return self._style_cache

    def set_properties(self, props: Dict[str, Any]) -> None:
        self._chart._verify_active()
        self.properties.update(props)
        self._chart._update_drawing_state(self.drawing_id, self.points, self.properties)

    def set_points(self, points: List[Dict[str, float]]) -> None:
        self._chart._verify_active()
        self.points = points
        self._chart._update_drawing_state(self.drawing_id, self.points, self.properties)

    def show(self) -> None:
        self._chart._verify_active()
        self.visible = True

    def hide(self) -> None:
        self._chart._verify_active()
        self.visible = False

    def remove(self) -> None:
        self._chart._verify_active()
        self._chart.remove_drawing(self.drawing_id)

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

        Converts the API points into a DrawingObject and delegates to its hit_test.
        """
        if not self.visible:
            return None
        anchors = []
        for p in self.points:
            if "logical_index" in p and "price" in p:
                anchors.append(DrawingPoint(float(p["logical_index"]), float(p["price"])))
            elif "x_percent" in p and "y_percent" in p:
                # Percent-based points are not directly convertible without chart dims;
                # skip them for hit testing.
                continue
        if not anchors:
            return None
        obj = DrawingObject(
            drawing_id=self.drawing_id,
            drawing_type=self.shape_type,
            anchors=anchors,
            style=DrawingStyle()
        )
        return obj.hit_test(
            mouse_x, mouse_y, time_scale, price_scale,
            tolerance=tolerance, handle_tolerance=handle_tolerance
        )


class PaneAPI:
    """Public wrapper object for manipulating a Layout Pane."""

    def __init__(self, pane_id: str, chart: Any):
        self.pane_id = pane_id
        self._chart = chart

    @property
    def height(self) -> float:
        pane = self._chart.layout.get_pane(self.pane_id)
        return pane.height if pane else 0.0

    def resize(self, height: float) -> None:
        self._chart._verify_active()
        pane = self._chart.layout.get_pane(self.pane_id)
        if pane:
            pane.height = max(pane.min_height, min(height, pane.max_height))
            self._chart.event_registry.emit("pane_changed", {"pane_id": self.pane_id, "action": "resize"})

    def collapse(self) -> None:
        self._chart._verify_active()
        pane = self._chart.layout.get_pane(self.pane_id)
        if pane:
            pane.collapsed = True

    def expand(self) -> None:
        self._chart._verify_active()
        pane = self._chart.layout.get_pane(self.pane_id)
        if pane:
            pane.collapsed = False

    def remove(self) -> None:
        self._chart._verify_active()
        self._chart.remove_pane(self.pane_id)


class TimeScaleAPI:
    """Public API for interacting with the TimeScale and viewport navigation."""

    def __init__(self, chart: Any):
        self._chart = chart

    def fit_content(self) -> None:
        self._chart._verify_active()
        self._chart.viewport.bar_spacing = self._chart.time_scale.bar_spacing
        self._chart._set_viewport_to_latest_edge(len(self._chart._primary_series or []))
        if self._chart.invalidation_scheduler:
            self._chart.invalidation_scheduler.request_invalidation()
        self._chart.event_registry.emit("visible_range_changed", {"start": self._chart.viewport.visible_start, "end": self._chart.viewport.visible_end})

    def reset_view(self) -> None:
        self.fit_content()

    def set_options(self, opts: Dict[str, Any]) -> None:
        self._chart._verify_active()
        if "bar_spacing" in opts:
            self._chart.time_scale.set_bar_spacing(opts["bar_spacing"])
            self._chart.viewport.bar_spacing = self._chart.time_scale.bar_spacing
            self._chart.viewport.visible_start = self._chart.time_scale.visible_start
            self._chart.viewport.visible_end = self._chart.time_scale.visible_end
        if "right_offset" in opts:
            self._chart.time_scale.right_offset = opts["right_offset"]
            self._chart.viewport.right_offset = opts["right_offset"]
        if "fix_left_edge" in opts:
            self._chart.time_scale.fix_left_edge = opts["fix_left_edge"]
            self._chart.viewport.fix_left_edge = opts["fix_left_edge"]
        if "fix_right_edge" in opts:
            self._chart.time_scale.fix_right_edge = opts["fix_right_edge"]
            self._chart.viewport.fix_right_edge = opts["fix_right_edge"]
        if self._chart.invalidation_scheduler:
            self._chart.invalidation_scheduler.request_invalidation()

    def scroll(self, delta_bars: float) -> None:
        self._chart._verify_active()
        self._chart.viewport.follow_latest = False
        self._chart.viewport.visible_start += delta_bars
        self._chart.viewport.visible_end += delta_bars
        self._chart.time_scale.visible_start = self._chart.viewport.visible_start
        self._chart.time_scale.visible_end = self._chart.viewport.visible_end
        if self._chart.invalidation_scheduler:
            self._chart.invalidation_scheduler.request_invalidation()
        self._chart.event_registry.emit("visible_range_changed", {"start": self._chart.viewport.visible_start, "end": self._chart.viewport.visible_end})

    def zoom(self, factor: float) -> None:
        self._chart._verify_active()
        self._chart.time_scale.set_bar_spacing(self._chart.time_scale.bar_spacing * factor)
        self._chart.viewport.bar_spacing = self._chart.time_scale.bar_spacing
        self._chart.viewport.visible_start = self._chart.time_scale.visible_start
        self._chart.viewport.visible_end = self._chart.time_scale.visible_end
        if self._chart.invalidation_scheduler:
            self._chart.invalidation_scheduler.request_invalidation()


class PriceScaleAPI:
    """Public API for interacting with a specific Pane's PriceScale."""

    def __init__(self, pane_id: str, chart: Any):
        self.pane_id = pane_id
        self._chart = chart

    def set_mode(self, mode: str) -> None:
        self._chart._verify_active()
        self._chart.options.price_scale.mode = mode

    def set_range(self, p_min: float, p_max: float) -> None:
        self._chart._verify_active()
        p_scale = self._chart.price_scales.get(self.pane_id)
        if p_scale:
            p_scale.set_range(p_min, p_max)
            self._chart.viewport.set_pane_price_range(self.pane_id, p_min, p_max)

# Added Features:
# - Entity API wrappers (SeriesAPI, IndicatorAPI, DrawingAPI, PaneAPI, TimeScaleAPI, PriceScaleAPI).
