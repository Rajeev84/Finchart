"""
FinChart TradingView Pointer Capture Manager module (Layer 1.7).
Manages pointer capture semantics during active drag/resize gestures.
"""

from typing import Optional
from .input_events import HitTarget


class PointerCaptureManager:
    """Tracks captured pointer ID and initial target region during active drag operations."""

    def __init__(self):
        self._captured_pointer_id: Optional[int] = None
        self._capture_target: Optional[HitTarget] = None
        self._is_active: bool = False

    @property
    def is_captured(self) -> bool:
        return self._is_active and self._captured_pointer_id is not None

    @property
    def captured_pointer_id(self) -> Optional[int]:
        return self._captured_pointer_id

    @property
    def capture_target(self) -> Optional[HitTarget]:
        return self._capture_target

    def set_capture(self, pointer_id: int, target: HitTarget) -> None:
        """Establishes pointer capture for a specific pointer ID and target."""
        self._captured_pointer_id = pointer_id
        self._capture_target = target
        self._is_active = True

    def release_capture(self, pointer_id: Optional[int] = None) -> None:
        """Releases pointer capture if active."""
        if pointer_id is None or self._captured_pointer_id == pointer_id:
            self._captured_pointer_id = None
            self._capture_target = None
            self._is_active = False

# Added Features:
# - PointerCaptureManager supporting set_capture, release_capture, and active state queries.
