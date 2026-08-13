"""
FinChart TradingView Chart State module (Layer 1.5 Foundation).
Stores persistent configuration and chart state without computing authoritative screen coordinates.
"""

from typing import List, Dict, Any, Optional
from .enums import ChartType, PaneRole
from .chart_layout import ChartLayout, PaneModel


class ChartState:
    """Stores persistent chart state, symbol, interval, layout, and drawings metadata."""
    def __init__(self, chart_id: str = "chart_1", symbol: str = "AAPL", interval: str = "1D"):
        self.chart_id = chart_id
        self.symbol = symbol
        self.interval = interval
        self.chart_type: ChartType = ChartType.CANDLESTICK
        self.layout: ChartLayout = ChartLayout()
        self.drawings: List[Dict[str, Any]] = []
        self.active_tool: str = "cursor"

    def to_dict(self) -> Dict[str, Any]:
        """Serializes logical configuration to dictionary format."""
        return {
            "chart_id": self.chart_id,
            "symbol": self.symbol,
            "interval": self.interval,
            "chart_type": self.chart_type.value,
            "layout": {
                "layout_id": self.layout.layout_id,
                "panes": [
                    {
                        "pane_id": pane.pane_id,
                        "index": pane.index,
                        "role": pane.role.value,
                        "visible": pane.visible,
                        "collapsed": pane.collapsed,
                        "height": pane.height,
                        "min_height": pane.min_height,
                        "max_height": pane.max_height,
                        "previous_height": pane.previous_height
                    }
                    for pane in self.layout.get_all_panes()
                ]
            },
            "drawings": [
                {
                    "id": d.get("id"),
                    "type": d.get("type"),
                    "points": d.get("points")
                }
                for d in self.drawings
            ],
            "active_tool": self.active_tool
        }

    # Schema versioning and snapshot API
    STATE_VERSION = 1

    def snapshot(self) -> Dict[str, Any]:
        """Return a schema-envelope snapshot suitable for persistence or transport.

        Envelope format:
        {
            "version": int,
            "chart_id": str,
            "state": { ... }  # payload matching to_dict()
        }
        """
        return {
            "version": ChartState.STATE_VERSION,
            "chart_id": self.chart_id,
            "state": self.to_dict()
        }

    @classmethod
    def restore_from_snapshot(cls, snapshot: Dict[str, Any]) -> "ChartState":
        """Restore a ChartState instance from a snapshot envelope.

        Performs basic validation of the envelope and delegates to `from_dict`.
        If the snapshot version differs from the current `STATE_VERSION`, the
        `migrate_snapshot` hook will be invoked (may raise if migration is not implemented).
        """
        if not isinstance(snapshot, dict):
            raise ValueError("snapshot must be a dict")
        if "version" not in snapshot or "state" not in snapshot or "chart_id" not in snapshot:
            raise ValueError("invalid snapshot envelope")

        version = int(snapshot["version"])
        if version != cls.STATE_VERSION:
            # Attempt migration if available
            snapshot = cls.migrate_snapshot(snapshot)
            if int(snapshot.get("version", -1)) != cls.STATE_VERSION:
                raise NotImplementedError("Snapshot migration to current STATE_VERSION not implemented")

        state_payload = snapshot["state"]
        chart = cls(chart_id=snapshot.get("chart_id", "chart_1"))
        chart.from_dict(state_payload)
        return chart

    @classmethod
    def migrate_snapshot(cls, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """Migration hook for older snapshot versions.

        By default this raises NotImplementedError to avoid silent schema changes.
        Implementers can provide conversion logic from older versions to the current
        envelope format and return a new snapshot with `version == STATE_VERSION`.
        """
        # Basic example migration: support legacy snapshots with no envelope where
        # callers previously saved the raw `to_dict()` payload. Also support
        # upgrading version 0 -> 1 where layout panes may have omitted new fields.
        if not isinstance(snapshot, dict):
            raise ValueError("snapshot must be a dict")

        # If snapshot looks like a raw state payload (no 'version' key), wrap it.
        if "version" not in snapshot and "state" not in snapshot:
            return {
                "version": cls.STATE_VERSION,
                "chart_id": snapshot.get("chart_id", "chart_1") if isinstance(snapshot, dict) else "chart_1",
                "state": snapshot
            }

        # Example: migrate version 0 payloads (hypothetical)
        ver = int(snapshot.get("version", -1))
        if ver == 0:
            state = snapshot.get("state", {})
            # Ensure panes have required fields
            layout = state.get("layout", {})
            panes = layout.get("panes", [])
            for p in panes:
                if "min_height" not in p:
                    p["min_height"] = 50.0
                if "max_height" not in p:
                    p["max_height"] = 2000.0
                if "previous_height" not in p:
                    p["previous_height"] = p.get("height", 400.0)
            state["layout"] = layout
            return {
                "version": cls.STATE_VERSION,
                "chart_id": snapshot.get("chart_id", "chart_1"),
                "state": state
            }

        raise NotImplementedError("No migration path available for snapshot version")

    def from_dict(self, data: Dict[str, Any]) -> None:
        if "symbol" in data:
            self.symbol = data["symbol"]
        if "interval" in data:
            self.interval = data["interval"]
        if "chart_type" in data:
            self.chart_type = ChartType(data["chart_type"])
        if "active_tool" in data:
            self.active_tool = data["active_tool"]
        if "layout" in data and isinstance(data["layout"], dict):
            self.layout = ChartLayout(layout_id=data["layout"].get("layout_id", self.layout.layout_id))
            self.layout._panes.clear()
            self.layout._pane_order.clear()
            for pane_data in data["layout"].get("panes", []):
                pane = PaneModel(
                    pane_id=pane_data.get("pane_id", "pane_main"),
                    index=pane_data.get("index", 0),
                    role=PaneRole(pane_data.get("role", PaneRole.MAIN.value)),
                    visible=pane_data.get("visible", True),
                    collapsed=pane_data.get("collapsed", False),
                    height=pane_data.get("height", 400.0),
                    min_height=pane_data.get("min_height", 50.0),
                    max_height=pane_data.get("max_height", 2000.0),
                    previous_height=pane_data.get("previous_height", 400.0)
                )
                self.layout._panes[pane.pane_id] = pane
                self.layout._pane_order.append(pane.pane_id)
        if "drawings" in data and isinstance(data["drawings"], list):
            self.drawings = [
                {"id": d.get("id"), "type": d.get("type"), "points": d.get("points", [])}
                for d in data["drawings"]
            ]

# Added Features:
# - ChartState storing configuration, symbol, interval, layout reference, drawings list, and persistence helpers.
