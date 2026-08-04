"""finchart.interaction - Mouse/keyboard interaction controller and hit testing."""
from .controller import InteractionController
from .hit_test import (
    point_to_line_distance,
    is_point_near_line,
    is_point_in_rect,
    is_point_near_handle,
)

# Aliases for consistency with drawing/__init__.py exports
hit_test_line = is_point_near_line
hit_test_rect = is_point_in_rect
distance_point_to_segment = point_to_line_distance

__all__ = [
    "InteractionController",
    "point_to_line_distance",
    "is_point_near_line",
    "is_point_in_rect",
    "is_point_near_handle",
    "hit_test_line",
    "hit_test_rect",
    "distance_point_to_segment",
]
