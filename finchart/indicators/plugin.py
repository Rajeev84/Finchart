"""BaseIndicator Plugin Contract - EasyPyChart-compatible indicator system.

This module defines the BaseIndicator plugin contract that matches EasyPyChart's
indicator system exactly, allowing user-defined indicators from def_scanners.py
to work seamlessly with FinChart.
"""
from __future__ import annotations

from typing import Optional, Any, List, Dict
import pandas as pd


class BaseIndicator:
    """Base class for all indicator plugins.
    
    This contract must match EasyPyChart's BaseIndicator exactly to ensure
    compatibility with existing user-defined indicators.
    
    Attributes:
        name: Display name of the indicator
        description: Human-readable description of what the indicator does
        defaults: Default parameter values
        param_schema: Schema for UI parameter generation (list of param definitions)
    """
    name: str = "Base"
    description: str = "Base indicator"
    defaults: dict = {}
    param_schema: list = []

    @classmethod
    def calculate(cls, df: pd.DataFrame, params: dict) -> Optional[pd.Series]:
        """Pure calculation. No side effects.
        
        Args:
            df: DataFrame with OHLCV data (columns: open, high, low, close, volume)
            params: Parameter values for the indicator
            
        Returns:
            Series with calculated values, or None if calculation fails
        """
        return None

    @classmethod
    def on_render(
        cls,
        chart: Any,
        subplot: str,
        params: dict,
        df: Optional[pd.DataFrame] = None
    ) -> None:
        """Side effects: hlines, markers, extra series, etc.
        
        This method is called after calculate() to add visual elements
        like horizontal lines, markers, or additional series to the chart.
        
        Args:
            chart: Chart handle (or proxy) for rendering operations
            subplot: Name of the subplot to render in
            params: Parameter values for the indicator
            df: DataFrame with OHLCV data (optional, may be None)
        """
        pass