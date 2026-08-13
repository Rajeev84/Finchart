"""
FinChart TradingView HitTester module (Layer 1.7).
Deterministic resolution of HitTarget from screen coordinates against layout geometry, scales, and drawing objects.
"""

from typing import Optional, List, Dict, Any
from .enums import HitRegion
from .input_events import HitTarget
from .chart_layout import ChartLayout
from .time_scale import TimeScale
from .price_scale import PriceScale
from .drawing_hit_tester import DrawingHitTester


class HitTester:
    """Performs deterministic hit testing following FinChart architectural priority rules."""

    def __init__(
        self,
        layout: ChartLayout,
        time_scale: TimeScale,
        price_scales: Optional[Dict[str, PriceScale]] = None,
        drawings_provider: Optional[Any] = None
    ):
        self.layout = layout
        self.time_scale = time_scale
        self.price_scales = price_scales or {}
        self.drawings_provider = drawings_provider
        self.time_scale_height: float = 30.0
        self.price_scale_width: float = 60.0
        self.splitter_thickness: float = 6.0
        self.drawing_hit_tester = DrawingHitTester(
            time_scale=time_scale,
            price_scales=self.price_scales,
            drawings_provider=drawings_provider
        )

    def hit_test(self, screen_x: float, screen_y: float, chart_or_width=None, chart_height: float = None) -> HitTarget:
        """
        Determines the target region by inspecting boundaries in deterministic priority order:
        1. Active drawing handle
        2. Selected drawing body
        3. Other drawing body
        4. Pane splitter
        5. Price scale
        6. Time scale
        7. Series / indicator
        8. Pane body
        9. Chart background
        """
        

        # Resolve pane bounds
        panes = self.layout.get_all_panes()
        if not panes:
            return HitTarget(target_type=HitRegion.CHART_BACKGROUND)

        # 1-3. Check drawings if provider is registered
        if self.drawings_provider:
            drawing_hit = self._check_drawings(screen_x, screen_y)
            if drawing_hit:
                return drawing_hit

        # Determine chart dimensions. Support either a Chart instance or explicit width/height.
        resolved_chart_width = 0.0
        resolved_chart_height = 0.0
        if chart_or_width is None:
            resolved_chart_width = 0.0
            resolved_chart_height = 0.0
        elif isinstance(chart_or_width, (int, float)):
            resolved_chart_width = float(chart_or_width)
            resolved_chart_height = float(chart_height or 0.0)
        else:
            try:
                resolved_chart_width = float(chart_or_width.options.dimensions.width)
                resolved_chart_height = float(chart_or_width.options.dimensions.height)
            except Exception:
                resolved_chart_width = 0.0
                resolved_chart_height = 0.0

        main_content_width = max(0.0, resolved_chart_width - self.price_scale_width)
        is_in_price_scale = screen_x >= main_content_width

        # Check bottom time scale region
        main_content_height = max(0.0, resolved_chart_height - self.time_scale_height)
        is_in_time_scale = screen_y >= main_content_height
        

        if is_in_time_scale and not is_in_price_scale:
            logical_idx = self.time_scale.x_to_index(screen_x)
            return HitTarget(
                target_type=HitRegion.TIME_SCALE,
                logical_index=logical_idx
            )

        if is_in_price_scale and not is_in_time_scale:
            # Determine which pane row Y falls into
            pane_id = self._resolve_pane_id_at_y(screen_y, main_content_height, panes)
            p_scale = self.price_scales.get(pane_id)
            price_val = p_scale.y_to_price(screen_y) if p_scale else None
            return HitTarget(
                target_type=HitRegion.PRICE_SCALE,
                pane_id=pane_id,
                price_position=price_val
            )

        # 4. Check pane splitter
        splitter_hit = self._check_splitters(screen_y, main_content_height, panes)
        if splitter_hit:
            return splitter_hit

        # 8. Check pane body
        pane_id = self._resolve_pane_id_at_y(screen_y, main_content_height, panes)
        logical_idx = self.time_scale.x_to_index(screen_x)
        p_scale = self.price_scales.get(pane_id)
        price_val = p_scale.y_to_price(screen_y) if p_scale else None

        return HitTarget(
            target_type=HitRegion.PANE_BODY,
            pane_id=pane_id,
            logical_index=logical_idx,
            price_position=price_val
        )

    def _resolve_pane_id_at_y(self, screen_y: float, total_height: float, panes: list) -> str:
        if not panes:
            return "pane_main"
        accumulated_y = 0.0
        total_pane_heights = sum(p.height for p in panes)
        if total_pane_heights <= 0:
            return panes[0].pane_id

        for p in panes:
            h = (p.height / total_pane_heights) * total_height
            if accumulated_y <= screen_y <= accumulated_y + h:
                return p.pane_id
            accumulated_y += h
        return panes[-1].pane_id

    def _check_splitters(self, screen_y: float, total_height: float, panes: list) -> Optional[HitTarget]:
        if len(panes) < 2:
            return None
        accumulated_y = 0.0
        total_pane_heights = sum(p.height for p in panes)
        for i in range(len(panes) - 1):
            h = (panes[i].height / total_pane_heights) * total_height
            boundary_y = accumulated_y + h
            half_t = self.splitter_thickness / 2.0
            if boundary_y - half_t <= screen_y <= boundary_y + half_t:
                return HitTarget(
                    target_type=HitRegion.PANE_SPLITTER,
                    pane_id=panes[i].pane_id,
                    component_id=f"splitter_{panes[i].pane_id}_{panes[i+1].pane_id}"
                )
            accumulated_y += h
        return None

    def _check_drawings(self, screen_x: float, screen_y: float) -> Optional[HitTarget]:
        if self.drawing_hit_tester is None:
            return None
        return self.drawing_hit_tester.hit_test(screen_x, screen_y)

# Added Features:
# - Deterministic HitTester with priority ordering (drawing handle, drawing body, splitter, price scale, time scale, pane body, background).
