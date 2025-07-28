#
# Modern dataclasses for ASTM protocol
#
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from astmio.exceptions import ValidationError
from astmio.field_mapper import FieldMappingUnion, create_field_mapping

from .enums import CommunicationProtocol, ConnectionState, RecordType
from .logging import get_logger

log = get_logger(__name__)


@dataclass
class ConnectionConfig:
    """Configuration for ASTM connections."""

    host: str = "localhost"
    port: int = 15200
    timeout: float = 10.0
    encoding: str = "latin-1"
    chunk_size: Optional[int] = None
    max_retries: int = 3
    retry_delay: float = 1.0
    keepalive: bool = True
    device_profile: Optional[str] = None

    def __str__(self) -> str:
        return f"ConnectionConfig(host={self.host}, port={self.port})"

    def __repr__(self) -> str:
        return (
            f"ConnectionConfig(host={self.host!r}, port={self.port}, "
            f"timeout={self.timeout}, encoding={self.encoding!r})"
        )


@dataclass
class ConnectionStatus:
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

    @property
    def uptime(self) -> Optional[timedelta]:
        """Calculate connection uptime."""
        if self.connected_at:
            return datetime.now() - self.connected_at
        return None

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


@dataclass
class MessageMetrics:
    """Metrics for ASTM message processing."""

    timestamp: datetime = field(default_factory=datetime.now)
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


@dataclass
class ValidationResult:
    """Result of data validation operations."""

    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    field_errors: Dict[str, List[str]] = field(default_factory=dict)

    def add_error(self, message: str, field: Optional[str] = None) -> None:
        """Add a validation error."""
        self.is_valid = False
        self.errors.append(message)
        if field:
            if field not in self.field_errors:
                self.field_errors[field] = []
            self.field_errors[field].append(message)

    def add_warning(self, message: str) -> None:
        """Add a validation warning."""
        self.warnings.append(message)

    @property
    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return len(self.errors) > 0

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


@dataclass
class SecurityConfig:
    """Security configuration for ASTM connections."""

    enable_tls: bool = False
    cert_file: Optional[Path] = None
    key_file: Optional[Path] = None
    ca_file: Optional[Path] = None
    verify_certificates: bool = True

    # Data protection
    mask_sensitive_data: bool = True
    sensitive_fields: List[str] = field(
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

    def __str__(self) -> str:
        tls_status = "TLS enabled" if self.enable_tls else "TLS disabled"
        return f"SecurityConfig({tls_status})"

    def __repr__(self) -> str:
        return (
            f"SecurityConfig(enable_tls={self.enable_tls}, "
            f"mask_sensitive_data={self.mask_sensitive_data})"
        )


@dataclass
class PerformanceMetrics:
    """Performance metrics for ASTM operations."""

    start_time: datetime = field(default_factory=datetime.now)
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

    @property
    def duration(self) -> Optional[timedelta]:
        """Calculate total duration."""
        if self.end_time:
            return self.end_time - self.start_time
        return datetime.now() - self.start_time

    @property
    def average_processing_time(self) -> float:
        """Calculate average processing time per message."""
        if self.messages_processed > 0:
            return self.total_processing_time / self.messages_processed
        return 0.0

    @property
    def throughput_messages_per_second(self) -> float:
        """Calculate message throughput."""
        duration = self.duration
        if duration and duration.total_seconds() > 0:
            return self.messages_processed / duration.total_seconds()
        return 0.0

    @property
    def throughput_bytes_per_second(self) -> float:
        """Calculate byte throughput."""
        duration = self.duration
        if duration and duration.total_seconds() > 0:
            return self.bytes_processed / duration.total_seconds()
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


@dataclass
class SerialConfig:
    """Configuration for a Serial port connection."""

    port: str
    mode: Literal[CommunicationProtocol.SERIAL] = CommunicationProtocol.SERIAL
    baudrate: int = 9600
    databits: int = 8
    parity: Optional[str] = None
    stopbits: int = 1
    timeout: float = 10.0

    def __post_init__(self):
        """serial configuration validation."""
        if not self.port:
            raise ValidationError("Serial port name cannot be empty.")
        if self.baudrate <= 0:
            raise ValidationError("Baud rate must be positive.")

        valid_baudrates = [
            300,
            600,
            1200,
            2400,
            4800,
            9600,
            19200,
            38400,
            57600,
            115200,
        ]
        if self.baudrate not in valid_baudrates:
            log.warning(
                f"Unusual baud rate: {self.baudrate}. Common rates: {valid_baudrates}"
            )

        if self.databits not in [5, 6, 7, 8]:
            raise ValidationError(
                f"Invalid data bits: {self.databits}. Must be 5, 6, 7, or 8"
            )

        if self.stopbits not in [1, 2]:
            raise ValidationError(
                f"Invalid stop bits: {self.stopbits}. Must be 1 or 2"
            )

        if self.parity and self.parity.upper() not in [
            "NONE",
            "EVEN",
            "ODD",
            "MARK",
            "SPACE",
        ]:
            raise ValidationError(
                f"Invalid parity: {self.parity}. Must be None, EVEN, ODD, MARK, or SPACE"
            )


@dataclass
class BaseNetworkConfig:
    """Base configuration for IP-based network protocols."""

    host: str = "0.0.0.0"
    port: int = 15200
    timeout: float = 30.0
    encoding: str = "ascii"
    control_chars: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        """Validate common network configuration."""
        if not 1 <= self.port <= 65535:
            raise ValidationError(f"Invalid port number: {self.port}")

        if self.timeout <= 0:
            raise ValidationError(f"Timeout must be positive: {self.timeout}")


@dataclass
class TCPConfig(BaseNetworkConfig):
    """Configuration for TCP, UDP, or WebSocket connections."""

    mode: Literal[CommunicationProtocol.TCP] = CommunicationProtocol.TCP
    ssl_enabled: bool = False
    ssl_cert_path: Optional[str] = None
    ssl_key_path: Optional[str] = None
    max_connections: int = 10

    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.max_connections <= 0:
            raise ValidationError(
                f"Max connections must be positive: {self.max_connections}"
            )

        if self.ssl_enabled:
            if not self.ssl_cert_path or not self.ssl_key_path:
                raise ValidationError(
                    "SSL enabled but certificate or key path missing"
                )


@dataclass
class UDPConfig(BaseNetworkConfig):
    """Configuration for TCP, UDP, or WebSocket connections."""

    mode: Literal[CommunicationProtocol.UDP] = CommunicationProtocol.UDP


@dataclass
class FrameConfig:
    """Enhanced frame configuration with validation."""

    start: str = "STX"
    end: List[str] = field(default_factory=lambda: ["ETX", "CR", "LF"])
    checksum: bool = True
    max_length: int = 240
    sequence_numbers: bool = True
    chunking_enabled: bool = True
    chunk_size: int = 240

    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.max_length <= 0:
            raise ValidationError(
                f"Max length must be positive: {self.max_length}"
            )

        if self.chunking_enabled and self.chunk_size <= 0:
            raise ValidationError(
                f"Chunk size must be positive: {self.chunk_size}"
            )

        if self.chunk_size > self.max_length:
            log.warning(
                "Chunk size (%s) larger than max length (%s)",
                self.chunk_size,
                self.max_length,
            )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FrameConfig":
        """Create from dictionary with validation."""
        try:
            return cls(**data)
        except (ValueError, TypeError) as e:
            raise ValidationError(f"Invalid frame configuration: {e}")


@dataclass
class RecordConfig:
    """Configuration for a specific record type."""

    record_type: RecordType
    description: Optional[str] = None
    total_fields: Optional[int] = None
    repeated: bool = False
    fields: List[FieldMappingUnion] = field(default_factory=list)

    validation_rules: Dict[str, Any] = field(default_factory=dict)
    custom_parser: Optional[str] = None

    def __post_init__(self):
        """Validate record configuration."""
        positions = [f.astm_position for f in self.fields]
        if len(positions) != len(set(positions)):
            raise ValidationError(
                f"Duplicate ASTM positions in record {self.record_type}"
            )

        if (
            self.total_fields is not None
            and len(self.fields) > self.total_fields
        ):
            log.warning(
                f"Record {self.record_type} has {len(self.fields)} fields but total_fields is {self.total_fields}"
            )

    @classmethod
    def from_dict(
        cls, record_type: str, data: Dict[str, Any]
    ) -> "RecordConfig":
        try:
            fields = [
                create_field_mapping(field_data, i + 1)
                for i, field_data in enumerate(data.get("fields", []))
            ]

        except ValidationError as e:
            log.error(f"Failed to parse fields for {record_type}: {e}")
            raise

        return cls(
            record_type=RecordType(record_type.upper()),
            description=data.get("description"),
            total_fields=data.get("total_fields"),
            repeated=data.get("repeated", False),
            fields=fields,
            validation_rules=data.get("validation_rules", {}),
            custom_parser=data.get("custom_parser"),
        )

    def validate_record_config(self) -> List[str]:
        """
        record configuration validation.
        - Validates if the astm positions are sequential or not
        - Validates if there are any required fields or not
        - Validates if there are any duplicate fields or not
        - Validates if the present fields are equal to the expected fields
        """
        errors = []

        if not self.fields:
            errors.append(f"No fields present to validate : {self.fields}")

        # Validate field positions are sequential
        positions = [f.astm_position for f in self.fields]
        if len(positions) != len(set(positions)):
            seen = set()
            duplicates = {p for p in positions if p in seen or seen.add(p)}
            errors.append(
                f"Duplicate ASTM positions found: {sorted(duplicates)}"
            )

        # Validate required fields
        required_fields = [f for f in self.fields if f.required]
        if not required_fields:
            errors.append("No required fields defined")

        # Validate field names are unique
        field_names = [f.field_name for f in self.fields]
        duplicates = {
            name for name in field_names if field_names.count(name) > 1
        }
        if duplicates:
            errors.append(f"Duplicate field names: {duplicates}")

        # Validates total_fields
        if not self.total_fields or not self.fields:
            errors.append("fields are not present for comparision")
        elif len(self.fields) != self.total_fields:
            errors.append("total_fields and record fields don't match")

        return errors


@dataclass
class ParserConfig:
    """Parser configuration with customization options."""

    strict_mode: bool = False
    ignore_checksum_errors: bool = False
    auto_sequence_correction: bool = True
    max_message_size: int = 64000
    custom_handlers: Dict[str, str] = field(default_factory=dict)
    preprocessing_rules: List[str] = field(default_factory=list)

    # Field mapping and separator configuration
    patient_name_field: Optional[str] = None
    sample_id_field: Optional[str] = None
    test_separator: str = "\\"
    component_separator: str = "^"

    def __post_init__(self):
        """Validate parser configuration."""
        if self.max_message_size <= 0:
            raise ValidationError(
                f"Max message size must be positive: {self.max_message_size}"
            )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ParserConfig":
        """Create from dictionary with validation."""
        try:
            return cls(**data)
        except (ValueError, TypeError) as e:
            raise ValidationError(f"Invalid parser configuration: {e}")


# Export all dataclasses
__all__ = [
    "ConnectionConfig",
    "ConnectionStatus",
    "MessageMetrics",
    "ValidationResult",
    "SecurityConfig",
    "PerformanceMetrics",
    "SerialConfig",
    "BaseNetworkConfig",
    "TCPConfig",
    "UDPConfig",
    "FrameConfig",
    "RecordConfig",
    "ParserConfig",
]
