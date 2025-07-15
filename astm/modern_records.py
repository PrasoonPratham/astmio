# -*- coding: utf-8 -*-
#
# Modern Pydantic-based ASTM record definitions
#
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional, Union
from xml.etree.ElementTree import Element, SubElement, tostring
import csv
import io
import json

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic.json_schema import JsonSchemaValue


class ASTMBaseRecord(BaseModel):
    """Base class for all ASTM records with common functionality."""
    
    model_config = {
        "str_strip_whitespace": True,
        "validate_assignment": True,
        "extra": "forbid",
    }
    
    def to_json(self, **kwargs) -> str:
        """Convert record to JSON string."""
        return self.model_dump_json(**kwargs)
    
    def to_xml(self, root_name: Optional[str] = None) -> str:
        """Convert record to XML string."""
        root_name = root_name or self.__class__.__name__
        root = Element(root_name)
        
        def add_element(parent: Element, key: str, value: Any) -> None:
            elem = SubElement(parent, key)
            if isinstance(value, dict):
                for k, v in value.items():
                    add_element(elem, k, v)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    add_element(elem, f"item_{i}", item)
            else:
                elem.text = str(value) if value is not None else ""
        
        for key, value in self.model_dump().items():
            add_element(root, key, value)
        
        return tostring(root, encoding='unicode')
    
    def to_csv_row(self) -> List[str]:
        """Convert record to CSV row."""
        def flatten_value(value: Any) -> str:
            if isinstance(value, (dict, list)):
                return json.dumps(value)
            return str(value) if value is not None else ""
        
        return [flatten_value(v) for v in self.model_dump().values()]
    
    @classmethod
    def csv_headers(cls) -> List[str]:
        """Get CSV headers for this record type."""
        return list(cls.model_fields.keys())
    
    @classmethod
    def to_csv(cls, records: List['ASTMBaseRecord']) -> str:
        """Convert list of records to CSV string."""
        if not records:
            return ""
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow(cls.csv_headers())
        
        # Write data rows
        for record in records:
            writer.writerow(record.to_csv_row())
        
        return output.getvalue()


class HeaderRecord(ASTMBaseRecord):
    """Modern ASTM Header Record with comprehensive validation."""
    
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
    processing_id: str = Field(default="P", description="Processing ID")
    version: Optional[str] = Field(default=None, max_length=20, description="Version number")
    timestamp: datetime = Field(default_factory=datetime.now, description="Message timestamp")
    
    @field_validator('processing_id')
    @classmethod
    def validate_processing_id(cls, v: str) -> str:
        if v not in ['P', 'T', 'D']:
            raise ValueError("Processing ID must be P (Production), T (Test), or D (Debug)")
        return v
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v and not v.replace('-', '').replace('(', '').replace(')', '').replace(' ', '').isdigit():
            raise ValueError("Phone number must contain only digits and formatting characters")
        return v


class PatientRecord(ASTMBaseRecord):
    """Modern ASTM Patient Record with comprehensive validation."""
    
    record_type: Literal["P"] = Field(default="P", description="Record type identifier")
    sequence: int = Field(ge=1, le=99, description="Sequence number")
    practice_id: Optional[str] = Field(default=None, max_length=20, description="Practice assigned patient ID")
    laboratory_id: Optional[str] = Field(default=None, max_length=20, description="Laboratory assigned patient ID")
    patient_id: Optional[str] = Field(default=None, max_length=20, description="Patient ID")
    name: Optional[str] = Field(default=None, max_length=200, description="Patient name")
    maiden_name: Optional[str] = Field(default=None, max_length=200, description="Mother's maiden name")
    birthdate: Optional[datetime] = Field(default=None, description="Patient birthdate")
    sex: Optional[Literal["M", "F", "U"]] = Field(default=None, description="Patient sex")
    race: Optional[str] = Field(default=None, max_length=50, description="Patient race/ethnicity")
    address: Optional[str] = Field(default=None, max_length=200, description="Patient address")
    reserved: Optional[str] = Field(default=None, description="Reserved field")
    phone: Optional[str] = Field(default=None, max_length=20, description="Patient phone number")
    physician_id: Optional[str] = Field(default=None, max_length=20, description="Attending physician ID")
    special_1: Optional[str] = Field(default=None, max_length=50, description="Special field 1")
    special_2: Optional[str] = Field(default=None, max_length=50, description="Special field 2")
    height: Optional[Decimal] = Field(default=None, ge=0, description="Patient height")
    weight: Optional[Decimal] = Field(default=None, ge=0, description="Patient weight")
    diagnosis: Optional[str] = Field(default=None, max_length=200, description="Patient diagnosis")
    medication: Optional[str] = Field(default=None, max_length=200, description="Active medications")
    diet: Optional[str] = Field(default=None, max_length=100, description="Patient diet")
    
    @field_validator('patient_id', 'practice_id', 'laboratory_id')
    @classmethod
    def validate_ids(cls, v: Optional[str]) -> Optional[str]:
        if v and not v.strip():
            raise ValueError("ID fields cannot be empty strings")
        return v
    
    @field_validator('birthdate')
    @classmethod
    def validate_birthdate(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v and v > datetime.now():
            raise ValueError("Birthdate cannot be in the future")
        return v


class OrderRecord(ASTMBaseRecord):
    """Modern ASTM Order Record with comprehensive validation."""
    
    record_type: Literal["O"] = Field(default="O", description="Record type identifier")
    sequence: int = Field(ge=1, le=99, description="Sequence number")
    sample_id: Optional[str] = Field(default=None, max_length=20, description="Specimen ID")
    instrument: Optional[str] = Field(default=None, max_length=20, description="Instrument specimen ID")
    test: Optional[str] = Field(default=None, max_length=50, description="Universal test ID")
    priority: Optional[Literal["S", "A", "R"]] = Field(default=None, description="Priority (S=STAT, A=ASAP, R=Routine)")
    created_at: Optional[datetime] = Field(default=None, description="Requested/ordered date/time")
    sampled_at: Optional[datetime] = Field(default=None, description="Specimen collection date/time")
    collected_at: Optional[datetime] = Field(default=None, description="Collection end time")
    volume: Optional[Decimal] = Field(default=None, ge=0, description="Collection volume")
    collector: Optional[str] = Field(default=None, max_length=50, description="Collector ID")
    action_code: Optional[str] = Field(default=None, max_length=10, description="Action code")
    danger_code: Optional[str] = Field(default=None, max_length=10, description="Danger code")
    clinical_info: Optional[str] = Field(default=None, max_length=500, description="Relevant clinical information")
    delivered_at: Optional[datetime] = Field(default=None, description="Date/time specimen received")
    biomaterial: Optional[str] = Field(default=None, max_length=100, description="Specimen descriptor")
    physician: Optional[str] = Field(default=None, max_length=100, description="Ordering physician")
    physician_phone: Optional[str] = Field(default=None, max_length=20, description="Physician phone number")
    
    @model_validator(mode='after')
    def validate_dates(self) -> 'OrderRecord':
        if self.created_at and self.sampled_at and self.created_at > self.sampled_at:
            raise ValueError("Order creation date cannot be after sample collection date")
        if self.sampled_at and self.collected_at and self.sampled_at > self.collected_at:
            raise ValueError("Sample collection start cannot be after collection end")
        return self


class ResultRecord(ASTMBaseRecord):
    """Modern ASTM Result Record with comprehensive validation."""
    
    record_type: Literal["R"] = Field(default="R", description="Record type identifier")
    sequence: int = Field(ge=1, le=99, description="Sequence number")
    test: Optional[str] = Field(default=None, max_length=50, description="Universal test ID")
    value: Optional[Union[str, Decimal]] = Field(default=None, description="Data or measurement value")
    units: Optional[str] = Field(default=None, max_length=20, description="Units of measure")
    references: Optional[str] = Field(default=None, max_length=100, description="Reference ranges")
    abnormal_flag: Optional[Literal["N", "A", "H", "L", "HH", "LL"]] = Field(
        default=None, description="Result abnormal flags"
    )
    abnormality_nature: Optional[str] = Field(default=None, max_length=50, description="Nature of abnormal testing")
    status: Optional[Literal["F", "P", "C", "X"]] = Field(
        default=None, description="Results status (F=Final, P=Preliminary, C=Corrected, X=Cannot report)"
    )
    norms_changed_at: Optional[datetime] = Field(default=None, description="Date of normative values change")
    operator: Optional[str] = Field(default=None, max_length=50, description="Operator identification")
    started_at: Optional[datetime] = Field(default=None, description="Date/time test started")
    completed_at: Optional[datetime] = Field(default=None, description="Date/time test completed")
    instrument: Optional[str] = Field(default=None, max_length=50, description="Instrument identification")
    
    @field_validator('value')
    @classmethod
    def validate_value(cls, v: Optional[Union[str, Decimal]]) -> Optional[Union[str, Decimal]]:
        if isinstance(v, str) and v.strip() == "":
            return None
        return v
    
    @model_validator(mode='after')
    def validate_test_dates(self) -> 'ResultRecord':
        if self.started_at and self.completed_at and self.started_at > self.completed_at:
            raise ValueError("Test start time cannot be after completion time")
        return self


class CommentRecord(ASTMBaseRecord):
    """Modern ASTM Comment Record with comprehensive validation."""
    
    record_type: Literal["C"] = Field(default="C", description="Record type identifier")
    sequence: int = Field(ge=1, le=99, description="Sequence number")
    source: Optional[str] = Field(default=None, max_length=50, description="Comment source")
    data: Optional[str] = Field(default=None, max_length=1000, description="Comment text")
    comment_type: Optional[Literal["G", "I", "P"]] = Field(
        default=None, description="Comment type (G=Generic, I=Instrument, P=Patient)"
    )
    
    @field_validator('data')
    @classmethod
    def validate_data(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v.strip()) == 0:
            return None
        return v


class TerminatorRecord(ASTMBaseRecord):
    """Modern ASTM Terminator Record with comprehensive validation."""
    
    record_type: Literal["L"] = Field(default="L", description="Record type identifier")
    sequence: int = Field(default=1, ge=1, le=99, description="Sequence number")
    termination_code: Literal["N", "T", "Q"] = Field(
        default="N", description="Termination code (N=Normal, T=Terminated, Q=Query)"
    )


# Export all record types
__all__ = [
    "ASTMBaseRecord",
    "HeaderRecord", 
    "PatientRecord",
    "OrderRecord",
    "ResultRecord", 
    "CommentRecord",
    "TerminatorRecord"
]