import logging
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional

from .base import BasePlugin

log = logging.getLogger(__name__)


class PluginManager:
    """
    Manages the lifecycle of active plugins and the event system (Observer pattern).
    """

    def __init__(self, server: Any = None):
        self.server = server
        self._plugins: Dict[str, BasePlugin] = {}
        self._event_listeners: Dict[str, List[Callable]] = defaultdict(list)

    def on(self, event_name: str, handler: Callable):
        """Register an event listener."""
        self._event_listeners[event_name].append(handler)
        log.debug(
            f"Handler {handler.__name__} registered for event '{event_name}'"
        )

    def emit(self, event_name: str, *args, **kwargs):
        """Emit an event to all registered listeners."""
        log.info(f"Emitting event: {event_name}")
        for handler in self._event_listeners.get(event_name, []):
            try:
                handler(*args, **kwargs)
            except Exception as e:
                log.error(f"Error in event handler for {event_name}: {e}")

    def register_plugin(self, plugin: BasePlugin):
        """Registers and installs a single plugin instance."""
        if plugin.name in self._plugins:
            log.warning(f"Plugin '{plugin.name}' is already registered.")
            return

        self._plugins[plugin.name] = plugin
        plugin.install(self)

    def unregister_plugin(self, name: str):
        """Uninstalls and unregisters a plugin by name."""
        if name in self._plugins:
            plugin = self._plugins.pop(name)
            plugin.uninstall(self)
        else:
            log.warning(
                f"Attempted to unregister a non-existent plugin: {name}"
            )

    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        """Get an active plugin instance by name."""
        return self._plugins.get(name)

    def list_plugins(self) -> List[str]:
        """List the names of all active plugins."""
        return list(self._plugins.keys())
