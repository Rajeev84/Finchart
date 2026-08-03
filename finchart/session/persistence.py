"""Layout Persistence - JSON save/load for indicator layouts.

This module provides LayoutPersistence for saving and loading indicator
configurations and subplot layouts to JSON files.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Any
import json
import os
from pathlib import Path
import copy

from .manager import SessionManager, SessionState


class LayoutPersistence:
    """Handles JSON save/load for indicator layouts.
    
    Layouts are stored as JSON files in the Config/ directory with the
    naming pattern: {layout_name}_layout.json
    """
    
    def __init__(self, session_manager: SessionManager, config_dir: str = "Config"):
        """Initialize LayoutPersistence.
        
        Args:
            session_manager: SessionManager instance
            config_dir: Directory to store layout files
        """
        self._session_manager = session_manager
        self._config_dir = Path(config_dir)
        self._config_dir.mkdir(exist_ok=True)
    
    def save_layout(self, layout_name: str) -> None:
        """Save current indicator layout to JSON.
        
        Args:
            layout_name: Name for the layout
        """
        current_context = self._session_manager.get_current_context()
        if not current_context:
            raise RuntimeError("No active context to save layout from")
        
        session = self._session_manager.get_session_state(*current_context)
        if not session:
            raise RuntimeError("No session state found for current context")
        
        # Create layout data structure
        layout_data = {
            "version": "1.0",
            "layout_name": layout_name,
            "indicators": copy.deepcopy(session.indicators),
            "subplot_configs": copy.deepcopy(session.subplot_configs)
        }
        
        # Save to file
        filepath = self._config_dir / f"{layout_name}_layout.json"
        with open(filepath, "w") as f:
            json.dump(layout_data, f, indent=2)
    
    def load_layout(self, layout_name: str) -> None:
        """Load indicator layout from JSON.
        
        Args:
            layout_name: Name of the layout to load
        """
        filepath = self._config_dir / f"{layout_name}_layout.json"
        if not filepath.exists():
            raise FileNotFoundError(f"Layout '{layout_name}' not found")
        
        with open(filepath, "r") as f:
            layout_data = json.load(f)
        
        # Validate version
        if layout_data.get("version") != "1.0":
            raise ValueError(f"Unsupported layout version: {layout_data.get('version')}")
        
        # Get current session
        current_context = self._session_manager.get_current_context()
        if not current_context:
            raise RuntimeError("No active context to load layout into")
        
        session = self._session_manager.get_session_state(*current_context)
        if not session:
            raise RuntimeError("No session state found for current context")
        
        # Apply layout data
        session.indicators = copy.deepcopy(layout_data.get("indicators", []))
        session.subplot_configs = copy.deepcopy(layout_data.get("subplot_configs", {}))
        
        # Rebuild chart with new layout
        self._session_manager._rebuild_indicators()
    
    def refresh_layouts(self) -> List[str]:
        """Scan Config/ folder and return available layout names.
        
        Returns:
            List of layout names
        """
        layouts = []
        for filepath in self._config_dir.glob("*_layout.json"):
            # Extract layout name from filename
            layout_name = filepath.stem.replace("_layout", "")
            layouts.append(layout_name)
        
        return sorted(layouts)
    
    def remove_layout(self, layout_name: str) -> None:
        """Delete a layout file.
        
        Args:
            layout_name: Name of the layout to delete
        """
        if layout_name == "default":
            raise ValueError("Cannot delete default layout")
        
        filepath = self._config_dir / f"{layout_name}_layout.json"
        if filepath.exists():
            filepath.remove()
    
    def new_layout(self) -> None:
        """Clear all indicators and reset to empty layout."""
        current_context = self._session_manager.get_current_context()
        if not current_context:
            raise RuntimeError("No active context")
        
        session = self._session_manager.get_session_state(*current_context)
        if not session:
            raise RuntimeError("No session state found")
        
        # Clear indicators and subplot configs
        session.indicators.clear()
        session.subplot_configs.clear()
        
        # Keep only candlestick subplot
        session.subplot_configs["candlestick"] = {"weight": 3.0}
        
        # Rebuild chart
        self._session_manager._rebuild_indicators()
    
    def set_auto_save(self, setting_name: str = "setting_last_layout") -> None:
        """Enable auto-save of last used layout.
        
        Args:
            setting_name: Name of the setting to store auto-save preference
        """
        # This would integrate with a global settings store
        # For now, this is a placeholder for future implementation
        pass
    
    def get_last_layout(self) -> Optional[str]:
        """Get the last used layout name.
        
        Returns:
            Last layout name or None
        """
        # This would read from global settings
        # For now, return None
        return None