from dataclasses import dataclass
from dataclasses import fields as dataclass_fields
from typing import Any, Dict, List, Literal, Optional, Type, Union

from .exceptions import ValidationError


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
class IntegerField(RecordFieldMapping):
    """A field with an integer value"""

    field_type: Literal["integer"] = "integer"


@dataclass
class DecimalField(RecordFieldMapping):
    """A field with an decimal value"""

    field_type: Literal["decimal"] = "decimal"


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
    ConstantField,
    StringField,
    EnumField,
    DateTimeField,
    ComponentField,
    IntegerField,
]

FIELD_TYPE_MAP: Dict[str, Type[RecordFieldMapping]] = {
    "constant": ConstantField,
    "string": StringField,
    "enum": EnumField,
    "datetime": DateTimeField,
    "component": ComponentField,
    "integer": IntegerField,
    "decimal": DecimalField,
    "ignored": StringField,
}


def create_field_mapping(
    field_data: Dict[str, Any], position: int
) -> Optional[FieldMappingUnion]:
    """
    Factory to create the correct FieldMapping dataclass object based on its type.
    This version is robust against unexpected keyword arguments.
    """
    field_type = field_data.get("type", "string")

    target_class = FIELD_TYPE_MAP.get(field_type)
    if not target_class:
        raise ValidationError(
            f"Unknown field type specified in YAML: '{field_type}'"
        )

    # 1. Prepare a dictionary of ALL potential parameters.
    all_params = {
        "field_name": field_data.get("name", "").rstrip(","),
        "astm_position": position,
        "field_type": field_type,
        "required": field_data.get("required", False),
        "repeated": field_data.get("repeated", False),
        "max_length": field_data.get("max_length"),
        "default_value": field_data.get("default"),
        "enum_values": field_data.get("values"),
        "format": field_data.get("format"),
        "parsing": field_data.get("parsing"),
    }

    # 2. Handle recursive ComponentField creation.
    if target_class is ComponentField:
        sub_fields_data = field_data.get("fields", [])
        all_params["component_fields"] = [
            create_field_mapping(sf, i + 1)
            for i, sf in enumerate(sub_fields_data)
        ]

    # --- THIS IS THE CRITICAL FIX ---
    # 3. Get expected fields using the correct function from the 'dataclasses' module.
    expected_fields = {f.name for f in dataclass_fields(target_class)}

    # 4. Create the final, filtered dictionary of arguments.
    final_constructor_args = {
        key: value
        for key, value in all_params.items()
        if key in expected_fields
    }

    try:
        # 5. Use the safe, filtered arguments to create the instance.
        return target_class(**final_constructor_args)
    except TypeError as e:
        raise ValidationError(
            f"Mismatched configuration for field '{all_params['field_name']}' of type '{field_type}'. "
            f"Details: {e}"
        ) from e
