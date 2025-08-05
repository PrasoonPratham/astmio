import importlib
import logging
import pkgutil
from typing import Dict, List, Optional, Type

from .base import BasePlugin

log = logging.getLogger(__name__)


class PluginRegistry:
    """
    Acts as a static catalog of all available plugin classes.
    It discovers plugins and stores their blueprints (classes), but does not run them.
    """

    def __init__(self):
        self._plugins: Dict[str, Type[BasePlugin]] = {}
        self._categories: Dict[str, List[str]] = {
            "compliance": [],
            "monitoring": [],
            "security": [],
            "data_processing": [],
            "integration": [],
            "custom": [],
        }
        self._register_builtin_plugins()

    def register(
        self,
        name: str,
        plugin_class: Type[BasePlugin],
        category: str = "custom",
    ):
        """
        Registers a plugin class in the catalog under a specific category.

        Args:
            name: The unique identifier for the plugin.
            plugin_class: The plugin class itself (not an instance).
            category: The category to list the plugin under.
        """
        if not issubclass(plugin_class, BasePlugin):
            log.error(
                f"Failed to register '{name}': Class does not inherit from BasePlugin."
            )
            return

        self._plugins[name] = plugin_class
        if category not in self._categories:
            self._categories[category] = []
        self._categories[category].append(name)
        log.info(f"Plugin class '{name}' registered in category '{category}'.")

    def get(self, name: str) -> Optional[Type[BasePlugin]]:
        """Gets a plugin class (blueprint) by its name."""
        return self._plugins.get(name)

    def list_all(self) -> List[str]:
        """Returns a list of names of all registered plugin classes."""
        return list(self._plugins.keys())

    def list_by_category(self, category: str) -> List[str]:
        """Returns a list of plugin names within a specific category."""
        return self._categories.get(category, [])

    def get_categories(self) -> List[str]:
        """Returns a list of all available plugin categories."""
        return list(self._categories.keys())

    def get_plugin_info(self, name: str) -> Optional[Dict[str, str]]:
        """Retrieves metadata from a plugin class without instantiating it."""
        plugin_class = self.get(name)
        if not plugin_class:
            return None

        category = "unknown"
        for cat, plugins in self._categories.items():
            if name in plugins:
                category = cat
                break

        return {
            "name": getattr(plugin_class, "name", name),
            "version": getattr(plugin_class, "version", "unknown"),
            "description": getattr(
                plugin_class, "description", "No description available"
            ),
            "category": category,
        }

    def discover_and_register(self, package):
        """
        Discovers and registers all valid plugin classes within a given Python package.

        Args:
            package: The Python package to scan for plugins (e.g., my_app.plugins_dir).
        """
        log.info(f"Discovering plugins in package: {package.__name__}")
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
                        # Use the plugin's own name attribute for registration
                        plugin_name = getattr(
                            item, "name", item.__name__.lower()
                        )
                        plugin_category = getattr(item, "category", "custom")
                        self.register(
                            plugin_name, item, category=plugin_category
                        )
            except Exception as e:
                log.error(f"Failed to discover plugin in module {name}: {e}")

    def _register_builtin_plugins(self):
        """Register all built-in plugins."""

        try:
            # HIPAA Compliance Plugin
            from astmio.plugins.hipaa import HIPAAAuditPlugin

            self.register("hipaa", HIPAAAuditPlugin, "compliance")

            # Metrics Plugins
            from astmio.plugins.metrics import (
                MetricsPlugin,
                PrometheusMetricsPlugin,
            )

            self.register("metrics", MetricsPlugin, "monitoring")
            self.register("prometheus", PrometheusMetricsPlugin, "monitoring")

            # Modern_Records Plugin
            from astmio.plugins.records import ModernRecordsPlugin

            self.register(
                "modern_records", ModernRecordsPlugin, "data_processing"
            )

            log.info("Built-in plugins registered successfully")

        except ImportError as e:
            log.warning(f"Some built-in plugins could not be registered: {e}")
