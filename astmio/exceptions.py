# -*- coding: utf-8 -*-
#
# Enhanced exception system for ASTM library
#
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


@dataclass
class ErrorContext:
    """Context information for errors."""

    operation: str
    timestamp: datetime = field(default_factory=datetime.now)
    data: Dict[str, Any] = field(default_factory=dict)
    suggestions: List[str] = field(default_factory=list)
    recoverable: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/serialization."""
        return {
            "operation": self.operation,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "suggestions": self.suggestions,
            "recoverable": self.recoverable,
        }


class BaseASTMError(Exception):
    """Enhanced base ASTM error with context and recovery information."""

    def __init__(
        self,
        message: str,
        context: Optional[ErrorContext] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.message = message
        self.context = context or ErrorContext(operation="unknown")
        self.cause = cause
        self.timestamp = datetime.now()

        # Log the error
        log.error(
            "ASTM Error occurred: %s - %s (context: %s, cause: %s)",
            self.__class__.__name__,
            message,
            self.context.to_dict(),
            str(cause) if cause else None,
        )

    def __str__(self) -> str:
        """Enhanced string representation with context."""
        parts = [self.message]

        if self.context.operation != "unknown":
            parts.append(f"Operation: {self.context.operation}")

        if self.context.suggestions:
            parts.append(f"Suggestions: {', '.join(self.context.suggestions)}")

        if self.cause:
            parts.append(f"Caused by: {self.cause}")

        return " | ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for serialization."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "context": self.context.to_dict(),
            "cause": str(self.cause) if self.cause else None,
            "recoverable": self.context.recoverable,
        }


class InvalidState(BaseASTMError):
    """Raised for invalid ASTM handler state."""

    def __init__(
        self,
        message: str,
        current_state: Optional[str] = None,
        expected_state: Optional[str] = None,
        **kwargs,
    ):
        context = ErrorContext(
            operation="state_validation",
            data={"current_state": current_state, "expected_state": expected_state},
            suggestions=[
                "Check connection state before operation",
                "Ensure proper initialization sequence",
                "Verify protocol compliance",
            ],
            recoverable=True,
        )
        super().__init__(message, context, **kwargs)


class NotAccepted(BaseASTMError):
    """Raised when received data is not acceptable."""

    def __init__(
        self,
        message: str,
        data: Optional[Any] = None,
        reason: Optional[str] = None,
        **kwargs,
    ):
        context = ErrorContext(
            operation="data_validation",
            data={"rejected_data": str(data) if data else None, "reason": reason},
            suggestions=[
                "Verify data format compliance",
                "Check field validation rules",
                "Review protocol specifications",
            ],
            recoverable=True,
        )
        super().__init__(message, context, **kwargs)


class ProtocolError(BaseASTMError):
    """Raised for errors related to the ASTM protocol."""

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        protocol_data: Optional[bytes] = None,
        **kwargs,
    ):
        context = ErrorContext(
            operation="protocol_processing",
            data={
                "error_code": code,
                "protocol_data_length": len(protocol_data) if protocol_data else None,
                "protocol_data_preview": (
                    protocol_data[:100].hex() if protocol_data else None
                ),
            },
            suggestions=[
                "Verify message framing (STX/ETX)",
                "Check checksum calculation",
                "Validate sequence numbers",
                "Review protocol compliance",
            ],
            recoverable=True,
        )
        super().__init__(message, context, **kwargs)


class ValidationError(BaseASTMError):
    """Raised for data validation errors."""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        constraint: Optional[str] = None,
        **kwargs,
    ):
        context = ErrorContext(
            operation="data_validation",
            data={
                "field": field,
                "value": str(value) if value is not None else None,
                "constraint": constraint,
            },
            suggestions=[
                "Check field format requirements",
                "Verify value constraints",
                "Review field validation rules",
                "Check for required fields",
            ],
            recoverable=True,
        )
        super().__init__(message, context, **kwargs)


class ConnectionError(BaseASTMError):
    """Raised for network connection errors."""

    def __init__(
        self,
        message: str,
        address: Optional[str] = None,
        port: Optional[int] = None,
        timeout: Optional[float] = None,
        **kwargs,
    ):
        context = ErrorContext(
            operation="connection_management",
            data={"address": address, "port": port, "timeout": timeout},
            suggestions=[
                "Verify network connectivity",
                "Check firewall settings",
                "Confirm target address and port",
                "Increase connection timeout",
                "Check service availability",
            ],
            recoverable=True,
        )
        super().__init__(message, context, **kwargs)


class TimeoutError(ConnectionError):
    """Raised for connection timeout errors."""

    def __init__(
        self,
        operation: str,
        timeout_value: float,
        **kwargs,
    ):
        super().__init__(
            operation=f"timeout_{operation}",
            data={"timeout_value": timeout_value, "operation_type": operation},
            message=f"Operation '{operation}' timed out after {timeout_value} seconds",
            **kwargs,
        )


class ParseError(BaseASTMError):
    """Raised for parsing errors."""

    def __init__(
        self,
        message: str,
        data: Optional[bytes] = None,
        position: Optional[int] = None,
        expected: Optional[str] = None,
        **kwargs,
    ):
        context = ErrorContext(
            operation="data_parsing",
            data={
                "data_length": len(data) if data else None,
                "data_preview": data[:50].hex() if data else None,
                "error_position": position,
                "expected_format": expected,
            },
            suggestions=[
                "Verify data format",
                "Check encoding settings",
                "Review message structure",
                "Validate control characters",
                "Check for data corruption",
            ],
            recoverable=True,
        )
        super().__init__(message, context, **kwargs)


class ChecksumError(ProtocolError):
    """Raised for checksum validation errors."""

    def __init__(
        self,
        message: str,
        expected: Optional[str] = None,
        calculated: Optional[str] = None,
        data: Optional[bytes] = None,
        **kwargs,
    ):
        context = ErrorContext(
            operation="checksum_validation",
            data={
                "expected_checksum": expected,
                "calculated_checksum": calculated,
                "data_length": len(data) if data else None,
            },
            suggestions=[
                "Verify data integrity",
                "Check transmission errors",
                "Review checksum algorithm",
                "Validate message framing",
                "Check for data corruption",
            ],
            recoverable=False,  # Usually indicates data corruption
        )
        super().__init__(message, context, **kwargs)


class ConfigurationError(BaseASTMError):
    """Raised for configuration errors."""

    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        config_value: Optional[Any] = None,
        **kwargs,
    ):
        context = ErrorContext(
            operation="configuration_validation",
            data={
                "config_key": config_key,
                "config_value": str(config_value) if config_value is not None else None,
            },
            suggestions=[
                "Check configuration file format",
                "Verify required settings",
                "Review default values",
                "Validate configuration schema",
                "Check file permissions",
            ],
            recoverable=True,
        )
        super().__init__(message, context, **kwargs)


class ResourceError(BaseASTMError):
    """Raised for resource-related errors."""

    def __init__(
        self,
        message: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        **kwargs,
    ):
        context = ErrorContext(
            operation="resource_management",
            data={"resource_type": resource_type, "resource_id": resource_id},
            suggestions=[
                "Check resource availability",
                "Verify resource limits",
                "Review resource allocation",
                "Check system resources",
                "Consider resource cleanup",
            ],
            recoverable=True,
        )
        super().__init__(message, context, **kwargs)


class SecurityError(BaseASTMError):
    """Raised for security-related errors."""

    def __init__(self, message: str, security_context: Optional[str] = None, **kwargs):
        context = ErrorContext(
            operation="security_validation",
            data={"security_context": security_context},
            suggestions=[
                "Verify authentication credentials",
                "Check authorization permissions",
                "Review security policies",
                "Validate certificates",
                "Check encryption settings",
            ],
            recoverable=False,  # Security errors are usually not recoverable
        )
        super().__init__(message, context, **kwargs)


class Rejected(BaseASTMError):
    """Raised after unsuccessful attempts to send data (receiver sends NAK reply)."""

    def __init__(
        self,
        message: str,
        attempts: Optional[int] = None,
        last_response: Optional[str] = None,
        **kwargs,
    ):
        context = ErrorContext(
            operation="data_transmission",
            data={"attempts": attempts, "last_response": last_response},
            suggestions=[
                "Check data format",
                "Verify protocol compliance",
                "Review transmission parameters",
                "Check receiver status",
                "Consider retry with different settings",
            ],
            recoverable=True,
        )
        super().__init__(message, context, **kwargs)


# Error recovery utilities
class ErrorRecovery:
    """Utilities for error recovery and retry logic."""

    @staticmethod
    def is_recoverable(error: BaseASTMError) -> bool:
        """Check if an error is recoverable."""
        return error.context.recoverable

    @staticmethod
    def get_retry_delay(
        attempt: int, base_delay: float = 1.0, max_delay: float = 30.0
    ) -> float:
        """Calculate exponential backoff delay."""
        delay = base_delay * (2**attempt)
        return min(delay, max_delay)

    @staticmethod
    def should_retry(error: BaseASTMError, attempt: int, max_attempts: int = 3) -> bool:
        """Determine if operation should be retried."""
        if attempt >= max_attempts:
            return False

        if not ErrorRecovery.is_recoverable(error):
            return False

        # Don't retry security errors
        if isinstance(error, SecurityError):
            return False

        # Don't retry checksum errors (usually data corruption)
        if isinstance(error, ChecksumError):
            return False

        return True

    @staticmethod
    def log_retry(error: BaseASTMError, attempt: int, delay: float) -> None:
        """Log retry attempt."""
        log.warning(
            "Retrying operation after error",
            error_type=error.__class__.__name__,
            attempt=attempt,
            delay=delay,
            operation=error.context.operation,
        )


# Error aggregation for multiple errors
class AggregateError(BaseASTMError):
    """Aggregates multiple errors into a single exception."""

    def __init__(self, message: str, errors: List[BaseASTMError], **kwargs):
        self.errors = errors

        context = ErrorContext(
            operation="aggregate_operation",
            data={
                "error_count": len(errors),
                "error_types": [type(e).__name__ for e in errors],
            },
            suggestions=[
                "Review individual error details",
                "Check for common error patterns",
                "Consider batch operation handling",
            ],
            recoverable=any(e.context.recoverable for e in errors),
        )
        super().__init__(message, context, **kwargs)

    def __str__(self) -> str:
        """String representation including all sub-errors."""
        parts = [super().__str__()]
        parts.append(f"Contains {len(self.errors)} errors:")
        for i, error in enumerate(self.errors, 1):
            parts.append(f"  {i}. {error}")
        return "\n".join(parts)


# Export all exception classes
__all__ = [
    "BaseASTMError",
    "InvalidState",
    "NotAccepted",
    "ProtocolError",
    "ValidationError",
    "ConnectionError",
    "TimeoutError",
    "ParseError",
    "ChecksumError",
    "ConfigurationError",
    "ResourceError",
    "SecurityError",
    "Rejected",
    "AggregateError",
    "ErrorContext",
    "ErrorRecovery",
]
