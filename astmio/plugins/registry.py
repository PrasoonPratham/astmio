
#!/usr/bin/env python3
"""
Plugin Registry for ASTM Library

This module provides a centralized registry for all available plugins,
making it easy to discover, install, and manage plugins.
"""

from typing import Dict, List, Type, Optional
from . import BasePlugin
from ..logging import get_logger

log = get_logger(__name__)


class PluginRegistry:
    """
    Central registry for all available plugins.
    """
    
    def __init__(self):
        self._plugins: Dict[str, Type[BasePlugin]] = {}
        self._categories: Dict[str, List[str]] = {
            "compliance": [],
            "monitoring": [],
            "security": [],
            "data_processing": [],
            "integration": [],
            "custom": []
        }
        
        # Auto-register built-in plugins
        self._register_builtin_plugins()
    
    def register(self, name: str, plugin_class: Type[BasePlugin], category: str = "custom"):
        """
        Register a plugin in the registry.
        
        Args:
            name: Plugin name
            plugin_class: Plugin class
            category: Plugin category
        """
        self._plugins[name] = plugin_class
        if category in self._categories:
            self._categories[category].append(name)
        else:
            self._categories["custom"].append(name)
        
        log.info(f"Plugin registered: {name} ({category})")
    
    def get(self, name: str) -> Optional[Type[BasePlugin]]:
        """Get a plugin class by name."""
        return self._plugins.get(name)
    
    def list_all(self) -> List[str]:
        """List all available plugins."""
        return list(self._plugins.keys())
    
    def list_by_category(self, category: str) -> List[str]:
        """List plugins by category."""
        return self._categories.get(category, [])
    
    def get_categories(self) -> List[str]:
        """Get all available categories."""
        return list(self._categories.keys())
    
    def get_plugin_info(self, name: str) -> Dict[str, str]:
        """Get detailed information about a plugin."""
        plugin_class = self._plugins.get(name)
        if not plugin_class:
            return {}
        
        return {
            "name": getattr(plugin_class, "name", name),
            "version": getattr(plugin_class, "version", "unknown"),
            "description": getattr(plugin_class, "description", "No description available"),
            "category": self._get_plugin_category(name)
        }
    
    def _get_plugin_category(self, name: str) -> str:
        """Get the category of a plugin."""
        for category, plugins in self._categories.items():
            if name in plugins:
                return category
        return "unknown"
    
    def _register_builtin_plugins(self):
        """Register all built-in plugins."""
        try:
            # HIPAA Compliance Plugin
            from .hipaa import HIPAAAuditPlugin
            self.register("hipaa", HIPAAAuditPlugin, "compliance")
            
            # Metrics Plugins
            from .metrics import MetricsPlugin, PrometheusMetricsPlugin
            self.register("metrics", MetricsPlugin, "monitoring")
            self.register("prometheus", PrometheusMetricsPlugin, "monitoring")
            
            log.info("Built-in plugins registered successfully")
            
        except ImportError as e:
            log.warning(f"Some built-in plugins could not be registered: {e}")


# Global plugin registry instance
_registry = PluginRegistry()


def register_plugin(name: str, plugin_class: Type[BasePlugin], category: str = "custom"):
    """
    Register a plugin globally.
    
    Args:
        name: Plugin name
        plugin_class: Plugin class
        category: Plugin category
    """
    _registry.register(name, plugin_class, category)


def get_plugin_class(name: str) -> Optional[Type[BasePlugin]]:
    """Get a plugin class by name."""
    return _registry.get(name)


def list_available_plugins() -> List[str]:
    """List all available plugins."""
    return _registry.list_all()


def list_plugins_by_category(category: str) -> List[str]:
    """List plugins by category."""
    return _registry.list_by_category(category)


def get_plugin_categories() -> List[str]:
    """Get all available categories."""
    return _registry.get_categories()


def get_plugin_info(name: str) -> Dict[str, str]:
    """Get detailed information about a plugin."""
    return _registry.get_plugin_info(name)


def print_plugin_catalog():
    """Print a formatted catalog of all available plugins."""
    print("🔌 ASTM Library Plugin Catalog")
    print("=" * 50)
    
    for category in _registry.get_categories():
        plugins = _registry.list_by_category(category)
        if plugins:
            print(f"\n📂 {category.title()}")
            print("-" * 20)
            
            for plugin_name in plugins:
                info = _registry.get_plugin_info(plugin_name)
                print(f"  • {plugin_name}")
                print(f"    Version: {info.get('version', 'unknown')}")
                print(f"    Description: {info.get('description', 'No description')}")
                print()


# Example custom plugin for demonstration
class CustomLoggerPlugin(BasePlugin):
    """
    Example custom plugin that logs all events to a file.
    """
    
    name = "custom_logger"
    version = "1.0.0"
    description = "Custom plugin that logs all events to a file"
    
    def __init__(self, log_file: str = "astm_events.log", **kwargs):
        super().__init__(**kwargs)
        self.log_file = log_file
        self.event_count = 0
    
    def install(self, manager):
        """Install the custom logger plugin."""
        super().install(manager)
        
        # Register for all events
        manager.on("record_processed", self.on_any_event)
        manager.on("connection_established", self.on_any_event)
        manager.on("connection_failed", self.on_any_event)
        
        log.info(f"Custom logger plugin installed, logging to: {self.log_file}")
    
    def on_any_event(self, *args, **kwargs):
        """Log any event to file."""
        self.event_count += 1
        
        with open(self.log_file, 'a') as f:
            f.write(f"Event {self.event_count}: {args} {kwargs}\n")


# Register the example plugin
register_plugin("custom_logger", CustomLoggerPlugin, "custom")


# Plugin creation helper
def create_custom_plugin(name: str, description: str = "Custom plugin"):
    """
    Helper function to create a custom plugin class.
    
    Args:
        name: Plugin name
        description: Plugin description
        
    Returns:
        Plugin class that can be customized
    """
    
    class CustomPlugin(BasePlugin):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.name = name
            self.description = description
            self.version = "1.0.0"
        
        def install(self, manager):
            super().install(manager)
            print(f"Custom plugin '{name}' installed")
        
        def uninstall(self, manager):
            super().uninstall(manager)
            print(f"Custom plugin '{name}' uninstalled")
    
    return CustomPlugin


__all__ = [
    "PluginRegistry",
    "register_plugin",
    "get_plugin_class",
    "list_available_plugins",
    "list_plugins_by_category",
    "get_plugin_categories",
    "get_plugin_info",
    "print_plugin_catalog",
    "create_custom_plugin",
    "CustomLoggerPlugin"
] 