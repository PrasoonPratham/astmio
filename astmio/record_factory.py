from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Dict, List, Type

from pydantic import (
    BeforeValidator,
    Field,
    create_model,
)

from .field_mapper import (
    ComponentField,
    DateTimeField,
    DecimalField,
    IgnoredField,
    IntegerField,
    RecordFieldMapping,
    StringField,
)
from .logging import get_logger
from .models import RecordConfig
from .modern_records import ASTMBaseRecord, RecordMetadata

log = get_logger(__name__)

_record_class_cache: Dict[int, Type[ASTMBaseRecord]] = {}


class RecordFactory:
    """
    Creates dynamic Pydantic models from validated RecordConfig objects.
    These generated models are used to parse live ASTM data at runtime.
    """

    @staticmethod
    def create_record_class(
        record_type: str, config: RecordConfig
    ) -> Type[ASTMBaseRecord]:
        """
        Public-facing method to create a dynamic Pydantic class from RecordConfig.
        This method uses a cache to avoid re-creating classes unnecessarily.
        """
        cache_key = hash(config.model_dump_json())

        if cache_key in _record_class_cache:
            log.debug(f"Returning cached record class for '{record_type}'.")
            return _record_class_cache[cache_key]

        # If not in cache, call the internal implementation to build it.
        log.debug(f"Cache miss for '{record_type}'. Creating new record class.")
        new_class = RecordFactory._create_record_class_impl(record_type, config)
        _record_class_cache[cache_key] = new_class
        return new_class

    @staticmethod
    def _create_record_class_impl(
        record_type: str, config: RecordConfig
    ) -> Type[ASTMBaseRecord]:
        """
        Internal implementation of the record class creation logic.
        This contains the clean, Pydantic-based logic from our new approach.
        """
        class_name = f"{record_type.upper()}Record"
        fields: Dict[str, Any] = {}
        metadata = RecordMetadata(source_config=config)

        sub_fields = []
        if isinstance(config, RecordConfig):
            sub_fields = config.fields
        elif isinstance(config, ComponentField):
            sub_fields = config.component_fields

        for field_config in sub_fields:
            field_name = field_config.field_name

            # Populate metadata
            metadata.position_to_name[field_config.astm_position] = field_name
            metadata.name_to_position[field_name] = field_config.astm_position
            metadata.field_types[field_name] = field_config.field_type

            if isinstance(field_config, IgnoredField):
                continue

            if field_config.required:
                metadata.required_fields.append(field_name)

            (
                pydantic_type,
                field_args,
            ) = RecordFactory._get_pydantic_type_and_args(field_config)
            fields[field_name] = (pydantic_type, Field(**field_args))

        dynamic_class = create_model(
            class_name, __base__=ASTMBaseRecord, **fields
        )
        dynamic_class._astm_metadata = metadata
        log.debug(f"Successfully created dynamic record class '{class_name}'.")
        return dynamic_class

    @staticmethod
    def _get_pydantic_type_and_args(
        field: RecordFieldMapping,
    ) -> tuple[Type, Dict[str, Any]]:
        pydantic_type: Type = str
        field_args: Dict[str, Any] = {"default": None}

        # Determine base type based on the validated config model
        if isinstance(field, IntegerField):
            pydantic_type = int
        elif isinstance(field, DecimalField):
            pydantic_type = Decimal
        elif isinstance(field, DateTimeField):

            def parse_datetime_with_format(value: Any) -> datetime:
                if isinstance(value, datetime):
                    return value
                if not isinstance(value, str):
                    raise ValueError("datetime field must be a string to parse")

                cleaned_value = value.strip()
                try:
                    return datetime.strptime(cleaned_value, field.format)
                except ValueError:
                    raise ValueError(
                        f"Value '{value}' does not match format '{field.format}'"
                    )

            pydantic_type = Annotated[
                datetime, BeforeValidator(parse_datetime_with_format)
            ]
        elif isinstance(field, ComponentField):
            component_class_name = (
                f"{field.field_name.title().replace('_', '')}Component"
            )
            pydantic_type = RecordFactory.create_record_class(
                component_class_name, field
            )

        # Handle optionality and defaults
        if field.required and field.default_value is None:
            field_args["default"] = ...
        if field.default_value is not None:
            field_args["default"] = field.default_value

        # Handle repeated fields
        if field.repeated:
            pydantic_type = List[pydantic_type]
            if "default" not in field_args or field_args["default"] is None:
                field_args["default_factory"] = list

        if field.max_length:
            if isinstance(field, StringField):
                field_args["max_length"] = field.max_length
            elif isinstance(field, IntegerField):
                field_args["le"] = (10**field.max_length) - 1

        return pydantic_type, field_args
