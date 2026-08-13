"""
FinChart TradingView Drawing Hit-Test Engine (Layer 1.6).
Coordinates hit testing across all registered drawings with z-order priority.
"""
from typing import Any, Dict, List, Optional
from .enums import HitRegion
from .input_events import HitTarget
from .drawing_primitives import DrawingHitResult


class DrawingHitTester:
    """Deterministic hit testing across all drawings in z-order.

    Priority: iterate drawings front-most first (highest z_order). For each
    drawing, check handle first then body. First hit wins.
    """

    def __init__(self, time_scale: Any, price_scales: Dict[str, Any],
                 drawings_provider: Optional[Any] = None,
                 selection_manager: Optional[Any] = None,
                 body_tolerance: float = 6.0,
                 handle_tolerance: Optional[float] = None):
        self.time_scale = time_scale
        self.price_scales = price_scales
        self.drawings_provider = drawings_provider
        self.selection_manager = selection_manager
        self.body_tolerance = body_tolerance
        self.handle_tolerance = handle_tolerance

    def _get_drawings(self) -> List[Any]:
        if self.drawings_provider is None:
            return []
        if hasattr(self.drawings_provider, "values"):
            drawings = list(self.drawings_provider.values())
        elif isinstance(self.drawings_provider, (list, tuple)):
            drawings = list(self.drawings_provider)
        else:
            drawings = []
        # Sort by z_order descending so the front-most (highest z) is tested first
        drawings.sort(key=lambda d: getattr(d, "z_order", 100), reverse=True)
        return drawings

    def _resolve_price_scale(self, drawing: Any) -> Optional[Any]:
        pane_id = getattr(drawing, "pane_id", "pane_main")
        return self.price_scales.get(pane_id)

    def hit_test(self, screen_x: float, screen_y: float) -> Optional[HitTarget]:
        drawings = self._get_drawings()
        if not drawings:
            return None

        for drawing in drawings:
            if not getattr(drawing, "visible", True):
                continue
            p_scale = self._resolve_price_scale(drawing)
            if p_scale is None:
                continue

            result = drawing.hit_test(
                screen_x, screen_y, self.time_scale, p_scale,
                tolerance=self.body_tolerance, handle_tolerance=self.handle_tolerance
            )
            if result is None:
                continue

            # First hit wins (front-most drawing, handle before body)
            return self._build_target(drawing, result, is_handle=(result.region == "HANDLE"))

        return None

    def _build_target(self, drawing: Any, result: DrawingHitResult, is_handle: bool) -> HitTarget:
        pane_id = getattr(drawing, "pane_id", "pane_main")
        # Prefer the semantic handle id produced by the Handle Engine (1.7);
        # fall back to the legacy "handle_{index}" format for any caller that
        # still populates only handle_index.
        handle_id = None
        if is_handle:
            handle_id = result.handle_id or (
                f"handle_{result.handle_index}"
                if result.handle_index is not None else None
            )
        return HitTarget(
            target_type=HitRegion.DRAWING_HANDLE if is_handle else HitRegion.DRAWING_BODY,
            target_id=result.drawing_id,
            pane_id=pane_id,
            handle_id=handle_id,
            handle_role=getattr(result, "handle_role", None),
            hit_distance=result.distance
        )
