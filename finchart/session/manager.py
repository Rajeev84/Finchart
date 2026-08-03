"""Session Manager - Per-symbol context management for indicators and layouts.

This module provides SessionManager for managing per-symbol indicator configurations,
view states, and data isolation, matching EasyPyChart's LayoutManager pattern.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
import uuid
import pandas as pd

from ..core.types import OHLCV


@dataclass
class SessionState:
    """State for a single (symbol, timeframe) context.
    
    Each session maintains independent indicator configurations, subplot layouts,
    and view states to ensure complete isolation between different symbols/timeframes.
    """
    symbol: str
    timeframe: str
    data: List[OHLCV] = field(default_factory=list)
    indicators: List[Dict[str, Any]] = field(default_factory=list)  # [{"id": str, "type": str, "params": dict, "subplot": str}]
    subplot_configs: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # {"candlestick": {"weight": 3.0}, "RSI_123": {"weight": 1.0}}
    view_state: Dict[str, Any] = field(default_factory=dict)  # {"zoom": float, "scroll_offset": int}


class SessionManager:
    """Manages per-symbol indicator configurations and view states.
    
    SessionManager provides the core functionality for:
    - Isolating indicator configurations per symbol/timeframe
    - Storing and restoring view states (zoom, scroll)
    - Managing subplot layouts per context
    - Providing context switching between different symbols
    """
    
    def __init__(self):
        self._sessions: Dict[Tuple[str, str], SessionState] = {}
        self._current_context: Optional[Tuple[str, str]] = None
        self._chart_widget: Optional[Any] = None  # Reference to ChartWidget
    
    def set_chart_widget(self, widget: Any) -> None:
        """Set the ChartWidget reference for rendering operations.
        
        Args:
            widget: The ChartWidget instance
        """
        self._chart_widget = widget
    
    def set_context(self, symbol: str, timeframe: str, data: Optional[List[OHLCV]] = None) -> None:
        """Switch to a new symbol/timeframe context.
        
        This method:
        1. Saves current context state if there is one
        2. Loads the new context state (or creates a new one)
        3. Updates the ChartWidget with the new data and indicator configurations
        4. Restores the view state for the new context
        
        Args:
            symbol: Symbol name (e.g., "AAPL")
            timeframe: Timeframe string (e.g., "1m", "1h", "1d")
            data: OHLCV data for the symbol (optional, uses existing if not provided)
        """
        # Save current context if we have one
        if self._current_context and self._chart_widget:
            self._save_current_context()
        
        # Switch to new context
        context_key = (symbol, timeframe)
        self._current_context = context_key
        
        # Get or create session state
        if context_key not in self._sessions:
            self._sessions[context_key] = SessionState(
                symbol=symbol,
                timeframe=timeframe,
                data=data or []
            )
        else:
            # Update data if provided
            if data is not None:
                self._sessions[context_key].data = data
        
        # Apply context to ChartWidget
        if self._chart_widget:
            self._apply_context(context_key)
    
    def add_indicator_config(
        self,
        indicator_type: str,
        params: Optional[Dict[str, Any]] = None,
        subplot: str = "candlestick"
    ) -> str:
        """Add an indicator configuration to the current context.
        
        Args:
            indicator_type: Name of the indicator type (must be registered)
            params: Parameter values for the indicator
            subplot: Subplot name ("candlestick" for overlay, or custom name)
            
        Returns:
            Unique indicator ID for the new indicator
        """
        if not self._current_context:
            raise RuntimeError("No active context. Call set_context() first.")
        
        # Generate unique ID
        ind_id = f"{indicator_type}_{uuid.uuid4().hex[:8]}"
        
        # Get default params if not provided
        from ..indicators.registry import get_indicator
        indicator_class = get_indicator(indicator_type)
        if indicator_class and params is None:
            params = indicator_class.defaults.copy()
        elif params is None:
            params = {}
        
        # Add to session
        session = self._sessions[self._current_context]
        session.indicators.append({
            "id": ind_id,
            "type": indicator_type,
            "params": params,
            "subplot": subplot
        })
        
        # Create subplot config if needed
        if subplot != "candlestick" and subplot not in session.subplot_configs:
            session.subplot_configs[subplot] = {"weight": 1.0}
            
            # Also add subplot to chart widget's layout engine
            if self._chart_widget and hasattr(self._chart_widget, '_layout_engine'):
                if subplot not in self._chart_widget._layout_engine.panes:
                    self._chart_widget._layout_engine.add_pane(subplot, weight=1.0)
        
        # Mark session as dirty for rebuild
        self._rebuild_indicators()
        
        return ind_id
    
    def remove_indicator_config(self, ind_id: str) -> None:
        """Remove an indicator configuration from the current context.
        
        Args:
            ind_id: Unique indicator ID to remove
        """
        if not self._current_context:
            raise RuntimeError("No active context. Call set_context() first.")
        
        session = self._sessions[self._current_context]
        
        # Find and remove indicator
        for i, ind in enumerate(session.indicators):
            if ind["id"] == ind_id:
                removed_subplot = ind["subplot"]
                session.indicators.pop(i)
                
                # Clean up empty subplot
                if removed_subplot != "candlestick":
                    # Check if any other indicators use this subplot
                    subplot_still_used = any(
                        ind["subplot"] == removed_subplot 
                        for ind in session.indicators
                    )
                    if not subplot_still_used:
                        session.subplot_configs.pop(removed_subplot, None)
                
                break
        
        # Rebuild indicators
        self._rebuild_indicators()
    
    def update_indicator_params(self, ind_id: str, params: Dict[str, Any]) -> None:
        """Update parameters for an indicator in the current context.
        
        Args:
            ind_id: Unique indicator ID to update
            params: New parameter values
        """
        if not self._current_context:
            raise RuntimeError("No active context. Call set_context() first.")
        
        session = self._sessions[self._current_context]
        
        # Find and update indicator
        for ind in session.indicators:
            if ind["id"] == ind_id:
                ind["params"].update(params)
                break
        
        # Rebuild indicators
        self._rebuild_indicators()
    
    def get_indicator_config(self, ind_id: str) -> Optional[Dict[str, Any]]:
        """Get the configuration for an indicator.
        
        Args:
            ind_id: Unique indicator ID
            
        Returns:
            Indicator config dict or None if not found
        """
        if not self._current_context:
            return None
        
        session = self._sessions[self._current_context]
        
        for ind in session.indicators:
            if ind["id"] == ind_id:
                return ind.copy()
        
        return None
    
    def get_current_context(self) -> Optional[Tuple[str, str]]:
        """Get the current (symbol, timeframe) context.
        
        Returns:
            Current context tuple or None if no context is set
        """
        return self._current_context
    
    def get_session_state(self, symbol: str, timeframe: str) -> Optional[SessionState]:
        """Get the session state for a specific context.
        
        Args:
            symbol: Symbol name
            timeframe: Timeframe string
            
        Returns:
            SessionState or None if context doesn't exist
        """
        return self._sessions.get((symbol, timeframe))
    
    def _save_current_context(self) -> None:
        """Save the current context state from ChartWidget."""
        if not self._current_context or not self._chart_widget:
            return
        
        session = self._sessions[self._current_context]
        
        # Save view state (zoom, scroll offset)
        # This would be implemented by querying the ChartWidget's current state
        # For now, we'll store a placeholder
        session.view_state = {
            "zoom": 1.0,  # Would get from ChartWidget
            "scroll_offset": 0  # Would get from ChartWidget
        }
    
    def _apply_context(self, context_key: Tuple[str, str]) -> None:
        """Apply a context to the ChartWidget.
        
        Args:
            context_key: (symbol, timeframe) tuple
        """
        if not self._chart_widget:
            return
        
        session = self._sessions[context_key]
        
        # Set data
        if session.data:
            self._chart_widget.set_data(session.data)
        
        # Restore view state
        if session.view_state:
            # Apply zoom and scroll offset to ChartWidget
            pass  # Would be implemented when ChartWidget has the API
        
        # Rebuild indicators
        self._rebuild_indicators()
    
    def _rebuild_indicators(self) -> None:
        """Rebuild all indicators for the current context.
        
        This method:
        1. Clears existing indicators from ChartWidget
        2. Re-adds all indicators from the current session configuration
        3. Triggers a chart render
        """
        if not self._current_context or not self._chart_widget:
            return
        
        session = self._sessions[self._current_context]
        
        # Import here to avoid circular dependencies
        from ..indicators.registry import get_indicator
        from ..indicators.adapter import IndicatorAdapter
        
        # Store indicator adapters for rendering
        if not hasattr(self, '_indicator_adapters'):
            self._indicator_adapters = {}
        
        # Clear existing adapters for this context
        self._indicator_adapters[self._current_context] = []
        
        # Calculate all indicators
        for ind_config in session.indicators:
            indicator_type = ind_config["type"]
            params = ind_config["params"]
            subplot = ind_config["subplot"]
            
            # Get indicator class
            indicator_class = get_indicator(indicator_type)
            if not indicator_class:
                continue
            
            # Create adapter
            adapter = IndicatorAdapter(indicator_class, params, subplot)
            
            # Calculate indicator values
            if session.data:
                adapter.calculate(session.data)
            
            # Store adapter for rendering
            self._indicator_adapters[self._current_context].append(adapter)
        
        # Trigger chart refresh
        if hasattr(self._chart_widget, '_request_render'):
            self._chart_widget._request_render()