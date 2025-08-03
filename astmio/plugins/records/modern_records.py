#
# Modern Pydantic-based ASTM record definitions as a plugin
#

from dataclasses import dataclass, field
from datetime import datetime
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Dict,
    List,
    Optional,
    Type,
    Union,
)

from pydantic import BaseModel, ConfigDict, PrivateAttr

from ...exceptions import InvalidFieldError, ValidationError
from ...field_mapper import (
    ComponentField,
    DateTimeField,
    RecordFieldMapping,
)
from ...logging import get_logger
from .. import BasePlugin

if TYPE_CHECKING:
    from ...models import RecordConfig

log = get_logger(__name__)


@dataclass(slots=True)
class RecordMetadata:
    """
    A container for metadata attached to a dynamically generated record model.

    This metadata provides the bridge between the ASTM standard's positional
    field structure and the named fields of the Pydantic model at runtime.
    """

    source_config: Union["RecordConfig", "ComponentField"]

    # Bidirectional mapping for easy lookups
    position_to_name: Dict[int, str] = field(default_factory=dict)
    name_to_position: Dict[str, int] = field(default_factory=dict)

    # Simple lists and dictionaries for runtime checks
    required_fields: List[str] = field(default_factory=list)
    field_types: Dict[str, str] = field(default_factory=dict)

    def get_position(self, name: str) -> Optional[int]:
        """Looks up the 1-based ASTM position for a given field name."""
        return self.name_to_position.get(name)

    def get_type(self, name: str) -> Optional[str]:
        """Looks up the configured type string for a given field name."""
        return self.field_types.get(name)


class ASTMBaseRecord(BaseModel):
    """
    The final, definitive base class for all dynamically created Pydantic models.
    It provides a robust parser for pre-processed data, audit metadata, and
    essential serialization methods.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
        frozen=False,
        arbitrary_types_allowed=True,
    )

    _created_at: datetime = PrivateAttr(default_factory=datetime.now)
    _updated_at: Optional[datetime] = PrivateAttr(default=None)
    _source: Optional[str] = PrivateAttr(default=None)

    _astm_metadata: ClassVar["RecordMetadata"]

    def __setattr__(self, name: str, value: Any) -> None:
        """Override to automatically track updates for an audit trail."""
        if hasattr(self, "__pydantic_private__") and name != "_updated_at":
            self._updated_at = datetime.now()
        super().__setattr__(name, value)

    @classmethod
    def from_astm_record(
        cls: Type["ASTMBaseRecord"], values: List[Any]
    ) -> "ASTMBaseRecord":
        """
        Parses a pre-processed list of values from a smart decoder into a
        validated instance of this dynamic model
        """
        mapped_dict: Dict[str, Any] = {}

        is_top_level_record = "record_type" in cls.model_fields
        data_fields = values[1:] if is_top_level_record else values

        for i, value in enumerate(data_fields):
            position = i + 2 if is_top_level_record else i + 1

            field_name = cls._astm_metadata.position_to_name.get(position)

            if not field_name or field_name not in cls.model_fields:
                continue

            if value is None:
                continue

            field_info = cls.model_fields[field_name]
            field_annotation = field_info.annotation

            if isinstance(field_annotation, type) and issubclass(
                field_annotation, BaseModel
            ):
                if isinstance(value, list):
                    mapped_dict[field_name] = field_annotation.from_astm_record(
                        value
                    )
                else:
                    mapped_dict[field_name] = value
            else:
                mapped_dict[field_name] = value

        try:
            return cls.model_validate(mapped_dict)
        except ValidationError as e:
            first_error = e.errors()[0]
            field_name_tuple = first_error["loc"]
            field_name = str(field_name_tuple[0])
            astm_position = cls._astm_metadata.get_position(field_name)

            raise InvalidFieldError(
                message=f"Invalid value for field '{field_name}': {first_error['msg']}",
                field_type=cls._astm_metadata.get_type(field_name),
                index=astm_position,
                field_value=first_error.get("input"),
                cause=e,
            )

    def to_json(self, indent: int = 2, **kwargs) -> str:
        """Serializes the record to a JSON string."""
        return self.model_dump_json(indent=indent, **kwargs)

    def to_astm(
        self,
        repeat_delimiter: str = "~",
        component_delimiter: str = "^",
    ) -> List[Optional[str]]:
        """
        Serializes the record back into a positional, 0-indexed list of strings.
        This version correctly handles 0-based list indexing.
        """
        data = self.model_dump()

        max_pos = max(self._astm_metadata.name_to_position.values(), default=0)
        # Create a list of the correct size. If max_pos is 13, we need 13 slots (0-12).
        astm_fields: List[Optional[str]] = [""] * max_pos

        for name, position in self._astm_metadata.name_to_position.items():
            if name not in self.model_fields:
                continue

            # Convert 1-based ASTM position to 0-based list index.
            idx = position - 1
            if not (0 <= idx < len(astm_fields)):
                continue

            value = data.get(name)
            if value is None:
                continue

            field_config = self._astm_metadata.source_config.get_field_by_name(
                name
            )
            if not field_config:
                continue

            if (
                hasattr(field_config, "repeated")
                and field_config.repeated
                and isinstance(value, list)
            ):
                serialized_values = [
                    self._serialize_value(item, field_config) for item in value
                ]
                # Use the parameter and the correct index (idx).
                astm_fields[idx] = repeat_delimiter.join(serialized_values)

            elif isinstance(field_config, ComponentField) and isinstance(
                value, dict
            ):
                # Pass the delimiter and use the correct index (idx).
                astm_fields[idx] = self._serialize_component(
                    value, field_config, component_delimiter
                )
            else:
                astm_fields[idx] = self._serialize_value(value, field_config)

        return astm_fields

    def _serialize_value(self, value: Any, config: "RecordFieldMapping") -> str:
        if value is None:
            return ""
        if isinstance(config, DateTimeField) and isinstance(value, datetime):
            return value.strftime(config.format)
        return str(value)

    def _serialize_component(
        self,
        component_data: Dict[str, Any],
        config: "ComponentField",
        component_delimiter: str,
    ) -> str:
        """Serializes a nested component into a delimited string."""
        max_comp_pos = max(
            (f.astm_position for f in config.component_fields), default=0
        )
        component_parts = [""] * max_comp_pos

        for sub_field_config in config.component_fields:
            sub_value = component_data.get(sub_field_config.field_name)
            if sub_value is not None:
                pos_index = sub_field_config.astm_position - 1
                if 0 <= pos_index < len(component_parts):
                    component_parts[pos_index] = self._serialize_value(
                        sub_value, sub_field_config
                    )

        return component_delimiter.join(component_parts)


class ModernRecordsPlugin(BasePlugin):
    """
    Plugin for modern Pydantic-based ASTM record handling.

    This plugin provides the ASTMBaseRecord class and related functionality
    for parsing, validating, and serializing ASTM records using Pydantic models.
    """

    name = "modern_records"
    version = "1.0.0"
    description = "Modern Pydantic-based ASTM record definitions and processing"

    def __init__(
        self,
        enable_audit_trail: bool = True,
        default_repeat_delimiter: str = "~",
        default_component_delimiter: str = "^",
        validation_mode: str = "strict",
        **kwargs,
    ):
        """
        Initialize the Modern Records plugin.

        Args:
            enable_audit_trail: Whether to track record creation/updates
            default_repeat_delimiter: Default delimiter for repeated fields
            default_component_delimiter: Default delimiter for component fields
            validation_mode: Pydantic validation mode ('strict' or 'lax')
            **kwargs: Additional configuration options
        """
        super().__init__(**kwargs)

        self.enable_audit_trail = enable_audit_trail
        self.default_repeat_delimiter = default_repeat_delimiter
        self.default_component_delimiter = default_component_delimiter
        self.validation_mode = validation_mode

        # Registry for dynamically created record classes
        self.record_classes: Dict[str, Type[ASTMBaseRecord]] = {}

        # Statistics
        self.records_processed = 0
        self.validation_errors = 0

    def install(self, manager):
        """Install the modern records plugin."""
        super().install(manager)

        # Register event listeners
        manager.on("record_parsed", self.on_record_parsed)
        manager.on("record_validation_failed", self.on_validation_failed)
        manager.on("record_created", self.on_record_created)

        # Make ASTMBaseRecord available globally through the manager
        if hasattr(manager, "server") and manager.server:
            manager.server.astm_base_record = ASTMBaseRecord

        log.info("Modern Records plugin installed successfully")

    def uninstall(self, manager):
        """Uninstall the modern records plugin."""
        super().uninstall(manager)

        # Clean up global references
        if hasattr(manager, "server") and manager.server:
            if hasattr(manager.server, "astm_base_record"):
                delattr(manager.server, "astm_base_record")

        log.info("Modern Records plugin uninstalled successfully")

    def create_record_class(
        self, record_name: str, config: "RecordConfig"
    ) -> Type[ASTMBaseRecord]:
        """
        Dynamically create a new record class based on configuration.

        Args:
            record_name: Name for the new record class
            config: Record configuration defining fields and structure

        Returns:
            Dynamically created ASTMBaseRecord subclass
        """
        if record_name in self.record_classes:
            return self.record_classes[record_name]

        # Create metadata
        metadata = RecordMetadata(source_config=config)

        # Build field mappings from config
        for field_config in config.fields:
            metadata.position_to_name[
                field_config.astm_position
            ] = field_config.field_name
            metadata.name_to_position[
                field_config.field_name
            ] = field_config.astm_position
            metadata.field_types[
                field_config.field_name
            ] = field_config.field_type

            if field_config.required:
                metadata.required_fields.append(field_config.field_name)

        # Create the dynamic class
        class_dict = {
            "_astm_metadata": metadata,
            "__module__": __name__,
        }

        # Add fields based on configuration
        annotations = {}
        for field_config in config.fields:
            field_type = self._get_python_type(field_config)
            annotations[field_config.field_name] = field_type

        class_dict["__annotations__"] = annotations

        # Create the class
        record_class = type(record_name, (ASTMBaseRecord,), class_dict)

        # Cache the class
        self.record_classes[record_name] = record_class

        log.debug(f"Created dynamic record class: {record_name}")
        return record_class

    def _get_python_type(self, field_config: "RecordFieldMapping") -> Type:
        """Convert field configuration to Python type annotation."""
        if isinstance(field_config, DateTimeField):
            return Optional[datetime] if not field_config.required else datetime
        elif isinstance(field_config, ComponentField):
            return (
                Optional[Dict[str, Any]]
                if not field_config.required
                else Dict[str, Any]
            )
        elif field_config.repeated:
            return (
                Optional[List[str]] if not field_config.required else List[str]
            )
        else:
            return Optional[str] if not field_config.required else str

    def parse_record(
        self, record_class: Type[ASTMBaseRecord], values: List[Any]
    ) -> ASTMBaseRecord:
        """
        Parse ASTM record values into a validated record instance.

        Args:
            record_class: The record class to instantiate
            values: Raw ASTM field values

        Returns:
            Validated record instance
        """
        try:
            record = record_class.from_astm_record(values)
            self.records_processed += 1

            # Emit event for other plugins
            if self.manager:
                self.manager.emit("record_parsed", record, values)

            return record

        except (ValidationError, InvalidFieldError) as e:
            self.validation_errors += 1

            # Emit validation error event
            if self.manager:
                self.manager.emit(
                    "record_validation_failed", record_class, values, e
                )

            raise

    def serialize_record(
        self,
        record: ASTMBaseRecord,
        repeat_delimiter: Optional[str] = None,
        component_delimiter: Optional[str] = None,
    ) -> List[Optional[str]]:
        """
        Serialize a record back to ASTM format.

        Args:
            record: Record instance to serialize
            repeat_delimiter: Delimiter for repeated fields
            component_delimiter: Delimiter for component fields

        Returns:
            List of ASTM field values
        """
        repeat_delim = repeat_delimiter or self.default_repeat_delimiter
        component_delim = (
            component_delimiter or self.default_component_delimiter
        )

        return record.to_astm(
            repeat_delimiter=repeat_delim, component_delimiter=component_delim
        )

    def get_record_metadata(
        self, record_class: Type[ASTMBaseRecord]
    ) -> RecordMetadata:
        """Get metadata for a record class."""
        return record_class._astm_metadata

    def get_statistics(self) -> Dict[str, Any]:
        """Get plugin statistics."""
        return {
            "records_processed": self.records_processed,
            "validation_errors": self.validation_errors,
            "registered_classes": len(self.record_classes),
            "class_names": list(self.record_classes.keys()),
        }

    # Event handlers
    def on_record_parsed(self, record: ASTMBaseRecord, values: List[Any]):
        """Handle record parsed events."""
        log.debug(f"Record parsed: {type(record).__name__}")

    def on_validation_failed(
        self,
        record_class: Type[ASTMBaseRecord],
        values: List[Any],
        error: Exception,
    ):
        """Handle validation failure events."""
        log.warning(
            f"Validation failed for {record_class.__name__}: {error}",
            values=values[:5],  # Log first 5 values only
        )

    def on_record_created(self, record: ASTMBaseRecord):
        """Handle record creation events."""
        if self.enable_audit_trail:
            log.debug(
                f"Record created: {type(record).__name__} at {record._created_at}"
            )
