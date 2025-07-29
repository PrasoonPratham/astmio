#
# Copyright (C) 2013 Alexander Shorin
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#
from typing import Any, Iterator, List, Optional, Tuple, Union

from .constants import (
    COMPONENT_SEP,
    CRLF,
    ENCODING,
    ETB,
    ETX,
    FIELD_SEP,
    RECORD_SEP,
    REPEAT_SEP,
    STX,
)
from .dataclasses import DecodingResult, MessageType
from .enums import ErrorCode
from .exceptions import ChecksumError, ProtocolError, ValidationError
from .logging import get_logger
from .utils import is_chunked_message, make_checksum

log = get_logger(__name__)

# Type aliases
ASTMRecord = List[Union[str, List[Any], None]]

ASTM_Message = List[ASTMRecord]

# Will be used in where field contains escape value[|,^, &,\]
ASTM_UNESCAPE_MAP = {
    b"\\F\\": FIELD_SEP,  # \F\ -> |
    b"\\S\\": COMPONENT_SEP,  # \S\ -> ^
    b"\\R\\": REPEAT_SEP,  # \R\ -> &
    b"\\E\\": b"\\",  # \E\ -> \
}


# It will be used in case if the decoder has to decode live tcp_stream or large files
def decode_stream(
    stream: bytes, encoding: str = ENCODING, strict: bool = False
) -> Iterator[ASTM_Message]:
    """
    Decodes a stream of bytes containing multiple ASTM messages, yielding
    one decoded message at a time to save memory.
    """
    message_chunks = stream.split(STX)
    if stream.startswith(STX):
        message_chunks = message_chunks[1:]

    for chunk in message_chunks:
        if not chunk:
            continue

        full_message = STX + chunk
        try:
            yield decode(full_message, encoding, strict)
        except (ProtocolError, ValidationError) as e:
            log.warning("Skipping malformed message in stream: %s", e)
            continue


# It will be used if user wants only data
def decode(
    data: bytes, encoding: str = ENCODING, strict: bool = False
) -> ASTM_Message:
    """
    Simple public API that decodes ASTM data or raises a specific error.

    :param data: ASTM data object.
    :param encoding: Data encoding.
    :param strict: Whether to use strict validation.
    :return: List of ASTM records.
    :raises: ProtocolError for malformed data, ValidationError for validation issues.
    """
    try:
        result: DecodingResult = decode_with_metadata(data, encoding, strict)
        return result.data
    except (ProtocolError, ValidationError) as e:
        log.error("ASTM decoding failed: %s", e)
        raise e


# It will be used if user wants data + metadata
def decode_with_metadata(
    data: bytes, encoding: str = ENCODING, strict: bool = True
) -> "DecodingResult":
    """
    Main decoding function with comprehensive metadata.

    :param data: ASTM data object.
    :param encoding: Data encoding.
    :param strict: Whether to use strict validation.
    :return: DecodingResult with data and metadata.
    """
    if not isinstance(data, bytes):
        raise ValidationError(
            f"bytes expected, got {type(data).__name__}",
            code=ErrorCode.PROTOCOL_VIOLATION,
            details={"expected": "bytes", "got": type(data).__name__},
        )

    if not data:
        raise ValidationError(
            "No data found",
            code=ErrorCode.PROTOCOL_VIOLATION,
        )

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


def _decode_chunked_message(
    data: bytes, encoding: str, strict: bool
) -> "DecodingResult":
    """Decode a chunked message."""

    warnings = []
    warnings.append("Chunked message detected - may need additional chunks")

    seq, records, checksum = decode_message(data, encoding, strict)
    return DecodingResult(
        data=records,
        message_type=MessageType.CHUNKED_MESSAGE,
        sequence_number=seq,
        checksum=checksum,
        warnings=warnings,
    )


def _decode_complete_message(
    data: bytes, encoding: str, strict: bool
) -> "DecodingResult":
    """Decode a complete ASTM message with STX/ETX framing."""

    seq, records, checksum = decode_message(data, encoding, strict)
    return DecodingResult(
        data=records,
        message_type=MessageType.COMPLETE_MESSAGE,
        sequence_number=seq,
        checksum=checksum,
        checksum_valid=True,
    )


def _decode_frame_only(
    data: bytes, encoding: str, strict: bool
) -> "DecodingResult":
    """Decode a frame without STX/ETX framing."""

    seq, records = decode_frame(data, encoding, strict)
    return DecodingResult(
        data=records,
        message_type=MessageType.FRAME_ONLY,
        sequence_number=seq,
    )


def _decode_record_only(
    data: bytes, encoding: str, strict: bool
) -> "DecodingResult":
    """Decode a single record."""

    record = decode_record(data, encoding, strict)
    return DecodingResult(data=[record], message_type=MessageType.RECORD_ONLY)


def decode_message(
    message: bytes, encoding: str, strict: bool = False
) -> Tuple[Optional[int], ASTM_Message, Optional[str]]:
    """
    ASTM message decoder with proper error handling.

    :param message: ASTM message as bytes.
    :param encoding: Data encoding.
    :param strict: Whether to use strict validation.
    :return: Tuple of (sequence number, list of records, checksum).
    :raises: ProtocolError for malformed messages, ValidationError for
             validation issues.
    """
    if not isinstance(message, bytes):
        raise ValidationError(
            f"bytes expected, got {type(message).__name__}",
            field="record_input",
            value=type(message).__name__,
            constraint="must_be_bytes",
        )

    if not message:
        raise ValidationError(
            "Empty message provided",
            field="message_empty",
            value="<empty>",
            constraint="non_empty_required",
        )

    if not message.startswith(STX):
        if strict:
            raise ProtocolError(
                "Malformed ASTM message: Must start with STX",
                code=ErrorCode.PROTOCOL_VIOLATION,
                protocol_data=message[:50],
            )
        stx_pos = message.find(STX)
        if stx_pos > 0:
            message = message[stx_pos:]
            log.warning(f"Found STX at position {stx_pos}, truncated message")
        else:
            raise ProtocolError(
                "No STX found in message",
                code=ErrorCode.PROTOCOL_VIOLATION,
                protocol_data=message[:50],
            )

    frame_end_pos: int = message.rfind(ETX)
    if frame_end_pos == -1:
        frame_end_pos = message.rfind(ETB)

    if frame_end_pos == -1:
        if strict:
            raise ProtocolError(
                "Malformed ASTM message: No ETX or ETB found",
                code=ErrorCode.PROTOCOL_VIOLATION,
                protocol_data=message[-50:],
            )
        log.warning("No ETX or ETB found, using end of message")
        frame_end_pos = (
            len(message) - 3
        )  # Assume checksum is last 2 chars + CRLF

    if frame_end_pos <= 1:
        raise ProtocolError(
            f"Malformed ASTM message: Frame is too short (length: {len(message)})",
            code=ErrorCode.INVALID_MESSAGE_FORMAT,
            protocol_data=message,
        )

    frame_for_checksum: bytes = message[1 : frame_end_pos + 1]
    trailer = message[frame_end_pos + 1 :]
    cs = trailer.rstrip(CRLF)

    # Validate checksum
    ccs = make_checksum(frame_for_checksum)
    checksum_valid = cs == ccs

    if not checksum_valid:
        if strict:
            raise ChecksumError(
                calculated=ccs,
                data=message,
                expected=cs,
                message=f"Checksum failure: expected {cs!r}, calculated {ccs!r}. Data may be corrupt.",
            )
        log.warning(
            f"Checksum failure: expected {cs!r}, calculated {ccs!r}. Data may be corrupt."
        )

    frame_content = frame_for_checksum[:-1]
    seq, records = decode_frame(frame_content, encoding, strict)

    return seq, records, cs.decode(ENCODING, errors="replace") if cs else None


def decode_frame(
    frame: bytes, encoding: str, strict: bool = False
) -> Tuple[Optional[int], ASTM_Message]:
    """
    ASTM frame decoder.

    :param frame: ASTM frame.
    :param encoding: Data encoding.
    :param strict: Whether to use strict validation.
    :return: Tuple of (sequence number, list of records).
    :raises: ValidationError for validation issues.
    """

    if not isinstance(frame, bytes):
        raise ValidationError(
            f"bytes expected, got {type(frame).__name__}",
            field="frame_input",
            value=type(frame).__name__,
            constraint="must_be_bytes",
        )

    if not frame:
        return None, []

    seq: Optional[int] = None
    records_data: bytes = frame

    if frame and frame[:1].isdigit():
        try:
            # Using 'ascii' here because we are handling digits
            parsed_seq = int(frame[:1].decode("ascii"))

            if 0 <= parsed_seq <= 7:
                seq = parsed_seq
            else:
                # Sequence number is out of the valid 0-7 range
                if strict:
                    raise ValidationError(
                        f"Invalid sequence number: {parsed_seq} (must be 0-7)"
                    )
                log.warning(
                    f"Invalid sequence number {parsed_seq}, using modulo 8"
                )
                seq = parsed_seq % 8

            records_data = frame[1:]

        except (ValueError, UnicodeDecodeError):
            # This handles cases where the first char is a digit but part of a word
            log.debug(
                "First character is a digit but not a valid sequence number."
            )
            seq = None
            records_data = frame

    # The rest of the function now receives clean data
    records = []
    for record in records_data.split(RECORD_SEP):
        if record:
            records.append(decode_record(record, encoding, strict))

    return seq, records


def decode_record(
    record: bytes, encoding: str, strict: bool = False
) -> ASTMRecord:
    """
    Decodes a single ASTM record from bytes into a list of fields.

    This function is context-aware: it applies special parsing rules for
    Header and Comment records and correctly handles ASTM escape sequences.

    :param record: ASTM record bytes.
    :param encoding: Data encoding (e.g., 'latin-1').
    :param strict: If True, raises exceptions on parsing errors. If False,
                   logs warnings and attempts to use fallback values.
    :return: A list representing the decoded ASTM record.
    :raises: ValidationError if input is not bytes or is malformed in strict mode.
    """
    if not isinstance(record, bytes):
        raise ValidationError(
            f"bytes expected, got {type(record).__name__}",
            code=ErrorCode.INVALID_FIELD_VALUE,
            details={"expected": "bytes", "got": type(record).__name__},
        )

    if not record:
        if strict:
            raise ValidationError(
                "Empty record provided for decoding",
                code=ErrorCode.INVALID_MESSAGE_FORMAT,
            )
        return []

    fields: ASTMRecord = []
    field_parts = record.split(FIELD_SEP)

    # Extracting record type for context-aware parsing.
    record_type_bytes = field_parts[0]

    for i, item_bytes in enumerate(field_parts):
        try:
            # If any field is Empty then replace it with None
            if not item_bytes:
                fields.append(None)
                continue

            item: Union[str, List[Any], None]

            # Header record's delimiter field must be treated as a literal string
            # This case will handle the \^& case properly and not split on '^' character
            if record_type_bytes.endswith(b"H") and i == 1:
                item = item_bytes.decode(encoding)

            # Comment record's text field must be treated as a literal string.
            # In case a comment has escape character then it should handle it properly
            elif record_type_bytes.endswith(b"C") and i == 3:
                unescaped_bytes = unescape_astm_field(item_bytes)
                item = unescaped_bytes.decode(encoding)

            # For all other fields, unescape first, then parse.
            else:
                unescaped_bytes: bytes = unescape_astm_field(item_bytes)

                if REPEAT_SEP in unescaped_bytes:
                    item: List[List[Optional[str]]] = decode_repeated_component(
                        unescaped_bytes, encoding, strict
                    )
                elif COMPONENT_SEP in unescaped_bytes:
                    item: List[Optional[str]] = decode_component(
                        unescaped_bytes, encoding, strict
                    )
                else:
                    item: str = unescaped_bytes.decode(encoding)

            fields.append(item)

        except (ValidationError, ProtocolError) as e:
            if strict:
                raise e
            log.warning("A parsing error occurred in non-strict mode: %s", e)
            fields.append(item_bytes.decode(encoding, errors="replace"))

        except Exception as e:
            error_details = {
                "field_index": i,
                "record_type": record_type_bytes.decode(encoding, "replace"),
                "original_error": str(e),
            }
            if strict:
                raise ValidationError(
                    f"Failed to decode field {i} in record",
                    code=ErrorCode.FIELD_DECODE_ERROR,
                    details=error_details,
                )
            log.warning(
                "Field %d decode failed, using fallback value. Error: %s", i, e
            )
            # If a user passes some character like '€' then replace it with `` character as a fallback
            fields.append(item_bytes.decode(encoding, errors="replace"))

    return fields


def decode_component(
    field: bytes, encoding: str, strict: bool = False
) -> List[Optional[str]]:
    """
    ASTM field component decoder.

    :param field: Field bytes.
    :param encoding: Data encoding.
    :param strict: Whether to use strict validation.
    :return: List of component strings.
    :raises: ValidationError for validation issues.
    """
    if not isinstance(field, bytes):
        raise ValidationError(
            f"bytes expected, got {type(field).__name__}",
            code=ErrorCode.PROTOCOL_VIOLATION,
            details={"expected": "bytes", "got": type(field).__name__},
        )

    components = []
    for item in field.split(COMPONENT_SEP):
        if item:
            try:
                components.append(item.decode(encoding))
            except UnicodeDecodeError as e:
                if strict:
                    raise ValidationError(
                        f", got {type(field).__name__}",
                        code=ErrorCode.PROTOCOL_VIOLATION,
                        details={
                            "expected": "bytes",
                            "got": type(field).__name__,
                        },
                    )
                log.warning(
                    "Component decode failed, using error replacement",
                    error=str(e),
                )
                components.append(item.decode(encoding, errors="replace"))
        else:
            components.append(None)
    return components


def decode_repeated_component(
    component: bytes, encoding: str, strict: bool = False
) -> List[List[Optional[str]]]:
    """
    Repeated component decoder.

    :param component: Component bytes.
    :param encoding: Data encoding.
    :param strict: Whether to use strict validation.
    :return: List of component lists.
    :raises: ValidationError for validation issues.
    """
    if not isinstance(component, bytes):
        raise ValidationError(
            f"bytes expected, got {type(component).__name__}",
            code=ErrorCode.PROTOCOL_VIOLATION,
            details={"expected": "bytes", "got": type(component).__name__},
        )

    all_components = []
    repeated_items = component.split(REPEAT_SEP)

    for item in repeated_items:
        decoded_component = decode_component(item, encoding, strict)
        all_components.append(decoded_component)

    return all_components


def unescape_astm_field(field: bytes) -> bytes:
    """
    Unescape ASTM field content by handling escape sequences.

    :param field: Field content to unescape.
    :return: Unescaped field content.
    """
    if not isinstance(field, bytes):
        return field

    result = field
    for escaped, unescaped in ASTM_UNESCAPE_MAP.items():
        result = result.replace(escaped, unescaped)

    return result
