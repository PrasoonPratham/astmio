#
# Modern Pydantic-based ASTM record definitions
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

from astmio.exceptions import InvalidFieldError, ValidationError
from astmio.field_mapper import (
    ComponentField,
    DateTimeField,
    RecordFieldMapping,
)
from astmio.logging import get_logger

if TYPE_CHECKING:
    from .models import RecordConfig

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
