from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from astmio.validation import (
    validate_device_info,
    validate_frame_configuration,
    validate_transport_configuration,
)

try:
    import yaml
except ImportError:
    yaml = None
try:
    import toml
except ImportError:
    toml = None

from astmio.exceptions import ConfigurationError, ValidationError

from .dataclasses import (
    RecordConfig,
    RecordType,
)
from .enums import CommunicationProtocol
from .logging import get_logger
from .models import FrameConfig, SerialConfig, TCPConfig, UDPConfig

log = get_logger(__name__)


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
    transport: Union[TCPConfig, SerialConfig, UDPConfig] = field(
        default_factory=lambda: TCPConfig(mode=CommunicationProtocol.TCP)
    )
    frame: FrameConfig = field(default_factory=FrameConfig)
    records: Dict[RecordType, RecordConfig] = field(default_factory=dict)

    # Metadata
    description: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None

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
    def from_dict(
        cls, data: Dict[str, Any], source_file: Optional[str] = None
    ) -> "DeviceProfile":
        """
        Create profile from dictionary with comprehensive validation.
        """
        records = {}
        parsing_errors = []
        try:
            # validate basic information
            device = validate_device_info(data)

            # validate transport config
            transport_config: Union[
                TCPConfig, UDPConfig, SerialConfig
            ] = validate_transport_configuration(data)

            # Validate frame config
            frame_config: FrameConfig = validate_frame_configuration(data)

            # Validate records config
            records_data: Dict[RecordType, RecordConfig] = data.get(
                "records", {}
            )

            # Split dict item into recordType and record_data like 'H' and its fields
            for record_type_str, record_data in records_data.items():
                try:
                    record_type = RecordType(record_type_str.upper())
                    record_config: RecordConfig = RecordConfig.from_dict(
                        record_type_str, record_data
                    )

                    # Validate record configuration
                    config_errors = record_config.validate_record_config()
                    if config_errors:
                        parsing_errors.extend(
                            [
                                f"{record_type_str}: {error}"
                                for error in config_errors
                            ]
                        )
                        log.error(parsing_errors)

                    records[record_type] = record_config

                    log.debug(
                        f"Successfully parsed {record_type_str} record with {len(record_config.fields)} fields"
                    )
                except ValueError as ve:
                    log.warning(
                        f"Unknown record type: {record_type_str}, error: {ve}"
                    )
                    parsing_errors.append(
                        f"Unknown record type: {record_type_str}"
                    )
                except Exception as e:
                    log.error(
                        f"Failed to parse record config for {record_type_str}: {e}"
                    )
                    parsing_errors.append(
                        f"Failed to parse {record_type_str}: {str(e)}"
                    )

            # validate device specific quirks config
            quirks_config = data.get("quirks", {})

            # Create profile
            profile: DeviceProfile = cls(
                device=device,
                vendor=data.get("vendor"),
                model=data.get("model"),
                version=data.get("version"),
                protocol=data.get("protocol", "ASTM E1394"),
                transport=transport_config,
                frame=frame_config,
                records=records,
                description=data.get("description"),
                quirks=quirks_config,
                custom_extensions=data.get("custom_extensions", {}),
            )

            # Add source file to metadata if provided
            if source_file:
                profile.custom_extensions["source_file"] = source_file

            log.info("Loaded profile for %s", device)
            return profile
        except ConfigurationError as ce:
            raise ce
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
                        "description": config.description,
                        "total_fields": config.total_fields,
                        "repeated": config.repeated,
                        "fields": [
                            {
                                "name": field.field_name,
                                "type": field.field_type,
                                "required": field.required,
                                "max_length": field.max_length,
                                "default": field.default_value,
                                "values": field.enum_values,
                                "format": field.format,
                                "parsing": field.parsing,
                                "validation_pattern": field.validation_pattern,
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

    def get_field_mapping(self, record_type: RecordType) -> Dict[str, int]:
        """Get ASTM field mapping for a record type."""
        if record_type not in self.records:
            return {}

        return {
            field.field_name: field.astm_position
            for field in self.records[record_type].fields
        }

    def create_record_classes(self) -> Dict[RecordType, type]:
        """
        Create dynamic Pydantic record classes from this profile.
        """
        record_classes = {}
        if not self.records:
            log.warning(
                f"Cant create models, records are empty: {self.records}"
            )
        else:
            from astmio.record_factory import RecordFactory

            for record_type, record_fields_config in self.records.items():
                try:
                    record_class = RecordFactory.create_record_class(
                        record_fields_config
                    )
                    record_classes[record_type] = record_class
                    log.info(f"Created record class for {record_type.value}")
                except Exception as e:
                    log.error(
                        f"Failed to create record class for {record_type.value}: {e}"
                    )

        return record_classes

    def get_record_class(self, record_type: RecordType) -> Optional[type]:
        """Get a specific record class for this profile."""
        if record_type not in self.records:
            return None

        from astmio.record_factory import RecordFactory

        try:
            return RecordFactory.get_record_class(self.records[record_type])
        except Exception as e:
            log.error(
                f"Failed to create record class for {record_type.value}: {e}"
            )
            return None

    def validate(self, strict: bool = False) -> List[str]:
        """
        Performs high-level validation specific to the DeviceProfile.
        Relies on nested dataclasses to have already validated themselves on creation.
        """
        errors = []

        if not self.device.strip():
            errors.append("Device name cannot be empty")

        for record_type, config in self.records.items():
            try:
                if strict:
                    has_required_fields = any(f.required for f in config.fields)
                    if not has_required_fields:
                        errors.append(
                            f"Strict check failed: Record {record_type.value} has no required fields"
                        )
            except Exception as e:
                errors.append(
                    f"Validation of record {record_type.value} failed: {e}"
                )

        return errors

    def is_valid(self, strict: bool = False) -> bool:
        """Check if profile is valid."""
        return len(self.validate(strict=strict)) == 0

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
