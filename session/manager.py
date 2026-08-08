"""Persistent workspace/session manager for FinChart."""
from __future__ import annotations

import copy
import importlib
import json
import os
import time
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .schema import SCHEMA_VERSION, SessionState
from ..core.types import ChartType


class SessionManager:
    """Owns serializable workspace state and context switching.

    A context is ``(symbol, timeframe)``.  Drawings and viewport state are
    isolated per context; market data itself is intentionally not persisted.
    """

    def __init__(self, widget) -> None:
        self.widget = widget
        self.current_symbol = "default"
        self.current_timeframe = "default"
        self._contexts: Dict[str, Dict[str, Any]] = {}
        self._logger = logging.getLogger(__name__)

    @property
    def current_context(self) -> Tuple[str, str]:
        return self.current_symbol, self.current_timeframe

    @staticmethod
    def context_key(symbol: str, timeframe: str) -> str:
        return f"{symbol}|{timeframe}"

    def set_context(self, symbol: str, timeframe: str,
                    data: Any = None, clear_data: bool = True) -> None:
        """Switch logical chart context and restore its workspace state.

        If ``data`` is supplied it becomes the new context's data.  If no data
        is supplied, the existing data is retained by default unless
        ``clear_data`` is True.
        """
        symbol = str(symbol)
        timeframe = str(timeframe)
        if (symbol, timeframe) == self.current_context:
            if data is not None:
                self.widget.set_data(data)
            return

        self.capture_current_context()
        self.current_symbol = symbol
        self.current_timeframe = timeframe

        self.widget._drawings.clear()
        self.widget._drawing_tools.clear()
        self.widget._selection_manager.unselect()

        if data is not None:
            self.widget.set_data(data)
        elif clear_data:
            self.widget.set_data([])

        self.restore_current_context()
        self.widget._pipeline.force_full_redraw()
        self.widget._request_render()

    def capture_current_context(self) -> None:
        """Snapshot drawings and viewport for the active context."""
        key = self.context_key(self.current_symbol, self.current_timeframe)
        self._contexts[key] = {
            "symbol": self.current_symbol,
            "timeframe": self.current_timeframe,
            "drawings": {
                did: copy.deepcopy(state.to_dict())
                for did, state in self.widget._drawings.items()
            },
            "view": self._capture_view_state(),
        }

    def restore_current_context(self) -> None:
        """Restore drawings and viewport belonging to current context."""
        key = self.context_key(self.current_symbol, self.current_timeframe)
        state = self._contexts.get(key, {})
        self._restore_drawings(state.get("drawings", {}))
        self._restore_view_state(state.get("view", {}))

    def _capture_view_state(self) -> Dict[str, Any]:
        ce = self.widget._coord_engine
        count = self.widget._data_store.count
        spacing = float(ce.time_scale.bar_spacing)
        offset = float(ce.time_scale.offset)
        vp = ce.viewport
        right_index = ce.x_to_index(vp.right) if spacing > 0 else 0.0
        return {
            "bar_spacing": spacing,
            "offset_from_end": float(count - right_index),
            "visible_range": {
                "start_index": ce.visible_range.start_index,
                "end_index": ce.visible_range.end_index,
            },
            "price_scales": {
                name: {
                    "min_price": float(scale.min_price),
                    "max_price": float(scale.max_price),
                    "top_padding": float(scale.top_padding),
                    "bottom_padding": float(scale.bottom_padding),
                    "is_log": bool(scale.is_log),
                    "is_auto": bool(scale.is_auto),
                    "fixed_range": bool(scale.fixed_range),
                }
                for name, scale in ce._price_scales.items()
            },
        }

    def _restore_view_state(self, state: Dict[str, Any]) -> None:
        if not state:
            return
        ce = self.widget._coord_engine
        spacing = state.get("bar_spacing")
        if spacing is not None:
            ce.time_scale.bar_spacing = max(
                ce.time_scale.min_bar_spacing,
                min(ce.time_scale.max_bar_spacing, float(spacing))
            )
        distance = state.get("offset_from_end")
        if distance is not None:
            vp = ce.viewport
            count = self.widget._data_store.count
            right_index = count - float(distance)
            ce.time_scale.offset = vp.right - right_index * ce.time_scale.bar_spacing

        for name, cfg in state.get("price_scales", {}).items():
            ps = ce.get_pane_price_scale(name)
            for attr in ("min_price", "max_price", "top_padding",
                         "bottom_padding", "is_log", "is_auto", "fixed_range"):
                if attr in cfg:
                    setattr(ps, attr, cfg[attr])

        self.widget._update_visible_range()

    def _restore_drawings(self, drawings: Dict[str, Any]) -> None:
        from ..drawing.base import DrawingState
        for did, raw in drawings.items():
            state = DrawingState.from_dict(raw)
            self.widget._drawings[state.id] = state
            self.widget._drawing_tools[state.id] = self.widget._create_tool(state)

    def _indicator_to_dict(self, indicator) -> Dict[str, Any]:
        params = dict(getattr(indicator, "params", {}) or {})
        # Store constructor-relevant scalar attributes when available.  The
        # params field remains the stable plugin contract.
        data = {
            "module": indicator.__class__.__module__,
            "class": indicator.__class__.__name__,
            "name": indicator.name,
            "pane": getattr(indicator, "pane", "candlestick"),
            "params": self._json_safe(params),
        }
        return data

    def _indicator_from_dict(self, raw: Dict[str, Any]):
        module_name = raw.get("module", "")
        class_name = raw.get("class", "")
        if not module_name.startswith("finchart.indicators"):
            raise ValueError(f"Unsupported indicator module: {module_name}")
        module = importlib.import_module(module_name)
        cls = getattr(module, class_name, None)
        if cls is None:
            raise ValueError(f"Unknown indicator class: {class_name}")

        params = dict(raw.get("params") or {})
        # Built-in indicator constructors use explicit arguments, so filter
        # the generic params dictionary to their accepted signatures.
        import inspect
        sig = inspect.signature(cls.__init__)
        kwargs = {}
        for key, value in params.items():
            if key in sig.parameters:
                kwargs[key] = value
        indicator = cls(**kwargs)
        if raw.get("pane") and raw["pane"] != "candlestick":
            indicator.pane = raw["pane"]
        return indicator

    def build_state(self) -> Dict[str, Any]:
        self.capture_current_context()
        contexts = copy.deepcopy(self._contexts)

        # Preserve current chart state and settings separately from contexts.
        chart_type = getattr(self.widget._series_renderer, "chart_type", ChartType.CANDLESTICK)
        chart_name = chart_type.name if isinstance(chart_type, ChartType) else str(chart_type)
        theme = getattr(self.widget, "_theme", None)
        theme_name = theme.__class__.__name__ if theme else None

        state = SessionState(
            current_context={
                "symbol": self.current_symbol,
                "timeframe": self.current_timeframe,
            },
            layout=self.widget._layout_manager.snapshot(),
            indicators=[self._indicator_to_dict(i) for i in self.widget._indicators],
            contexts=contexts,
            chart={"chart_type": chart_name, "theme": theme_name},
            settings={
                "auto_scale": bool(self.widget._auto_scale),
                "right_offset_bars": int(self.widget._right_offset_bars),
            },
            metadata={"saved_at": time.time()},
        )
        return state.to_dict()

    def save(self, filepath: str) -> None:
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(self.build_state(), f, indent=2, ensure_ascii=False)

    def load(self, filepath: str) -> None:
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(str(path))
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)

        if not isinstance(raw, dict):
            raise ValueError("Session root must be a JSON object")
        if "schema_version" not in raw:
            raw = self._upgrade_v1(raw)

        version = int(raw.get("schema_version", 1))
        if version > SCHEMA_VERSION:
            raise ValueError(
                f"Session schema {version} is newer than supported {SCHEMA_VERSION}"
            )

        # Validate and construct all external/plugin state before mutating the widget.
        new_contexts = raw.get("contexts", {})
        if not isinstance(new_contexts, dict):
            raise ValueError("Session contexts must be an object")
        ctx = raw.get("current_context", {})
        if not isinstance(ctx, dict):
            raise ValueError("Session current_context must be an object")
        new_symbol = str(ctx.get("symbol", "default"))
        new_timeframe = str(ctx.get("timeframe", "default"))

        new_indicators = []
        indicator_errors = []
        for index, item in enumerate(raw.get("indicators", [])):
            try:
                new_indicators.append(self._indicator_from_dict(item))
            except (ImportError, AttributeError, TypeError, ValueError) as exc:
                indicator_errors.append(f"indicator[{index}]: {exc}")
        if indicator_errors:
            raise ValueError("Session contains invalid indicators: " + "; ".join(indicator_errors))

        chart = raw.get("chart", {})
        if not isinstance(chart, dict):
            raise ValueError("Session chart must be an object")
        chart_name = chart.get("chart_type")
        chart_type = None
        if chart_name:
            try:
                chart_type = ChartType[chart_name]
            except KeyError as exc:
                raise ValueError(f"Unsupported chart type in session: {chart_name!r}") from exc

        settings = raw.get("settings", {})
        if not isinstance(settings, dict):
            raise ValueError("Session settings must be an object")
        new_auto_scale = bool(settings.get("auto_scale", True))
        new_right_offset = int(settings.get("right_offset_bars", 5))
        if new_right_offset < 0:
            raise ValueError("right_offset_bars cannot be negative")

        # Validate layout without changing the live layout first.
        layout_state = raw.get("layout", {})
        panes = (layout_state or {}).get("panes", {})
        if not isinstance(panes, dict):
            raise ValueError("Session layout.panes must be an object")
        for name, cfg in panes.items():
            if not isinstance(cfg, dict):
                raise ValueError(f"Invalid pane configuration: {name!r}")
            if float(cfg.get("weight", 1.0)) <= 0:
                raise ValueError(f"Pane {name!r} weight must be greater than zero")

        # Apply validated state.
        self._contexts = copy.deepcopy(new_contexts)
        self.current_symbol = new_symbol
        self.current_timeframe = new_timeframe
        self.widget._layout_manager.restore(layout_state)
        self.widget._layout_engine = self.widget._layout_manager.engine
        self.widget._indicators = new_indicators
        self.widget._auto_scale = new_auto_scale
        self.widget._right_offset_bars = new_right_offset

        if chart_type is not None:
            self.widget.set_chart_type(chart_type)

        theme_name = chart.get("theme")
        if theme_name == "DarkTheme":
            from ..themes.style import DarkTheme
            self.widget.set_theme(DarkTheme())
        elif theme_name == "LightTheme":
            from ..themes.style import LightTheme
            self.widget.set_theme(LightTheme())

        self.widget._layout_manager.sync_indicators(self.widget._indicators)
        self.widget._update_viewport()
        self.widget._update_indicators()
        self.widget._update_price_scale()

        self.widget._drawings.clear()
        self.widget._drawing_tools.clear()
        self.widget._selection_manager.unselect()
        self.restore_current_context()
        self.widget._pipeline.force_full_redraw()
        self.widget._request_render()

    def _upgrade_v1(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        drawings = raw.get("drawings", {})
        normalized = {}
        for did, d in drawings.items():
            normalized[did] = {
                "id": did,
                "tool_type": d.get("tool_type", ""),
                "label": d.get("label", ""),
                "points": d.get("points", []),
                "color": d.get("color", "#FFA500"),
                "width": d.get("width", 2.0),
                "style": d.get("style", "solid"),
                "fill": d.get("fill"),
                "visible": d.get("visible", True),
                "selected": False,
                "hovered": False,
                "locked": d.get("locked", False),
                "pane_name": d.get("pane_name", "candlestick"),
                "quantity": d.get("quantity", 1.0),
            }
        return {
            "schema_version": 2,
            "current_context": {"symbol": "default", "timeframe": "default"},
            "layout": {"panes": {"candlestick": {"weight": 3.0, "overlay_on": None}}},
            "indicators": [],
            "contexts": {
                "default|default": {
                    "symbol": "default",
                    "timeframe": "default",
                    "drawings": normalized,
                    "view": {},
                }
            },
            "chart": {},
            "settings": {},
            "metadata": {"upgraded_from": "1.0"},
        }

    @staticmethod
    def _json_safe(value):
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, (list, tuple)):
            return [SessionManager._json_safe(v) for v in value]
        if isinstance(value, dict):
            return {str(k): SessionManager._json_safe(v) for k, v in value.items()
                    if not callable(v)}
        return str(value)
