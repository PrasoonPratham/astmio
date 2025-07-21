# -*- coding: utf-8 -*-
#
# Enhanced configuration system for ASTM library
#
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Union, Set, Callable
from pathlib import Path
import yaml
import json
import logging
from datetime import datetime
from enum import Enum

from .exceptions import ValidationError
from .enums import RecordType

log = logging.getLogger(__name__)


class ProfileFormat(str, Enum):
    """Supported profile formats."""

    YAML = "yaml"
    JSON = "json"
    TOML = "toml"


class TransportMode(str, Enum):
    """Supported transport modes."""

    TCP = "tcp"
    SERIAL = "serial"
    UDP = "udp"
    WEBSOCKET = "websocket"


@dataclass
class TransportConfig:
    """Enhanced transport configuration with validation."""

    mode: TransportMode = TransportMode.TCP
    port: int = 15200
    host: str = "0.0.0.0"
    encoding: str = "ascii"
    timeout: float = 30.0
    max_connections: int = 10
    control_chars: Dict[str, int] = field(default_factory=dict)
    ssl_enabled: bool = False
    ssl_cert_path: Optional[str] = None
    ssl_key_path: Optional[str] = None

    def __post_init__(self):
        """Validate configuration after initialization."""
        if not 1 <= self.port <= 65535:
            raise ValidationError(f"Invalid port number: {self.port}")

        if self.timeout <= 0:
            raise ValidationError(f"Timeout must be positive: {self.timeout}")

        if self.max_connections <= 0:
            raise ValidationError(
                f"Max connections must be positive: {self.max_connections}"
            )

        if self.ssl_enabled:
            if not self.ssl_cert_path or not self.ssl_key_path:
                raise ValidationError("SSL enabled but certificate or key path missing")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TransportConfig":
        """Create from dictionary with type conversion."""
        try:
            # Convert mode to enum if string
            if "mode" in data and isinstance(data["mode"], str):
                data["mode"] = TransportMode(data["mode"].lower())

            return cls(**data)
        except (ValueError, TypeError) as e:
            raise ValidationError(f"Invalid transport configuration: {e}")


@dataclass
class FrameConfig:
    """Enhanced frame configuration with validation."""

    start: str = "STX"
    end: List[str] = field(default_factory=lambda: ["ETX", "CR", "LF"])
    checksum: bool = True
    max_length: int = 240
    sequence_numbers: bool = True
    chunking_enabled: bool = True
    chunk_size: int = 240

    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.max_length <= 0:
            raise ValidationError(f"Max length must be positive: {self.max_length}")

        if self.chunking_enabled and self.chunk_size <= 0:
            raise ValidationError(f"Chunk size must be positive: {self.chunk_size}")

        if self.chunk_size > self.max_length:
            log.warning(
                "Chunk size (%s) larger than max length (%s)",
                self.chunk_size,
                self.max_length,
            )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FrameConfig":
        """Create from dictionary with validation."""
        try:
            return cls(**data)
        except (ValueError, TypeError) as e:
            raise ValidationError(f"Invalid frame configuration: {e}")


@dataclass
class RecordFieldMapping:
    """Field mapping for a specific record type."""

    field_name: str
    astm_position: int
    required: bool = False
    max_length: Optional[int] = None
    validation_pattern: Optional[str] = None
    default_value: Optional[str] = None

    def __post_init__(self):
        """Validate field mapping."""
        if self.astm_position < 0:
            raise ValidationError(
                f"ASTM position must be non-negative: {self.astm_position}"
            )

        if self.max_length is not None and self.max_length <= 0:
            raise ValidationError(f"Max length must be positive: {self.max_length}")


@dataclass
class RecordConfig:
    """Configuration for a specific record type."""

    record_type: RecordType
    fields: List[RecordFieldMapping] = field(default_factory=list)
    validation_rules: Dict[str, Any] = field(default_factory=dict)
    custom_parser: Optional[str] = None

    def __post_init__(self):
        """Validate record configuration."""
        # Check for duplicate ASTM positions
        positions = [f.astm_position for f in self.fields]
        if len(positions) != len(set(positions)):
            raise ValidationError(
                f"Duplicate ASTM positions in record {self.record_type}"
            )

    @classmethod
    def from_dict(cls, record_type: str, data: Dict[str, Any]) -> "RecordConfig":
        """Create from dictionary with validation."""
        try:
            # Convert record type to enum
            if isinstance(record_type, str):
                record_type = RecordType(record_type.upper())

            # Parse field mappings
            fields = []
            for field_data in data.get("fields", []):
                if isinstance(field_data, dict):
                    fields.append(RecordFieldMapping(**field_data))
                elif isinstance(field_data, str):
                    # Simple field name - create basic mapping
                    # Mark the first field (usually 'type') as required
                    is_required = len(fields) == 0 and field_data == "type"
                    fields.append(
                        RecordFieldMapping(
                            field_name=field_data,
                            astm_position=len(fields),
                            required=is_required,
                        )
                    )
                else:
                    log.warning(f"Invalid field mapping format: {field_data}")

            return cls(
                record_type=record_type,
                fields=fields,
                validation_rules=data.get("validation_rules", {}),
                custom_parser=data.get("custom_parser"),
            )
        except (ValueError, TypeError) as e:
            raise ValidationError(
                f"Invalid record configuration for {record_type}: {e}"
            )


@dataclass
class ParserConfig:
    """Parser configuration with customization options."""

    strict_mode: bool = False
    ignore_checksum_errors: bool = False
    auto_sequence_correction: bool = True
    max_message_size: int = 64000
    custom_handlers: Dict[str, str] = field(default_factory=dict)
    preprocessing_rules: List[str] = field(default_factory=list)

    # Field mapping and separator configuration
    patient_name_field: Optional[str] = None
    sample_id_field: Optional[str] = None
    test_separator: str = "\\"
    component_separator: str = "^"

    def __post_init__(self):
        """Validate parser configuration."""
        if self.max_message_size <= 0:
            raise ValidationError(
                f"Max message size must be positive: {self.max_message_size}"
            )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ParserConfig":
        """Create from dictionary with validation."""
        try:
            return cls(**data)
        except (ValueError, TypeError) as e:
            raise ValidationError(f"Invalid parser configuration: {e}")


@dataclass
class DeviceProfile:
    """Enhanced device profile with comprehensive configuration."""

    # Basic information
    device: str
    vendor: Optional[str] = None
    model: Optional[str] = None
    version: Optional[str] = None
    protocol: str = "ASTM E1394"

    # Configuration sections
    transport: TransportConfig = field(default_factory=TransportConfig)
    frame: FrameConfig = field(default_factory=FrameConfig)
    records: Dict[RecordType, RecordConfig] = field(default_factory=dict)
    parser: ParserConfig = field(default_factory=ParserConfig)

    # Metadata
    description: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    tags: Set[str] = field(default_factory=set)

    # Device-specific quirks and customizations
    quirks: Dict[str, Any] = field(default_factory=dict)
    custom_extensions: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate profile after initialization."""
        if not self.device:
            raise ValidationError("Device name is required")

        # Validate record types
        for record_type in self.records:
            if not isinstance(record_type, RecordType):
                raise ValidationError(f"Invalid record type: {record_type}")

    @classmethod
    def from_file(cls, filepath: Union[str, Path]) -> "DeviceProfile":
        """Load profile from file with enhanced error handling."""
        filepath = Path(filepath)

        if not filepath.exists():
            raise ValidationError(f"Profile file not found: {filepath}")

        try:
            # Determine format from extension
            format_map = {
                ".yaml": ProfileFormat.YAML,
                ".yml": ProfileFormat.YAML,
                ".json": ProfileFormat.JSON,
                ".toml": ProfileFormat.TOML,
            }

            profile_format = format_map.get(filepath.suffix.lower(), ProfileFormat.YAML)

            with open(filepath, "r", encoding="utf-8") as f:
                if profile_format == ProfileFormat.YAML:
                    config_data = yaml.safe_load(f)
                elif profile_format == ProfileFormat.JSON:
                    config_data = json.load(f)
                elif profile_format == ProfileFormat.TOML:
                    try:
                        import toml

                        config_data = toml.load(f)
                    except ImportError:
                        raise ValidationError("TOML support requires 'toml' package")
                else:
                    raise ValidationError(f"Unsupported format: {profile_format}")

            return cls.from_dict(config_data, source_file=str(filepath))

        except (IOError, yaml.YAMLError, json.JSONDecodeError) as e:
            log.error("Failed to load profile from %s: %s", str(filepath), str(e))
            raise ValidationError(f"Error loading profile from {filepath}: {e}")

    @classmethod
    def from_dict(
        cls, data: Dict[str, Any], source_file: Optional[str] = None
    ) -> "DeviceProfile":
        """Create profile from dictionary with comprehensive validation."""
        try:
            # Extract and validate basic information
            device = data.get("device")
            if not device:
                raise ValidationError("Device name is required")

            # Parse transport configuration
            transport_data = data.get("transport", {})
            transport = TransportConfig.from_dict(transport_data)

            # Parse frame configuration
            frame_data = data.get("frame", {})
            frame = FrameConfig.from_dict(frame_data)

            # Parse record configurations
            records = {}
            records_data = data.get("records", {})
            for record_type_str, record_data in records_data.items():
                try:
                    record_type = RecordType(record_type_str.upper())
                    records[record_type] = RecordConfig.from_dict(
                        record_type_str, record_data
                    )
                except ValueError:
                    log.warning(f"Unknown record type: {record_type_str}")

            # Parse parser configuration
            parser_data = data.get("parser", {})
            parser = ParserConfig.from_dict(parser_data)

            # Parse tags
            tags = set(data.get("tags", []))

            # Create profile
            profile = cls(
                device=device,
                vendor=data.get("vendor"),
                model=data.get("model"),
                version=data.get("version"),
                protocol=data.get("protocol", "ASTM E1394"),
                transport=transport,
                frame=frame,
                records=records,
                parser=parser,
                description=data.get("description"),
                tags=tags,
                quirks=data.get("quirks", {}),
                custom_extensions=data.get("custom_extensions", {}),
            )

            # Add source file to metadata if provided
            if source_file:
                profile.custom_extensions["source_file"] = source_file

            log.info(
                "Loaded profile for %s (vendor: %s, model: %s)",
                device,
                profile.vendor,
                profile.model,
            )
            return profile

        except Exception as e:
            log.error("Failed to create profile from dictionary: %s", str(e))
            raise ValidationError(f"Invalid profile configuration: {e}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert profile to dictionary for serialization."""
        try:
            return {
                "device": self.device,
                "vendor": self.vendor,
                "model": self.model,
                "version": self.version,
                "protocol": self.protocol,
                "transport": {
                    "mode": self.transport.mode.value,
                    "port": self.transport.port,
                    "host": self.transport.host,
                    "encoding": self.transport.encoding,
                    "timeout": self.transport.timeout,
                    "max_connections": self.transport.max_connections,
                    "control_chars": self.transport.control_chars,
                    "ssl_enabled": self.transport.ssl_enabled,
                    "ssl_cert_path": self.transport.ssl_cert_path,
                    "ssl_key_path": self.transport.ssl_key_path,
                },
                "frame": {
                    "start": self.frame.start,
                    "end": self.frame.end,
                    "checksum": self.frame.checksum,
                    "max_length": self.frame.max_length,
                    "sequence_numbers": self.frame.sequence_numbers,
                    "chunking_enabled": self.frame.chunking_enabled,
                    "chunk_size": self.frame.chunk_size,
                },
                "records": {
                    record_type.value: {
                        "fields": [
                            {
                                "field_name": field.field_name,
                                "astm_position": field.astm_position,
                                "required": field.required,
                                "max_length": field.max_length,
                                "validation_pattern": field.validation_pattern,
                                "default_value": field.default_value,
                            }
                            for field in config.fields
                        ],
                        "validation_rules": config.validation_rules,
                        "custom_parser": config.custom_parser,
                    }
                    for record_type, config in self.records.items()
                },
                "parser": {
                    "strict_mode": self.parser.strict_mode,
                    "ignore_checksum_errors": self.parser.ignore_checksum_errors,
                    "auto_sequence_correction": self.parser.auto_sequence_correction,
                    "max_message_size": self.parser.max_message_size,
                    "custom_handlers": self.parser.custom_handlers,
                    "preprocessing_rules": self.parser.preprocessing_rules,
                },
                "description": self.description,
                "tags": list(self.tags),
                "quirks": self.quirks,
                "custom_extensions": self.custom_extensions,
            }
        except Exception as e:
            log.error("Failed to convert profile to dictionary: %s", str(e))
            raise ValidationError(f"Profile serialization failed: {e}")

    def save_to_file(
        self, filepath: Union[str, Path], format: ProfileFormat = ProfileFormat.YAML
    ) -> None:
        """Save profile to file in specified format."""
        filepath = Path(filepath)

        try:
            data = self.to_dict()

            with open(filepath, "w", encoding="utf-8") as f:
                if format == ProfileFormat.YAML:
                    yaml.dump(data, f, default_flow_style=False, indent=2)
                elif format == ProfileFormat.JSON:
                    json.dump(data, f, indent=2, default=str)
                elif format == ProfileFormat.TOML:
                    try:
                        import toml

                        toml.dump(data, f)
                    except ImportError:
                        raise ValidationError("TOML support requires 'toml' package")
                else:
                    raise ValidationError(f"Unsupported format: {format}")

            log.info(f"Saved profile to {filepath} in {format.value} format")

        except Exception as e:
            log.error("Failed to save profile to %s: %s", str(filepath), str(e))
            raise ValidationError(f"Failed to save profile: {e}")

    def validate(self, strict: bool = False) -> List[str]:
        """Comprehensive profile validation."""
        errors = []

        try:
            # Validate basic information
            if not self.device.strip():
                errors.append("Device name cannot be empty")

            # Validate transport configuration
            try:
                # Re-validate transport
                if self.transport.port < 1 or self.transport.port > 65535:
                    errors.append(f"Invalid port: {self.transport.port}")
            except Exception as e:
                errors.append(f"Transport validation failed: {e}")

            # Validate frame configuration
            try:
                if self.frame.max_length <= 0:
                    errors.append(f"Invalid max frame length: {self.frame.max_length}")
            except Exception as e:
                errors.append(f"Frame validation failed: {e}")

            # Validate record configurations
            for record_type, config in self.records.items():
                try:
                    # Check for required fields
                    required_fields = [f for f in config.fields if f.required]
                    if not required_fields and strict:
                        errors.append(
                            f"Record {record_type.value} has no required fields"
                        )

                    # Check field mappings
                    positions = [f.astm_position for f in config.fields]
                    if len(positions) != len(set(positions)):
                        errors.append(
                            f"Duplicate ASTM positions in record {record_type.value}"
                        )

                except Exception as e:
                    errors.append(f"Record {record_type.value} validation failed: {e}")

            # Validate parser configuration
            try:
                if self.parser.max_message_size <= 0:
                    errors.append(
                        f"Invalid max message size: {self.parser.max_message_size}"
                    )
            except Exception as e:
                errors.append(f"Parser validation failed: {e}")

            return errors

        except Exception as e:
            log.error("Profile validation process failed: %s", str(e))
            return [f"Validation process failed: {e}"]

    def is_valid(self, strict: bool = False) -> bool:
        """Check if profile is valid."""
        return len(self.validate(strict=strict)) == 0

    def get_field_mapping(self, record_type: RecordType) -> Dict[str, int]:
        """Get ASTM field mapping for a record type."""
        if record_type not in self.records:
            return {}

        return {
            field.field_name: field.astm_position
            for field in self.records[record_type].fields
        }

    def merge_with(
        self, other: "DeviceProfile", prefer_other: bool = True
    ) -> "DeviceProfile":
        """Merge this profile with another profile."""
        try:
            # Determine which profile takes precedence
            base = other if prefer_other else self
            overlay = self if prefer_other else other

            # Create merged configuration
            merged_data = base.to_dict()
            overlay_data = overlay.to_dict()

            # Deep merge logic (simplified)
            def deep_merge(base_dict: Dict, overlay_dict: Dict) -> Dict:
                result = base_dict.copy()
                for key, value in overlay_dict.items():
                    if (
                        key in result
                        and isinstance(result[key], dict)
                        and isinstance(value, dict)
                    ):
                        result[key] = deep_merge(result[key], value)
                    else:
                        result[key] = value
                return result

            merged_data = deep_merge(merged_data, overlay_data)

            # Update metadata
            merged_data["device"] = f"{base.device}+{overlay.device}"
            merged_data["updated_at"] = datetime.now().isoformat()

            return DeviceProfile.from_dict(merged_data)

        except Exception as e:
            log.error("Failed to merge profiles: %s", str(e))
            raise ValidationError(f"Profile merge failed: {e}")


class ConfigManager:
    """Enhanced configuration manager with advanced features."""

    def __init__(self, profile_directories: Optional[List[Union[str, Path]]] = None):
        """Initialize with optional profile directories."""
        self._profiles: Dict[str, DeviceProfile] = {}
        self._profile_directories: List[Path] = []
        self._watchers: List[Callable[[str, DeviceProfile], None]] = []

        if profile_directories:
            for directory in profile_directories:
                self.add_profile_directory(directory)

    def add_profile_directory(self, directory: Union[str, Path]) -> None:
        """Add a directory to search for profiles."""
        directory = Path(directory)
        if directory.exists() and directory.is_dir():
            self._profile_directories.append(directory)
            log.info(f"Added profile directory: {directory}")
        else:
            log.warning(f"Profile directory not found: {directory}")

    def discover_profiles(self) -> List[DeviceProfile]:
        """Discover and load all profiles from configured directories."""
        discovered = []

        for directory in self._profile_directories:
            try:
                # Look for YAML, JSON, and TOML files
                patterns = ["*.yaml", "*.yml", "*.json", "*.toml"]
                for pattern in patterns:
                    for filepath in directory.glob(pattern):
                        try:
                            profile = DeviceProfile.from_file(filepath)
                            self.add_profile(profile)
                            discovered.append(profile)
                            log.info(f"Discovered profile: {profile.device}")
                        except Exception as e:
                            log.warning(f"Failed to load profile from {filepath}: {e}")
            except Exception as e:
                log.error(f"Failed to scan directory {directory}: {e}")

        return discovered

    def load_profile(self, filepath: Union[str, Path]) -> DeviceProfile:
        """Load a specific profile file."""
        try:
            profile = DeviceProfile.from_file(filepath)
            self.add_profile(profile)
            return profile
        except Exception as e:
            log.error(f"Failed to load profile from {filepath}: {e}")
            raise

    def add_profile(self, profile: DeviceProfile) -> None:
        """Add a profile to the manager."""
        if not isinstance(profile, DeviceProfile):
            raise ValidationError(f"Expected DeviceProfile, got {type(profile)}")

        if not profile.is_valid():
            errors = profile.validate()
            log.warning(f"Adding invalid profile {profile.device}: {errors}")

        self._profiles.get(profile.device)
        self._profiles[profile.device] = profile

        # Notify watchers
        for watcher in self._watchers:
            try:
                watcher(profile.device, profile)
            except Exception as e:
                log.error(f"Profile watcher failed: {e}")

        log.info(f"Added profile: {profile.device}")

    def get_profile(self, device: str) -> Optional[DeviceProfile]:
        """Get a profile by device name."""
        return self._profiles.get(device)

    def remove_profile(self, device: str) -> bool:
        """Remove a profile by device name."""
        if device in self._profiles:
            del self._profiles[device]
            log.info(f"Removed profile: {device}")
            return True
        return False

    def list_profiles(self) -> List[str]:
        """List all available profile names."""
        return list(self._profiles.keys())

    def get_all_profiles(self) -> Dict[str, DeviceProfile]:
        """Get all loaded profiles."""
        return self._profiles.copy()

    def find_profiles_by_tag(self, tag: str) -> List[DeviceProfile]:
        """Find profiles with a specific tag."""
        return [profile for profile in self._profiles.values() if tag in profile.tags]

    def find_profiles_by_vendor(self, vendor: str) -> List[DeviceProfile]:
        """Find profiles by vendor."""
        return [
            profile
            for profile in self._profiles.values()
            if profile.vendor and profile.vendor.lower() == vendor.lower()
        ]

    def validate_all_profiles(self, strict: bool = False) -> Dict[str, List[str]]:
        """Validate all loaded profiles."""
        results = {}
        for device, profile in self._profiles.items():
            errors = profile.validate(strict=strict)
            if errors:
                results[device] = errors
        return results

    def add_watcher(self, callback: Callable[[str, DeviceProfile], None]) -> None:
        """Add a callback to be notified when profiles change."""
        self._watchers.append(callback)

    def remove_watcher(self, callback: Callable[[str, DeviceProfile], None]) -> None:
        """Remove a profile change watcher."""
        if callback in self._watchers:
            self._watchers.remove(callback)

    def export_profiles(
        self, directory: Union[str, Path], format: ProfileFormat = ProfileFormat.YAML
    ) -> None:
        """Export all profiles to a directory."""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)

        for device, profile in self._profiles.items():
            # Sanitize filename
            safe_name = "".join(
                c for c in device if c.isalnum() or c in ("-", "_")
            ).lower()
            filename = f"{safe_name}.{format.value}"
            filepath = directory / filename

            try:
                profile.save_to_file(filepath, format)
                log.info(f"Exported profile {device} to {filepath}")
            except Exception as e:
                log.error(f"Failed to export profile {device}: {e}")


# Legacy compatibility functions
def load_profile_from_file(filepath: str) -> Optional[DeviceProfile]:
    """Legacy function for loading profiles."""
    try:
        return DeviceProfile.from_file(filepath)
    except Exception as e:
        log.error(f"Failed to load profile: {e}")
        return None


def load_profile(filepath: str) -> Optional[DeviceProfile]:
    """Legacy function for loading profiles."""
    return load_profile_from_file(filepath)


def validate_profile(profile_data: Dict[str, Any]) -> bool:
    """Legacy validation function."""
    try:
        profile = DeviceProfile.from_dict(profile_data)
        return profile.is_valid(strict=True)
    except ValidationError as e:
        # Re-raise ValidationError as ValueError for backward compatibility
        raise ValueError(str(e))
    except Exception as e:
        log.error(f"Profile validation failed: {e}")
        raise ValueError(f"Profile validation failed: {e}")


# Create default global config manager
default_config_manager = ConfigManager()

# Export main classes and functions
__all__ = [
    "DeviceProfile",
    "ConfigManager",
    "TransportConfig",
    "FrameConfig",
    "RecordConfig",
    "ParserConfig",
    "ProfileFormat",
    "TransportMode",
    "default_config_manager",
    "load_profile",
    "validate_profile",
]
