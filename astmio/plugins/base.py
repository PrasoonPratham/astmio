import importlib
import pkgutil
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Type

from astmio.logging import get_logger

log = get_logger(__name__)


class BasePlugin:
    """
    Base class for all plugins.
    """

    name: str = "BasePlugin"
    version: str = "1.0.0"
    description: str = "Base plugin class"

    def __init__(self, **kwargs):
        """Initialize plugin with configuration."""
        self.config = kwargs
        self.manager: Optional[PluginManager] = None

    def install(self, manager: "PluginManager"):
        """Install the plugin."""
        self.manager = manager
        log.info(f"Installing plugin: {self.name}")

    def uninstall(self, manager: "PluginManager"):
        """Uninstall the plugin."""
        log.info(f"Uninstalling plugin: {self.name}")
        self.manager = None

    def configure(self, **kwargs):
        """Configure the plugin with new settings."""
        self.config.update(kwargs)


class PluginManager:
    """
    Manages the lifecycle of plugins and the event system.
    """

    def __init__(self, server: Any = None):
        self.server = server
        self._plugins: Dict[str, BasePlugin] = {}
        self._event_listeners: Dict[str, List[Callable]] = defaultdict(list)

    def on(self, event_name: str, handler: Callable):
        """Register an event listener."""
        self._event_listeners[event_name].append(handler)

    def emit(self, event_name: str, *args, **kwargs):
        """Emit an event to all registered listeners."""
        for handler in self._event_listeners[event_name]:
            try:
                handler(*args, **kwargs)
            except Exception as e:
                log.error(
                    f"Error in event handler for {event_name}: {e}",
                    event=event_name,
                    handler=handler,
                )

    def register_plugin(self, plugin: BasePlugin):
        """Register a single plugin."""
        self._plugins[plugin.name] = plugin
        plugin.install(self)

    def unregister_plugin(self, name: str):
        """Unregister a plugin by name."""
        if name in self._plugins:
            plugin = self._plugins.pop(name)
            plugin.uninstall(self)

    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        """Get a plugin by name."""
        return self._plugins.get(name)

    def list_plugins(self) -> List[str]:
        """List all registered plugins."""
        return list(self._plugins.keys())

    def discover_plugins(self, package):
        """Discover and register all plugins within a given package."""
        for _, name, _ in pkgutil.iter_modules(
            package.__path__, package.__name__ + "."
        ):
            try:
                module = importlib.import_module(name)
                for item_name in dir(module):
                    item = getattr(module, item_name)
                    if (
                        isinstance(item, type)
                        and issubclass(item, BasePlugin)
                        and item is not BasePlugin
                    ):
                        self.register_plugin(item())
            except Exception as e:
                log.error(f"Failed to discover plugin in {name}: {e}")


# Global plugin registry for pip-like installation
_available_plugins: Dict[str, Callable] = {}


def register_available_plugin(name: str, plugin_class: Type[BasePlugin]):
    """Register a plugin class as available for installation."""
    _available_plugins[name] = plugin_class


def install_plugin(name: str, **kwargs) -> BasePlugin:
    """
    Install a plugin by name (pip-like interface).


    Args:
        name: Plugin name
        **kwargs: Plugin configuration


    Returns:
        Installed plugin instance


    Raises:
        ValueError: If plugin not found
    """
    if name not in _available_plugins:
        # Try to import from plugins module
        try:
            module = importlib.import_module(f"astmio.plugins.{name}")
            # Look for plugin class in the module
            for item_name in dir(module):
                item = getattr(module, item_name)
                if (
                    isinstance(item, type)
                    and issubclass(item, BasePlugin)
                    and item is not BasePlugin
                ):
                    _available_plugins[name] = item
                    break
        except ImportError:
            raise ValueError(f"Plugin '{name}' not found")

    plugin_class = _available_plugins[name]
    plugin = plugin_class(**kwargs)

    log.info(f"Plugin '{name}' installed successfully")
    return plugin


def uninstall_plugin(name: str):
    """
    Uninstall a plugin by name.


    Args:
        name: Plugin name to uninstall
    """
    if name in _available_plugins:
        log.info(f"Plugin '{name}' uninstalled successfully")
    else:
        log.warning(f"Plugin '{name}' was not installed")


def list_plugins() -> List[str]:
    """List all available plugins."""
    return list(_available_plugins.keys())


def list_available_plugins() -> Dict[str, str]:
    """List all available plugins with descriptions."""
    plugins = {}

    import astmio.plugins

    for _, name, _ in pkgutil.iter_modules(astmio.plugins.__path__):
        if name.startswith("_"):
            continue

        try:
            module = importlib.import_module(f"astmio.plugins.{name}")
            for item_name in dir(module):
                item = getattr(module, item_name)
                if (
                    isinstance(item, type)
                    and issubclass(item, BasePlugin)
                    and item is not BasePlugin
                ):
                    plugins[name] = getattr(
                        item, "description", "No description available"
                    )
                    break
        except ImportError:
            continue

    return plugins


__all__ = [
    "BasePlugin",
    "PluginManager",
    "install_plugin",
    "uninstall_plugin",
    "list_plugins",
    "list_available_plugins",
    "register_available_plugin",
]
