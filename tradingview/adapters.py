"""
FinChart TradingView Adapters module (Layer 1.8).
Provides EasyPyChart legacy compatibility and TradingView lightweight-charts style compatibility wrappers.
"""

from typing import List, Dict, Any, Optional, Callable
from .chart_api import Chart
from .types import OHLCVBar
from .api_entities import SeriesAPI, IndicatorAPI, DrawingAPI, PaneAPI
from .event_subscription import Subscription


class EasyPyChartAdapter:
    """Pythonic legacy compatibility wrapper delegating to canonical FinChart public API."""

    def __init__(self, chart: Chart):
        self.chart = chart

    def load_data(self, data: List[OHLCVBar]) -> None:
        self.chart.set_data(data)

    def create_subplot(self, title: str = "Subplot", height: float = 150.0) -> PaneAPI:
        return self.chart.add_pane(height=height)

    def create_series(self, series_type: str = "candlestick", pane_id: str = "pane_main") -> SeriesAPI:
        return self.chart.add_series(series_type=series_type, pane_id=pane_id)

    def create_line(self, x1: float, y1: float, x2: float, y2: float, pane_id: str = "pane_main") -> DrawingAPI:
        points = [{"time": x1, "price": y1}, {"time": x2, "price": y2}]
        return self.chart.create_multipoint_shape(points, shape_type="trend_line", pane_id=pane_id)

    def create_hline(self, price: float, pane_id: str = "pane_main") -> DrawingAPI:
        points = [{"time": 0.0, "price": price}, {"time": 1000.0, "price": price}]
        return self.chart.create_multipoint_shape(points, shape_type="horizontal_line", pane_id=pane_id)

    def create_vline(self, time_index: float, pane_id: str = "pane_main") -> DrawingAPI:
        points = [{"time": time_index, "price": 0.0}, {"time": time_index, "price": 10000.0}]
        return self.chart.create_multipoint_shape(points, shape_type="vertical_line", pane_id=pane_id)

    def create_rectangle(self, x1: float, y1: float, x2: float, y2: float, pane_id: str = "pane_main") -> DrawingAPI:
        points = [{"time": x1, "price": y1}, {"time": x2, "price": y2}]
        return self.chart.create_multipoint_shape(points, shape_type="rectangle", pane_id=pane_id)

    def create_text(self, text: str, x: float, y: float, pane_id: str = "pane_main") -> DrawingAPI:
        drawing = self.chart.create_shape({"time": x, "price": y}, shape_type="text", pane_id=pane_id)
        drawing.set_properties({"text": text})
        return drawing

    def save_session(self) -> Dict[str, Any]:
        return self.chart.save_session()

    def load_session(self, session_data: Dict[str, Any]) -> None:
        self.chart.load_session(session_data)


class TradingViewAdapter:
    """TradingView Lightweight-Charts style compatibility wrapper delegating to canonical FinChart public API."""

    def __init__(self, chart: Chart):
        self.chart = chart

    def addSeries(self, series_type: str, options: Optional[Dict[str, Any]] = None) -> SeriesAPI:
        return self.chart.add_series(series_type=series_type, options=options)

    def createShape(self, point: Dict[str, float], options: Optional[Dict[str, Any]] = None) -> DrawingAPI:
        shape_type = options.get("shape", "trend_line") if options else "trend_line"
        return self.chart.create_shape(point, shape_type=shape_type)

    def createMultipointShape(self, points: List[Dict[str, float]], options: Optional[Dict[str, Any]] = None) -> DrawingAPI:
        shape_type = options.get("shape", "trend_line") if options else "trend_line"
        return self.chart.create_multipoint_shape(points, shape_type=shape_type)

    def createAnchoredShape(self, x_percent: float, y_percent: float, options: Optional[Dict[str, Any]] = None) -> DrawingAPI:
        shape_type = options.get("shape", "text") if options else "text"
        return self.chart.create_anchored_shape(x_percent, y_percent, shape_type=shape_type)

    def getAllShapes(self) -> List[DrawingAPI]:
        return self.chart.get_drawings()

    def removeEntity(self, entity_id: str) -> bool:
        if self.chart.remove_series(entity_id):
            return True
        if self.chart.remove_indicator(entity_id):
            return True
        if self.chart.remove_drawing(entity_id):
            return True
        return False

    def removeAllShapes(self) -> None:
        for drawing in self.chart.get_drawings():
            self.chart.remove_drawing(drawing.drawing_id)

    def subscribe(self, event_name: str, callback: Callable[[Any], None]) -> Subscription:
        return self.chart.on(event_name, callback)

    def unsubscribe(self, subscription: Subscription) -> None:
        self.chart.off(subscription)

# Added Features:
# - EasyPyChartAdapter and TradingViewAdapter compatibility wrappers mapping to canonical FinChart API methods.
