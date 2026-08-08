"""Session state models for FinChart.

The schema deliberately stores logical workspace state, not Tkinter canvas
objects or market-data buffers.  Market data is an external/runtime resource.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


SCHEMA_VERSION = 2


@dataclass
class SessionState:
    schema_version: int = SCHEMA_VERSION
    current_context: Dict[str, str] = field(
        default_factory=lambda: {"symbol": "default", "timeframe": "default"}
    )
    layout: Dict[str, Any] = field(default_factory=dict)
    indicators: list = field(default_factory=list)
    contexts: Dict[str, Any] = field(default_factory=dict)
    chart: Dict[str, Any] = field(default_factory=dict)
    settings: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "current_context": self.current_context,
            "layout": self.layout,
            "indicators": self.indicators,
            "contexts": self.contexts,
            "chart": self.chart,
            "settings": self.settings,
            "metadata": self.metadata,
        }
