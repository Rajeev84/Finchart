import os
import sys
from unittest.mock import MagicMock

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from EasyPyChart.interaction_manager import InteractionManager
from EasyPyChart.layout_manager import LayoutManager


class FakeData:
    def get_index_from_time(self, time_val):
        return float(time_val)

    def get_time_from_index(self, idx):
        return float(idx)


class FakeChart:
    def __init__(self):
        self.callback = MagicMock()
        self.selected_tags = set()
        self.drawings = {}
        self.drag_start = None
        self.data = FakeData()
        self.aline_calls = []
        self.line_calls = []
        self.width = 200
        self.height = 200
        self.subplots = {
            "candlestick": {"bounds": (0.25, 0.75), "overlay_on": None},
            "rsi": {"bounds": (0.75, 1.0), "overlay_on": None},
        }
        self.price_ranges = {
            "candlestick": (0.0, 100.0),
            "rsi": (0.0, 100.0),
        }

    def render(self):
        pass

    def get_chart_area(self):
        return self.width, self.height

    def _panel_pixels(self, plot_name):
        bounds = self.subplots[plot_name]["bounds"]
        return bounds[0] * self.height, bounds[1] * self.height

    def _price_range(self, plot_name):
        return self.price_ranges[plot_name]

    def get_plot_at_y(self, y):
        norm_y = y / self.height
        for name, sp in self.subplots.items():
            if sp.get("overlay_on"):
                continue
            top, bottom = sp["bounds"]
            if top <= norm_y <= bottom:
                return name
        return None

    def transform_index_to_x(self, idx):
        return float(idx)

    def transform_price_to_y(self, price, plot_name="candlestick"):
        top, bottom = self._panel_pixels(plot_name)
        low, high = self._price_range(plot_name)
        span = high - low
        if span == 0:
            span = 1.0
        ratio = (float(price) - low) / span
        return bottom - ratio * (bottom - top)

    def inverse_transform_x(self, x):
        return float(x)

    def inverse_transform_y(self, y):
        for name, sp in self.subplots.items():
            if sp.get("overlay_on"):
                continue
            top, bottom = self._panel_pixels(name)
            if top <= y <= bottom:
                low, high = self._price_range(name)
                span = bottom - top
                if span == 0:
                    return low
                ratio = (bottom - y) / span
                return low + ratio * (high - low)
        return 0.0

    def create_aline(self, *args, **kwargs):
        self.aline_calls.append((args, kwargs))
        return "ghost"

    def create_line(self, *args, **kwargs):
        self.line_calls.append((args, kwargs))
        return "line"


def make_interaction_manager():
    chart = FakeChart()
    layout = MagicMock()
    im = InteractionManager(chart, layout)
    return chart, layout, im


def test_angle_tool_defaults_to_45_degrees_and_stays_up_right():
    chart, layout, im = make_interaction_manager()

    im.active_angle = 80.0
    im.set_tool("angle_line")

    assert im.active_angle == 45.0
    assert im.capture_state["target"] == 1

    im._handle_capture(
        "move",
        {"time": 10.0, "y": 80.0, "sub_plot": "candlestick"},
    )
    assert chart.aline_calls, "Expected a ghost angle line to be drawn"

    args, kwargs = chart.aline_calls[-1]
    x1, y1, x2, y2 = args[:4]
    assert x2 > x1
    assert y2 > y1
    assert kwargs["tags"] == "ghost"
    assert kwargs["plot_name"] == "candlestick"

    im._handle_capture(
        "click",
        {"button": "left", "time": 10.0, "y": 80.0, "sub_plot": "candlestick"},
    )

    layout.add_drawing.assert_called_once()
    args, kwargs = layout.add_drawing.call_args
    _, shape_type, points = args[:3]
    assert shape_type == "line"
    start_pt, end_pt = points
    assert end_pt[0] > start_pt[0]
    assert end_pt[1] > start_pt[1]
    assert kwargs["plot_name"] == "candlestick"


def test_angle_tool_keeps_subplot_context_for_preview_and_commit():
    chart, layout, im = make_interaction_manager()

    im.set_tool("angle_line")
    im._handle_capture(
        "move",
        {"time": 25.0, "y": 40.0, "sub_plot": "rsi"},
    )

    args, kwargs = chart.aline_calls[-1]
    assert kwargs["plot_name"] == "rsi"
    x1, y1, x2, y2 = args[:4]
    assert x2 > x1
    assert y2 > y1

    im._handle_capture(
        "click",
        {"button": "left", "time": 25.0, "y": 40.0, "sub_plot": "rsi"},
    )

    args, kwargs = layout.add_drawing.call_args
    assert kwargs["plot_name"] == "rsi"


def test_layout_manager_replays_angle_line_with_plot_name():
    chart = FakeChart()
    layout = LayoutManager(chart)
    layout.current_symbol = "TEST"
    layout.symbol_drawings["TEST"] = {
        "aline_1": {
            "type": "line",
            "points": [(10.0, 40.0), (20.0, 60.0)],
            "kwargs": {"plot_name": "rsi", "color": "#FF0000", "label": "AngleLine"},
        }
    }

    layout._restore_drawings()

    assert chart.line_calls, "Expected the stored line to be replayed"
    args, kwargs = chart.line_calls[-1]
    assert kwargs["plot_name"] == "rsi"
    assert kwargs["tags"] == "aline_1"


if __name__ == "__main__":
    test_angle_tool_defaults_to_45_degrees_and_stays_up_right()
    test_angle_tool_keeps_subplot_context_for_preview_and_commit()
    test_layout_manager_replays_angle_line_with_plot_name()
    print("Angle line regression passed.")
