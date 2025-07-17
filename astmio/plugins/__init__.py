
import importlib
import pkgutil
from typing import Dict, Type, List, Any, Callable
from collections import defaultdict

from ..logging import get_logger

log = get_logger(__name__)


class BasePlugin:
    """
    Base class for all plugins.
    """
    name: str = "BasePlugin"

    def install(self, manager: "PluginManager"):
        log.info("Installing plugin", plugin_name=self.name)

    def uninstall(self, manager: "PluginManager"):
        log.info("Uninstalling plugin", plugin_name=self.name)


class PluginManager:
    """
    Manages the lifecycle of plugins and the event system.
    """
    def __init__(self, server: Any):
        self.server = server
        self._plugins: Dict[str, BasePlugin] = {}
        self._event_listeners: Dict[str, List[Callable]] = defaultdict(list)

    def on(self, event_name: str, handler: Callable):
        """
        Registers an event listener.
        """
        self._event_listeners[event_name].append(handler)

    def emit(self, event_name: str, *args, **kwargs):
        """
        Emits an event to all registered listeners.
        """
        for handler in self._event_listeners[event_name]:
            try:
                handler(*args, **kwargs)
            except Exception:
                log.exception(
                    "Error in event handler",
                    event=event_name,
                    handler=handler,
                )

    def register_plugin(self, plugin: BasePlugin):
        """
        Registers a single plugin.
        """
        self._plugins[plugin.name] = plugin
        plugin.install(self)

    def unregister_plugin(self, name: str):
        """
        Unregisters a plugin by name.
        """
        if name in self._plugins:
            plugin = self._plugins.pop(name)
            plugin.uninstall(self)

    def get_plugin(self, name: str) -> BasePlugin:
        """
        Gets a plugin by name.
        """
        return self._plugins.get(name)

    def discover_plugins(self, package):
        """
        Discovers and registers all plugins within a given package.
        """
        for _, name, _ in pkgutil.iter_modules(package.__path__, package.__name__ + "."):
            module = importlib.import_module(name)
            for item_name in dir(module):
                item = getattr(module, item_name)
                if isinstance(item, type) and issubclass(item, BasePlugin) and item is not BasePlugin:
                    self.register_plugin(item()) 