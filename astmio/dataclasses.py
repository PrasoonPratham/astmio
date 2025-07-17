# -*- coding: utf-8 -*-
#
# Modern dataclasses for ASTM protocol
#
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from pathlib import Path

from .enums import ConnectionState, ProcessingId


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
            f"messages_sent={self.messages_sent}, messages_received={self.messages_received})"
        )


@dataclass
class DeviceProfile:
    """Device-specific configuration profile."""
    
    name: str
    vendor: str
    model: str
    version: Optional[str] = None
    description: Optional[str] = None
    
    # Protocol settings
    encoding: str = "latin-1"
    chunk_size: Optional[int] = None
    timeout: float = 10.0
    
    # Field mappings and overrides
    field_mappings: Dict[str, str] = field(default_factory=dict)
    field_overrides: Dict[str, Any] = field(default_factory=dict)
    required_fields: List[str] = field(default_factory=list)
    
    # Protocol quirks and special handling
    quirks: List[str] = field(default_factory=list)
    custom_handlers: Dict[str, str] = field(default_factory=dict)
    
    # Validation rules
    validation_rules: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    def __str__(self) -> str:
        return f"DeviceProfile({self.vendor} {self.model})"
    
    def __repr__(self) -> str:
        return (
            f"DeviceProfile(name={self.name!r}, vendor={self.vendor!r}, "
            f"model={self.model!r}, version={self.version!r})"
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
        return f"MessageMetrics({self.message_type}, {status}, {self.processing_time_ms:.2f}ms)"
    
    def __repr__(self) -> str:
        return (
            f"MessageMetrics(timestamp={self.timestamp}, message_type={self.message_type!r}, "
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
    sensitive_fields: List[str] = field(default_factory=lambda: [
        "patient_id", "name", "address", "phone", "ssn"
    ])
    
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
    min_processing_time: float = float('inf')
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
        self.min_processing_time = min(self.min_processing_time, processing_time)
        self.max_processing_time = max(self.max_processing_time, processing_time)
    
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


# Export all dataclasses
__all__ = [
    "ConnectionConfig",
    "ConnectionStatus", 
    "DeviceProfile",
    "MessageMetrics",
    "ValidationResult",
    "SecurityConfig",
    "PerformanceMetrics"
]