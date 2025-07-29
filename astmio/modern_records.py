#
# Modern Pydantic-based ASTM record definitions
#
import csv
import io
import json
import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, ClassVar, List, Optional, Union
from xml.etree.ElementTree import Element, SubElement, tostring

from pydantic import (
    BaseModel,
    ConfigDict,
    PrivateAttr,
)

from astmio.dataclasses import RecordMetadata

from .exceptions import ValidationError

log = logging.getLogger(__name__)


class ASTMBaseRecord(BaseModel):
    """
    Enhanced base class for all ASTM records with comprehensive functionality.

    Features:
    - Robust validation and error handling
    - Multiple serialization formats (JSON, XML, CSV, ASTM)
    - Metadata tracking and audit trails
    - Type-safe field access
    - Performance optimizations
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
        frozen=False,  # Allow modification for practical use
        arbitrary_types_allowed=True,
        use_enum_values=True,
    )

    # Metadata fields (private attributes)
    _created_at: Optional[datetime] = PrivateAttr(default_factory=datetime.now)
    _updated_at: Optional[datetime] = PrivateAttr(default=None)
    _validation_errors: List[str] = PrivateAttr(default_factory=list)
    _source: Optional[str] = PrivateAttr(default=None)

    # Class-level configuration
    _metadata: ClassVar[Optional[RecordMetadata]] = None

    def __setattr__(self, name: str, value: Any) -> None:
        """Track updates for audit trail."""
        if hasattr(self, "__pydantic_private__") and name != "_updated_at":
            self._updated_at = datetime.now()
        super().__setattr__(name, value)

    def to_json(self, **kwargs) -> str:
        """
        Convert record to JSON string with enhanced options.

        :param kwargs: Additional options for JSON serialization
        :return: JSON string representation
        """
        try:
            # Default options for better JSON output
            default_kwargs = {
                "indent": 2,
                "exclude_none": True,
                "by_alias": True,
            }
            default_kwargs.update(kwargs)

            return self.model_dump_json(**default_kwargs)
        except Exception as e:
            log.error(
                "Failed to serialize to JSON",
                error=str(e),
                record_type=self.__class__.__name__,
            )
            raise ValidationError(f"JSON serialization failed: {e}")

    def to_xml(
        self, root_name: Optional[str] = None, pretty: bool = True
    ) -> str:
        """
        Convert record to XML string with enhanced formatting.

        :param root_name: Custom root element name
        :param pretty: Whether to format XML for readability
        :return: XML string representation
        """
        try:
            root_name = root_name or self.__class__.__name__
            root = Element(root_name)

            # Add metadata attributes
            root.set("record_type", getattr(self, "record_type", "Unknown"))
            if hasattr(self, "_created_at") and self._created_at:
                root.set("created_at", self._created_at.isoformat())

            def add_element(parent: Element, key: str, value: Any) -> None:
                """Recursively add elements with type preservation."""
                elem = SubElement(parent, key)

                if value is None:
                    elem.set("nil", "true")
                elif isinstance(value, dict):
                    for k, v in value.items():
                        add_element(elem, k, v)
                elif isinstance(value, list):
                    elem.set("type", "array")
                    for i, item in enumerate(value):
                        add_element(elem, f"item_{i}", item)
                elif isinstance(value, datetime):
                    elem.set("type", "datetime")
                    elem.text = value.isoformat()
                elif isinstance(value, date):
                    elem.set("type", "date")
                    elem.text = value.isoformat()
                elif isinstance(value, Decimal):
                    elem.set("type", "decimal")
                    elem.text = str(value)
                elif isinstance(value, bool):
                    elem.set("type", "boolean")
                    elem.text = str(value).lower()
                else:
                    elem.text = str(value)

            data = self.model_dump(
                exclude={
                    "_created_at",
                    "_updated_at",
                    "_validation_errors",
                    "_source",
                }
            )
            for key, value in data.items():
                add_element(root, key, value)

            xml_str = tostring(root, encoding="unicode")

            if pretty:
                # Simple pretty printing
                import xml.dom.minidom

                dom = xml.dom.minidom.parseString(xml_str)
                xml_str = dom.toprettyxml(indent="  ")
                # Remove extra whitespace
                lines = [line for line in xml_str.split("\n") if line.strip()]
                xml_str = "\n".join(lines)

            return xml_str

        except Exception as e:
            log.error(
                "Failed to serialize to XML",
                error=str(e),
                record_type=self.__class__.__name__,
            )
            raise ValidationError(f"XML serialization failed: {e}")

    def to_csv_row(self, include_metadata: bool = False) -> List[str]:
        """
        Convert record to CSV row with enhanced options.

        :param include_metadata: Whether to include metadata fields
        :return: List of string values for CSV
        """
        try:

            def flatten_value(value: Any) -> str:
                """Convert any value to string for CSV."""
                if value is None:
                    return ""
                elif isinstance(value, (dict, list)):
                    return json.dumps(value, default=str)
                elif isinstance(value, datetime):
                    return value.isoformat()
                elif isinstance(value, date):
                    return value.isoformat()
                elif isinstance(value, Decimal):
                    return str(value)
                elif isinstance(value, bool):
                    return str(value).lower()
                else:
                    return str(value)

            exclude_fields = set()
            if not include_metadata:
                exclude_fields.update(
                    {
                        "_created_at",
                        "_updated_at",
                        "_validation_errors",
                        "_source",
                    }
                )

            data = self.model_dump(exclude=exclude_fields)
            return [flatten_value(v) for v in data.values()]

        except Exception as e:
            log.error(
                "Failed to convert to CSV row",
                error=str(e),
                record_type=self.__class__.__name__,
            )
            raise ValidationError(f"CSV row conversion failed: {e}")

    @classmethod
    def csv_headers(cls, include_metadata: bool = False) -> List[str]:
        """
        Get CSV headers for this record type.

        :param include_metadata: Whether to include metadata fields
        :return: List of field names
        """
        try:
            headers = list(cls.model_fields.keys())
            if not include_metadata:
                headers = [h for h in headers if not h.startswith("_")]
            return headers
        except Exception as e:
            log.error(
                "Failed to get CSV headers",
                error=str(e),
                record_type=cls.__name__,
            )
            raise ValidationError(f"CSV headers generation failed: {e}")

    @classmethod
    def to_csv(
        cls, records: List["ASTMBaseRecord"], include_metadata: bool = False
    ) -> str:
        """
        Convert list of records to CSV string with enhanced options.

        :param records: List of records to convert
        :param include_metadata: Whether to include metadata fields
        :return: CSV string
        """
        if not records:
            return ""

        try:
            output = io.StringIO()
            writer = csv.writer(output)

            # Write headers
            writer.writerow(cls.csv_headers(include_metadata=include_metadata))

            # Write data rows
            for record in records:
                if not isinstance(record, cls):
                    log.warning(
                        "Record type mismatch: expected %s, got %s",
                        cls.__name__,
                        type(record).__name__,
                    )
                    continue
                writer.writerow(
                    record.to_csv_row(include_metadata=include_metadata)
                )

            return output.getvalue()

        except Exception as e:
            log.error(
                "Failed to convert to CSV",
                error=str(e),
                record_count=len(records),
            )
            raise ValidationError(f"CSV conversion failed: {e}")

    def to_astm(self) -> List[Union[str, None]]:
        """
        Convert record to ASTM field list format.

        :return: List of ASTM fields
        """
        try:
            # Use field mapping if available
            if (
                hasattr(self.__class__, "_astm_field_mapping")
                and self._astm_field_mapping
            ):
                fields = [None] * (max(self._astm_field_mapping.values()) + 1)
                data = self.model_dump(
                    exclude={
                        "_created_at",
                        "_updated_at",
                        "_validation_errors",
                        "_source",
                    }
                )

                for field_name, astm_index in self._astm_field_mapping.items():
                    if field_name in data:
                        value = data[field_name]
                        if isinstance(value, datetime):
                            fields[astm_index] = value.strftime("%Y%m%d%H%M%S")
                        elif isinstance(value, date):
                            fields[astm_index] = value.strftime("%Y%m%d")
                        elif isinstance(value, Decimal):
                            fields[astm_index] = str(value)
                        elif value is not None:
                            fields[astm_index] = str(value)

                return fields
            else:
                # Fallback: return model dump values
                data = self.model_dump(
                    exclude={
                        "_created_at",
                        "_updated_at",
                        "_validation_errors",
                        "_source",
                    }
                )
                return list(data.values())

        except Exception as e:
            log.error(
                "Failed to convert to ASTM format",
                error=str(e),
                record_type=self.__class__.__name__,
            )
            raise ValidationError(f"ASTM conversion failed: {e}")

    @classmethod
    def from_astm(
        cls, fields: List[Union[str, None]], strict: bool = False
    ) -> "ASTMBaseRecord":
        """
        Create record from ASTM field list.

        :param fields: List of ASTM fields
        :param strict: Whether to use strict validation
        :return: Record instance
        """
        try:
            if not isinstance(fields, (list, tuple)):
                raise ValidationError(
                    f"List or tuple expected, got {type(fields).__name__}"
                )

            kwargs = {}

            # Use reverse field mapping if available
            if hasattr(cls, "_astm_field_mapping") and cls._astm_field_mapping:
                reverse_mapping = {
                    v: k for k, v in cls._astm_field_mapping.items()
                }

                for i, field_value in enumerate(fields):
                    if i in reverse_mapping and field_value is not None:
                        field_name = reverse_mapping[i]

                        # Type conversion based on field type
                        field_info = cls.model_fields.get(field_name)
                        if field_info:
                            try:
                                # Get the field type
                                field_type = field_info.annotation

                                # Handle Optional types
                                if (
                                    hasattr(field_type, "__origin__")
                                    and field_type.__origin__ is Union
                                ):
                                    args = field_type.__args__
                                    if len(args) == 2 and type(None) in args:
                                        field_type = (
                                            args[0]
                                            if args[1] is type(None)
                                            else args[1]
                                        )

                                # Convert based on type
                                if field_type == datetime:
                                    if (
                                        isinstance(field_value, str)
                                        and field_value
                                    ):
                                        kwargs[field_name] = datetime.strptime(
                                            field_value, "%Y%m%d%H%M%S"
                                        )
                                elif field_type == date:
                                    if (
                                        isinstance(field_value, str)
                                        and field_value
                                    ):
                                        kwargs[field_name] = datetime.strptime(
                                            field_value, "%Y%m%d"
                                        ).date()
                                elif field_type == Decimal:
                                    if (
                                        isinstance(field_value, str)
                                        and field_value
                                    ):
                                        kwargs[field_name] = Decimal(
                                            field_value
                                        )
                                elif field_type is int:
                                    if (
                                        isinstance(field_value, str)
                                        and field_value
                                    ):
                                        kwargs[field_name] = int(field_value)
                                else:
                                    kwargs[field_name] = field_value

                            except (ValueError, InvalidOperation) as e:
                                if strict:
                                    raise ValidationError(
                                        f"Failed to convert field {field_name}: {e}"
                                    )
                                log.warning(
                                    "Field conversion failed for %s, using raw value",
                                    field_name,
                                    error=str(e),
                                )
                                kwargs[field_name] = field_value
            else:
                # Fallback: map fields by position to model fields
                field_names = list(cls.model_fields.keys())
                for i, field_value in enumerate(fields):
                    if i < len(field_names) and field_value is not None:
                        kwargs[field_names[i]] = field_value

            return cls(**kwargs)

        except Exception as e:
            log.error(
                "Failed to create from ASTM fields",
                error=str(e),
                record_type=cls.__name__,
            )
            if strict:
                raise ValidationError(f"ASTM field conversion failed: {e}")
            # Return minimal valid record
            return cls()

    def is_valid(self, strict: bool = False) -> bool:
        """
        Check if record is valid.

        :param strict: Whether to use strict validation
        :return: True if valid, False otherwise
        """
        return len(self.validate_record(strict=strict)) == 0

    def validate_record(self, strict: bool = False) -> List[str]:
        """
        Comprehensive record validation.

        :param strict: Whether to use strict validation
        :return: List of validation errors
        """
        errors = []

        try:
            # Check required fields
            if hasattr(self.__class__, "_required_fields"):
                for field_name in self._required_fields:
                    value = getattr(self, field_name, None)
                    if value is None or (
                        isinstance(value, str) and not value.strip()
                    ):
                        errors.append(
                            f"Required field '{field_name}' is missing or empty"
                        )

            # Check field lengths
            if hasattr(self.__class__, "_max_field_lengths"):
                for field_name, max_length in self._max_field_lengths.items():
                    value = getattr(self, field_name, None)
                    if isinstance(value, str) and len(value) > max_length:
                        error_msg = f"Field '{field_name}' exceeds max length of {max_length}"
                        if strict:
                            errors.append(error_msg)
                        else:
                            log.warning(error_msg)

            # Validate using Pydantic
            try:
                self.model_validate(self.model_dump())
            except Exception as e:
                errors.append(f"Model validation failed: {e}")

            # Store validation errors
            self._validation_errors = errors

            return errors

        except Exception as e:
            log.error(
                "Validation process failed",
                error=str(e),
                record_type=self.__class__.__name__,
            )
            return [f"Validation process failed: {e}"]

    @classmethod
    def save_to_file(
        cls,
        records: List["ASTMBaseRecord"],
        filepath: Union[str, Path],
        format: str = "json",
        **kwargs,
    ) -> None:
        """
        Save records to file in specified format.

        :param records: List of records to save
        :param filepath: Path to save file
        :param format: Output format ('json', 'xml', 'csv')
        :param kwargs: Additional format-specific options
        """
        filepath = Path(filepath)

        try:
            if format.lower() == "json":
                data = [
                    record.model_dump(
                        exclude={
                            "_created_at",
                            "_updated_at",
                            "_validation_errors",
                            "_source",
                        }
                    )
                    for record in records
                ]
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, default=str, **kwargs)

            elif format.lower() == "csv":
                csv_data = cls.to_csv(records, **kwargs)
                with open(filepath, "w", encoding="utf-8", newline="") as f:
                    f.write(csv_data)

            elif format.lower() == "xml":
                # Create root element for multiple records
                root = Element("Records")
                root.set("count", str(len(records)))
                root.set("type", cls.__name__)

                for record in records:
                    record_xml = record.to_xml(**kwargs)
                    # Parse and append to root
                    import xml.etree.ElementTree as ET

                    record_elem = ET.fromstring(record_xml)
                    root.append(record_elem)

                xml_str = tostring(root, encoding="unicode")
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(xml_str)

            else:
                raise ValidationError(f"Unsupported format: {format}")

            log.info(
                f"Saved {len(records)} records to {filepath} in {format} format"
            )

        except Exception as e:
            log.error(
                "Failed to save records to file",
                error=str(e),
                filepath=str(filepath),
                format=format,
            )
            raise ValidationError(f"Failed to save records: {e}")

    @classmethod
    def load_from_file(
        cls, filepath: Union[str, Path], format: str = "json", **kwargs
    ) -> List["ASTMBaseRecord"]:
        """
        Load records from file.

        :param filepath: Path to load file
        :param format: Input format ('json', 'csv')
        :param kwargs: Additional format-specific options
        :return: List of loaded records
        """
        filepath = Path(filepath)

        if not filepath.exists():
            raise ValidationError(f"File not found: {filepath}")

        try:
            if format.lower() == "json":
                with open(filepath, encoding="utf-8") as f:
                    data = json.load(f)

                if isinstance(data, list):
                    return [cls(**item) for item in data]
                else:
                    return [cls(**data)]

            elif format.lower() == "csv":
                records = []
                with open(filepath, encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # Convert empty strings to None
                        cleaned_row = {
                            k: v if v != "" else None for k, v in row.items()
                        }
                        records.append(cls(**cleaned_row))
                return records

            else:
                raise ValidationError(f"Unsupported format: {format}")

        except Exception as e:
            log.error(
                "Failed to load records from file",
                error=str(e),
                filepath=str(filepath),
                format=format,
            )
            raise ValidationError(f"Failed to load records: {e}")


__all__ = ["ASTMBaseRecord"]
