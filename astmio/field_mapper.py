from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Union

from .exceptions import ValidationError

# @dataclass
# class BaseFieldMapping:
#     field_name: str
#     astm_position: int
#     required: bool = False
#     max_length: Optional[int] = None


@dataclass
class RecordFieldMapping:
    """
    CHANGED: This is now the common base class for all field types.
    It contains only the attributes that EVERY field mapping shares.
    """

    field_name: str
    astm_position: int
    field_type: str
    required: bool = False
    repeated: bool = False
    max_length: Optional[int] = None
    default_value: Optional[Any] = None

    def __post_init__(self):
        """Basic validation for all fields."""
        if not self.field_name or not self.field_name.strip():
            raise ValidationError("Field name cannot be empty")
        if self.astm_position < 0:
            raise ValidationError("ASTM position must be non-negative")

    def validate_field_config(self) -> List[str]:
        """Validate individual field configuration and return errors."""
        errors = []

        # Validate field name
        if not self.field_name or not self.field_name.strip():
            errors.append("Field name cannot be empty")

        # Validate ASTM position
        if self.astm_position < 0:
            errors.append(
                f"ASTM position must be non-negative: {self.astm_position}"
            )

        # Validate max length
        if self.max_length is not None and self.max_length <= 0:
            errors.append(f"Max length must be positive: {self.max_length}")

        # Validate field type specific requirements
        if self.field_type == "enum" and not self.enum_values:
            errors.append("Enum field type requires enum_values")

        if self.field_type == "component" and not self.component_fields:
            errors.append("Component field type requires component_fields")

        if self.field_type == "constant" and not self.default_value:
            errors.append("Constant field type requires default_value")

        return errors


@dataclass
class ConstantField(RecordFieldMapping):
    """A field with a fixed, default value."""

    field_type: Literal["constant"] = "constant"
    default_value: Any = None

    def __post_init__(self):
        if self.default_value is None:
            raise ValidationError(
                f"ConstantField '{self.field_name}' must have a default_value."
            )


@dataclass
class StringField(RecordFieldMapping):
    """A standard string field with optional parsing rules."""

    field_type: Literal["string"] = "string"
    parsing: Optional[Literal["literal"]] = None


@dataclass
class EnumField(RecordFieldMapping):
    """A field constrained to a list of possible values."""

    field_type: Literal["enum"] = "enum"
    enum_values: List[str] = None

    def __post_init__(self):
        if not self.enum_values:
            raise ValidationError(
                f"EnumField '{self.field_name}' must have a non-empty enum_values list."
            )


@dataclass
class DateTimeField(RecordFieldMapping):
    """A field representing a date and/or time."""

    field_type: Literal["datetime"] = "datetime"
    format: str = None

    def __post_init__(self):
        if not self.format:
            raise ValidationError(
                f"DateTimeField '{self.field_name}' must have a format string."
            )


@dataclass
class ComponentField(RecordFieldMapping):
    """A field that is composed of other sub-fields (recursive)."""

    field_type: Literal["component"] = "component"
    component_fields: List["FieldMappingUnion"] = None


FieldMappingUnion = Union[
    ConstantField, StringField, EnumField, DateTimeField, ComponentField
]


def create_field_mapping(
    field_data: Dict[str, Any], position: int
) -> FieldMappingUnion:
    """Factory to create the correct FieldMapping object based on its type."""
    field_type = field_data.get("type", "string")

    # This lines will remove the ignored field from the final model
    # if field_type == "ignored":
    #     return None

    field_data["field_name"] = field_data.pop("name", "").rstrip(",")
    field_data["astm_position"] = position

    if "type" in field_data:
        field_data["field_type"] = field_data.pop("type")
    else:
        field_data["field_type"] = "string"

    if "default" in field_data:
        field_data["default_value"] = field_data.pop("default")
    if "values" in field_data:
        field_data["enum_values"] = field_data.pop("values")
    if "format" in field_data:
        field_data["format"] = field_data.pop("format")

    try:
        if field_type == "constant":
            return ConstantField(**field_data)
        if field_type == "enum":
            return EnumField(**field_data)
        if field_type == "datetime":
            return DateTimeField(**field_data)
        if field_type == "component":
            sub_fields_data = field_data.pop("fields", [])
            component_fields = [
                field_map
                for i, sf in enumerate(sub_fields_data)
                if (field_map := create_field_mapping(sf, i)) is not None
            ]
            return ComponentField(
                component_fields=component_fields, **field_data
            )

        return StringField(**field_data)
    except TypeError as e:
        raise ValidationError(
            f"Mismatched or missing key for field '{field_data['field_name']}' of type '{field_type}'. Details: {e}"
        ) from e
