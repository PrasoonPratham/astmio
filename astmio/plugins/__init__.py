import logging
from typing import Dict, List, Optional, Type

from .base import BasePlugin, PluginManager
from .registry import PluginRegistry

log = logging.getLogger(__name__)

# This is our Singleton instance.
registry = PluginRegistry()

_default_manager = PluginManager()


def get_default_manager() -> PluginManager:
    """Returns the default, shared PluginManager instance."""
    return _default_manager


# --- Registry Functions (Operating on the Catalog) ---


def register_plugin_class(
    name: str, plugin_class: Type[BasePlugin], category: str = "custom"
):
    """
    Functional wrapper to register a plugin class to the global registry.
    This makes a plugin *available* to be used.
    """
    registry.register(name, plugin_class, category)


def get_plugin_class(name: str) -> Optional[Type[BasePlugin]]:
    """Functional wrapper to get a plugin class (blueprint) from the registry."""
    return registry.get(name)


def list_available_plugins() -> List[str]:
    """Functional wrapper to list all available plugin classes in the registry."""
    return registry.list_all()


def get_plugin_info(name: str) -> Optional[Dict[str, str]]:
    """Functional wrapper to get metadata for an available plugin."""
    return registry.get_plugin_info(name)


# --- Manager Functions (Operating on Active Plugins) ---


def activate_plugin(name: str, **config) -> Optional[BasePlugin]:
    """
    Finds a plugin in the registry, instantiates it, and registers it
    with the default manager to make it *active*.

    Args:
        name: The name of the plugin to activate.
        **config: Configuration options to pass to the plugin's constructor.

    Returns:
        The activated plugin instance, or None if activation failed.
    """
    plugin_class = registry.get(name)
    if not plugin_class:
        log.error(f"Cannot activate plugin '{name}': Not found in registry.")
        return None

    try:
        plugin_instance = plugin_class(**config)
        manager = get_default_manager()
        manager.register_plugin(plugin_instance)
        log.info(f"Plugin '{name}' activated successfully.")
        return plugin_instance
    except Exception as e:
        log.error(f"Failed to instantiate or register plugin '{name}': {e}")
        return None


def deactivate_plugin(name: str):
    """Deactivates a plugin by removing it from the default manager."""
    manager = get_default_manager()
    manager.unregister_plugin(name)


def list_active_plugins() -> List[str]:
    """Lists the names of all currently active plugins in the default manager."""
    manager = get_default_manager()
    return manager.list_plugins()


def emit_event(event_name: str, *args, **kwargs):
    """Emits an event through the default plugin manager."""
    manager = get_default_manager()
    manager.emit(event_name, *args, **kwargs)


__all__ = [
    # Core Classes (for type hinting and advanced usage)
    "BasePlugin",
    "PluginManager",
    "PluginRegistry",
    # Core Instances (for direct access)
    "registry",
    # Functional API (for convenience)
    "register_plugin_class",
    "get_plugin_class",
    "list_available_plugins",
    "get_plugin_info",
    "activate_plugin",
    "deactivate_plugin",
    "list_active_plugins",
    "emit_event",
    "get_default_manager",
]
