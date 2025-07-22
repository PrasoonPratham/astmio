#
# Copyright (C) 2013 Alexander Shorin
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from itertools import zip_longest
from typing import Any, Iterator, List, Optional, Tuple, Union

from .constants import (
    COMPONENT_SEP,
    CR,
    CRLF,
    ENCODING,
    ETB,
    ETX,
    FIELD_SEP,
    RECORD_SEP,
    REPEAT_SEP,
    STX,
)
from .exceptions import ProtocolError, ValidationError

log = logging.getLogger(__name__)

# Type aliases
ASTMRecord = List[Union[str, List[Any], None]]
ASTMData = List[ASTMRecord]


class MessageType(Enum):
    """ASTM message types for better classification."""

    COMPLETE_MESSAGE = "complete_message"
    FRAME_ONLY = "frame_only"
    RECORD_ONLY = "record_only"
    CHUNKED_MESSAGE = "chunked_message"


@dataclass
class DecodingResult:
    """Result of decoding operation with metadata."""

    data: ASTMData
    message_type: MessageType
    sequence_number: Optional[int] = None
    checksum: Optional[str] = None
    checksum_valid: bool = True
    warnings: List[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


@dataclass
class EncodingOptions:
    """Options for encoding ASTM messages."""

    encoding: str = ENCODING
    size: Optional[int] = None
    validate_checksum: bool = True
    strict_validation: bool = False
    include_metadata: bool = False


def decode(
    data: bytes, encoding: str = ENCODING, strict: bool = False
) -> ASTMData:
    """
    Enhanced ASTM decoding function with better error handling.

    :param data: ASTM data object.
    :param encoding: Data encoding.
    :param strict: Whether to use strict validation.
    :return: List of ASTM records.
    :raises: ProtocolError for malformed data, ValidationError for validation issues.
    """
    if not isinstance(data, bytes):
        raise ValidationError(f"bytes expected, got {type(data).__name__}")

    if not data:
        raise ValidationError("Empty data provided")

    if FIELD_SEP not in data:
        raise ProtocolError("Data is missing the required Field Separator.")

    try:
        result = decode_with_metadata(data, encoding, strict)
        return result.data
    except Exception as e:
        log.error(
            "Failed to decode ASTM data", error=str(e), data_length=len(data)
        )
        if strict:
            raise
        # In non-strict mode, try to recover
        log.warning("Attempting recovery decode")
        return _attempt_recovery_decode(data, encoding)


def decode_with_metadata(
    data: bytes, encoding: str = ENCODING, strict: bool = True
) -> DecodingResult:
    """
    Enhanced decoding with comprehensive metadata.

    :param data: ASTM data object.
    :param encoding: Data encoding.
    :param strict: Whether to use strict validation.
    :return: DecodingResult with data and metadata.
    """
    if not isinstance(data, bytes):
        raise ValidationError(f"bytes expected, got {type(data).__name__}")

    if not data:
        raise ValidationError("Empty data provided")

    # The message is normal(with STX and sequence number)
    if data.startswith(STX):
        if is_chunked_message(data):
            return _decode_chunked_message(data, encoding, strict)
        else:
            return _decode_complete_message(data, encoding, strict)

    # The message is without the STX(Only sequence number)
    elif data and data[:1].isdigit():
        return _decode_frame_only(data, encoding, strict)

    # The message contains only record(No sequence number and STX)
    else:
        return _decode_record_only(data, encoding, strict)


def _decode_complete_message(
    data: bytes, encoding: str, strict: bool
) -> DecodingResult:
    """Decode a complete ASTM message with STX/ETX framing."""
    try:
        seq, records, checksum = decode_message(data, encoding, strict)
        return DecodingResult(
            data=records,
            message_type=MessageType.COMPLETE_MESSAGE,
            sequence_number=seq,
            checksum=checksum,
            checksum_valid=True,  # decode_message validates checksum
        )
    except Exception as e:
        if strict:
            raise ProtocolError(f"Failed to decode complete message: {e}")
        log.warning(
            "Complete message decode failed, attempting recovery", error=str(e)
        )
        return _attempt_recovery_decode_with_metadata(data, encoding)


def _decode_frame_only(
    data: bytes, encoding: str, strict: bool
) -> DecodingResult:
    """Decode a frame without STX/ETX framing."""
    try:
        seq, records = decode_frame(data, encoding, strict)
        return DecodingResult(
            data=records,
            message_type=MessageType.FRAME_ONLY,
            sequence_number=seq,
        )
    except Exception as e:
        if strict:
            raise ProtocolError(f"Failed to decode frame: {e}")
        log.warning("Frame decode failed, attempting recovery", error=str(e))
        return _attempt_recovery_decode_with_metadata(data, encoding)


def _decode_record_only(
    data: bytes, encoding: str, strict: bool
) -> DecodingResult:
    """Decode a single record."""
    try:
        record = decode_record(data, encoding, strict)
        return DecodingResult(
            data=[record], message_type=MessageType.RECORD_ONLY
        )
    except Exception as e:
        if strict:
            raise ProtocolError(f"Failed to decode record: {e}")
        log.warning("Record decode failed, attempting recovery", error=str(e))
        return _attempt_recovery_decode_with_metadata(data, encoding)


def _decode_chunked_message(
    data: bytes, encoding: str, strict: bool
) -> DecodingResult:
    """Decode a chunked message."""
    warnings = []
    warnings.append("Chunked message detected - may need additional chunks")

    try:
        # For chunked messages, we decode what we have
        seq, records, checksum = decode_message(data, encoding, strict)
        return DecodingResult(
            data=records,
            message_type=MessageType.CHUNKED_MESSAGE,
            sequence_number=seq,
            checksum=checksum,
            warnings=warnings,
        )
    except Exception as e:
        if strict:
            raise ProtocolError(f"Failed to decode chunked message: {e}")
        log.warning("Chunked message decode failed", error=str(e))
        return _attempt_recovery_decode_with_metadata(data, encoding)


def _attempt_recovery_decode(data: bytes, encoding: str) -> ASTMData:
    """Attempt to recover from decode failures."""
    result = _attempt_recovery_decode_with_metadata(data, encoding)
    return result.data


def _attempt_recovery_decode_with_metadata(
    data: bytes, encoding: str
) -> DecodingResult:
    """Attempt to recover from decode failures with metadata."""
    warnings = ["Recovery decode attempted due to parsing failure"]

    try:
        # Try to decode as raw text split by common separators
        text = data.decode(encoding, errors="replace")

        # Split by record separator or line breaks
        if RECORD_SEP.decode(encoding) in text:
            parts = text.split(RECORD_SEP.decode(encoding))
        elif "\r\n" in text:
            parts = text.split("\r\n")
        elif "\n" in text:
            parts = text.split("\n")
        else:
            parts = [text]

        records = []
        for part in parts:
            if part.strip():
                # Split by field separator
                fields = part.split(FIELD_SEP.decode(encoding))
                records.append(fields)

        warnings.append(f"Recovered {len(records)} records from malformed data")

        return DecodingResult(
            data=records,
            message_type=MessageType.RECORD_ONLY,
            checksum_valid=False,
            warnings=warnings,
        )

    except Exception as e:
        log.error("Recovery decode also failed", error=str(e))
        raise ProtocolError(f"Unable to decode data even with recovery: {e}")


def decode_message(
    message: bytes, encoding: str, strict: bool = False
) -> Tuple[Optional[int], ASTMData, Optional[str]]:
    """
    Enhanced ASTM message decoder with better error handling.

    :param message: ASTM message as bytes.
    :param encoding: Data encoding.
    :param strict: Whether to use strict validation.
    :return: Tuple of (sequence number, list of records, checksum).
    :raises: ProtocolError for malformed messages, ValidationError for
             validation issues.
    """
    if not isinstance(message, bytes):
        raise ValidationError(f"bytes expected, got {type(message).__name__}")

    if not message:
        raise ValidationError("Empty message provided")

    if not message.startswith(STX):
        if strict:
            raise ProtocolError("Malformed ASTM message: Must start with STX")
        log.warning("Message doesn't start with STX, attempting to find STX")
        stx_pos = message.find(STX)
        if stx_pos > 0:
            message = message[stx_pos:]
            log.warning(f"Found STX at position {stx_pos}, truncated message")
        else:
            raise ProtocolError("No STX found in message")

    frame_end_pos = message.rfind(ETX)
    if frame_end_pos == -1:
        frame_end_pos = message.rfind(ETB)

    if frame_end_pos == -1:
        if strict:
            raise ProtocolError("Malformed ASTM message: No ETX or ETB found")
        log.warning("No ETX or ETB found, using end of message")
        frame_end_pos = (
            len(message) - 3
        )  # Assume checksum is last 2 chars + CRLF

    if frame_end_pos <= 1:
        raise ProtocolError("Malformed ASTM message: Frame too short")

    frame_for_checksum = message[1 : frame_end_pos + 1]
    trailer = message[frame_end_pos + 1 :]
    cs = trailer.rstrip(CRLF)

    # Validate checksum
    ccs = make_checksum(frame_for_checksum)
    checksum_valid = cs == ccs

    if not checksum_valid:
        error_msg = f"Checksum failure: expected {cs!r}, calculated {ccs!r}"
        if strict:
            raise ProtocolError(error_msg)
        log.warning(f"{error_msg}. Data may be corrupt.")

    frame_content = frame_for_checksum[:-1]

    try:
        seq, records = decode_frame(frame_content, encoding, strict)
    except Exception as e:
        if strict:
            raise ProtocolError(f"Failed to decode frame content: {e}")
        log.warning(
            "Frame decode failed, attempting simple split", error=str(e)
        )
        # Simple fallback: just split by record separator
        records = []
        for record_data in frame_content.split(RECORD_SEP):
            if record_data:
                try:
                    records.append(decode_record(record_data, encoding, False))
                except Exception:
                    # Last resort: just decode as string fields
                    fields = record_data.decode(
                        encoding, errors="replace"
                    ).split(FIELD_SEP.decode(encoding))
                    records.append(fields)
        seq = None

    return seq, records, cs.decode("ascii", errors="replace") if cs else None


def decode_frame(
    frame: bytes, encoding: str, strict: bool = False
) -> Tuple[Optional[int], ASTMData]:
    """
    Enhanced ASTM frame decoder.

    :param frame: ASTM frame.
    :param encoding: Data encoding.
    :param strict: Whether to use strict validation.
    :return: Tuple of (sequence number, list of records).
    :raises: ValidationError for validation issues.
    """
    if not isinstance(frame, bytes):
        raise ValidationError(f"bytes expected, got {type(frame).__name__}")

    if not frame:
        if strict:
            raise ValidationError("Empty frame provided")
        return None, []

    seq: Optional[int]
    if frame and frame[:1].isdigit():
        try:
            seq = int(frame[:1].decode("ascii"))
            if seq < 0 or seq > 7:
                if strict:
                    raise ValidationError(
                        f"Invalid sequence number: {seq} (must be 0-7)"
                    )
                log.warning(f"Invalid sequence number {seq}, using modulo 8")
                seq = seq % 8
        except ValueError as e:
            if strict:
                raise ValidationError(f"Invalid sequence number format: {e}")
            log.warning("Invalid sequence number format, assuming no sequence")
            seq = None
            records_data = frame
        else:
            records_data = frame[1:]
    else:
        seq = None
        records_data = frame

    records = []
    for record in records_data.split(RECORD_SEP):
        if record:
            try:
                decoded_record = decode_record(record, encoding, strict)
                records.append(decoded_record)
            except Exception as e:
                if strict:
                    raise ValidationError(f"Failed to decode record: {e}")
                log.warning(
                    "Record decode failed, using fallback", error=str(e)
                )
                # Fallback: split by field separator and decode as strings
                try:
                    fields = record.decode(encoding, errors="replace").split(
                        FIELD_SEP.decode(encoding)
                    )
                    records.append(fields)
                except Exception:
                    log.error("Complete record decode failure, skipping record")

    return seq, records


def decode_record(
    record: bytes, encoding: str, strict: bool = False
) -> ASTMRecord:
    """
    Enhanced ASTM record decoder.

    :param record: ASTM record bytes.
    :param encoding: Data encoding.
    :param strict: Whether to use strict validation.
    :return: Decoded ASTM record.
    :raises: ValidationError for validation issues.
    """
    if not isinstance(record, bytes):
        raise ValidationError(f"bytes expected, got {type(record).__name__}")

    if not record:
        if strict:
            raise ValidationError("Empty record provided")
        return []

    fields: ASTMRecord = []

    try:
        field_parts = record.split(FIELD_SEP)
    except Exception as e:
        if strict:
            raise ValidationError(f"Failed to split record into fields: {e}")
        log.warning(
            "Field splitting failed, treating as single field", error=str(e)
        )
        field_parts = [record]

    for i, item_bytes in enumerate(field_parts):
        try:
            if not item_bytes:
                fields.append(None)
                continue

            if REPEAT_SEP in item_bytes:
                item: Union[str, List[Any], None] = decode_repeated_component(
                    item_bytes, encoding, strict
                )
            elif COMPONENT_SEP in item_bytes:
                item = decode_component(item_bytes, encoding, strict)
            else:
                item = item_bytes.decode(encoding)
            fields.append(item)

        except Exception as e:
            if strict:
                raise ValidationError(f"Failed to decode field {i}: {e}")
            log.warning(
                f"Field {i} decode failed, using fallback", error=str(e)
            )
            # Fallback: decode as string with error replacement
            try:
                fallback_value = item_bytes.decode(encoding, errors="replace")
                fields.append(fallback_value)
            except Exception:
                fields.append(None)

    return fields


def decode_component(
    field: bytes, encoding: str, strict: bool = False
) -> List[Optional[str]]:
    """
    Enhanced ASTM field component decoder.

    :param field: Field bytes.
    :param encoding: Data encoding.
    :param strict: Whether to use strict validation.
    :return: List of component strings.
    :raises: ValidationError for validation issues.
    """
    if not isinstance(field, bytes):
        raise ValidationError(f"bytes expected, got {type(field).__name__}")

    try:
        components = []
        for item in field.split(COMPONENT_SEP):
            if item:
                try:
                    components.append(item.decode(encoding))
                except UnicodeDecodeError as e:
                    if strict:
                        raise ValidationError(
                            f"Failed to decode component: {e}"
                        )
                    log.warning(
                        "Component decode failed, using error replacement",
                        error=str(e),
                    )
                    components.append(item.decode(encoding, errors="replace"))
            else:
                components.append(None)
        return components
    except Exception as e:
        if strict:
            raise ValidationError(f"Failed to decode components: {e}")
        log.warning("Component splitting failed", error=str(e))
        # Fallback: return as single component
        try:
            return [field.decode(encoding, errors="replace")]
        except Exception:
            return [None]


def decode_repeated_component(
    component: bytes, encoding: str, strict: bool = False
) -> List[List[Optional[str]]]:
    """
    Enhanced repeated component decoder.

    :param component: Component bytes.
    :param encoding: Data encoding.
    :param strict: Whether to use strict validation.
    :return: List of component lists.
    :raises: ValidationError for validation issues.
    """
    if not isinstance(component, bytes):
        raise ValidationError(f"bytes expected, got {type(component).__name__}")

    try:
        return [
            decode_component(item, encoding, strict)
            for item in component.split(REPEAT_SEP)
        ]
    except Exception as e:
        if strict:
            raise ValidationError(f"Failed to decode repeated components: {e}")
        log.warning("Repeated component decode failed", error=str(e))
        # Fallback: treat as single component
        return [decode_component(component, encoding, False)]


def encode(
    records: Iterable[ASTMRecord],
    encoding: str = ENCODING,
    size: Optional[int] = None,
    seq: int = 1,
    options: Optional[EncodingOptions] = None,
) -> List[bytes]:
    """
    Enhanced ASTM encoder with validation and options.

    :param records: An iterable of ASTM records.
    :param encoding: Data encoding.
    :param size: Chunk size in bytes.
    :param seq: Frame start sequence number.
    :param options: Encoding options.
    :return: A list of ASTM message chunks.
    :raises: ValidationError for validation issues.
    """
    if options is None:
        options = EncodingOptions(encoding=encoding, size=size)

    if not isinstance(records, Iterable):
        raise ValidationError(
            f"Iterable expected, got {type(records).__name__}"
        )

    records_list = list(records)
    if not records_list:
        if options.strict_validation:
            raise ValidationError("No records provided for encoding")
        log.warning("No records provided, returning empty message")
        return []

    try:
        msg = encode_message(
            seq, records_list, options.encoding, options.strict_validation
        )

        if options.validate_checksum:
            # Validate the generated message can be decoded
            try:
                decode_message(msg, options.encoding, options.strict_validation)
            except Exception as e:
                if options.strict_validation:
                    raise ValidationError(
                        f"Generated message failed validation: {e}"
                    )
                log.warning("Generated message validation failed", error=str(e))

        if options.size is not None and len(msg) > options.size:
            try:
                return list(split(msg, options.size))
            except ValueError as split_error:
                if options.strict_validation:
                    raise ValidationError(
                        f"Cannot split message: {split_error}"
                    )
                log.warning(
                    "Message splitting failed, returning single message: %s",
                    str(split_error),
                )
                return [msg]
        return [msg]

    except Exception as e:
        log.error(
            "Failed to encode records: %s (record_count=%d)",
            str(e),
            len(records_list),
        )
        if options and options.strict_validation:
            raise
        raise ValidationError(f"Failed to encode records: {e}")


def iter_encode(
    records: Iterable[ASTMRecord],
    encoding: str = ENCODING,
    size: Optional[int] = None,
    seq: int = 1,
    options: Optional[EncodingOptions] = None,
) -> Iterator[bytes]:
    """
    Enhanced iterator encoder with validation.

    :param records: An iterable of ASTM records.
    :param encoding: Data encoding.
    :param size: Chunk size in bytes.
    :param seq: Frame start sequence number.
    :param options: Encoding options.
    :yields: ASTM message chunks.
    :raises: ValidationError for validation issues.
    """
    if options is None:
        options = EncodingOptions(encoding=encoding, size=size)

    if not isinstance(records, Iterable):
        raise ValidationError(
            f"Iterable expected, got {type(records).__name__}"
        )

    record_count = 0
    for record in records:
        if record is None:
            if options.strict_validation:
                raise ValidationError(f"None record at position {record_count}")
            log.warning(f"Skipping None record at position {record_count}")
            continue

        try:
            msg = encode_message(
                seq, [record], options.encoding, options.strict_validation
            )

            if options.validate_checksum:
                # Validate the generated message
                try:
                    decode_message(
                        msg, options.encoding, options.strict_validation
                    )
                except Exception as e:
                    if options.strict_validation:
                        raise ValidationError(
                            f"Generated message failed validation: {e}"
                        )
                    log.warning(
                        "Generated message validation failed", error=str(e)
                    )

            if options.size is not None and len(msg) > options.size:
                yield from split(msg, options.size)
            else:
                yield msg

        except Exception as e:
            if options.strict_validation:
                raise ValidationError(
                    f"Failed to encode record {record_count}: {e}"
                )
            log.warning(
                f"Failed to encode record {record_count}, skipping",
                error=str(e),
            )

        seq = (seq + 1) % 8
        record_count += 1

    if record_count == 0:
        log.warning("No valid records found for encoding")


def encode_message(
    seq: int, records: Iterable[ASTMRecord], encoding: str, strict: bool = False
) -> bytes:
    """
    Enhanced ASTM message encoder with validation.

    :param seq: Frame sequence number.
    :param records: An iterable of ASTM records.
    :param encoding: Data encoding.
    :param strict: Whether to use strict validation.
    :return: A complete ASTM message.
    :raises: ValidationError for validation issues.
    """
    if not isinstance(seq, int):
        raise ValidationError(
            f"Integer sequence number expected, got {type(seq).__name__}"
        )

    if seq < 0:
        if strict:
            raise ValidationError(
                f"Invalid sequence number: {seq} (must be >= 0)"
            )
        log.warning(f"Negative sequence number {seq}, using absolute value")
        seq = abs(seq)

    if not isinstance(records, Iterable):
        raise ValidationError(
            f"Iterable records expected, got {type(records).__name__}"
        )

    records_list = list(records)
    if not records_list:
        if strict:
            raise ValidationError("No records provided for encoding")
        log.warning("No records provided, creating empty message")

    try:
        # Encode each record with error handling
        encoded_records = []
        for i, record in enumerate(records_list):
            if record is None:
                if strict:
                    raise ValidationError(f"None record at position {i}")
                log.warning(f"Skipping None record at position {i}")
                continue

            try:
                encoded_record = encode_record(record, encoding, strict)
                encoded_records.append(encoded_record)
            except Exception as e:
                if strict:
                    raise ValidationError(f"Failed to encode record {i}: {e}")
                log.warning(
                    f"Failed to encode record {i}, skipping", error=str(e)
                )

        if not encoded_records and strict:
            raise ValidationError("No valid records could be encoded")

        data = RECORD_SEP.join(encoded_records)
        frame = b"".join((str(seq % 8).encode(), data, CR, ETX))
        message = b"".join((STX, frame, make_checksum(frame), CRLF))

        # Validate message length
        if len(message) > 64000:  # Reasonable maximum
            if strict:
                raise ValidationError(
                    f"Message too large: {len(message)} bytes"
                )
            log.warning(f"Large message generated: {len(message)} bytes")

        return message

    except Exception as e:
        log.error(
            "Failed to encode message",
            error=str(e),
            seq=seq,
            record_count=len(records_list),
        )
        if strict:
            raise
        raise ValidationError(f"Failed to encode message: {e}")


def encode_record(
    record: ASTMRecord, encoding: str, strict: bool = False
) -> bytes:
    """
    Enhanced ASTM record encoder with validation.

    :param record: An ASTM record.
    :param encoding: Data encoding.
    :param strict: Whether to use strict validation.
    :return: An encoded ASTM record.
    :raises: ValidationError for validation issues.
    """
    if not isinstance(record, (list, tuple)):
        raise ValidationError(
            f"List or tuple record expected, got {type(record).__name__}"
        )

    if not record:
        if strict:
            raise ValidationError("Empty record provided")
        log.warning("Empty record provided")
        return b""

    def _iter_fields(record: ASTMRecord) -> Iterator[bytes]:
        for i, field in enumerate(record):
            try:
                if field is None:
                    yield b""
                elif isinstance(field, bytes):
                    yield field
                elif isinstance(field, str):
                    yield field.encode(encoding)
                elif isinstance(field, Iterable):
                    yield encode_component(field, encoding, strict)
                else:
                    yield str(field).encode(encoding)
            except Exception as e:
                if strict:
                    raise ValidationError(f"Failed to encode field {i}: {e}")
                log.warning(
                    f"Failed to encode field {i}, using fallback", error=str(e)
                )
                # Fallback: convert to string and encode
                try:
                    yield str(field).encode(encoding, errors="replace")
                except Exception:
                    yield b""

    try:
        return FIELD_SEP.join(_iter_fields(record))
    except Exception as e:
        log.error(
            "Failed to encode record", error=str(e), record_length=len(record)
        )
        if strict:
            raise ValidationError(f"Failed to encode record: {e}")
        # Last resort fallback
        return b""


def encode_component(
    component: Iterable[Any], encoding: str, strict: bool = False
) -> bytes:
    """
    Enhanced ASTM component encoder with validation.

    :param component: Component data.
    :param encoding: Data encoding.
    :param strict: Whether to use strict validation.
    :return: Encoded component.
    :raises: ValidationError for validation issues.
    """
    if not isinstance(component, Iterable):
        raise ValidationError(
            f"Iterable component expected, got {type(component).__name__}"
        )

    def _iter_items(component: Iterable[Any]) -> Iterator[bytes]:
        for i, item in enumerate(component):
            try:
                if item is None:
                    yield b""
                elif isinstance(item, bytes):
                    yield item
                elif isinstance(item, str):
                    yield item.encode(encoding)
                elif isinstance(item, Iterable) and not isinstance(
                    item, (str, bytes)
                ):
                    # This indicates a repeated component
                    yield encode_repeated_component([item], encoding, strict)
                else:
                    yield str(item).encode(encoding)
            except Exception as e:
                if strict:
                    raise ValidationError(
                        f"Failed to encode component item {i}: {e}"
                    )
                log.warning(
                    f"Failed to encode component item {i}, using fallback",
                    error=str(e),
                )
                try:
                    yield str(item).encode(encoding, errors="replace")
                except Exception:
                    yield b""

    try:
        # Convert to list to allow peeking
        component_list = list(component)
        if not component_list:
            return b""

        # Check if first item is iterable (indicates repeated components)
        first_item = component_list[0]
        if isinstance(first_item, Iterable) and not isinstance(
            first_item, (str, bytes)
        ):
            return encode_repeated_component(component_list, encoding, strict)

        return COMPONENT_SEP.join(_iter_items(component_list))

    except Exception as e:
        if strict:
            raise ValidationError(f"Failed to encode component: {e}")
        log.warning("Component encoding failed, using fallback", error=str(e))
        try:
            # Fallback: join as strings
            return COMPONENT_SEP.join(
                str(item).encode(encoding, errors="replace")
                for item in component
            )
        except Exception:
            return b""


def encode_repeated_component(
    components: Iterable[Any], encoding: str, strict: bool = False
) -> bytes:
    """
    Enhanced repeated component encoder with validation.

    :param components: Repeated components.
    :param encoding: Data encoding.
    :param strict: Whether to use strict validation.
    :return: Encoded repeated components.
    :raises: ValidationError for validation issues.
    """
    if not isinstance(components, Iterable):
        raise ValidationError(
            f"Iterable components expected, got {type(components).__name__}"
        )

    try:
        encoded_components = []
        for i, item in enumerate(components):
            try:
                if isinstance(item, Iterable) and not isinstance(
                    item, (str, bytes)
                ):
                    encoded_components.append(
                        encode_component(item, encoding, strict)
                    )
                else:
                    # Single item, encode as component
                    encoded_components.append(
                        encode_component([item], encoding, strict)
                    )
            except Exception as e:
                if strict:
                    raise ValidationError(
                        f"Failed to encode repeated component {i}: {e}"
                    )
                log.warning(
                    f"Failed to encode repeated component {i}, skipping",
                    error=str(e),
                )

        return REPEAT_SEP.join(encoded_components)

    except Exception as e:
        if strict:
            raise ValidationError(f"Failed to encode repeated components: {e}")
        log.warning("Repeated component encoding failed", error=str(e))
        return b""


def make_checksum(message: bytes) -> bytes:
    """
    Calculates a checksum for the given message.

    :param message: ASTM message frame.
    :return: The checksum as a 2-character hexadecimal bytestring.
    """
    return b"%02X" % (sum(message) & 0xFF)


def make_chunks(s: bytes, n: int) -> List[bytes]:
    """Splits a bytestring into chunks of size n."""
    iter_bytes = (s[i : i + 1] for i in range(len(s)))
    return [
        b"".join(item) for item in zip_longest(*[iter_bytes] * n, fillvalue=b"")
    ]


def split(msg: bytes, size: int) -> Iterator[bytes]:
    """
    Splits a message into chunks of a specified size.

    :param msg: An ASTM message.
    :param size: The chunk size in bytes.
    :yields: ASTM message chunks.
    """
    if not (size and size >= 7):
        raise ValueError("Chunk size cannot be less than 7")

    stx, frame, msg_body, tail = msg[:1], msg[1:2], msg[2:-5], msg[-5:]
    if not (stx == STX and frame.isdigit() and tail.startswith(CR + ETX)):
        raise ValueError("Invalid message format for splitting")

    frame_num = int(frame)
    chunks = make_chunks(msg_body, size - 7)

    for i, chunk in enumerate(chunks[:-1]):
        current_frame = str((frame_num + i) % 8).encode()
        item = b"".join((current_frame, chunk, ETB))
        yield b"".join((STX, item, make_checksum(item), CRLF))

    last_chunk = chunks[-1]
    current_frame = str((frame_num + len(chunks) - 1) % 8).encode()
    item = b"".join((current_frame, last_chunk, CR, ETX))
    yield b"".join((STX, item, make_checksum(item), CRLF))


def join(chunks: Iterable[bytes], strict: bool = False) -> bytes:
    """
    Enhanced chunk merger with validation.

    :param chunks: An iterable of ASTM message chunks.
    :param strict: Whether to use strict validation.
    :return: A single, complete ASTM message.
    :raises: ValidationError for validation issues.
    """
    if not isinstance(chunks, Iterable):
        raise ValidationError(
            f"Iterable chunks expected, got {type(chunks).__name__}"
        )

    chunks_list = list(chunks)
    if not chunks_list:
        if strict:
            raise ValidationError("No chunks provided for joining")
        log.warning("No chunks provided")
        return b""

    try:
        # Validate all chunks
        for i, chunk in enumerate(chunks_list):
            if not isinstance(chunk, bytes):
                if strict:
                    raise ValidationError(
                        f"Chunk {i} must be bytes, got {type(chunk).__name__}"
                    )
                log.warning(f"Chunk {i} is not bytes, attempting conversion")
                try:
                    chunks_list[i] = bytes(chunk)
                except Exception:
                    if strict:
                        raise ValidationError(
                            f"Failed to convert chunk {i} to bytes"
                        )
                    log.warning(f"Failed to convert chunk {i}, skipping")
                    continue

            if len(chunk) < 5:
                if strict:
                    raise ValidationError(
                        f"Chunk {i} too short: {len(chunk)} bytes"
                    )
                log.warning(f"Chunk {i} too short, skipping")
                continue

        # Filter out invalid chunks
        valid_chunks = [
            c for c in chunks_list if isinstance(c, bytes) and len(c) >= 5
        ]
        if not valid_chunks:
            if strict:
                raise ValidationError("No valid chunks found")
            log.warning("No valid chunks found")
            return b""

        # Get initial frame number from first chunk
        try:
            first_frame_num = int(valid_chunks[0][1:2])
        except (ValueError, IndexError) as e:
            if strict:
                raise ValidationError(
                    f"Invalid frame number in first chunk: {e}"
                )
            log.warning("Invalid frame number, using 1")
            first_frame_num = 1

        # Extract message body from each chunk
        body_parts = []
        for i, chunk in enumerate(valid_chunks):
            try:
                # Extract body (skip STX, frame num, and last 5 bytes for checksum+CRLF)
                body_part = chunk[2:-5]
                body_parts.append(body_part)
            except Exception as e:
                if strict:
                    raise ValidationError(
                        f"Failed to extract body from chunk {i}: {e}"
                    )
                log.warning(
                    f"Failed to extract body from chunk {i}, skipping",
                    error=str(e),
                )

        body = b"".join(body_parts)

        # Remove ETB markers from body
        body = body.replace(ETB, b"")

        # Construct the full message frame for checksum calculation
        full_frame = str(first_frame_num).encode() + body + CR + ETX

        # Construct the final message
        message = b"".join((STX, full_frame, make_checksum(full_frame), CRLF))

        return message

    except Exception as e:
        log.error(
            "Failed to join chunks", error=str(e), chunk_count=len(chunks_list)
        )
        if strict:
            raise ValidationError(f"Failed to join chunks: {e}")
        # Return empty message as fallback
        return b""


def is_chunked_message(message: bytes) -> bool:
    """
    Checks if a message is a chunked message.

    :param message: An ASTM message.
    :return: True if the message is chunked, False otherwise.
    """
    if len(message) < 5:
        return False
    # Check for ETB at the expected position for a chunked message
    return message.rfind(ETB) == len(message) - 5
