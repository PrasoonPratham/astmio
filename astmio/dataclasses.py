#
# Modern Pydantic models for ASTM protocol
#
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, computed_field, model_validator

from astmio.constants import ENCODING

from .enums import ConnectionState, MessageType
from .logging import get_logger

log = get_logger(__name__)


class ConnectionStatus(BaseModel):
    """Status information for ASTM connections."""

    state: ConnectionState
    connected_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    bytes_sent: int = 0
    bytes_received: int = 0
    messages_sent: int = 0
    messages_received: int = 0
    errors: int = 0
    last_error: Optional[str] = None

    @computed_field
    @property
    def uptime(self) -> Optional[timedelta]:
        """Calculate connection uptime."""
        if self.connected_at:
            return datetime.now() - self.connected_at
        return None

    @computed_field
    @property
    def is_active(self) -> bool:
        """Check if connection is active."""
        return self.state in [ConnectionState.CONNECTED, ConnectionState.READY]

    def __str__(self) -> str:
        return f"ConnectionStatus(state={self.state}, uptime={self.uptime})"

    def __repr__(self) -> str:
        return (
            f"ConnectionStatus(state={self.state}, connected_at={self.connected_at}, "
            f"messages_sent={self.messages_sent}, "
            f"messages_received={self.messages_received})"
        )


class MessageMetrics(BaseModel):
    """Metrics for ASTM message processing."""

    timestamp: datetime = Field(default_factory=datetime.now)
    message_type: str = ""
    record_count: int = 0
    size_bytes: int = 0
    processing_time_ms: float = 0.0
    success: bool = True
    error_message: Optional[str] = None

    def __str__(self) -> str:
        status = "SUCCESS" if self.success else "ERROR"
        return (
            f"MessageMetrics({self.message_type}, {status}, "
            f"{self.processing_time_ms:.2f}ms)"
        )

    def __repr__(self) -> str:
        return (
            f"MessageMetrics(timestamp={self.timestamp}, "
            f"message_type={self.message_type!r}, "
            f"record_count={self.record_count}, success={self.success})"
        )


class ValidationResult(BaseModel):
    """Result of data validation operations."""

    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    field_errors: Dict[str, List[str]] = Field(default_factory=dict)

    def add_error(self, message: str, field: Optional[str] = None) -> None:
        """Add a validation error."""
        self.is_valid = False
        self.errors.append(message)
        if field:
            self.field_errors.setdefault(field, []).append(message)

    def add_warning(self, message: str) -> None:
        """Add a validation warning."""
        self.warnings.append(message)

    @computed_field
    @property
    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return len(self.errors) > 0

    @computed_field
    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return len(self.warnings) > 0

    def __str__(self) -> str:
        if self.is_valid:
            return "ValidationResult(VALID)"
        return f"ValidationResult(INVALID, {len(self.errors)} errors)"

    def __repr__(self) -> str:
        return (
            f"ValidationResult(is_valid={self.is_valid}, errors={len(self.errors)}, "
            f"warnings={len(self.warnings)})"
        )


class SecurityConfig(BaseModel):
    """Security configuration for ASTM connections."""

    enable_tls: bool = False
    cert_file: Optional[Path] = None
    key_file: Optional[Path] = None
    ca_file: Optional[Path] = None
    verify_certificates: bool = True

    # Data protection
    mask_sensitive_data: bool = True

    sensitive_fields: List[str] = Field(
        default_factory=lambda: [
            "patient_id",
            "name",
            "address",
            "phone",
            "ssn",
        ]
    )

    # Audit logging
    enable_audit_log: bool = False
    audit_log_file: Optional[Path] = None

    @model_validator(mode="after")
    def check_tls_files(self) -> "SecurityConfig":
        """Ensure certificate files are provided if TLS is enabled."""
        if self.enable_tls and (not self.cert_file or not self.key_file):
            raise ValueError(
                "If TLS is enabled, 'cert_file' and 'key_file' must be provided."
            )
        return self

    def __str__(self) -> str:
        tls_status = "TLS enabled" if self.enable_tls else "TLS disabled"
        return f"SecurityConfig({tls_status})"

    def __repr__(self) -> str:
        return (
            f"SecurityConfig(enable_tls={self.enable_tls}, "
            f"mask_sensitive_data={self.mask_sensitive_data})"
        )


class PerformanceMetrics(BaseModel):
    """Performance metrics for ASTM operations."""

    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None

    # Message statistics
    messages_processed: int = 0
    records_processed: int = 0
    bytes_processed: int = 0

    # Timing statistics
    min_processing_time: float = float("inf")
    max_processing_time: float = 0.0
    total_processing_time: float = 0.0

    # Error statistics
    errors: int = 0
    timeouts: int = 0
    retries: int = 0

    @computed_field
    @property
    def duration(self) -> timedelta:
        """Calculate total duration."""
        if self.end_time:
            return self.end_time - self.start_time
        return datetime.now() - self.start_time

    @computed_field
    @property
    def average_processing_time(self) -> float:
        """Calculate average processing time per message."""
        if self.messages_processed > 0:
            return self.total_processing_time / self.messages_processed
        return 0.0

    @computed_field
    @property
    def throughput_messages_per_second(self) -> float:
        """Calculate message throughput."""
        duration_secs = self.duration.total_seconds()
        if duration_secs > 0:
            return self.messages_processed / duration_secs
        return 0.0

    @computed_field
    @property
    def throughput_bytes_per_second(self) -> float:
        """Calculate byte throughput."""
        duration_secs = self.duration.total_seconds()
        if duration_secs > 0:
            return self.bytes_processed / duration_secs
        return 0.0

    def record_processing_time(self, processing_time: float) -> None:
        """Record a processing time measurement."""
        self.total_processing_time += processing_time
        self.min_processing_time = min(
            self.min_processing_time, processing_time
        )
        self.max_processing_time = max(
            self.max_processing_time, processing_time
        )

    def __str__(self) -> str:
        return (
            f"PerformanceMetrics({self.messages_processed} messages, "
            f"{self.throughput_messages_per_second:.2f} msg/s)"
        )

    def __repr__(self) -> str:
        return (
            f"PerformanceMetrics(messages_processed={self.messages_processed}, "
            f"duration={self.duration}, errors={self.errors})"
        )


ASTMRecord = List[Union[str, List[Any], None]]
ASTMData = List[ASTMRecord]


class DecodingResult(BaseModel):
    """Result of decoding operation with metadata."""

    data: ASTMData
    message_type: MessageType
    sequence_number: Optional[int] = None
    checksum: Optional[str] = None
    checksum_valid: bool = True
    warnings: List[str] = Field(default_factory=list)


class EncodingOptions(BaseModel):
    """Options for encoding ASTM messages."""

    encoding: str = ENCODING
    size: Optional[int] = None
    validate_checksum: bool = True
    strict_validation: bool = False
    include_metadata: bool = False


__all__ = [
    "ConnectionStatus",
    "MessageMetrics",
    "ValidationResult",
    "SecurityConfig",
    "PerformanceMetrics",
    "DecodingResult",
    "EncodingOptions",
]
