import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pandas as pd

from EasyPyChart.data import ChartData
from EasyPyChart.layout_manager import LayoutManager


def _make_df(rows=20):
    dates = pd.date_range("2024-01-01", periods=rows, freq="D")
    return pd.DataFrame(
        {
            "Datetime": dates,
            "Open": range(rows),
            "High": [x + 1 for x in range(rows)],
            "Low": [x - 1 for x in range(rows)],
            "Close": range(rows),
            "Volume": [1000 + x for x in range(rows)],
        }
    )


def _make_group(df, uid, start_idx, end_idx):
    start_dt = df.iloc[start_idx]["Datetime"]
    end_dt = df.iloc[end_idx]["Datetime"]
    entry = float(df.iloc[start_idx]["Close"])
    sl = entry - 1.0
    target = entry + 2.0

    return {
        f"PosUnit_{uid}_SL": {
            "type": "rect",
            "points": [(start_dt, entry), (end_dt, sl)],
            "fill": "#FF0000",
            "label": "",
            "plot": "candlestick",
            "kwargs": {},
        },
        f"PosUnit_{uid}_Text_Entry": {
            "type": "text",
            "points": [(start_dt, entry)],
            "fill": "#FFFFFF",
            "text": f"Entry: {entry:.2f}",
            "plot": "candlestick",
            "kwargs": {},
        },
        f"PosUnit_{uid}_Text_SL": {
            "type": "text",
            "points": [(start_dt, sl)],
            "fill": "#FFAAAA",
            "text": f"Stop: {sl:.2f}",
            "plot": "candlestick",
            "kwargs": {},
        },
        f"PosUnit_{uid}_TGT": {
            "type": "rect",
            "points": [(start_dt, entry), (end_dt, target)],
            "fill": "#00B341",
            "label": "",
            "plot": "candlestick",
            "kwargs": {},
        },
        f"PosUnit_{uid}_Text_TGT": {
            "type": "text",
            "points": [(start_dt, target)],
            "fill": "#AAFFAA",
            "text": f"Target: {target:.2f}",
            "plot": "candlestick",
            "kwargs": {},
        },
    }


class FakeChart:
    def __init__(self, df):
        self.data = ChartData(df)
        self.drawings = {}
        self.config = {"offset_x": 0, "scale_x": 1}
        self.subplots = {"candlestick": {"weight": 3.0, "overlay_on": None, "bounds": (0, 1)}}
        self.calls = []

    def clear(self):
        self.drawings = {}

    def reset_subplots(self):
        self.subplots = {"candlestick": {"weight": 3.0, "overlay_on": None, "bounds": (0, 1)}}

    def create_subplot(self, name, weight=1.0, overlay_on=None):
        self.subplots[name] = {"weight": weight, "overlay_on": overlay_on, "bounds": (0, 1)}

    def render(self):
        pass

    def create_rectangle(self, *args, **kwargs):
        tag = kwargs.get("tags")
        self.calls.append(("rect", tag))
        self.drawings[tag] = {
            "type": "rect",
            "points": [(args[0], args[1]), (args[2], args[3])],
            "kwargs": kwargs,
        }
        return tag

    def create_text(self, *args, **kwargs):
        tag = kwargs.get("tags")
        self.calls.append(("text", tag))
        self.drawings[tag] = {
            "type": "text",
            "points": [(args[0], args[1])],
            "kwargs": kwargs,
        }
        return tag


def test_narrow_position_group_is_skipped():
    df = _make_df()
    chart = FakeChart(df)
    layout = LayoutManager(chart)
    layout.current_symbol = "ABC"
    layout.current_timeframe = "1d"
    layout.symbol_drawings["ABC"] = _make_group(df, uid="1", start_idx=0, end_idx=5)

    layout._restore_drawings()

    assert chart.calls == []


def test_wide_position_group_is_rendered():
    df = _make_df()
    chart = FakeChart(df)
    layout = LayoutManager(chart)
    layout.current_symbol = "ABC"
    layout.current_timeframe = "1d"
    layout.symbol_drawings["ABC"] = _make_group(df, uid="2", start_idx=0, end_idx=6)

    layout._restore_drawings()

    assert any(kind == "rect" for kind, _ in chart.calls)
    assert any(kind == "text" for kind, _ in chart.calls)


if __name__ == "__main__":
    test_narrow_position_group_is_skipped()
    test_wide_position_group_is_rendered()
    print("Position width filter regression passed.")
