#
# Modern Pydantic-based ASTM record definitions - Plugin Interface
#

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type

from astmio.logging import get_logger
from astmio.plugins import install_plugin

if TYPE_CHECKING:
    from astmio.models import RecordConfig
    from astmio.plugins.records import (
        ASTMBaseRecord,
        ModernRecordsPlugin,
        RecordMetadata,
    )

log = get_logger(__name__)

# Global plugin instance
_modern_records_plugin: Optional["ModernRecordsPlugin"] = None


def get_modern_records_plugin() -> "ModernRecordsPlugin":
    """
    Get or create the modern records plugin instance.

    Returns:
        ModernRecordsPlugin instance
    """
    global _modern_records_plugin

    if _modern_records_plugin is None:
        _modern_records_plugin = install_plugin("modern_records")
        log.info("Modern Records plugin initialized")

    return _modern_records_plugin


def get_astm_base_record() -> Type["ASTMBaseRecord"]:
    """
    Get the ASTMBaseRecord class from the plugin.

    Returns:
        ASTMBaseRecord class
    """
    from astmio.plugins.records import ASTMBaseRecord

    return ASTMBaseRecord


def create_record_class(
    record_name: str, config: "RecordConfig"
) -> Type["ASTMBaseRecord"]:
    """
    Create a dynamic record class using the plugin system.

    Args:
        record_name: Name for the new record class
        config: Record configuration

    Returns:
        Dynamically created ASTMBaseRecord subclass
    """
    plugin: ModernRecordsPlugin = get_modern_records_plugin()
    return plugin.create_record_class(record_name, config)


def parse_record(
    record_class: Type["ASTMBaseRecord"], values: List[Any]
) -> "ASTMBaseRecord":
    """
    Parse ASTM record values using the plugin system.

    Args:
        record_class: The record class to instantiate
        values: Raw ASTM field values

    Returns:
        Validated record instance
    """
    plugin = get_modern_records_plugin()
    return plugin.parse_record(record_class, values)


def serialize_record(
    record: "ASTMBaseRecord",
    repeat_delimiter: Optional[str] = None,
    component_delimiter: Optional[str] = None,
) -> List[Optional[str]]:
    """
    Serialize a record using the plugin system.

    Args:
        record: Record instance to serialize
        repeat_delimiter: Delimiter for repeated fields
        component_delimiter: Delimiter for component fields

    Returns:
        List of ASTM field values
    """
    plugin = get_modern_records_plugin()
    return plugin.serialize_record(
        record, repeat_delimiter, component_delimiter
    )


def get_record_metadata(
    record_class: Type["ASTMBaseRecord"],
) -> "RecordMetadata":
    """
    Get metadata for a record class using the plugin system.

    Args:
        record_class: Record class to get metadata for

    Returns:
        RecordMetadata instance
    """
    plugin = get_modern_records_plugin()
    return plugin.get_record_metadata(record_class)


def get_plugin_statistics() -> Dict[str, Any]:
    """
    Get statistics from the modern records plugin.

    Returns:
        Dictionary containing plugin statistics
    """
    plugin = get_modern_records_plugin()
    return plugin.get_statistics()


# Backward compatibility - expose classes and functions that were previously available
def __getattr__(name: str):
    """
    Provide backward compatibility for direct imports.

    This allows existing code that imports ASTMBaseRecord or RecordMetadata
    directly from this module to continue working.
    """
    if name == "ASTMBaseRecord":
        from astmio.plugins.records import ASTMBaseRecord

        return ASTMBaseRecord
    elif name == "RecordMetadata":
        from astmio.plugins.records import RecordMetadata

        return RecordMetadata
    else:
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


# Export the main interface functions
__all__ = [
    "get_modern_records_plugin",
    "get_astm_base_record",
    "create_record_class",
    "parse_record",
    "serialize_record",
    "get_record_metadata",
    "get_plugin_statistics",
    # Backward compatibility
    "ASTMBaseRecord",
    "RecordMetadata",
]
