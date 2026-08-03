"""Indicator Registry - Auto-discovery and registration of BaseIndicator plugins.

This module provides the INDICATOR_REGISTRY and functions to auto-discover
indicator plugins from user modules like def_scanners.py.
"""
from __future__ import annotations

from typing import Dict, Type, Optional, List
import importlib.util
import sys
import os
from pathlib import Path

from .plugin import BaseIndicator


# Global registry of indicator classes
INDICATOR_REGISTRY: Dict[str, Type[BaseIndicator]] = {}


def register_indicator(cls: Type[BaseIndicator]) -> Type[BaseIndicator]:
    """Decorator to register an indicator class in the global registry.
    
    Usage:
        @register_indicator
        class MyIndicator(BaseIndicator):
            name = "My Indicator"
            ...
    
    Args:
        cls: The indicator class to register
        
    Returns:
        The same class, registered in INDICATOR_REGISTRY
    """
    if not hasattr(cls, 'name') or not cls.name:
        raise ValueError(f"Indicator class {cls.__name__} must have a 'name' attribute")
    
    INDICATOR_REGISTRY[cls.name] = cls
    return cls


def auto_discover(folder: Optional[str] = None) -> None:
    """Auto-discover and register indicators from Python files in a folder.
    
    This function scans the specified folder (or current directory) for .py files
    and imports them to discover any BaseIndicator subclasses that use the
    @register_indicator decorator.
    
    Args:
        folder: Path to folder to scan. If None, scans current directory.
    """
    if folder is None:
        folder = os.getcwd()
    
    folder_path = Path(folder)
    if not folder_path.exists():
        return
    
    # Look for .py files (but skip __pycache__ and hidden files)
    py_files = [f for f in folder_path.glob("*.py") if not f.name.startswith("_")]
    
    for py_file in py_files:
        try:
            # Import the module
            spec = importlib.util.spec_from_file_location(py_file.stem, py_file)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[py_file.stem] = module
                spec.loader.exec_module(module)
        except Exception as e:
            # Skip files that fail to import (they may not be indicator files)
            continue


def get_indicator(name: str) -> Optional[Type[BaseIndicator]]:
    """Get an indicator class by name from the registry.
    
    Args:
        name: The indicator name
        
    Returns:
        The indicator class if found, None otherwise
    """
    return INDICATOR_REGISTRY.get(name)


def list_indicators() -> List[str]:
    """List all registered indicator names.
    
    Returns:
        List of indicator names
    """
    return list(INDICATOR_REGISTRY.keys())


def clear_registry() -> None:
    """Clear all indicators from the registry (useful for testing)."""
    INDICATOR_REGISTRY.clear()