"""Tool State Machine - GUI state management for drawing tool creation.

Manages the state transitions for drawing tool activation:
IDLE -> WAIT_FIRST_CLICK -> PREVIEW -> IDLE
"""
from __future__ import annotations

from enum import Enum, auto
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass, field


class ToolState(Enum):
    """States for drawing tool creation workflow."""
    IDLE = auto()
    WAIT_FIRST_CLICK = auto()
    PREVIEW = auto()
    PREVIEW_2 = auto()  # For three-click tools like LongShort


@dataclass
class ToolContext:
    """Context for the active drawing tool session."""
    tool_type: str = ""           # "trendline", "hline", "vline", "angleline", "rectangle", "longshort"
    position_type: str = ""       # For longshort: "long" or "short"
    state: ToolState = ToolState.IDLE
    preview_shape: Optional[Any] = None   # DrawingState for preview
    preview_tool: Optional[Any] = None    # DrawingTool instance for preview
    start_index: float = 0.0
    start_price: float = 0.0
    current_index: float = 0.0
    current_price: float = 0.0
    on_complete: Optional[Callable[[Dict[str, Any]], None]] = None
