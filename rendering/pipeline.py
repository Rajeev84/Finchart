"""Rendering Pipeline - Retained-mode frame scheduler and layer manager.

Collects abstract DrawCommand instances from renderers, sorts by layer and z-index,
configures items acquired from CanvasItemPool, and schedules deferred frame passes.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field
from enum import Enum, auto
import tkinter as tk

from ..core.events import EventBus, EventType
from .pool import CanvasItemPool


class Layer(Enum):
    """Z-ordered rendering layers from bottom to top."""
    BACKGROUND = 100
    GRID = 200
    AXIS_BG = 250        # Axis backgrounds (above grid lines, below series)
    SERIES = 300
    INDICATORS = 400
    DRAWING = 500
    AXIS_TEXT = 550      # Axis labels (above indicators/drawings, below crosshair)
    CROSSHAIR = 600
    UI = 700
    OVERLAY = 800


@dataclass(slots=True)
class DrawCommand:
    """Abstract draw command container."""
    layer: Layer
    tag: str
    item_type: str  # 'line', 'rectangle', 'polygon', 'oval', 'text'
    coords: Tuple[float, ...]
    options: Dict[str, Any] = field(default_factory=dict)
    z_index: int = 0


class LayerManager:
    """Manages layer tag assignments and z-ordering."""

    def __init__(self, canvas: tk.Canvas) -> None:
        self._canvas = canvas
        self._layer_tags: Dict[Layer, str] = {
            layer: f"layer_{layer.name.lower()}" for layer in Layer
        }

    def get_tag(self, layer: Layer) -> str:
        """Get canvas tag string for layer."""
        return self._layer_tags[layer]

    def clear_layer(self, layer: Layer) -> None:
        """Delete all items assigned to a layer tag."""
        tag = self._layer_tags[layer]
        self._canvas.delete(tag)


class RenderingPipeline:
    """Main retained-mode rendering pipeline and deferred frame scheduler."""

    def __init__(self, canvas: tk.Canvas, event_bus: EventBus) -> None:
        self._canvas = canvas
        self._event_bus = event_bus
        self._layer_manager = LayerManager(canvas)
        self._item_pool = CanvasItemPool(canvas)

        # Active item IDs per layer
        self._current_items: Dict[Layer, List[int]] = {layer: [] for layer in Layer}
        self._command_buffer: List[DrawCommand] = []

        self._needs_full_redraw = True
        self._pending_layers: Set[Layer] = set()
        self._render_scheduled = False

    @property
    def canvas(self) -> tk.Canvas:
        return self._canvas

    @property
    def item_pool(self) -> CanvasItemPool:
        return self._item_pool

    def schedule_render(self, full_redraw: bool = False) -> None:
        """Schedule a deferred frame render pass via idle queue."""
        if full_redraw:
            self._needs_full_redraw = True

        if not self._render_scheduled:
            self._render_scheduled = True
            try:
                self._canvas.after_idle(self._render)
            except Exception:
                self._render()

    def schedule_layer(self, layer: Layer) -> None:
        """Mark a specific layer dirty for fast selective redraw."""
        self._pending_layers.add(layer)
        self.schedule_render()

    def add_command(self, command: DrawCommand) -> None:
        """Add a draw command to current frame buffer."""
        self._command_buffer.append(command)

    def add_commands(self, commands: List[DrawCommand]) -> None:
        """Add multiple draw commands."""
        self._command_buffer.extend(commands)

    def clear_commands(self) -> None:
        """Clear the command buffer."""
        self._command_buffer.clear()

    def clear_layer_commands(self, layer: Layer) -> None:
        """Remove buffered draw commands for a single layer."""
        self._command_buffer = [c for c in self._command_buffer if c.layer != layer]

    def force_full_redraw(self) -> None:
        """Force complete redraw of all layers on next render pass."""
        self._needs_full_redraw = True
        self.schedule_render()

    def _render(self) -> None:
        """Execute scheduled frame render pass."""
        self._render_scheduled = False

        if self._needs_full_redraw:
            self._full_render()
        else:
            self._incremental_render()

        self._event_bus.emit_new(EventType.RENDER_COMPLETE, self)

    def _full_render(self) -> None:
        """Full redraw: release all items and execute commands sorted by layer and z-index."""
        # Only sort if we have multiple layers or z-indices that need ordering
        if len(self._command_buffer) > 1:
            self._command_buffer.sort(key=lambda c: (c.layer.value, c.z_index))

        # Release all items per layer back to pool
        for layer in Layer:
            self._item_pool.release_all(self._current_items[layer])
            self._current_items[layer] = []

        # Execute sorted draw commands
        for cmd in self._command_buffer:
            item_id = self._execute_command(cmd)
            if item_id is not None:
                self._current_items[cmd.layer].append(item_id)

        self._command_buffer.clear()
        self._needs_full_redraw = False
        self._pending_layers.clear()

        # Re-establish proper z-ordering on canvas after full render
        self._reorder_layers()

    def _incremental_render(self) -> None:
        """Incremental redraw: re-render only dirty pending layers."""
        if not self._pending_layers:
            self._command_buffer.clear()
            return

        pending_cmds = [c for c in self._command_buffer if c.layer in self._pending_layers]
        # Sort by layer value first, then z-index to maintain proper draw order
        if len(pending_cmds) > 1:
            pending_cmds.sort(key=lambda c: (c.layer.value, c.z_index))

        # Release items for dirty layers only
        for layer in self._pending_layers:
            self._item_pool.release_all(self._current_items[layer])
            self._current_items[layer] = []

        for cmd in pending_cmds:
            item_id = self._execute_command(cmd)
            if item_id is not None:
                self._current_items[cmd.layer].append(item_id)

        # Remove executed commands
        self._command_buffer = [c for c in self._command_buffer if c.layer not in self._pending_layers]
        self._pending_layers.clear()

        # Re-establish proper z-ordering on canvas after incremental render
        # This ensures grid is below series, series below indicators, etc.
        self._reorder_layers()

    def _reorder_layers(self) -> None:
        """Re-establish proper z-ordering of layer tags on canvas."""
        # Lower layers first (bottom), higher layers last (top)
        ordered_layers = sorted(Layer, key=lambda l: l.value)
        for i, layer in enumerate(ordered_layers):
            tag = self._layer_manager.get_tag(layer)
            try:
                if i == 0:
                    self._canvas.tag_lower(tag)
                else:
                    self._canvas.tag_raise(tag)
            except Exception:
                pass

    def _execute_command(self, cmd: DrawCommand) -> Optional[int]:
        """Configure a canvas item acquired from item pool using command options."""
        try:
            item_id = self._item_pool.acquire(cmd.item_type)
            layer_tag = self._layer_manager.get_tag(cmd.layer)

            options = dict(cmd.options)
            options["tags"] = (layer_tag, cmd.tag)
            options["state"] = "normal"

            # Pool reuse leaves sticky Tk options (stipple/dash) unless cleared.
            # Hollow candles / MACD bars happen when a crosshair stipple bleeds
            # onto a recycled rectangle fill.
            if cmd.item_type in ("line", "rectangle", "oval", "polygon"):
                # For solid fills, we need to delete the stipple option entirely
                # For stippled fills, keep the stipple option
                if "stipple" in options and options["stipple"]:
                    # Keep the stipple pattern
                    pass
                else:
                    # Remove stipple option for solid fill
                    options.pop("stipple", None)
                if "dash" not in options:
                    options["dash"] = ()
                
                self._canvas.coords(item_id, *cmd.coords)
                self._canvas.itemconfig(item_id, **options)
            elif cmd.item_type == "text":
                x, y = cmd.coords[:2]
                self._canvas.coords(item_id, x, y)
                self._canvas.itemconfig(item_id, **options)

            return item_id
        except Exception:
            return None
