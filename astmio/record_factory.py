from datetime import datetime
from typing import Any, Callable, Dict, List, Type

from pydantic import (
    Field,
    ValidationError,
    create_model,
)

from astmio.dataclasses import RecordConfig, RecordMetadata
from astmio.field_mapper import (
    ComponentField,
    ConstantField,
    DateTimeField,
    DecimalField,
    EnumField,
    FieldMappingUnion,
    IntegerField,
    RecordFieldMapping,
    StringField,
)
from astmio.logging import get_logger
from astmio.modern_records import ASTMBaseRecord

from .record_cache import RecordClassCache

log = get_logger(__name__)


class RecordFactory:
    """
    Enhanced and refactored factory for creating dynamic record classes.
    This version works with the new specialized field mapping classes.
    """

    @staticmethod
    def create_record_class(record_fields_config: RecordConfig) -> type:
        """Create dynamic Pydantic class from RecordConfig with caching."""
        return RecordClassCache.get_or_create(
            record_fields_config, RecordFactory._create_record_class_impl
        )

    @staticmethod
    def _create_record_class_impl(record_config: RecordConfig) -> type:
        """Internal implementation of the record class creation logic."""
        try:
            config_errors: list[str] = record_config.validate_record_config()
            if config_errors:
                log.warning(
                    f"Record config validation warnings for {record_config.record_type}: {config_errors}"
                )

            fields: Dict[str, tuple] = {}
            validators: Dict[str, Callable] = {}
            metadata = RecordMetadata(record_config=record_config)

            for record_field in record_config.fields:
                try:
                    RecordFactory._process_field_config(
                        record_field, fields, validators, metadata
                    )
                except Exception as e:
                    log.error(
                        f"Failed to process field '{getattr(record_field, 'field_name', 'UNKNOWN')}': {e}"
                    )
                    continue

            class_name = f"{record_config.record_type.value}Record"
            dynamic_class: ASTMBaseRecord = create_model(
                class_name,
                __base__=ASTMBaseRecord,
                **fields,
            )

            RecordFactory._attach_class_metadata(dynamic_class, metadata)

            for validator_name, validator_func in validators.items():
                setattr(dynamic_class, validator_name, validator_func)

            log.info(
                f"Successfully created {class_name} with {len(fields)} fields"
            )
            return dynamic_class

        except Exception as e:
            log.error(
                f"Failed to create record class for {record_config.record_type}: {e}"
            )
            raise ValidationError(f"Record class creation failed: {e}")

    @staticmethod
    def _process_field_config(
        record_field: FieldMappingUnion,
        fields: Dict[str, tuple],
        validators: Dict[str, Callable],
        metadata: RecordMetadata,
    ):
        """Processes a single field's configuration and updates all relevant collections."""
        field_name = record_field.field_name

        metadata.astm_field_mapping[field_name] = record_field.astm_position
        if record_field.required:
            metadata.required_fields.append(field_name)

        if isinstance(record_field, DateTimeField):
            metadata.datetime_formats[field_name] = record_field.format
        if isinstance(record_field, EnumField):
            metadata.enum_validations[field_name] = record_field.enum_values

        (
            pydantic_type,
            field_args,
        ) = RecordFactory._create_pydantic_field_definition(record_field)
        field_info = Field(**field_args)
        fields[field_name] = (pydantic_type, field_info)

        RecordFactory._attach_runtime_validators(record_field, validators)

    @staticmethod
    def _create_pydantic_field_definition(
        field_mapping: RecordFieldMapping,
    ) -> tuple[type, dict]:
        """
        Determines the correct Pydantic type AND field arguments for a field mapping.

        Returns:
            A tuple containing (pydantic_type, field_args_dictionary).
        """
        from datetime import datetime
        from decimal import Decimal
        from typing import List, Optional

        from pydantic import BaseModel, ConfigDict

        base_type = str
        if isinstance(field_mapping, DateTimeField):
            base_type = datetime
        elif isinstance(field_mapping, IntegerField):
            base_type = int
        elif isinstance(field_mapping, DecimalField):
            base_type = Decimal
        elif isinstance(field_mapping, ComponentField):
            if field_mapping.component_fields:
                component_annotations = {}
                component_fields_dict = {}
                for component_field in field_mapping.component_fields:
                    (
                        comp_type,
                        comp_args,
                    ) = RecordFactory._create_pydantic_field_definition(
                        component_field
                    )
                    component_annotations[
                        component_field.field_name
                    ] = comp_type
                    if "default" in comp_args:
                        component_fields_dict[
                            component_field.field_name
                        ] = comp_args["default"]

                model_name = f"{field_mapping.field_name.title()}Component"
                base_type = type(
                    model_name,
                    (BaseModel,),
                    {
                        "__annotations__": component_annotations,
                        **component_fields_dict,
                        "model_config": ConfigDict(
                            extra="forbid",
                            str_strip_whitespace=True,
                            validate_assignment=True,
                        ),
                    },
                )
            else:
                base_type = str

        field_args = {
            "description": f"ASTM position {field_mapping.astm_position} - {field_mapping.field_type}",
        }

        if field_mapping.default_value is not None:
            field_args["default"] = field_mapping.default_value

        if (
            isinstance(field_mapping, StringField)
            and field_mapping.max_length is not None
        ):
            field_args["max_length"] = field_mapping.max_length

        if (
            isinstance(field_mapping, IntegerField)
            and field_mapping.max_length is not None
        ):
            upper_bound = (10**field_mapping.max_length) - 1
            field_args["le"] = upper_bound

        final_type = base_type
        if field_mapping.repeated:
            final_type = List[base_type]
        elif (
            not field_mapping.required
            or field_mapping.default_value is not None
        ):
            final_type = Optional[base_type]

        return (final_type, field_args)

    @staticmethod
    def _attach_class_metadata(
        dynamic_class: Type[ASTMBaseRecord], metadata: RecordMetadata
    ):
        """Attaches the completed RecordMetadata object to the dynamic class."""
        dynamic_class._metadata = metadata

    @staticmethod
    def _attach_runtime_validators(
        field: RecordFieldMapping, pydantic_validators: Dict[str, Callable]
    ):
        """Attaches custom Pydantic validators based on the field's configuration."""
        if isinstance(field, EnumField) and field.enum_values:
            pydantic_validators[
                f"validate_{field.field_name}"
            ] = RecordFactory._create_enum_validator(
                field.field_name, field.enum_values
            )

        if isinstance(field, DateTimeField) and field.format:
            pydantic_validators[
                f"validate_{field.field_name}"
            ] = RecordFactory._create_datetime_validator(
                field.field_name, field.format
            )

        if isinstance(field, ConstantField) and field.default_value:
            pydantic_validators[
                f"validate_{field.field_name}"
            ] = RecordFactory._create_constant_validator(
                field.field_name, field.default_value
            )

    @staticmethod
    def _create_enum_validator(field_name: str, enum_values: List[str]):
        """Create a validator function for enum fields."""
        from pydantic import field_validator

        def _validator(cls, v):
            if v is not None and str(v) not in enum_values:
                raise ValueError(
                    f"Value must be one of: {enum_values}, got: {v}"
                )
            return v

        return field_validator(field_name, mode="before")(_validator)

    @staticmethod
    def _create_datetime_validator(field_name: str, format_str: str):
        """A factory that creates a Pydantic validator function for a specific format."""
        from pydantic import field_validator

        def _validator(value: Any) -> datetime:
            if isinstance(value, datetime):
                return value
            if not isinstance(value, str):
                raise ValueError("datetime field must be a string to parse")

            try:
                return datetime.strptime(value, format_str)
            except ValueError:
                raise ValueError(
                    f"must be a valid datetime string in the format '{format_str}'"
                )

        return field_validator(field_name, mode="before")(_validator)

    @staticmethod
    def _create_constant_validator(field_name: str, constant_value: Any):
        from pydantic import field_validator

        def _validator(cls, v):
            if v is not None and v != constant_value:
                raise ValueError(
                    f"Value must be '{constant_value}', but got '{v}'"
                )
            return v

        return field_validator(field_name, mode="before")(_validator)
