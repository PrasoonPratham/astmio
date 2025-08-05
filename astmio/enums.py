#
# Modern enums for ASTM protocol
#
from enum import Enum, IntEnum


class RecordType(str, Enum):
    """ASTM record type identifiers."""

    HEADER = "H"
    PATIENT = "P"
    ORDER = "O"
    RESULT = "R"
    COMMENT = "C"
    SCIENTIFIC = "S"
    MANUFACTURER = "M"
    TERMINATOR = "L"

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"RecordType.{self.name}"


class ProcessingId(str, Enum):
    """Processing ID values for header records."""

    PRODUCTION = "P"
    TEST = "T"
    DEBUG = "D"

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"ProcessingId.{self.name}"


class Sex(str, Enum):
    """Patient sex values."""

    MALE = "M"
    FEMALE = "F"
    UNKNOWN = "U"

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"Sex.{self.name}"


class Priority(str, Enum):
    """Order priority values."""

    STAT = "S"
    ASAP = "A"
    ROUTINE = "R"

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"Priority.{self.name}"


class AbnormalFlag(str, Enum):
    """Result abnormal flag values."""

    NORMAL = "N"
    ABNORMAL = "A"
    HIGH = "H"
    LOW = "L"
    VERY_HIGH = "HH"
    VERY_LOW = "LL"
    CRITICAL_HIGH = ">"
    CRITICAL_LOW = "<"

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"AbnormalFlag.{self.name}"


class ResultStatus(str, Enum):
    """Result status values."""

    FINAL = "F"
    PRELIMINARY = "P"
    CORRECTED = "C"
    CANNOT_REPORT = "X"

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"ResultStatus.{self.name}"


class CommentType(str, Enum):
    """Comment type values."""

    GENERIC = "G"
    INSTRUMENT = "I"
    PATIENT = "P"

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"CommentType.{self.name}"


class TerminationCode(str, Enum):
    """Termination code values."""

    NORMAL = "N"
    TERMINATED = "T"
    QUERY = "Q"

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"TerminationCode.{self.name}"


class ConnectionState(str, Enum):
    """Connection state values."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATING = "authenticating"
    READY = "ready"
    SENDING = "sending"
    RECEIVING = "receiving"
    ERROR = "error"
    CLOSING = "closing"

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"ConnectionState.{self.name}"


class ErrorCode(IntEnum):
    """Error code values for ASTM operations."""

    # Protocol errors (1000-1999)
    PROTOCOL_VIOLATION = 1000
    INVALID_MESSAGE_FORMAT = 1001
    CHECKSUM_MISMATCH = 1002
    SEQUENCE_ERROR = 1003
    TIMEOUT = 1004

    # Connection errors (2000-2999)
    CONNECTION_FAILED = 2000
    CONNECTION_LOST = 2001
    CONNECTION_REFUSED = 2002
    AUTHENTICATION_FAILED = 2003

    # Data errors (3000-3999)
    VALIDATION_ERROR = 3000
    MISSING_REQUIRED_FIELD = 3001
    INVALID_FIELD_VALUE = 3002
    FIELD_TOO_LONG = 3003

    # System errors (4000-4999)
    INTERNAL_ERROR = 4000
    RESOURCE_UNAVAILABLE = 4001
    CONFIGURATION_ERROR = 4002

    def __str__(self) -> str:
        return f"{self.name} ({self.value})"

    def __repr__(self) -> str:
        return f"ErrorCode.{self.name}"


class CommunicationProtocol(str, Enum):
    """Communication protocol types."""

    TCP = "tcp"
    SERIAL = "serial"
    UDP = "udp"
    HTTP = "http"

    def __str__(self) -> str:
        return self.value


class SerializationFormat(str, Enum):
    """Serialization format types."""

    YAML = "yaml"
    JSON = "json"
    TOML = "toml"

    def __str__(self) -> str:
        return self.value


class MessageType(Enum):
    """ASTM message types for better classification."""

    COMPLETE_MESSAGE = "complete_message"
    FRAME_ONLY = "frame_only"
    RECORD_ONLY = "record_only"
    CHUNKED_MESSAGE = "chunked_message"


# Export all enums
__all__ = [
    "RecordType",
    "ProcessingId",
    "Sex",
    "Priority",
    "AbnormalFlag",
    "ResultStatus",
    "CommentType",
    "TerminationCode",
    "ConnectionState",
    "ErrorCode",
    "CommunicationProtocol",
    "SerializationFormat",
    "MessageType",
]
