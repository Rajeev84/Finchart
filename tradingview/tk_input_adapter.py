"""
Tkinter Input Adapter for FinChart (Layer 1.7).
Provides a safe, optional adapter that maps common Tk events to `InputEngine` callbacks.
This adapter is implemented defensively: it does not require a running Tk mainloop to be imported
and will raise a clear error if Tkinter is not available.
"""
from typing import Any, Optional
from .input_adapter import InputAdapter
from .input_engine import InputEngine
from .input_events import ModifierState

try:
    import tkinter as tk
except Exception:
    tk = None


class TkInputAdapter(InputAdapter):
    """Adapter for Tkinter widgets.

    This adapter attaches to a Tk `Canvas` or `Widget` and forwards pointer, wheel,
    keyboard, focus, and resize events to the provided `InputEngine` instance.

    It is safe to import in environments without a display; in that case `tk` will be
    `None` and attempting to `bind()` will raise `RuntimeError`.
    """

    def __init__(self, input_engine: InputEngine):
        self.input_engine = input_engine
        self._widget: Optional[Any] = None
        self._bindings = []

    def bind(self, container_widget: Any) -> None:
        if tk is None:
            raise RuntimeError("tkinter is not available in this environment")
        if container_widget is None:
            raise ValueError("container_widget must be a tkinter widget")

        self._widget = container_widget
        # Pointer events
        self._bind("<ButtonPress>", self._on_button_press)
        self._bind("<ButtonRelease>", self._on_button_release)
        self._bind("<Motion>", self._on_motion)
        # Wheel (platform-specific mouse wheel events)
        self._bind("<MouseWheel>", self._on_wheel)
        self._bind("<Button-4>", self._on_wheel)
        self._bind("<Button-5>", self._on_wheel)
        # Keyboard
        self._bind("<Key>", self._on_key)
        # Focus
        self._bind("<FocusIn>", self._on_focus_in)
        self._bind("<FocusOut>", self._on_focus_out)
        # Configure (resize)
        self._bind("<Configure>", self._on_configure)

    def unbind(self) -> None:
        if not self._widget:
            return
        for seq in self._bindings:
            try:
                self._widget.unbind(seq)
            except Exception:
                pass
        self._bindings = []
        self._widget = None

    def _bind(self, sequence: str, handler) -> None:
        try:
            self._widget.bind(sequence, handler)
            self._bindings.append(sequence)
        except Exception:
            pass

    # Event handlers (map tkinter event to InputEngine)
    def _on_button_press(self, e) -> None:
        try:
            self.input_engine.on_pointer_down(screen_x=float(e.x), screen_y=float(e.y), button=getattr(e, 'num', 1))
        except Exception:
            pass

    def _on_button_release(self, e) -> None:
        try:
            self.input_engine.on_pointer_up(screen_x=float(e.x), screen_y=float(e.y), button=getattr(e, 'num', 1))
        except Exception:
            pass

    def _on_motion(self, e) -> None:
        try:
            buttons = 1 if getattr(e, 'state', 0) & 0x0100 else 0
            self.input_engine.on_pointer_move(screen_x=float(e.x), screen_y=float(e.y), buttons_down=buttons)
        except Exception:
            pass

    def _on_wheel(self, e) -> None:
        try:
            if hasattr(e, 'delta') and e.delta:
                # On Windows, e.delta is a multiple of 120 per notch.
                delta = -e.delta
            elif getattr(e, 'num', None) == 4:
                delta = -120
            elif getattr(e, 'num', None) == 5:
                delta = 120
            else:
                delta = 0
            self.input_engine.on_wheel(delta_x=0.0, delta_y=float(delta), screen_x=float(e.x), screen_y=float(e.y))
        except Exception:
            pass

    def _on_key(self, e) -> None:
        try:
            from .input_events import KeyboardEvent, KeyboardEventType
            kt = KeyboardEventType.KEY_DOWN
            self.input_engine.on_key(event_type=kt, key=getattr(e, 'keysym', str(e.char) if hasattr(e, 'char') else ''))
        except Exception:
            pass

    def _on_focus_in(self, e) -> None:
        try:
            self.input_engine.on_focus_change(True)
        except Exception:
            pass

    def _on_focus_out(self, e) -> None:
        try:
            self.input_engine.on_focus_change(False)
        except Exception:
            pass

    def _on_configure(self, e) -> None:
        try:
            self.input_engine.on_resize(width=float(e.width), height=float(e.height))
        except Exception:
            pass
