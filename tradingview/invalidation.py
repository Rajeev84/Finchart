"""
FinChart TradingView Invalidation Scheduler module.
Coalesces rendering invalidation requests to prevent excessive renders during high-frequency events.
"""

from typing import Callable, Optional


class InvalidationScheduler:
    """Manages render dirty flags and schedules batched frame renders."""
    def __init__(self, render_callback: Optional[Callable[[], None]] = None):
        self.render_callback = render_callback
        self._is_dirty: bool = False
        self.invalidation_count: int = 0
        self.render_count: int = 0

    def request_invalidation(self) -> None:
        """Flags chart as dirty for render."""
        self._is_dirty = True
        self.invalidation_count += 1

    def flush_if_dirty(self) -> bool:
        """Executes render callback if invalidation was requested."""
        if self._is_dirty:
            self._is_dirty = False
            self.render_count += 1
            if self.render_callback:
                self.render_callback()
            return True
        return False

# Added Features:
# - InvalidationScheduler to track dirty flags and coalesce rendering calls.
