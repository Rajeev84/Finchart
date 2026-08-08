"""Workspace layout orchestration for FinChart.

The LayoutManager owns declarative layout state while LayoutEngine remains the
low-level geometry calculator.  Runtime pane viewports are projections of the
stored pane definitions and can therefore be rebuilt safely.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from ..core.events import EventBus, EventType
from ..core.types import Viewport
from .engine import LayoutEngine


class LayoutManager:
    """High-level layout state manager around :class:`LayoutEngine`."""

    def __init__(self, engine: Optional[LayoutEngine] = None,
                 event_bus: Optional[EventBus] = None) -> None:
        self.engine = engine or LayoutEngine()
        self._event_bus = event_bus

    @property
    def panes(self):
        return self.engine.panes

    def add_pane(self, name: str, weight: float = 1.0,
                 overlay_on: Optional[str] = None):
        pane = self.engine.add_pane(name, weight=weight, overlay_on=overlay_on)
        self._emit()
        return pane

    def remove_pane(self, name: str) -> bool:
        removed = self.engine.remove_pane(name)
        if removed:
            self._emit()
        return removed

    def reset(self) -> None:
        self.engine.reset()
        self._emit()

    def calculate_layout(self, viewport: Viewport):
        return self.engine.calculate_layout(viewport)

    def ensure_pane(self, name: str, weight: float = 1.0,
                    overlay_on: Optional[str] = None):
        if name == "candlestick":
            return self.engine.panes["candlestick"]
        if name not in self.engine.panes:
            return self.add_pane(name, weight, overlay_on)
        return self.engine.panes[name]

    def sync_indicators(self, indicators) -> None:
        """Make structural panes exactly match indicator pane requirements."""
        required = {"candlestick"}
        for indicator in indicators:
            pane = getattr(indicator, "pane", "candlestick") or "candlestick"
            required.add(pane)
            if pane not in self.engine.panes:
                self.engine.add_pane(pane, weight=1.0)

        # Do not remove explicitly overlay/empty panes blindly if callers have
        # configured them.  Remove only panes no longer referenced by indicators.
        for name in list(self.engine.panes):
            if name != "candlestick" and name not in required:
                self.engine.remove_pane(name)
        self._emit()

    def snapshot(self) -> Dict[str, Any]:
        """Return JSON-compatible declarative layout state."""
        return {
            "panes": {
                name: {
                    "weight": float(pane.weight),
                    "overlay_on": pane.overlay_on,
                }
                for name, pane in self.engine.panes.items()
            }
        }

    def restore(self, state: Optional[Dict[str, Any]]) -> None:
        """Restore declarative pane definitions atomically."""
        panes = (state or {}).get("panes", {})
        if not isinstance(panes, dict):
            raise ValueError("layout.panes must be an object")

        normalized = []
        for name, cfg in panes.items():
            if not isinstance(cfg, dict):
                raise ValueError(f"Invalid configuration for pane {name!r}")
            weight = float(cfg.get("weight", 3.0 if name == "candlestick" else 1.0))
            overlay_on = cfg.get("overlay_on")
            if not isinstance(name, str) or not name.strip():
                raise ValueError("Pane name must be a non-empty string")
            if weight <= 0:
                raise ValueError(f"Pane {name!r} weight must be greater than zero")
            if overlay_on == name:
                raise ValueError(f"Pane {name!r} cannot overlay itself")
            normalized.append((name, weight, overlay_on))

        names = {name for name, _, _ in normalized}
        for name, _, overlay_on in normalized:
            if overlay_on is not None and overlay_on not in names and overlay_on != "candlestick":
                raise ValueError(f"Pane {name!r} references unknown overlay target {overlay_on!r}")

        self.engine.reset()
        for name, weight, overlay_on in normalized:
            if name == "candlestick":
                self.engine.panes["candlestick"].weight = weight
                self.engine.panes["candlestick"].overlay_on = overlay_on
            else:
                self.engine.add_pane(name, weight=weight, overlay_on=overlay_on)
        self._emit()

    def _emit(self) -> None:
        if self._event_bus is not None:
            self._event_bus.emit_new(
                EventType.LAYOUT_CHANGED, self,
                panes=list(self.engine.panes.keys())
            )
