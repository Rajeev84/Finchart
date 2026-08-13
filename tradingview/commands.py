"""
FinChart Command Pattern definitions for Undo/Redo (Layer 1.11).
"""

import uuid
from abc import ABC, abstractmethod
from typing import Any, List, Dict, Optional
from .api_entities import SeriesAPI, IndicatorAPI
from .data_series import OHLCVSeries


class Command(ABC):
    """Abstract base class for all undoable commands."""

    @abstractmethod
    def execute(self) -> None:
        """Executes the state change."""
        pass

    @abstractmethod
    def undo(self) -> None:
        """Undoes the state change."""
        pass


class AddDrawingCommand(Command):
    """Command to add a drawing shape to the chart."""

    def __init__(self, chart: Any, drawing_id: str, shape_type: str, points: List[Dict[str, float]], pane_id: str):
        self.chart = chart
        self.drawing_id = drawing_id
        self.shape_type = shape_type
        self.points = points
        self.pane_id = pane_id

    def execute(self) -> None:
        from .api_entities import DrawingAPI
        # Add to registries
        api_drawing = DrawingAPI(self.drawing_id, self.shape_type, self.points, self.pane_id, self.chart)
        self.chart._drawing_registry[self.drawing_id] = api_drawing
        # Add to state drawings if not already there
        if not any(d.get("id") == self.drawing_id for d in self.chart.chart_state.drawings):
            self.chart.chart_state.drawings.append({
                "id": self.drawing_id,
                "type": self.shape_type,
                "points": self.points
            })
        self.chart.event_registry.emit("drawing_created", {
            "drawing_id": self.drawing_id,
            "shape_type": self.shape_type
        })

    def undo(self) -> None:
        # Deselect if selected
        if self.chart.selection_manager.is_selected(self.drawing_id):
            self.chart.selection_manager.deselect(self.drawing_id)
        # Remove from registries
        if self.drawing_id in self.chart._drawing_registry:
            del self.chart._drawing_registry[self.drawing_id]
        # Remove from state
        self.chart.chart_state.drawings = [
            d for d in self.chart.chart_state.drawings if d.get("id") != self.drawing_id
        ]
        self.chart.event_registry.emit("drawing_removed", {"drawing_id": self.drawing_id})


class RemoveDrawingCommand(Command):
    """Command to remove a drawing shape from the chart."""

    def __init__(self, chart: Any, drawing_id: str):
        self.chart = chart
        self.drawing_id = drawing_id
        # Backup the existing drawing state
        drawing = chart.get_drawing(drawing_id)
        if drawing is None:
            raise ValueError(f"Drawing with ID '{drawing_id}' not found.")
        self.shape_type = drawing.shape_type
        self.points = list(drawing.points)
        self.pane_id = drawing.pane_id
        self.properties = dict(drawing.properties)

    def execute(self) -> None:
        # Deselect if selected
        if self.chart.selection_manager.is_selected(self.drawing_id):
            self.chart.selection_manager.deselect(self.drawing_id)
        # Remove from registry
        if self.drawing_id in self.chart._drawing_registry:
            del self.chart._drawing_registry[self.drawing_id]
        # Remove from state
        self.chart.chart_state.drawings = [
            d for d in self.chart.chart_state.drawings if d.get("id") != self.drawing_id
        ]
        self.chart.event_registry.emit("drawing_removed", {"drawing_id": self.drawing_id})

    def undo(self) -> None:
        from .api_entities import DrawingAPI
        # Restore registry
        api_drawing = DrawingAPI(self.drawing_id, self.shape_type, self.points, self.pane_id, self.chart)
        api_drawing.properties.update(self.properties)
        self.chart._drawing_registry[self.drawing_id] = api_drawing
        # Restore state
        if not any(d.get("id") == self.drawing_id for d in self.chart.chart_state.drawings):
            self.chart.chart_state.drawings.append({
                "id": self.drawing_id,
                "type": self.shape_type,
                "points": self.points
            })
        self.chart.event_registry.emit("drawing_created", {
            "drawing_id": self.drawing_id,
            "shape_type": self.shape_type
        })


class AddSeriesCommand(Command):
    """Command to add a new series to the chart."""

    def __init__(self, chart: Any, series_type: str = "candlestick", options: Optional[Dict[str, Any]] = None, pane_id: str = "pane_main"):
        self.chart = chart
        self.series_type = series_type
        self.options = options
        self.pane_id = pane_id
        # Generate a new series ID
        self.series_id = f"series_{uuid.uuid4().hex[:6]}"
        self.api_series: Optional[SeriesAPI] = None

    def execute(self) -> None:
        # Create API wrapper
        api_series = SeriesAPI(self.series_id, self.series_type, self.pane_id, self.chart)
        if self.options:
            api_series.apply_options(self.options)
        # Register
        self.chart._series_registry[self.series_id] = api_series
        # Store underlying data container (empty series for now)
        self.chart._series_data[self.series_id] = OHLCVSeries(self.chart.chart_state.symbol, [])
        pane = self.chart.layout.get_pane(self.pane_id)
        if pane:
            pane.series_ids.append(self.series_id)
        # Store reference for undo
        self.api_series = api_series
        # Emit event
        self.chart.event_registry.emit("series_added", {"series_id": self.series_id, "type": self.series_type})

    def undo(self) -> None:
        # Remove from registries
        if self.series_id in self.chart._series_registry:
            del self.chart._series_registry[self.series_id]
        if self.series_id in self.chart._series_data:
            del self.chart._series_data[self.series_id]
        pane = self.chart.layout.get_pane(self.pane_id)
        if pane and self.series_id in pane.series_ids:
            pane.series_ids.remove(self.series_id)
        self.chart.event_registry.emit("series_removed", {"series_id": self.series_id})

class RemoveSeriesCommand(Command):
    """Command to remove an existing series from the chart."""

    def __init__(self, chart: Any, series_id: str):
        self.chart = chart
        self.series_id = series_id
        # Backup state for undo
        self.backup_api: Optional[SeriesAPI] = None
        self.backup_data: Optional[OHLCVSeries] = None
        self.backup_options: Optional[Dict[str, Any]] = None
        # Retrieve current series if exists
        api_series = chart._series_registry.get(series_id)
        if api_series is None:
            raise ValueError(f"Series with ID '{series_id}' not found.")
        self.backup_api = api_series
        self.backup_data = chart._series_data.get(series_id)
        self.backup_options = dict(api_series.options) if hasattr(api_series, "options") else None

    def execute(self) -> None:
        # Remove series from registries
        if self.series_id in self.chart._series_registry:
            del self.chart._series_registry[self.series_id]
        if self.series_id in self.chart._series_data:
            del self.chart._series_data[self.series_id]
        self.chart.event_registry.emit("series_removed", {"series_id": self.series_id})

    def undo(self) -> None:
        # Restore series
        if self.backup_api:
            self.chart._series_registry[self.series_id] = self.backup_api
        if self.backup_data:
            self.chart._series_data[self.series_id] = self.backup_data
        # Restore options if any
        if self.backup_options is not None and hasattr(self.backup_api, "options"):
            self.backup_api.options.update(self.backup_options)
        pane = self.chart.layout.get_pane(self.backup_api.pane_id if self.backup_api else None)
        if pane and self.series_id not in pane.series_ids:
            pane.series_ids.append(self.series_id)
        self.chart.event_registry.emit("series_added", {"series_id": self.series_id, "type": self.backup_api.series_type if self.backup_api else None})

class AddIndicatorCommand(Command):
    """Command to add an indicator to a chart (optionally bound to a series)."""

    def __init__(self, chart: Any, name: str, pane_id: Optional[str] = None, inputs: Optional[Dict[str, Any]] = None):
        self.chart = chart
        self.name = name
        self.pane_id = pane_id or "pane_main"
        self.inputs = inputs or {}
        self.indicator_id = f"ind_{name}_{uuid.uuid4().hex[:6]}"
        self.api_indicator: Optional[IndicatorAPI] = None

    def execute(self) -> None:
        api_ind = IndicatorAPI(self.indicator_id, self.name, self.pane_id, self.chart)
        if self.inputs:
            api_ind.inputs.update(self.inputs)
        self.chart._indicator_registry[self.indicator_id] = api_ind
        pane = self.chart.layout.get_pane(self.pane_id)
        if pane:
            pane.indicator_ids.append(self.indicator_id)
        self.api_indicator = api_ind
        self.chart.event_registry.emit("indicator_added", {"indicator_id": self.indicator_id, "name": self.name, "pane_id": self.pane_id})

    def undo(self) -> None:
        if self.indicator_id in self.chart._indicator_registry:
            del self.chart._indicator_registry[self.indicator_id]
        pane = self.chart.layout.get_pane(self.pane_id)
        if pane and self.indicator_id in pane.indicator_ids:
            pane.indicator_ids.remove(self.indicator_id)
        self.chart.event_registry.emit("indicator_removed", {"indicator_id": self.indicator_id})

class RemoveIndicatorCommand(Command):
    """Command to remove an existing indicator from the chart."""

    def __init__(self, chart: Any, indicator_id: str):
        self.chart = chart
        self.indicator_id = indicator_id
        self.backup_api: Optional[IndicatorAPI] = None
        self.backup_inputs: Optional[Dict[str, Any]] = None
        api_indicator = chart._indicator_registry.get(indicator_id)
        if api_indicator is None:
            raise ValueError(f"Indicator with ID '{indicator_id}' not found.")
        self.backup_api = api_indicator
        self.backup_inputs = dict(api_indicator.inputs) if hasattr(api_indicator, "inputs") else None

    def execute(self) -> None:
        if self.indicator_id in self.chart._indicator_registry:
            del self.chart._indicator_registry[self.indicator_id]
        self.chart.event_registry.emit("indicator_removed", {"indicator_id": self.indicator_id})

    def undo(self) -> None:
        if self.backup_api:
            self.chart._indicator_registry[self.indicator_id] = self.backup_api
            if self.backup_inputs is not None:
                self.backup_api.inputs.update(self.backup_inputs)
        self.chart.event_registry.emit("indicator_added", {"indicator_id": self.indicator_id, "name": self.backup_api.name if self.backup_api else None, "pane_id": self.backup_api.pane_id if self.backup_api else None})


class ModifyDrawingCommand(Command):
    """Command to modify drawing coordinates or properties."""

    def __init__(self, chart: Any, drawing_id: str, old_points: List[Dict[str, float]], old_properties: Dict[str, Any], new_points: List[Dict[str, float]], new_properties: Dict[str, Any]):
        self.chart = chart
        self.drawing_id = drawing_id
        self.old_points = old_points
        self.old_properties = old_properties
        self.new_points = new_points
        self.new_properties = new_properties

    def execute(self) -> None:
        drawing = self.chart.get_drawing(self.drawing_id)
        if drawing:
            drawing.points = self.new_points
            drawing.properties.clear()
            drawing.properties.update(self.new_properties)
            # Update state dict
            for d in self.chart.chart_state.drawings:
                if d.get("id") == self.drawing_id:
                    d["points"] = self.new_points
            self.chart.event_registry.emit("drawing_modified", {"drawing_id": self.drawing_id})

    def undo(self) -> None:
        drawing = self.chart.get_drawing(self.drawing_id)
        if drawing:
            drawing.points = self.old_points
            drawing.properties.clear()
            drawing.properties.update(self.old_properties)
            # Update state dict
            for d in self.chart.chart_state.drawings:
                if d.get("id") == self.drawing_id:
                    d["points"] = self.old_points
            self.chart.event_registry.emit("drawing_modified", {"drawing_id": self.drawing_id})

