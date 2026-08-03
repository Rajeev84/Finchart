"""Session Management - Per-symbol context management for indicators and layouts.

This module provides SessionManager for managing per-symbol indicator configurations,
view states, and data isolation.
"""
from .manager import SessionManager, SessionState

__all__ = ["SessionManager", "SessionState"]