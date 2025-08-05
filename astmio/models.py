from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from .exceptions import ConfigurationError
from .field_mapper import DiscriminatedField
from .logging import get_logger

log = get_logger(__name__)

# --- Pydantic Models ---


class BaseNetworkConfig(BaseModel):
    """Base configuration for network-based transports (TCP/UDP)."""

    host: str = "0.0.0.0"
    port: int = Field(default=15200, ge=1, le=65535)
    timeout: float = Field(default=30.0, gt=0)
    encoding: str = "ascii"
    control_chars: Dict[str, int] = Field(default_factory=dict)


class SerialConfig(BaseModel):
    """Configuration for serial port communication."""

    port: str
    mode: Literal["serial"] = "serial"
    baudrate: int = 9600
    databits: int = 8
    parity: Optional[str] = None
    stopbits: int = 1
    timeout: float = Field(default=10.0, gt=0)

    @field_validator("port")
    def validate_port(cls, v: str) -> str:
        if not v:
            raise ConfigurationError(
                message="Serial port name cannot be empty.",
                config_key="port",
                config_value=v,
            )
        return v

    @field_validator("baudrate")
    def validate_baudrate(cls, v: int) -> int:
        standard_rates = {
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
        }
        if v not in standard_rates:
            log.warning(
                f"Unusual baud rate configured: {v}. Ensure the device supports it."
            )
        return v

    @field_validator("databits")
    def validate_databits(cls, v: int) -> int:
        if v not in [5, 6, 7, 8]:
            raise ConfigurationError(
                message="Invalid data bits. Must be one of: 5, 6, 7, 8.",
                config_key="databits",
                config_value=v,
            )
        return v

    @field_validator("stopbits")
    def validate_stopbits(cls, v: int) -> int:
        if v not in [1, 2]:
            raise ConfigurationError(
                message="Invalid stop bits. Must be 1 or 2.",
                config_key="stopbits",
                config_value=v,
            )
        return v

    @field_validator("parity")
    def validate_parity(cls, v: Optional[str]) -> Optional[str]:
        valid = {"NONE", "EVEN", "ODD", "MARK", "SPACE"}
        if v and v.upper() not in valid:
            raise ConfigurationError(
                message=f"Invalid parity '{v}'. Must be one of: {sorted(valid)}.",
                config_key="parity",
                config_value=v,
            )
        return v.upper() if v else v


class TCPConfig(BaseNetworkConfig):
    """Configuration for TCP transport, including SSL options."""

    mode: Literal["tcp"] = "tcp"
    ssl_enabled: bool = False
    ssl_cert_path: Optional[str] = None
    ssl_key_path: Optional[str] = None
    max_connections: int = Field(default=10, gt=0)

    @model_validator(mode="before")
    def validate_tcp_config(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate TCP-specific settings, like SSL dependencies."""
        if data.get("ssl_enabled"):
            if not data.get("ssl_cert_path"):
                raise ConfigurationError(
                    message="When SSL is enabled, 'ssl_cert_path' is required.",
                    config_key="ssl_cert_path",
                    config_value=data.get("ssl_cert_path"),
                )
            if not data.get("ssl_key_path"):
                raise ConfigurationError(
                    message="When SSL is enabled, 'ssl_key_path' is required.",
                    config_key="ssl_key_path",
                    config_value=data.get("ssl_key_path"),
                )
        return data


class UDPConfig(BaseNetworkConfig):
    """Configuration for UDP transport."""

    mode: Literal["udp"] = "udp"


class FrameConfig(BaseModel):
    """
    Configuration for message framing, validation, and chunking.
    Inherits from Pydantic's BaseModel for automatic validation and parsing.
    """

    start: str = "STX"
    end: List[str] = ["ETX", "CR", "LF"]
    checksum: bool = True
    max_length: int = 240
    sequence_numbers: bool = True
    chunking_enabled: bool = True
    chunk_size: int = 240

    @model_validator(mode="after")
    def validate_frame_logic(self) -> "FrameConfig":
        # Validate that max_length is a positive integer
        if self.max_length <= 0:
            raise ConfigurationError(
                message="Frame 'max_length' must be a positive integer.",
                config_key="max_length",
                config_value=self.max_length,
            )

        # If chunking is on, validate the chunk_size
        if self.chunking_enabled and self.chunk_size <= 0:
            raise ConfigurationError(
                message="When chunking is enabled, 'chunk_size' must be greater than zero.",
                config_key="chunk_size",
                config_value=self.chunk_size,
            )

        # Log a warning if chunk_size exceeds max_length
        if self.chunking_enabled and self.chunk_size > self.max_length:
            log.warning(
                "Configuration warning: chunk_size (%s) is larger than max_length (%s). "
                "This may result in messages that can never be sent in a single chunk.",
                self.chunk_size,
                self.max_length,
            )

        return self


class ConnectionConfig(BaseModel):
    """
    Configuration for ASTM connections, implemented as a Pydantic model
    for robust validation.
    """

    host: str = "localhost"
    port: int = Field(default=15200, ge=1, le=65535)
    timeout: float = Field(default=10.0, gt=0)
    encoding: str = "latin-1"
    chunk_size: Optional[int] = None
    max_retries: int = Field(default=3, ge=0)
    retry_delay: float = Field(default=1.0, gt=0)
    keepalive: bool = True
    device_profile: Optional[str] = None

    @field_validator("chunk_size")
    def validate_chunk_size(cls, v: Optional[int]) -> Optional[int]:
        """Ensure chunk_size is a positive integer if it is not None."""
        if v is not None and v <= 0:
            raise ValueError(
                "chunk_size must be a positive integer if provided."
            )
        return v

    def __str__(self) -> str:
        return f"ConnectionConfig(host={self.host}, port={self.port})"

    def __repr__(self) -> str:
        return (
            f"ConnectionConfig(host={self.host!r}, port={self.port}, "
            f"timeout={self.timeout}, encoding={self.encoding!r})"
        )


class RecordConfig(BaseModel):
    """
    A Pydantic model that validates the configuration for a single record type
    (e.g., the 'H' record or 'P' record) from the YAML file.
    """

    record_type: str
    description: Optional[str] = None
    total_fields: Optional[int] = Field(None, gt=0)
    repeated: bool = False
    fields: List[DiscriminatedField] = []
    validation_rules: Dict[str, Any] = {}
    custom_parser: Optional[str] = None

    @field_validator("fields", mode="before")
    @classmethod
    def assign_astm_positions(
        cls, fields_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Pre-processes the raw field data before validation.
        1. Renames the 'type' key from YAML to 'field_type' for our discriminator.
        2. Injects the astm_position based on list order.
        """
        for i, field in enumerate(fields_data):
            if isinstance(field, dict):
                if "type" in field:
                    field["field_type"] = field.pop("type")

                # Logic from your existing validator to set position
                if "astm_position" not in field:
                    field["astm_position"] = i + 1
        return fields_data

    @model_validator(mode="after")
    def validate_record_logic(self) -> "RecordConfig":
        """
        A post-validator that checks for consistency and correctness across the
        entire list of fields after they have all been individually parsed.
        """
        # Check for duplicate field names within this record
        names = [field.field_name for field in self.fields]
        if len(names) != len(set(names)):
            seen = set()
            duplicates = {n for n in names if n in seen or seen.add(n)}
            raise ConfigurationError(
                message=f"Duplicate field names found in record configuration: {sorted(duplicates)}",
                config_key="fields",
            )

        # Check that there is at least one field marked as required
        if not any(field.required for field in self.fields):
            log.warning(
                "Configuration warning: Record type '%s' has no fields marked as 'required: true'. "
                "This may make the record difficult to use for data validation.",
                self.record_type,
            )

        # Check if total_fields (if specified) matches the actual number of fields
        if (
            self.total_fields is not None
            and len(self.fields) != self.total_fields
        ):
            log.warning(
                "Configuration mismatch: The record is defined with 'total_fields' of %s, "
                "but contains %s fields.",
                self.total_fields,
                len(self.fields),
            )

        return self


__all__ = [
    "BaseNetworkConfig",
    "SerialConfig",
    "TCPConfig",
    "UDPConfig",
    "FrameConfig",
    "ConnectionConfig",
    "RecordConfig",
]
