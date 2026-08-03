"""Indicator Adapter - Bridge between BaseIndicator plugins and FinChart rendering.

This module provides:
1. ChartProxy: A thin proxy that exposes EasyPyChart-compatible chart methods
2. IndicatorAdapter: A bridge that converts BaseIndicator output to FinChart rendering commands
"""
from __future__ import annotations

from typing import Optional, Any, List, Dict, Tuple
import pandas as pd

from .plugin import BaseIndicator
from ..core.types import OHLCV, Color
from ..coordinates.engine import CoordinateEngine
from ..rendering.pipeline import DrawCommand, Layer


class ChartProxy:
    """Thin proxy that exposes EasyPyChart-compatible chart methods.
    
    This proxy allows existing BaseIndicator.on_render() implementations
    to work without modification by providing methods that match
    EasyPyChart's chart API.
    """
    
    def __init__(
        self,
        coord_engine: CoordinateEngine,
        pipeline: Any,
        viewport: Any,
        subplot: str = "candlestick"
    ):
        self._coord = coord_engine
        self._pipeline = pipeline
        self._viewport = viewport
        self._subplot = subplot
        self._commands: List[DrawCommand] = []
    
    def create_series(
        self,
        name: str,
        data: pd.Series,
        color: str = "#2196F3",
        width: float = 1.5,
        style: str = "line"
    ) -> None:
        """Create a series on the chart.
        
        Args:
            name: Series name for tagging
            data: Pandas Series with values
            color: Color hex string
            width: Line width
            style: "line", "area", or "histogram"
        """
        # Convert pandas Series to list of floats
        values = data.tolist()
        
        # Generate coordinate points
        points = []
        for i, val in enumerate(values):
            if val is None or pd.isna(val):
                continue
            x = self._coord.index_to_x(i)
            y = self._coord.price_to_y(val, self._viewport, self._subplot)
            points.extend([x, y])
        
        if len(points) < 4:
            return
        
        if style == "line":
            self._commands.append(DrawCommand(
                layer=Layer.INDICATORS,
                tag=f"series_{name}",
                item_type="line",
                coords=tuple(points),
                options={"fill": color, "width": width},
                z_index=10
            ))
        elif style == "histogram":
            # Render as histogram bars
            bar_w = self._coord.get_bar_width()
            for i, val in enumerate(values):
                if val is None or pd.isna(val):
                    continue
                x = self._coord.index_to_x(i)
                y_zero = self._coord.price_to_y(0, self._viewport, self._subplot)
                y_val = self._coord.price_to_y(val, self._viewport, self._subplot)
                
                self._commands.append(DrawCommand(
                    layer=Layer.INDICATORS,
                    tag=f"hist_{name}_{i}",
                    item_type="rectangle",
                    coords=(x - bar_w/2, min(y_zero, y_val), x + bar_w/2, max(y_zero, y_val)),
                    options={"fill": color, "outline": color},
                    z_index=5
                ))
    
    def create_hline(
        self,
        price: float,
        color: str = "#FF9800",
        width: float = 1.0,
        dash: Optional[str] = None,
        label: Optional[str] = None
    ) -> None:
        """Create a horizontal line at the given price.
        
        Args:
            price: Price level for the line
            color: Color hex string
            width: Line width
            dash: Dash pattern (e.g., "--", "-.")
            label: Optional text label
        """
        y = self._coord.price_to_y(price, self._viewport, self._subplot)
        
        options = {"fill": color, "width": width}
        if dash:
            options["dash"] = dash
        
        self._commands.append(DrawCommand(
            layer=Layer.INDICATORS,
            tag=f"hline_{price}",
            item_type="line",
            coords=(self._viewport.left, y, self._viewport.right, y),
            options=options,
            z_index=8
        ))
        
        if label:
            self.create_text(self._viewport.right - 50, y, label, color)
    
    def create_line(
        self,
        start_price: float,
        end_price: float,
        start_index: int,
        end_index: int,
        color: str = "#2196F3",
        width: float = 1.5
    ) -> None:
        """Create a line between two points.
        
        Args:
            start_price: Starting price
            end_price: Ending price
            start_index: Starting bar index
            end_index: Ending bar index
            color: Color hex string
            width: Line width
        """
        x1 = self._coord.index_to_x(start_index)
        y1 = self._coord.price_to_y(start_price, self._viewport, self._subplot)
        x2 = self._coord.index_to_x(end_index)
        y2 = self._coord.price_to_y(end_price, self._viewport, self._subplot)
        
        self._commands.append(DrawCommand(
            layer=Layer.INDICATORS,
            tag=f"line_{start_index}_{end_index}",
            item_type="line",
            coords=(x1, y1, x2, y2),
            options={"fill": color, "width": width},
            z_index=9
        ))
    
    def create_text(
        self,
        x: float,
        y: float,
        text: str,
        color: str = "#FFFFFF",
        anchor: str = "center"
    ) -> None:
        """Create text at the given coordinates.
        
        Args:
            x: X coordinate
            y: Y coordinate
            text: Text content
            color: Color hex string
            anchor: Text anchor (center, left, right, etc.)
        """
        self._commands.append(DrawCommand(
            layer=Layer.INDICATORS,
            tag=f"text_{x}_{y}",
            item_type="text",
            coords=(x, y),
            options={"text": text, "fill": color, "anchor": anchor},
            z_index=15
        ))
    
    def get_commands(self) -> List[DrawCommand]:
        """Get all accumulated draw commands."""
        return self._commands
    
    def clear_commands(self) -> None:
        """Clear accumulated commands."""
        self._commands.clear()


class IndicatorAdapter:
    """Bridge that wraps BaseIndicator and converts to FinChart rendering.
    
    This adapter:
    1. Converts FinChart's List[OHLCV] to pandas DataFrame for calculate()
    2. Calls calculate() to get indicator values
    3. Creates a ChartProxy for on_render()
    4. Calls on_render() to let indicator add visual elements
    5. Returns FinChart DrawCommand objects
    """
    
    def __init__(
        self,
        indicator_class: type[BaseIndicator],
        params: Dict[str, Any],
        subplot: str = "candlestick"
    ):
        self._indicator_class = indicator_class
        self._params = params
        self._subplot = subplot
        self._last_series: Optional[pd.Series] = None
    
    def calculate(self, data: List[OHLCV]) -> Optional[pd.Series]:
        """Calculate indicator values from OHLCV data.
        
        Args:
            data: List of OHLCV bars
            
        Returns:
            Pandas Series with calculated values
        """
        # Convert List[OHLCV] to pandas DataFrame
        df = self._ohlcv_to_dataframe(data)
        if df is None or df.empty:
            return None
        
        # Call indicator's calculate method
        self._last_series = self._indicator_class.calculate(df, self._params)
        return self._last_series
    
    def render(
        self,
        coord_engine: CoordinateEngine,
        pipeline: Any,
        viewport: Any,
        start_idx: int,
        end_idx: int
    ) -> List[DrawCommand]:
        """Generate draw commands for the indicator.
        
        Args:
            coord_engine: FinChart's coordinate engine
            pipeline: FinChart's rendering pipeline
            viewport: Current viewport
            start_idx: Start index for visible range
            end_idx: End index for visible range
            
        Returns:
            List of DrawCommand objects
        """
        # Create chart proxy
        proxy = ChartProxy(coord_engine, pipeline, viewport, self._subplot)
        
        # Call indicator's on_render method
        # Pass None for df since indicator should use cached calculation
        self._indicator_class.on_render(proxy, self._subplot, self._params, None)
        
        # Return accumulated commands
        return proxy.get_commands()
    
    @staticmethod
    def _ohlcv_to_dataframe(data: List[OHLCV]) -> Optional[pd.DataFrame]:
        """Convert List[OHLCV] to pandas DataFrame.
        
        Args:
            data: List of OHLCV bars
            
        Returns:
            DataFrame with columns: open, high, low, close, volume
        """
        if not data:
            return None
        
        # Extract data
        records = []
        for bar in data:
            records.append({
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume if hasattr(bar, 'volume') else 0
            })
        
        return pd.DataFrame(records)