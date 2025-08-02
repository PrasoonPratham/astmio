from datetime import datetime
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator

from .exceptions import ConfigurationError


class RecordFieldMapping(BaseModel):
    """
    The common base model for all field mapping configurations.

    This class defines attributes shared by every field type and uses Pydantic
    aliases to map from the user-friendly YAML keys (e.g., 'name', 'default')
    to more descriptive internal attribute names.
    """

    field_name: str = Field(..., alias="name")
    astm_position: Optional[int] = Field(None, ge=1)
    field_type: str
    required: bool = False
    repeated: bool = False
    max_length: Optional[int] = Field(None, gt=0)
    default_value: Optional[Any] = Field(None, alias="default")


class IgnoredField(RecordFieldMapping):
    """A field that should be ignored during parsing. Always optional."""

    field_type: Literal["ignored"] = "ignored"
    required: bool = False


class ConstantField(RecordFieldMapping):
    """A field with a fixed, constant value."""

    field_type: Literal["constant"] = "constant"
    default_value: Any = Field(..., alias="default")

    @model_validator(mode="after")
    def check_default_value_adheres_to_max_length(self) -> "ConstantField":
        """
        Validates that the provided 'default' value does not exceed 'max_length'.
        Example from your config: `default: H` must have `len('H') <= max_length: 1`.
        """
        if self.max_length is not None and self.default_value is not None:
            if len(str(self.default_value)) > self.max_length:
                raise ConfigurationError(
                    message=(
                        f"The default value ('{self.default_value}') for constant field "
                        f"'{self.field_name}' exceeds the specified max_length of {self.max_length}."
                    ),
                    config_key=self.field_name,
                )
        return self


class StringField(RecordFieldMapping):
    field_type: Literal["string"] = "string"
    parsing: Optional[Literal["literal"]] = None

    @model_validator(mode="after")
    def check_default_value_adheres_to_max_length(self) -> "StringField":
        """
        If a default value is provided, validates that it does not exceed 'max_length'.
        """
        if self.max_length is not None and self.default_value is not None:
            if len(str(self.default_value)) > self.max_length:
                raise ConfigurationError(
                    message=(
                        f"The default value for string field '{self.field_name}' "
                        f"exceeds the specified max_length of {self.max_length}."
                    ),
                    config_key=self.field_name,
                )
        return self


class IntegerField(RecordFieldMapping):
    """A field representing an integer."""

    field_type: Literal["integer"] = "integer"


class DecimalField(RecordFieldMapping):
    """A field representing a decimal number."""

    field_type: Literal["decimal"] = "decimal"


class EnumField(RecordFieldMapping):
    """A field constrained to a specific list of string values."""

    field_type: Literal["enum"] = "enum"
    enum_values: List[str] = Field(..., alias="values")

    @model_validator(mode="after")
    def check_enum_values_adhere_to_max_length(self) -> "EnumField":
        """
        If max_length is specified, ensure all values in the enum_values list
        comply with that length constraint.
        Example from your config: All values in `["PR", "QR", ...]` must have `len <= 2`.
        """
        if self.max_length is None:
            return self
        for value in self.enum_values:
            if len(value) > self.max_length:
                raise ConfigurationError(
                    message=(
                        f"A value in 'enum_values' ('{value}') for field '{self.field_name}' "
                        f"exceeds the specified max_length of {self.max_length}."
                    ),
                    config_key=self.field_name,
                    config_value=self.enum_values,
                )
        return self


class DateTimeField(RecordFieldMapping):
    """A field representing a date and/or time that requires a format string."""

    field_type: Literal["datetime"] = "datetime"
    format: str

    @model_validator(mode="after")
    def check_datetime_rules(self) -> "DateTimeField":
        """
        Validates consistency between 'format', 'max_length', and any 'default' value.
        Example from your config: `max_length: 14` must match the length of a
        timestamp formatted with `"%Y%m%d%H%M%S"`.
        """

        if self.default_value is not None:
            try:
                datetime.strptime(str(self.default_value), self.format)
            except ValueError:
                raise ConfigurationError(
                    message=(
                        f"The default value ('{self.default_value}') for datetime field "
                        f"'{self.field_name}' does not match the specified format '{self.format}'."
                    ),
                    config_key=self.field_name,
                )

        if self.max_length is not None:
            expected_length = len(datetime(2000, 1, 1).strftime(self.format))
            if expected_length != self.max_length:
                raise ConfigurationError(
                    message=(
                        f"The specified max_length ({self.max_length}) for datetime field "
                        f"'{self.field_name}' does not match the expected length ({expected_length}) "
                        f"from the format string '{self.format}'."
                    ),
                    config_key=self.field_name,
                )
        return self


class ComponentField(RecordFieldMapping):
    """
    A complex field composed of a list of other sub-fields.
    This model is recursive.
    """

    field_type: Literal["component"] = "component"
    component_fields: List["DiscriminatedField"] = Field(..., alias="fields")

    @field_validator("component_fields", mode="before")
    @classmethod
    def pre_process_component_fields(
        cls, fields_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Recursively pre-processes the raw field data for sub-components.
        1. Renames the 'type' key from YAML to 'field_type'.
        2. Injects the astm_position for the sub-fields.
        """
        for i, field in enumerate(fields_data):
            if isinstance(field, dict):
                if "type" in field:
                    field["field_type"] = field.pop("type")

                if "astm_position" not in field:
                    field["astm_position"] = i + 1
        return fields_data


FieldMappingUnion = Union[
    IgnoredField,
    ConstantField,
    StringField,
    IntegerField,
    DecimalField,
    EnumField,
    DateTimeField,
    ComponentField,
]

DiscriminatedField = Annotated[
    FieldMappingUnion, Field(discriminator="field_type")
]

ComponentField.model_rebuild()
