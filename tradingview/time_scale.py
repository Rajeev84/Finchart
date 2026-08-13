"""
FinChart TradingView TimeScale module (Layer 1.1 Foundation).
Authoritative coordinate transformation engine for X-axis (Logical Index <-> Screen Pixel X).
"""

from .constants import DEFAULT_BAR_SPACING, MIN_BAR_SPACING, MAX_BAR_SPACING, DEFAULT_RIGHT_OFFSET


class TimeScale:
    """Authoritative transform between logical time indices and screen X coordinates."""
    def __init__(
        self,
        width: float = 800.0,
        bar_spacing: float = DEFAULT_BAR_SPACING,
        right_offset: float = DEFAULT_RIGHT_OFFSET,
        fix_left_edge: bool = False,
        fix_right_edge: bool = False
    ):
        self.width = width
        self.bar_spacing = bar_spacing
        self.right_offset = right_offset
        self.fix_left_edge = fix_left_edge
        self.fix_right_edge = fix_right_edge
        self.visible_start: float = 0.0
        self.visible_end: float = 100.0

    def index_to_x(self, index: float) -> float:
        """Transforms a logical index into screen coordinate X."""
        return (index - self.visible_start) * self.bar_spacing

    def x_to_index(self, x: float) -> float:
        """Transforms screen coordinate X into a floating-point logical index."""
        if self.bar_spacing <= 0:
            return 0.0
        return self.visible_start + (x / self.bar_spacing)

    def set_bar_spacing(self, spacing: float) -> None:
        if MAX_BAR_SPACING > 0.0:
            spacing = min(spacing, MAX_BAR_SPACING)
        self.bar_spacing = max(spacing, MIN_BAR_SPACING)
        if self.fix_right_edge and not self.fix_left_edge:
            self.visible_start = self.visible_end - (self.width / self.bar_spacing)
        else:
            self.visible_end = self.visible_start + (self.width / self.bar_spacing)

    def zoom_at(self, mouse_x: float, zoom_scale: float) -> None:
        """Perform cursor-centered proportional zoom.

        `mouse_x` is the screen X position to keep anchored during zoom.
        `zoom_scale` is a proportional modifier (positive to zoom in / larger bar spacing,
        negative to zoom out / smaller bar spacing). The change uses the architecture's proportional
        divisor of 10. The method preserves the logical data point under the cursor.
        """
        if zoom_scale == 0 or self.bar_spacing <= 0:
            return

        # Anchor as floating logical index at the current spacing
        anchor_index = self.x_to_index(mouse_x)

        # Compute requested spacing change (proportional)
        delta = (zoom_scale * self.bar_spacing) / 10.0
        requested = self.bar_spacing + delta

        # Apply spacing with clamping
        self.set_bar_spacing(requested)

        # If either edge is fixed, preserve that edge
        if self.fix_left_edge or self.fix_right_edge:
            return

        # Recalculate visible_start so that the same logical anchor maps to mouse_x
        self.visible_start = anchor_index - (mouse_x / self.bar_spacing)
        self.visible_end = self.visible_start + (self.width / self.bar_spacing)

# Added Features:
# - Authoritative TimeScale transformation functions index_to_x and x_to_index.
