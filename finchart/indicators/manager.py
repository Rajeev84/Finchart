"""Indicator Manager - UI configuration bar and indicator management.

This module provides IndicatorManager which handles:
- Auto-generated config bar from param_schema
- Parameter editing with live updates
- Indicator selection and management
- Overlay/subplot toggle logic
"""
from __future__ import annotations

from typing import Optional, Dict, Any, List, Callable
import tkinter as tk
from tkinter import ttk

from ..session.manager import SessionManager
from .registry import INDICATOR_REGISTRY, list_indicators


class IndicatorManager:
    """Manages indicator UI and configuration.
    
    This class provides a configuration bar that is auto-generated from
    indicator param_schema, allowing users to edit parameters with live
    chart updates.
    """
    
    def __init__(self, form_home: tk.Widget, session_manager: SessionManager):
        """Initialize IndicatorManager.
        
        Args:
            form_home: Parent widget for the config bar
            session_manager: SessionManager instance for indicator management
        """
        self._form_home = form_home
        self._session_manager = session_manager
        self._config_bar: Optional[tk.Widget] = None
        self._active_indicator_id: Optional[str] = None
        self._param_widgets: Dict[str, tk.Widget] = {}
        self._indicator_combo: Optional[ttk.Combobox] = None
        self._overlay_var: Optional[tk.BooleanVar] = None
        
    def build_config_bar(self, context_bar: tk.Widget) -> None:
        """Build the indicator configuration bar UI.
        
        Args:
            context_bar: Parent widget to build the config bar in
        """
        self._config_bar = context_bar
        self._clear_config_bar()
        
        # Create indicator selection combo
        indicator_frame = ttk.Frame(context_bar)
        indicator_frame.pack(side="left", padx=5, pady=2)
        
        ttk.Label(indicator_frame, text="Indicator:").pack(side="left", padx=2)
        
        # Populate with registered indicators
        indicator_names = list_indicators()
        display_names = [f"{name} — {INDICATOR_REGISTRY[name].description}" 
                        for name in indicator_names]
        
        self._indicator_combo = ttk.Combobox(indicator_frame, values=display_names, 
                                            state="readonly", width=30)
        self._indicator_combo.pack(side="left", padx=2)
        self._indicator_combo.bind("<<ComboboxSelected>>", self._on_indicator_selected)
        
        # Add indicator button
        add_btn = ttk.Button(indicator_frame, text="+ Add", command=self._on_add_indicator)
        add_btn.pack(side="left", padx=5)
        
        # Overlay toggle
        self._overlay_var = tk.BooleanVar(value=True)
        overlay_check = ttk.Checkbutton(indicator_frame, text="Overlay", 
                                       variable=self._overlay_var,
                                       command=self._on_overlay_toggle)
        overlay_check.pack(side="left", padx=5)
        
        # Parameter edit area (initially empty)
        self._param_frame = ttk.Frame(context_bar)
        self._param_frame.pack(side="left", padx=10, pady=2)
        
        # Action buttons
        action_frame = ttk.Frame(context_bar)
        action_frame.pack(side="right", padx=5, pady=2)
        
        ttk.Button(action_frame, text="Apply", command=self._on_apply).pack(side="left", padx=2)
        ttk.Button(action_frame, text="Reset", command=self._on_reset).pack(side="left", padx=2)
        ttk.Button(action_frame, text="Delete", command=self._on_delete).pack(side="left", padx=2)
    
    def show_config_bar(self, ind_id: str) -> None:
        """Show config bar with selected indicator's parameters.
        
        Args:
            ind_id: Unique indicator ID to show config for
        """
        self._active_indicator_id = ind_id
        
        # Get indicator config
        ind_config = self._session_manager.get_indicator_config(ind_id)
        if not ind_config:
            self._clear_param_frame()
            return
        
        # Get indicator class for schema
        indicator_type = ind_config["type"]
        from .registry import get_indicator
        indicator_class = get_indicator(indicator_type)
        
        if not indicator_class:
            self._clear_param_frame()
            return
        
        # Clear existing param widgets
        self._clear_param_frame()
        
        # Build parameter widgets from schema
        params = ind_config["params"]
        schema = indicator_class.param_schema
        
        for param_def in schema:
            param_name = param_def["name"]
            param_type = param_def["type"]
            label = param_def.get("label", param_name)
            current_value = params.get(param_name)
            
            # Create label
            ttk.Label(self._param_frame, text=f"{label}:").pack(side="left", padx=2)
            
            # Create appropriate widget based on type
            if param_type == "int":
                widget = ttk.Entry(self._param_frame, width=8)
                widget.insert(0, str(current_value))
                widget.pack(side="left", padx=2)
                widget.bind("<Return>", lambda e, name=param_name: self._on_param_change(name))
                widget.bind("<FocusOut>", lambda e, name=param_name: self._on_param_change(name))
                
            elif param_type == "float":
                widget = ttk.Entry(self._param_frame, width=8)
                widget.insert(0, str(current_value))
                widget.pack(side="left", padx=2)
                widget.bind("<Return>", lambda e, name=param_name: self._on_param_change(name))
                widget.bind("<FocusOut>", lambda e, name=param_name: self._on_param_change(name))
                
            elif param_type == "combo":
                options = param_def.get("options", [])
                widget = ttk.Combobox(self._param_frame, values=options, state="readonly", width=10)
                if current_value in options:
                    widget.set(current_value)
                else:
                    widget.current(0)
                widget.pack(side="left", padx=2)
                widget.bind("<<ComboboxSelected>>", lambda e, name=param_name: self._on_param_change(name))
                
            elif param_type == "color":
                widget = ttk.Entry(self._param_frame, width=8)
                widget.insert(0, str(current_value))
                widget.pack(side="left", padx=2)
                widget.bind("<Return>", lambda e, name=param_name: self._on_param_change(name))
                widget.bind("<FocusOut>", lambda e, name=param_name: self._on_param_change(name))
                
            elif param_type == "bool":
                var = tk.BooleanVar(value=bool(current_value))
                widget = ttk.Checkbutton(self._param_frame, variable=var)
                widget.pack(side="left", padx=2)
                widget.bind("<Button-1>", lambda e, name=param_name, v=var: self._on_bool_change(name, v))
            
            # Store widget reference
            self._param_widgets[param_name] = widget
        
        # Update overlay toggle
        subplot = ind_config.get("subplot", "candlestick")
        self._overlay_var.set(subplot == "candlestick")
    
    def hide_config_bar(self) -> None:
        """Hide the config bar and clear active indicator."""
        self._active_indicator_id = None
        self._clear_param_frame()
    
    def _clear_config_bar(self) -> None:
        """Clear the entire config bar."""
        if self._config_bar:
            for widget in self._config_bar.winfo_children():
                widget.destroy()
    
    def _clear_param_frame(self) -> None:
        """Clear the parameter edit frame."""
        self._param_widgets.clear()
        for widget in self._param_frame.winfo_children():
            widget.destroy()
    
    def _on_indicator_selected(self, event) -> None:
        """Handle indicator selection from combo box.
        
        Args:
            event: Tkinter event
        """
        if not self._indicator_combo:
            return
        
        selection = self._indicator_combo.get()
        if not selection:
            return
        
        # Extract indicator name from display string
        indicator_name = selection.split(" — ")[0]
        
        # Get indicator defaults
        from .registry import get_indicator
        indicator_class = get_indicator(indicator_name)
        if not indicator_class:
            return
        
        # Add indicator with defaults
        subplot = "candlestick" if self._overlay_var.get() else indicator_name
        ind_id = self._session_manager.add_indicator_config(
            indicator_name,
            indicator_class.defaults.copy(),
            subplot
        )
        
        # Show config for new indicator
        self.show_config_bar(ind_id)
    
    def _on_add_indicator(self) -> None:
        """Handle add button click."""
        if self._indicator_combo:
            self._on_indicator_selected(None)
    
    def _on_overlay_toggle(self) -> None:
        """Handle overlay toggle checkbox."""
        if not self._active_indicator_id:
            return
        
        # Get current config
        ind_config = self._session_manager.get_indicator_config(self._active_indicator_id)
        if not ind_config:
            return
        
        # Update subplot based on overlay setting
        if self._overlay_var.get():
            new_subplot = "candlestick"
        else:
            new_subplot = ind_config["type"]  # Use indicator type as subplot name
        
        # Update config
        ind_config["subplot"] = new_subplot
        self._session_manager.update_indicator_params(self._active_indicator_id, ind_config["params"])
    
    def _on_param_change(self, param_name: str) -> None:
        """Handle parameter value change.
        
        Args:
            param_name: Name of the parameter that changed
        """
        if not self._active_indicator_id:
            return
        
        widget = self._param_widgets.get(param_name)
        if not widget:
            return
        
        # Get new value
        if isinstance(widget, ttk.Entry):
            new_value = widget.get()
        elif isinstance(widget, ttk.Combobox):
            new_value = widget.get()
        else:
            return
        
        # Convert to appropriate type
        ind_config = self._session_manager.get_indicator_config(self._active_indicator_id)
        if not ind_config:
            return
        
        indicator_type = ind_config["type"]
        from .registry import get_indicator
        indicator_class = get_indicator(indicator_type)
        
        if not indicator_class:
            return
        
        # Find param definition to get type
        param_def = None
        for pd in indicator_class.param_schema:
            if pd["name"] == param_name:
                param_def = pd
                break
        
        if not param_def:
            return
        
        # Convert value
        try:
            if param_def["type"] == "int":
                new_value = int(new_value)
            elif param_def["type"] == "float":
                new_value = float(new_value)
        except (ValueError, TypeError):
            return  # Invalid conversion, ignore
        
        # Update indicator params
        ind_config["params"][param_name] = new_value
        self._session_manager.update_indicator_params(self._active_indicator_id, ind_config["params"])
    
    def _on_bool_change(self, param_name: str, var: tk.BooleanVar) -> None:
        """Handle boolean parameter change.
        
        Args:
            param_name: Name of the parameter
            var: BooleanVar containing the value
        """
        if not self._active_indicator_id:
            return
        
        ind_config = self._session_manager.get_indicator_config(self._active_indicator_id)
        if not ind_config:
            return
        
        ind_config["params"][param_name] = var.get()
        self._session_manager.update_indicator_params(self._active_indicator_id, ind_config["params"])
    
    def _on_apply(self) -> None:
        """Apply all parameter changes."""
        # Trigger updates for all parameters
        for param_name in self._param_widgets.keys():
            self._on_param_change(param_name)
    
    def _on_reset(self) -> None:
        """Reset parameters to indicator defaults."""
        if not self._active_indicator_id:
            return
        
        ind_config = self._session_manager.get_indicator_config(self._active_indicator_id)
        if not ind_config:
            return
        
        indicator_type = ind_config["type"]
        from .registry import get_indicator
        indicator_class = get_indicator(indicator_type)
        
        if not indicator_class:
            return
        
        # Reset to defaults
        ind_config["params"] = indicator_class.defaults.copy()
        self._session_manager.update_indicator_params(self._active_indicator_id, ind_config["params"])
        
        # Refresh UI
        self.show_config_bar(self._active_indicator_id)
    
    def _on_delete(self) -> None:
        """Delete the active indicator."""
        if not self._active_indicator_id:
            return
        
        self._session_manager.remove_indicator_config(self._active_indicator_id)
        self.hide_config_bar()