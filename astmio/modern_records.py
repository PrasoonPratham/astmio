# -*- coding: utf-8 -*-
#
# Modern Pydantic-based ASTM record definitions
#
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Literal, Optional, Union, Type, ClassVar
from xml.etree.ElementTree import Element, SubElement, tostring
import csv
import io
import json
import logging
from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict, PrivateAttr
from pydantic.json_schema import JsonSchemaValue

from .enums import AbnormalFlag, CommentType, Priority, ResultStatus, Sex, TerminationCode, ProcessingId
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
    _astm_field_mapping: ClassVar[Dict[str, int]] = {}
    _required_fields: ClassVar[List[str]] = []
    _max_field_lengths: ClassVar[Dict[str, int]] = {}
    
    def __setattr__(self, name: str, value: Any) -> None:
        """Track updates for audit trail."""
        if hasattr(self, '__pydantic_private__') and name != '_updated_at':
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
                'indent': 2,
                'exclude_none': True,
                'by_alias': True,
            }
            default_kwargs.update(kwargs)
            
            return self.model_dump_json(**default_kwargs)
        except Exception as e:
            log.error("Failed to serialize to JSON", error=str(e), record_type=self.__class__.__name__)
            raise ValidationError(f"JSON serialization failed: {e}")
    
    def to_xml(self, root_name: Optional[str] = None, pretty: bool = True) -> str:
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
            root.set('record_type', getattr(self, 'record_type', 'Unknown'))
            if hasattr(self, '_created_at') and self._created_at:
                root.set('created_at', self._created_at.isoformat())
            
            def add_element(parent: Element, key: str, value: Any) -> None:
                """Recursively add elements with type preservation."""
                elem = SubElement(parent, key)
                
                if value is None:
                    elem.set('nil', 'true')
                elif isinstance(value, dict):
                    for k, v in value.items():
                        add_element(elem, k, v)
                elif isinstance(value, list):
                    elem.set('type', 'array')
                    for i, item in enumerate(value):
                        add_element(elem, f"item_{i}", item)
                elif isinstance(value, datetime):
                    elem.set('type', 'datetime')
                    elem.text = value.isoformat()
                elif isinstance(value, date):
                    elem.set('type', 'date')
                    elem.text = value.isoformat()
                elif isinstance(value, Decimal):
                    elem.set('type', 'decimal')
                    elem.text = str(value)
                elif isinstance(value, bool):
                    elem.set('type', 'boolean')
                    elem.text = str(value).lower()
                else:
                    elem.text = str(value)
            
            data = self.model_dump(exclude={'_created_at', '_updated_at', '_validation_errors', '_source'})
            for key, value in data.items():
                add_element(root, key, value)
            
            xml_str = tostring(root, encoding='unicode')
            
            if pretty:
                # Simple pretty printing
                import xml.dom.minidom
                dom = xml.dom.minidom.parseString(xml_str)
                xml_str = dom.toprettyxml(indent="  ")
                # Remove extra whitespace
                lines = [line for line in xml_str.split('\n') if line.strip()]
                xml_str = '\n'.join(lines)
            
            return xml_str
            
        except Exception as e:
            log.error("Failed to serialize to XML", error=str(e), record_type=self.__class__.__name__)
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
                exclude_fields.update({'_created_at', '_updated_at', '_validation_errors', '_source'})
            
            data = self.model_dump(exclude=exclude_fields)
            return [flatten_value(v) for v in data.values()]
            
        except Exception as e:
            log.error("Failed to convert to CSV row", error=str(e), record_type=self.__class__.__name__)
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
                headers = [h for h in headers if not h.startswith('_')]
            return headers
        except Exception as e:
            log.error("Failed to get CSV headers", error=str(e), record_type=cls.__name__)
            raise ValidationError(f"CSV headers generation failed: {e}")
    
    @classmethod
    def to_csv(cls, records: List['ASTMBaseRecord'], include_metadata: bool = False) -> str:
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
                    log.warning(f"Record type mismatch: expected {cls.__name__}, got {type(record).__name__}")
                    continue
                writer.writerow(record.to_csv_row(include_metadata=include_metadata))
            
            return output.getvalue()
            
        except Exception as e:
            log.error("Failed to convert to CSV", error=str(e), record_count=len(records))
            raise ValidationError(f"CSV conversion failed: {e}")
    
    def to_astm(self) -> List[Union[str, None]]:
        """
        Convert record to ASTM field list format.
        
        :return: List of ASTM fields
        """
        try:
            # Use field mapping if available
            if hasattr(self.__class__, '_astm_field_mapping') and self._astm_field_mapping:
                fields = [None] * (max(self._astm_field_mapping.values()) + 1)
                data = self.model_dump(exclude={'_created_at', '_updated_at', '_validation_errors', '_source'})
                
                for field_name, astm_index in self._astm_field_mapping.items():
                    if field_name in data:
                        value = data[field_name]
                        if isinstance(value, datetime):
                            fields[astm_index] = value.strftime('%Y%m%d%H%M%S')
                        elif isinstance(value, date):
                            fields[astm_index] = value.strftime('%Y%m%d')
                        elif isinstance(value, Decimal):
                            fields[astm_index] = str(value)
                        elif value is not None:
                            fields[astm_index] = str(value)
                
                return fields
            else:
                # Fallback: return model dump values
                data = self.model_dump(exclude={'_created_at', '_updated_at', '_validation_errors', '_source'})
                return list(data.values())
                
        except Exception as e:
            log.error("Failed to convert to ASTM format", error=str(e), record_type=self.__class__.__name__)
            raise ValidationError(f"ASTM conversion failed: {e}")
    
    @classmethod
    def from_astm(cls, fields: List[Union[str, None]], strict: bool = False) -> 'ASTMBaseRecord':
        """
        Create record from ASTM field list.
        
        :param fields: List of ASTM fields
        :param strict: Whether to use strict validation
        :return: Record instance
        """
        try:
            if not isinstance(fields, (list, tuple)):
                raise ValidationError(f"List or tuple expected, got {type(fields).__name__}")
            
            kwargs = {}
            
            # Use reverse field mapping if available
            if hasattr(cls, '_astm_field_mapping') and cls._astm_field_mapping:
                reverse_mapping = {v: k for k, v in cls._astm_field_mapping.items()}
                
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
                                if hasattr(field_type, '__origin__') and field_type.__origin__ is Union:
                                    args = field_type.__args__
                                    if len(args) == 2 and type(None) in args:
                                        field_type = args[0] if args[1] is type(None) else args[1]
                                
                                # Convert based on type
                                if field_type == datetime:
                                    if isinstance(field_value, str) and field_value:
                                        kwargs[field_name] = datetime.strptime(field_value, '%Y%m%d%H%M%S')
                                elif field_type == date:
                                    if isinstance(field_value, str) and field_value:
                                        kwargs[field_name] = datetime.strptime(field_value, '%Y%m%d').date()
                                elif field_type == Decimal:
                                    if isinstance(field_value, str) and field_value:
                                        kwargs[field_name] = Decimal(field_value)
                                elif field_type == int:
                                    if isinstance(field_value, str) and field_value:
                                        kwargs[field_name] = int(field_value)
                                else:
                                    kwargs[field_name] = field_value
                                    
                            except (ValueError, InvalidOperation) as e:
                                if strict:
                                    raise ValidationError(f"Failed to convert field {field_name}: {e}")
                                log.warning(f"Field conversion failed for {field_name}, using raw value", error=str(e))
                                kwargs[field_name] = field_value
            else:
                # Fallback: map fields by position to model fields
                field_names = list(cls.model_fields.keys())
                for i, field_value in enumerate(fields):
                    if i < len(field_names) and field_value is not None:
                        kwargs[field_names[i]] = field_value
            
            return cls(**kwargs)
            
        except Exception as e:
            log.error("Failed to create from ASTM fields", error=str(e), record_type=cls.__name__)
            if strict:
                raise ValidationError(f"ASTM field conversion failed: {e}")
            # Return minimal valid record
            return cls()
    
    def validate_record(self, strict: bool = False) -> List[str]:
        """
        Comprehensive record validation.
        
        :param strict: Whether to use strict validation
        :return: List of validation errors
        """
        errors = []
        
        try:
            # Check required fields
            if hasattr(self.__class__, '_required_fields'):
                for field_name in self._required_fields:
                    value = getattr(self, field_name, None)
                    if value is None or (isinstance(value, str) and not value.strip()):
                        errors.append(f"Required field '{field_name}' is missing or empty")
            
            # Check field lengths
            if hasattr(self.__class__, '_max_field_lengths'):
                for field_name, max_length in self._max_field_lengths.items():
                    value = getattr(self, field_name, None)
                    if isinstance(value, str) and len(value) > max_length:
                        error_msg = f"Field '{field_name}' exceeds maximum length of {max_length} characters"
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
            log.error("Validation process failed", error=str(e), record_type=self.__class__.__name__)
            return [f"Validation process failed: {e}"]
    
    def is_valid(self, strict: bool = False) -> bool:
        """
        Check if record is valid.
        
        :param strict: Whether to use strict validation
        :return: True if valid, False otherwise
        """
        return len(self.validate_record(strict=strict)) == 0
    
    @classmethod
    def save_to_file(cls, records: List['ASTMBaseRecord'], filepath: Union[str, Path], 
                     format: str = 'json', **kwargs) -> None:
        """
        Save records to file in specified format.
        
        :param records: List of records to save
        :param filepath: Path to save file
        :param format: Output format ('json', 'xml', 'csv')
        :param kwargs: Additional format-specific options
        """
        filepath = Path(filepath)
        
        try:
            if format.lower() == 'json':
                data = [record.model_dump(exclude={'_created_at', '_updated_at', '_validation_errors', '_source'}) 
                       for record in records]
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, default=str, **kwargs)
                    
            elif format.lower() == 'csv':
                csv_data = cls.to_csv(records, **kwargs)
                with open(filepath, 'w', encoding='utf-8', newline='') as f:
                    f.write(csv_data)
                    
            elif format.lower() == 'xml':
                # Create root element for multiple records
                root = Element('Records')
                root.set('count', str(len(records)))
                root.set('type', cls.__name__)
                
                for record in records:
                    record_xml = record.to_xml(**kwargs)
                    # Parse and append to root
                    import xml.etree.ElementTree as ET
                    record_elem = ET.fromstring(record_xml)
                    root.append(record_elem)
                
                xml_str = tostring(root, encoding='unicode')
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(xml_str)
                    
            else:
                raise ValidationError(f"Unsupported format: {format}")
                
            log.info(f"Saved {len(records)} records to {filepath} in {format} format")
            
        except Exception as e:
            log.error("Failed to save records to file", error=str(e), filepath=str(filepath), format=format)
            raise ValidationError(f"Failed to save records: {e}")
    
    @classmethod
    def load_from_file(cls, filepath: Union[str, Path], format: str = 'json', **kwargs) -> List['ASTMBaseRecord']:
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
            if format.lower() == 'json':
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if isinstance(data, list):
                    return [cls(**item) for item in data]
                else:
                    return [cls(**data)]
                    
            elif format.lower() == 'csv':
                records = []
                with open(filepath, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # Convert empty strings to None
                        cleaned_row = {k: v if v != '' else None for k, v in row.items()}
                        records.append(cls(**cleaned_row))
                return records
                
            else:
                raise ValidationError(f"Unsupported format: {format}")
                
        except Exception as e:
            log.error("Failed to load records from file", error=str(e), filepath=str(filepath), format=format)
            raise ValidationError(f"Failed to load records: {e}")


class ModernHeaderRecord(ASTMBaseRecord):
    """Enhanced ASTM Header Record with comprehensive validation and field mapping."""
    
    record_type: Literal["H"] = Field(default="H", description="Record type identifier")
    delimiter: str = Field(default=r"\^&", description="Field delimiter definition")
    message_id: Optional[str] = Field(default=None, max_length=20, description="Message control ID")
    password: Optional[str] = Field(default=None, max_length=20, description="Access password")
    sender: Optional[str] = Field(default=None, max_length=30, description="Sender name or ID")
    address: Optional[str] = Field(default=None, max_length=100, description="Sender address")
    reserved: Optional[str] = Field(default=None, description="Reserved field")
    phone: Optional[str] = Field(default=None, max_length=20, description="Sender phone number")
    capabilities: Optional[str] = Field(default=None, description="Sender capabilities")
    receiver: Optional[str] = Field(default=None, max_length=30, description="Receiver ID")
    comments: Optional[str] = Field(default=None, max_length=200, description="Comments")
    processing_id: ProcessingId = Field(default=ProcessingId.PRODUCTION, description="Processing ID")
    version: Optional[str] = Field(default=None, max_length=20, description="Version number")
    timestamp: datetime = Field(default_factory=datetime.now, description="Message timestamp")
    
    # ASTM field mapping (field_name -> ASTM position)
    _astm_field_mapping: ClassVar[Dict[str, int]] = {
        'record_type': 0,
        'delimiter': 1,
        'message_id': 2,
        'password': 3,
        'sender': 4,
        'address': 5,
        'reserved': 6,
        'phone': 7,
        'capabilities': 8,
        'receiver': 9,
        'comments': 10,
        'processing_id': 11,
        'version': 12,
        'timestamp': 13
    }
    
    _required_fields: ClassVar[List[str]] = ['record_type', 'processing_id']
    _max_field_lengths: ClassVar[Dict[str, int]] = {
        'message_id': 20,
        'password': 20,
        'sender': 30,
        'address': 100,
        'phone': 20,
        'receiver': 30,
        'comments': 200,
        'version': 20
    }
    
    @field_validator('processing_id')
    @classmethod
    def validate_processing_id(cls, v: Union[str, ProcessingId]) -> ProcessingId:
        if isinstance(v, str):
            try:
                return ProcessingId(v)
            except ValueError:
                raise ValueError("Processing ID must be P (Production), T (Test), or D (Debug)")
        return v
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v and not v.replace('-', '').replace('(', '').replace(')', '').replace(' ', '').replace('+', '').isdigit():
            raise ValueError("Phone number must contain only digits and formatting characters")
        return v
    
    @field_validator('timestamp')
    @classmethod
    def validate_timestamp(cls, v: datetime) -> datetime:
        if v > datetime.now():
            raise ValueError("Timestamp cannot be in the future")
        return v


# Backward compatibility alias
HeaderRecord = ModernHeaderRecord


class ModernPatientRecord(ASTMBaseRecord):
    """Enhanced ASTM Patient Record with comprehensive validation and field mapping."""
    
    record_type: Literal["P"] = Field(default="P", description="Record type identifier")
    sequence: int = Field(ge=1, le=99, description="Sequence number")
    practice_id: Optional[str] = Field(default=None, max_length=20, description="Practice assigned patient ID")
    laboratory_id: Optional[str] = Field(default=None, max_length=20, description="Laboratory assigned patient ID")
    patient_id: Optional[str] = Field(default=None, max_length=20, description="Patient ID")
    name: Optional[str] = Field(default=None, max_length=200, description="Patient name")
    maiden_name: Optional[str] = Field(default=None, max_length=200, description="Mother's maiden name")
    birthdate: Optional[date] = Field(default=None, description="Patient birthdate")
    sex: Optional[Sex] = Field(default=None, description="Patient sex")
    race: Optional[str] = Field(default=None, max_length=50, description="Patient race/ethnicity")
    address: Optional[str] = Field(default=None, max_length=200, description="Patient address")
    reserved: Optional[str] = Field(default=None, description="Reserved field")
    phone: Optional[str] = Field(default=None, max_length=20, description="Patient phone number")
    physician_id: Optional[str] = Field(default=None, max_length=20, description="Attending physician ID")
    special_1: Optional[str] = Field(default=None, max_length=50, description="Special field 1")
    special_2: Optional[str] = Field(default=None, max_length=50, description="Special field 2")
    height: Optional[Decimal] = Field(default=None, ge=0, description="Patient height in cm")
    weight: Optional[Decimal] = Field(default=None, ge=0, description="Patient weight in kg")
    diagnosis: Optional[str] = Field(default=None, max_length=200, description="Patient diagnosis")
    medication: Optional[str] = Field(default=None, max_length=200, description="Active medications")
    diet: Optional[str] = Field(default=None, max_length=100, description="Patient diet")
    
    # ASTM field mapping
    _astm_field_mapping: ClassVar[Dict[str, int]] = {
        'record_type': 0,
        'sequence': 1,
        'practice_id': 2,
        'laboratory_id': 3,
        'patient_id': 4,
        'name': 5,
        'maiden_name': 6,
        'birthdate': 7,
        'sex': 8,
        'race': 9,
        'address': 10,
        'reserved': 11,
        'phone': 12,
        'physician_id': 13,
        'special_1': 14,
        'special_2': 15,
        'height': 16,
        'weight': 17,
        'diagnosis': 18,
        'medication': 19,
        'diet': 20
    }
    
    _required_fields: ClassVar[List[str]] = ['record_type', 'sequence']
    _max_field_lengths: ClassVar[Dict[str, int]] = {
        'practice_id': 20,
        'laboratory_id': 20,
        'patient_id': 20,
        'name': 200,
        'maiden_name': 200,
        'race': 50,
        'address': 200,
        'phone': 20,
        'physician_id': 20,
        'special_1': 50,
        'special_2': 50,
        'diagnosis': 200,
        'medication': 200,
        'diet': 100
    }
    
    @field_validator('patient_id', 'practice_id', 'laboratory_id')
    @classmethod
    def validate_ids(cls, v: Optional[str]) -> Optional[str]:
        if v and not v.strip():
            raise ValueError("ID fields cannot be empty strings")
        return v
    
    @field_validator('birthdate')
    @classmethod
    def validate_birthdate(cls, v: Optional[date]) -> Optional[date]:
        if v and v > date.today():
            raise ValueError("Birthdate cannot be in the future")
        return v
    
    @field_validator('sex')
    @classmethod
    def validate_sex(cls, v: Union[str, Sex, None]) -> Optional[Sex]:
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return Sex(v.upper())
            except ValueError:
                raise ValueError("Sex must be M (Male), F (Female), or U (Unknown)")
        return v
    
    @field_validator('height', 'weight')
    @classmethod
    def validate_measurements(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("Height and weight must be non-negative")
        return v
    
    @model_validator(mode='after')
    def validate_patient_data(self) -> 'ModernPatientRecord':
        # Check that at least one identifier is present
        if not any([self.practice_id, self.laboratory_id, self.patient_id]):
            log.warning("Patient record has no identifiers")
        
        # Validate age if birthdate is provided
        if self.birthdate:
            age = (date.today() - self.birthdate).days // 365
            if age > 150:
                log.warning(f"Patient age appears unusually high: {age} years")
        
        return self


# Backward compatibility alias
PatientRecord = ModernPatientRecord


class ModernOrderRecord(ASTMBaseRecord):
    """Enhanced ASTM Order Record with comprehensive validation and field mapping."""
    
    record_type: Literal["O"] = Field(default="O", description="Record type identifier")
    sequence: int = Field(ge=1, le=99, description="Sequence number")
    sample_id: Optional[str] = Field(default=None, max_length=20, description="Specimen ID")
    instrument: Optional[str] = Field(default=None, max_length=20, description="Instrument specimen ID")
    test: Optional[str] = Field(default=None, max_length=50, description="Universal test ID")
    priority: Optional[Priority] = Field(default=None, description="Priority (S=STAT, A=ASAP, R=Routine)")
    created_at: Optional[datetime] = Field(default=None, description="Requested/ordered date/time")
    sampled_at: Optional[datetime] = Field(default=None, description="Specimen collection date/time")
    collected_at: Optional[datetime] = Field(default=None, description="Collection end time")
    volume: Optional[Decimal] = Field(default=None, ge=0, description="Collection volume in mL")
    collector: Optional[str] = Field(default=None, max_length=50, description="Collector ID")
    action_code: Optional[str] = Field(default=None, max_length=10, description="Action code")
    danger_code: Optional[str] = Field(default=None, max_length=10, description="Danger code")
    clinical_info: Optional[str] = Field(default=None, max_length=500, description="Relevant clinical information")
    delivered_at: Optional[datetime] = Field(default=None, description="Date/time specimen received")
    biomaterial: Optional[str] = Field(default=None, max_length=100, description="Specimen descriptor")
    physician: Optional[str] = Field(default=None, max_length=100, description="Ordering physician")
    physician_phone: Optional[str] = Field(default=None, max_length=20, description="Physician phone number")
    
    # ASTM field mapping
    _astm_field_mapping: ClassVar[Dict[str, int]] = {
        'record_type': 0,
        'sequence': 1,
        'sample_id': 2,
        'instrument': 3,
        'test': 4,
        'priority': 5,
        'created_at': 6,
        'sampled_at': 7,
        'collected_at': 8,
        'volume': 9,
        'collector': 10,
        'action_code': 11,
        'danger_code': 12,
        'clinical_info': 13,
        'delivered_at': 14,
        'biomaterial': 15,
        'physician': 16,
        'physician_phone': 17
    }
    
    _required_fields: ClassVar[List[str]] = ['record_type', 'sequence']
    _max_field_lengths: ClassVar[Dict[str, int]] = {
        'sample_id': 20,
        'instrument': 20,
        'test': 50,
        'collector': 50,
        'action_code': 10,
        'danger_code': 10,
        'clinical_info': 500,
        'biomaterial': 100,
        'physician': 100,
        'physician_phone': 20
    }
    
    @field_validator('priority')
    @classmethod
    def validate_priority(cls, v: Union[str, Priority, None]) -> Optional[Priority]:
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return Priority(v.upper())
            except ValueError:
                raise ValueError("Priority must be S (STAT), A (ASAP), or R (Routine)")
        return v
    
    @field_validator('volume')
    @classmethod
    def validate_volume(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError("Volume must be non-negative")
        if v is not None and v > 1000:  # Reasonable maximum
            log.warning(f"Volume appears unusually high: {v} mL")
        return v
    
    @model_validator(mode='after')
    def validate_dates(self) -> 'ModernOrderRecord':
        if self.created_at and self.sampled_at and self.created_at > self.sampled_at:
            raise ValueError("Order creation date cannot be after sample collection date")
        if self.sampled_at and self.collected_at and self.sampled_at > self.collected_at:
            raise ValueError("Sample collection start cannot be after collection end")
        if self.delivered_at and self.sampled_at and self.delivered_at < self.sampled_at:
            raise ValueError("Delivery date cannot be before sample collection date")
        return self


# Backward compatibility alias
OrderRecord = ModernOrderRecord


class ModernResultRecord(ASTMBaseRecord):
    """Enhanced ASTM Result Record with comprehensive validation and field mapping."""
    
    record_type: Literal["R"] = Field(default="R", description="Record type identifier")
    sequence: int = Field(ge=1, le=99, description="Sequence number")
    test: Optional[str] = Field(default=None, max_length=50, description="Universal test ID")
    value: Optional[Union[str, Decimal]] = Field(default=None, description="Data or measurement value")
    units: Optional[str] = Field(default=None, max_length=20, description="Units of measure")
    references: Optional[str] = Field(default=None, max_length=100, description="Reference ranges")
    abnormal_flag: Optional[AbnormalFlag] = Field(default=None, description="Result abnormal flags")
    abnormality_nature: Optional[str] = Field(default=None, max_length=50, description="Nature of abnormal testing")
    status: Optional[ResultStatus] = Field(default=None, description="Results status")
    norms_changed_at: Optional[datetime] = Field(default=None, description="Date of normative values change")
    operator: Optional[str] = Field(default=None, max_length=50, description="Operator identification")
    started_at: Optional[datetime] = Field(default=None, description="Date/time test started")
    completed_at: Optional[datetime] = Field(default=None, description="Date/time test completed")
    instrument: Optional[str] = Field(default=None, max_length=50, description="Instrument identification")
    
    # ASTM field mapping
    _astm_field_mapping: ClassVar[Dict[str, int]] = {
        'record_type': 0,
        'sequence': 1,
        'test': 2,
        'value': 3,
        'units': 4,
        'references': 5,
        'abnormal_flag': 6,
        'abnormality_nature': 7,
        'status': 8,
        'norms_changed_at': 9,
        'operator': 10,
        'started_at': 11,
        'completed_at': 12,
        'instrument': 13
    }
    
    _required_fields: ClassVar[List[str]] = ['record_type', 'sequence']
    _max_field_lengths: ClassVar[Dict[str, int]] = {
        'test': 50,
        'units': 20,
        'references': 100,
        'abnormality_nature': 50,
        'operator': 50,
        'instrument': 50
    }
    
    @field_validator('value')
    @classmethod
    def validate_value(cls, v: Optional[Union[str, Decimal]]) -> Optional[Union[str, Decimal]]:
        if isinstance(v, str) and v.strip() == "":
            return None
        # Try to convert numeric strings to Decimal for better precision
        if isinstance(v, str) and v:
            try:
                # Check if it's a numeric value
                if v.replace('.', '').replace('-', '').replace('+', '').isdigit():
                    return Decimal(v)
            except (ValueError, InvalidOperation):
                pass  # Keep as string if conversion fails
        return v
    
    @field_validator('abnormal_flag')
    @classmethod
    def validate_abnormal_flag(cls, v: Union[str, AbnormalFlag, None]) -> Optional[AbnormalFlag]:
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return AbnormalFlag(v.upper())
            except ValueError:
                raise ValueError(f"Invalid abnormal flag: {v}")
        return v
    
    @field_validator('status')
    @classmethod
    def validate_status(cls, v: Union[str, ResultStatus, None]) -> Optional[ResultStatus]:
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return ResultStatus(v.upper())
            except ValueError:
                raise ValueError(f"Invalid result status: {v}")
        return v
    
    @model_validator(mode='after')
    def validate_test_dates(self) -> 'ModernResultRecord':
        if self.started_at and self.completed_at and self.started_at > self.completed_at:
            raise ValueError("Test start time cannot be after completion time")
        
        # Validate that completed results have values
        if self.status == ResultStatus.FINAL and not self.value:
            log.warning("Final result has no value")
        
        # Check for reasonable test duration
        if self.started_at and self.completed_at:
            duration = self.completed_at - self.started_at
            if duration.total_seconds() > 86400:  # More than 24 hours
                log.warning(f"Test duration appears unusually long: {duration}")
        
        return self


# Backward compatibility alias
ResultRecord = ModernResultRecord


class ModernCommentRecord(ASTMBaseRecord):
    """Enhanced ASTM Comment Record with comprehensive validation and field mapping."""
    
    record_type: Literal["C"] = Field(default="C", description="Record type identifier")
    sequence: int = Field(ge=1, le=99, description="Sequence number")
    source: Optional[str] = Field(default=None, max_length=50, description="Comment source")
    data: Optional[str] = Field(default=None, max_length=1000, description="Comment text")
    comment_type: Optional[CommentType] = Field(default=None, description="Comment type")
    
    # ASTM field mapping
    _astm_field_mapping: ClassVar[Dict[str, int]] = {
        'record_type': 0,
        'sequence': 1,
        'source': 2,
        'data': 3,
        'comment_type': 4
    }
    
    _required_fields: ClassVar[List[str]] = ['record_type', 'sequence']
    _max_field_lengths: ClassVar[Dict[str, int]] = {
        'source': 50,
        'data': 1000
    }
    
    @field_validator('data')
    @classmethod
    def validate_data(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v.strip()) == 0:
            return None
        return v
    
    @field_validator('comment_type')
    @classmethod
    def validate_comment_type(cls, v: Union[str, CommentType, None]) -> Optional[CommentType]:
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return CommentType(v.upper())
            except ValueError:
                raise ValueError(f"Invalid comment type: {v}")
        return v


class ModernTerminatorRecord(ASTMBaseRecord):
    """Enhanced ASTM Terminator Record with comprehensive validation and field mapping."""
    
    record_type: Literal["L"] = Field(default="L", description="Record type identifier")
    sequence: int = Field(default=1, ge=1, le=99, description="Sequence number")
    termination_code: TerminationCode = Field(default=TerminationCode.NORMAL, description="Termination code")
    
    # ASTM field mapping
    _astm_field_mapping: ClassVar[Dict[str, int]] = {
        'record_type': 0,
        'sequence': 1,
        'termination_code': 2
    }
    
    _required_fields: ClassVar[List[str]] = ['record_type', 'sequence', 'termination_code']
    
    @field_validator('termination_code')
    @classmethod
    def validate_termination_code(cls, v: Union[str, TerminationCode]) -> TerminationCode:
        if isinstance(v, str):
            try:
                return TerminationCode(v.upper())
            except ValueError:
                raise ValueError(f"Invalid termination code: {v}")
        return v


# Backward compatibility aliases
CommentRecord = ModernCommentRecord
TerminatorRecord = ModernTerminatorRecord


# Export all record types
__all__ = [
    "ASTMBaseRecord",
    
    # Modern record types (preferred)
    "ModernHeaderRecord",
    "ModernPatientRecord", 
    "ModernOrderRecord",
    "ModernResultRecord",
    "ModernCommentRecord",
    "ModernTerminatorRecord",
    
    # Backward compatibility aliases
    "HeaderRecord", 
    "PatientRecord",
    "OrderRecord",
    "ResultRecord", 
    "CommentRecord",
    "TerminatorRecord"
]