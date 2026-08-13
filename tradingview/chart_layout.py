"""
FinChart TradingView Chart Layout module (Layer 1.6 Foundation).
Owns pane order, dimensions, placement, splitters, and scale allocation without Workspace dependency.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from .enums import PaneRole, PlacementMode, ScalePolicy


@dataclass
class PaneModel:
    pane_id: str
    index: int
    role: PaneRole = PaneRole.MAIN
    visible: bool = True
    collapsed: bool = False
    height: float = 400.0
    min_height: float = 50.0
    max_height: float = 2000.0
    previous_height: float = 400.0
    series_ids: List[str] = field(default_factory=list)
    indicator_ids: List[str] = field(default_factory=list)
    price_scale_ids: List[str] = field(default_factory=list)


class ChartLayout:
    """Manages panes, component placement, and pane boundaries for a single Chart instance."""
    def __init__(self, layout_id: str = "default_layout"):
        self.layout_id = layout_id
        self.version: int = 1
        self.main_pane_id: str = "pane_main"
        self._panes: Dict[str, PaneModel] = {}
        self._pane_order: List[str] = []

        # Create mandatory main pane
        main_pane = PaneModel(pane_id=self.main_pane_id, index=0, role=PaneRole.MAIN, height=400.0)
        self._panes[self.main_pane_id] = main_pane
        self._pane_order.append(self.main_pane_id)

    def get_pane(self, pane_id: str) -> Optional[PaneModel]:
        return self._panes.get(pane_id)

    def get_all_panes(self) -> List[PaneModel]:
        return [self._panes[pid] for pid in self._pane_order if pid in self._panes]

    def add_indicator_pane(self, pane_id: str, height: float = 150.0) -> PaneModel:
        if pane_id in self._panes:
            return self._panes[pane_id]
        new_pane = PaneModel(
            pane_id=pane_id,
            index=len(self._pane_order),
            role=PaneRole.INDICATOR,
            height=height
        )
        self._panes[pane_id] = new_pane
        self._pane_order.append(pane_id)
        return new_pane

    def remove_pane(self, pane_id: str) -> bool:
        if pane_id == self.main_pane_id:
            return False  # Main pane cannot be deleted
        if pane_id in self._panes:
            del self._panes[pane_id]
            self._pane_order.remove(pane_id)
            self._renumber_panes()
            return True
        return False

    def _renumber_panes(self) -> None:
        for idx, pid in enumerate(self._pane_order):
            if pid in self._panes:
                self._panes[pid].index = idx

    def resize_splitter_by_pixels(self, top_pane_id: str, delta_pixels: float, total_content_height: float) -> bool:
        """Resize the splitter between `top_pane_id` and the next pane by a pixel delta.

        Adjusts the `height` weight of the top and bottom panes proportionally to the
        change in pixels relative to the provided `total_content_height` (the pixel
        height available for panes). Returns True if any change was applied.
        """
        if top_pane_id not in self._panes:
            return False
        # Find pane index
        try:
            idx = self._pane_order.index(top_pane_id)
        except ValueError:
            return False
        if idx == len(self._pane_order) - 1:
            # No pane below to resize against
            return False

        top = self._panes[top_pane_id]
        bottom = self._panes[self._pane_order[idx + 1]]

        total_weights = sum(p.height for p in self.get_all_panes())
        if total_content_height <= 0 or total_weights <= 0:
            # fallback: apply pixel delta as weight directly
            delta_weight = delta_pixels
        else:
            # Map pixel delta into weight space
            scale = total_weights / total_content_height
            delta_weight = delta_pixels * scale

        new_top = max(top.min_height, min(top.height + delta_weight, top.max_height))
        new_bottom = max(bottom.min_height, min(bottom.height - delta_weight, bottom.max_height))

        # If clamping of one pane prevents applying full delta, adjust the other pane accordingly
        applied_top_delta = new_top - top.height
        applied_bottom_delta = bottom.height - new_bottom
        # Prefer top delta when both are possible; reconcile any mismatch by averaging
        if abs(applied_top_delta + applied_bottom_delta) > 1e-6:
            # small mismatch; distribute remaining delta to the pane that can accept it
            remaining = (applied_top_delta + applied_bottom_delta)
            if remaining > 0:
                # try to add to top within limits
                avail_top = top.max_height - new_top
                add = min(avail_top, remaining)
                new_top += add
                remaining -= add
            elif remaining < 0:
                avail_bottom = new_bottom - bottom.min_height
                rem = min(avail_bottom, -remaining)
                new_bottom -= rem

        changed = False
        if abs(new_top - top.height) > 1e-9:
            top.height = new_top
            changed = True
        if abs(new_bottom - bottom.height) > 1e-9:
            bottom.height = new_bottom
            changed = True

        return changed

    def reflow_panes(self, total_content_height: float) -> None:
        """Reflow pane heights to fill `total_content_height` while respecting min/max.

        Algorithm:
        1. Compute proportional target heights by scaling current heights to the new total.
        2. Clamp targets to pane min/max; if any panes are clamped, redistribute remaining space
           among the unclamped panes iteratively until all space is allocated or no change.
        """
        panes = self.get_all_panes()
        n = len(panes)
        if n == 0:
            return

        # Compute initial proportional targets based on current heights
        total_weight = sum(max(0.0, p.height) for p in panes)
        if total_weight <= 0:
            # fallback: distribute evenly
            for p in panes:
                p.height = max(p.min_height, min(total_content_height / n, p.max_height))
            return

        targets = [(p.pane_id, (p.height / total_weight) * total_content_height) for p in panes]

        # Prepare allocations and unclamped set
        allocs = {pid: 0.0 for pid, _ in targets}
        unclamped = set(pid for pid, _ in targets)
        remaining = total_content_height

        # First pass: clamp targets to min/max where necessary
        for pid, tgt in targets:
            p = self._panes[pid]
            clamped = max(p.min_height, min(tgt, p.max_height))
            allocs[pid] = clamped
            remaining -= clamped
            if abs(clamped - tgt) > 1e-9:
                if pid in unclamped:
                    unclamped.remove(pid)

        # Redistribute remaining among unclamped panes proportionally to their original targets
        if remaining > 1e-9 and len(unclamped) > 0:
            # sum of original targets for unclamped panes
            sum_unclamped_targets = sum(tgt for pid, tgt in targets if pid in unclamped)
            if sum_unclamped_targets <= 0:
                # evenly distribute
                per = remaining / len(unclamped)
                for pid in list(unclamped):
                    p = self._panes[pid]
                    add = max(p.min_height, min(per, p.max_height))
                    allocs[pid] += add
                    remaining -= add
            else:
                for pid, tgt in targets:
                    if pid not in unclamped:
                        continue
                    p = self._panes[pid]
                    share = (tgt / sum_unclamped_targets) * remaining
                    add = max(0.0, min(share, p.max_height - allocs[pid]))
                    allocs[pid] += add
                    remaining -= add

        # If still remaining due to clamping, try to distribute to any pane with available max space
        if remaining > 1e-9:
            for pid, _ in targets:
                if remaining <= 1e-9:
                    break
                p = self._panes[pid]
                avail = p.max_height - allocs[pid]
                add = min(avail, remaining)
                allocs[pid] += add
                remaining -= add

        # Final fallback: if rounding caused tiny deficit, adjust first pane
        if remaining > 1e-6:
            first_pid = targets[0][0]
            allocs[first_pid] += remaining
            remaining = 0.0

        # Apply allocations
        for pid, _ in targets:
            self._panes[pid].height = allocs[pid]

# Added Features:
# - PaneModel dataclass and ChartLayout class with mandatory main pane protection.
