#
# Copyright (C) 2013 Alexander Shorin
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#
import logging
from collections.abc import Iterable
from typing import Any, Iterator, List, Optional

from .constants import (
    COMPONENT_SEP,
    CR,
    CRLF,
    ENCODING,
    ETX,
    FIELD_SEP,
    RECORD_SEP,
    REPEAT_SEP,
    STX,
)
from .decoder import decode_message
from .enums import ErrorCode
from .exceptions import ProtocolError, ValidationError
from .types import ASTMRecord, EncodingOptions
from .utils import make_checksum, split

log = logging.getLogger(__name__)


def encode(
    records: Iterable[ASTMRecord],
    encoding: str = ENCODING,
    size: Optional[int] = None,
    seq: int = 1,
    options: Optional["EncodingOptions"] = None,
) -> List[bytes]:
    """
    ASTM encoder with validation and options.

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
            f"Iterable expected, got {type(records).__name__}",
            field="records",
            value=type(records).__name__,
            constraint="must be Iterable",
        )

    records_list = list(records)
    if not records_list:
        if options.strict_validation:
            raise ValidationError("No records provided for encoding")
        log.warning("No records provided, returning empty message")
        return []

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
                raise ValidationError(f"Cannot split message: {split_error}")
            log.warning(
                "Message splitting failed, returning single message: %s",
                str(split_error),
            )
            return [msg]
    return [msg]


def iter_encode(
    records: Iterable[ASTMRecord],
    encoding: str = ENCODING,
    size: Optional[int] = None,
    seq: int = 1,
    options: Optional["EncodingOptions"] = None,
) -> Iterator[bytes]:
    """
    Iterator encoder with validation.

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

        msg = encode_message(
            seq, [record], options.encoding, options.strict_validation
        )

        if options.validate_checksum:
            # Validate the generated message
            try:
                decode_message(msg, options.encoding, options.strict_validation)
            except Exception as e:
                if options.strict_validation:
                    raise ValidationError(
                        f"Generated message failed validation: {e}"
                    )
                log.warning("Generated message validation failed", error=str(e))

        if options.size is not None and len(msg) > options.size:
            yield from split(msg, options.size)
        else:
            yield msg

        seq = (seq + 1) % 8
        record_count += 1

    if record_count == 0:
        log.warning("No valid records found for encoding")


def encode_message(
    seq: int, records: Iterable[ASTMRecord], encoding: str, strict: bool = False
) -> bytes:
    """
    ASTM message encoder with validation.

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
            # Use ProtocolError for AST protocol problems
            raise ProtocolError(
                f"Invalid sequence number: {seq} (must be >= 0)",
                code="INVALID_SEQUENCE",
                protocol_data=str(seq).encode(),
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

    # Encode each record with error handling
    encoded_records = []
    for i, record in enumerate(records_list):
        if record is None:
            if strict:
                raise ValidationError(f"None record at position {i}")
            log.warning(f"Skipping None record at position {i}")
            continue

        encoded_record = encode_record(record, encoding, strict)
        encoded_records.append(encoded_record)

    if not encoded_records and strict:
        raise ValidationError("No valid records could be encoded")

    try:
        data = RECORD_SEP.join(encoded_records)
        frame = b"".join((str(seq % 8).encode(), data, CR, ETX))
        message = b"".join((STX, frame, make_checksum(frame), CRLF))

        if len(message) > 64000:
            if strict:
                raise ProtocolError(
                    f"Message too large: {len(message)} bytes",
                    code="MESSAGE_TOO_LARGE",
                    protocol_data=message[:100],
                )
            log.warning(f"Large message generated: {len(message)} bytes")

        return message
    except Exception as e:
        log.error("Encoding failed: %s", e)
        raise ProtocolError(f"Encoding failed: {e}", code="ENCODING_FAILED")


def encode_record(
    record: ASTMRecord, encoding: str, strict: bool = False
) -> bytes:
    """
    ASTM record encoder with validation.

    :param record: An ASTM record.
    :param encoding: Data encoding.
    :param strict: Whether to use strict validation.
    :return: An encoded ASTM record.
    :raises: ValidationError for validation issues.
    """
    if not isinstance(record, (list, tuple)):
        raise ValidationError(
            f"List or tuple record expected, got {type(record).__name__}",
            field="record",
            value=type(record).__name__,
            constraint="must be list or tuple",
        )

    if not record:
        if strict:
            raise ValidationError("Empty record provided")
        log.warning("Empty record provided")
        return b""

    def _iter_fields(record: ASTMRecord) -> Iterator[bytes]:
        for field in record:
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

    try:
        result = FIELD_SEP.join(_iter_fields(record))
        return result
    except Exception as e:
        log.error("Failed to encode record: %s", e)
        raise ValidationError(
            f"Record encoding error: {e}",
            field="encode_record",
            value=str(record),
            constraint="record encoding",
        )


def encode_component(
    component: Iterable[Any], encoding: str = ENCODING, strict: bool = False
) -> bytes:
    """
    Encodes a single component (a list of sub-components) into a byte string,
    joined by the component separator.

    :param component: An iterable of sub-component items (str, int, etc.).
    :param encoding: The character encoding to use.
    :param strict: If True, raises exceptions on errors.
    :return: An encoded component as a byte string.
    :raises: ValidationError for invalid input or encoding failures.
    """
    if not isinstance(component, Iterable) or isinstance(
        component, (str, bytes)
    ):
        raise ValidationError(
            f"Iterable (but not str/bytes) expected for component, got {type(component).__name__}",
            code=ErrorCode.VALIDATION_ERROR,
        )

    def _iter_items(sub_components: Iterable[Any]) -> Iterator[bytes]:
        """Yields each sub-component as encoded bytes with error handling."""
        for i, item in enumerate(sub_components):
            try:
                if item is None:
                    yield b""
                elif isinstance(item, bytes):
                    yield item
                elif isinstance(item, str):
                    yield item.encode(encoding)
                else:
                    yield str(item).encode(encoding)

            except Exception as e:
                error_details = {
                    "item_index": i,
                    "item_value_type": type(item).__name__,
                    "original_error": str(e),
                }
                if strict:
                    raise ValidationError(
                        f"Failed to encode sub-component at index {i}",
                        code=ErrorCode.VALIDATION_ERROR,
                        details=error_details,
                    )
                log.warning(
                    "Failed to encode sub-component %d, using safe fallback. Error: %s",
                    i,
                    e,
                )
                yield str(item).encode(encoding, errors="replace")

    return COMPONENT_SEP.join(_iter_items(component))


def encode_repeated_component(
    components: Iterable[Iterable[Any]],
    encoding: str = ENCODING,
    strict: bool = False,
) -> bytes:
    """
    Encodes a list of components into a single byte string, joined by the
    repeat separator.

    :param components: An iterable of components (e.g., a list of lists).
    :param encoding: The character encoding to use.
    :param strict: If True, raises exceptions on errors.
    :return: An encoded repeated component as a byte string.
    :raises: ValidationError for invalid input or encoding failures.
    """
    if not isinstance(components, Iterable) or isinstance(
        components, (str, bytes)
    ):
        raise ValidationError(
            f"Iterable of iterables expected for repeated component, got {type(components).__name__}",
            code=ErrorCode.VALIDATION_ERROR,
        )

    encoded_components = []
    for i, component_item in enumerate(components):
        try:
            encoded_components.append(
                encode_component(component_item, encoding, strict)
            )
        except Exception as e:
            error_details = {
                "component_index": i,
                "component_value_type": type(component_item).__name__,
                "original_error": str(e),
            }
            if strict:
                raise ValidationError(
                    f"Failed to encode component at index {i} within a repeated field",
                    code=ErrorCode.VALIDATION_ERROR,
                    details=error_details,
                )
            log.warning(
                "Failed to encode component %d in repeated field, skipping. Error: %s",
                i,
                e,
            )
            continue

    return REPEAT_SEP.join(encoded_components)
