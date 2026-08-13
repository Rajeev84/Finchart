"""FinChart TradingView Extension Contracts module (Layer 1.14).
Provides lightweight extension hooks for future synchronization and adapter
integration. This implementation is thread-safe and adds simple
introspection/management helpers for testability and integration.
"""

from typing import Any, Callable, Dict, List, Optional, Tuple
import threading
import warnings


class ExtensionHook:
    """A simple callable hook that can be registered for chart-level extension events.

    Attributes:
        name: The event name the hook is registered to.
        callback: The callable invoked when the event is emitted.
    """

    def __init__(self, name: str, callback: Callable[[Dict[str, Any]], Any]):
        self.name = name
        self.callback = callback


class ExtensionRegistry:
    """Stores extension hooks and dispatches notifications to registered listeners.

    Methods are guarded with an RLock so the registry is safe to use from
    different threads (simple synchronization layer for adapters).
    """

    def __init__(self) -> None:
        self._hooks: Dict[str, List[ExtensionHook]] = {}
        self._lock = threading.RLock()

    def register(self, name: str, callback: Callable[[Dict[str, Any]], Any]) -> ExtensionHook:
        """Register a callback under a named event and return the created hook."""
        hook = ExtensionHook(name, callback)
        with self._lock:
            self._hooks.setdefault(name, []).append(hook)
        return hook

    def unregister(self, hook: ExtensionHook) -> None:
        """Unregister the given hook instance from its event name."""
        with self._lock:
            hooks = self._hooks.get(hook.name, [])
            self._hooks[hook.name] = [item for item in hooks if item is not hook]

    def get_hooks(self, name: str) -> List[ExtensionHook]:
        """Return a copy of registered hooks for the given event name."""
        with self._lock:
            return list(self._hooks.get(name, []))

    def clear(self, name: Optional[str] = None) -> None:
        """Clear hooks for a specific name, or all hooks if name is None."""
        with self._lock:
            if name is None:
                self._hooks.clear()
            else:
                self._hooks.pop(name, None)

    def notify(self, name: str, payload: Optional[Dict[str, Any]] = None) -> List[Tuple[ExtensionHook, Any]]:
        """Notify all hooks registered under `name` with `payload`.

        Returns a list of tuples `(hook, result)` where `result` is either the
        callback return value or the exception instance raised by the callback.
        Exceptions are captured and returned, but do not stop other hooks from
        executing. Warnings are emitted for diagnostics.
        """
        results: List[Tuple[ExtensionHook, Any]] = []
        with self._lock:
            hooks = list(self._hooks.get(name, []))

        for hook in hooks:
            try:
                res = hook.callback(payload or {})
                results.append((hook, res))
            except Exception as exc:  # capture but continue
                warnings.warn(f"Extension hook '{hook.name}' raised: {exc}")
                results.append((hook, exc))

        return results
