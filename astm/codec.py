# -*- coding: utf-8 -*-
#
# Copyright (C) 2013 Alexander Shorin
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#
import logging
from collections.abc import Iterable
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
    LF,
    RECORD_SEP,
    REPEAT_SEP,
    STX,
)

log = logging.getLogger(__name__)

# Type aliases
ASTMRecord = List[Union[str, List[Any], None]]
ASTMData = List[ASTMRecord]


def decode(data: bytes, encoding: str = ENCODING) -> ASTMData:
    """
    Common ASTM decoding function that tries to guess which kind of data it
    handles.

    :param data: ASTM data object.
    :param encoding: Data encoding.
    :return: List of ASTM records.
    """
    if not isinstance(data, bytes):
        raise TypeError(f"bytes expected, got {type(data).__name__}")
    if data.startswith(STX):
        _, records, _ = decode_message(data, encoding)
        return records
    if data and data[:1].isdigit():
        _, records = decode_frame(data, encoding)
        return records
    return [decode_record(data, encoding)]


def decode_message(
    message: bytes, encoding: str
) -> Tuple[Optional[int], ASTMData, Optional[str]]:
    """
    Decodes a complete ASTM message.

    :param message: ASTM message.
    :param encoding: Data encoding.
    :return: Tuple of (sequence number, list of records, checksum).
    """
    if not isinstance(message, bytes):
        raise TypeError(f"bytes expected, got {type(message).__name__}")
    if not message.startswith(STX):
        raise ValueError("Malformed ASTM message: Must start with STX.")

    frame_end_pos = message.rfind(ETX)
    if frame_end_pos == -1:
        frame_end_pos = message.rfind(ETB)

    if frame_end_pos == -1:
        raise ValueError("Malformed ASTM message: No ETX or ETB found.")

    frame_for_checksum = message[1 : frame_end_pos + 1]
    trailer = message[frame_end_pos + 1 :]
    cs = trailer.rstrip(CRLF)

    ccs = make_checksum(frame_for_checksum)
    if cs != ccs:
        log.warning(
            "Checksum failure: expected %r, calculated %r. Data may be corrupt.", cs, ccs
        )

    frame_content = frame_for_checksum[:-1]
    seq, records = decode_frame(frame_content, encoding)

    return seq, records, cs.decode("ascii") if cs else None


def decode_frame(frame: bytes, encoding: str) -> Tuple[Optional[int], ASTMData]:
    """
    Decodes an ASTM frame.

    :param frame: ASTM frame.
    :param encoding: Data encoding.
    :return: Tuple of (sequence number, list of records).
    """
    if not isinstance(frame, bytes):
        raise TypeError(f"bytes expected, got {type(frame).__name__}")

    seq: Optional[int]
    if frame and frame[:1].isdigit():
        seq = int(frame[:1].decode("ascii"))
        records_data = frame[1:]
    else:
        seq = None
        records_data = frame

    return seq, [
        decode_record(record, encoding)
        for record in records_data.split(RECORD_SEP)
        if record
    ]


def decode_record(record: bytes, encoding: str) -> ASTMRecord:
    """Decodes an ASTM record message."""
    fields: ASTMRecord = []
    for item_bytes in record.split(FIELD_SEP):
        if not item_bytes:
            fields.append(None)
            continue
        if REPEAT_SEP in item_bytes:
            item: Union[str, List[Any], None] = decode_repeated_component(
                item_bytes, encoding
            )
        elif COMPONENT_SEP in item_bytes:
            item = decode_component(item_bytes, encoding)
        else:
            item = item_bytes.decode(encoding)
        fields.append(item)
    return fields


def decode_component(field: bytes, encoding: str) -> List[Optional[str]]:
    """Decodes an ASTM field component."""
    return [
        item.decode(encoding) if item else None for item in field.split(COMPONENT_SEP)
    ]


def decode_repeated_component(
    component: bytes, encoding: str
) -> List[List[Optional[str]]]:
    """Decodes an ASTM field's repeated components."""
    return [
        decode_component(item, encoding) for item in component.split(REPEAT_SEP)
    ]


def encode(
    records: Iterable[ASTMRecord],
    encoding: str = ENCODING,
    size: Optional[int] = None,
    seq: int = 1,
) -> List[bytes]:
    """
    Encodes a list of records into one or more ASTM message chunks.

    :param records: An iterable of ASTM records.
    :param encoding: Data encoding.
    :param size: Chunk size in bytes.
    :param seq: Frame start sequence number.
    :return: A list of ASTM message chunks.
    """
    msg = encode_message(seq, records, encoding)
    if size is not None and len(msg) > size:
        return list(split(msg, size))
    return [msg]


def iter_encode(
    records: Iterable[ASTMRecord],
    encoding: str = ENCODING,
    size: Optional[int] = None,
    seq: int = 1,
) -> Iterator[bytes]:
    """
    Encodes and yields each record as a separate message.

    :param records: An iterable of ASTM records.
    :param encoding: Data encoding.
    :param size: Chunk size in bytes.
    :param seq: Frame start sequence number.
    :yields: ASTM message chunks.
    """
    for record in records:
        msg = encode_message(seq, [record], encoding)
        if size is not None and len(msg) > size:
            for chunk in split(msg, size):
                yield chunk
        else:
            yield msg
        seq = (seq + 1) % 8


def encode_message(
    seq: int, records: Iterable[ASTMRecord], encoding: str
) -> bytes:
    """
    Encodes an ASTM message frame.

    :param seq: Frame sequence number.
    :param records: An iterable of ASTM records.
    :param encoding: Data encoding.
    :return: A complete ASTM message.
    """
    data = RECORD_SEP.join(encode_record(record, encoding) for record in records)
    frame = b"".join((str(seq % 8).encode(), data, CR, ETX))
    return b"".join((STX, frame, make_checksum(frame), CRLF))


def encode_record(record: ASTMRecord, encoding: str) -> bytes:
    """
    Encodes a single ASTM record.

    :param record: An ASTM record.
    :param encoding: Data encoding.
    :return: An encoded ASTM record.
    """

    def _iter_fields(record: ASTMRecord) -> Iterator[bytes]:
        for field in record:
            if field is None:
                yield b""
            elif isinstance(field, bytes):
                yield field
            elif isinstance(field, str):
                yield field.encode(encoding)
            elif isinstance(field, Iterable):
                yield encode_component(field, encoding)
            else:
                yield str(field).encode(encoding)

    return FIELD_SEP.join(_iter_fields(record))


def encode_component(component: Iterable[Any], encoding: str) -> bytes:
    """Encodes ASTM record field components."""

    def _iter_items(component: Iterable[Any]) -> Iterator[bytes]:
        for item in component:
            if item is None:
                yield b""
            elif isinstance(item, bytes):
                yield item
            elif isinstance(item, str):
                yield item.encode(encoding)
            elif isinstance(item, Iterable):
                # This indicates a repeated component, which should be handled by encode_repeated_component
                yield encode_repeated_component(item, encoding)
            else:
                yield str(item).encode(encoding)

    # Peek to see if we have nested iterables (repeated components)
    first_item = next(iter(component), None)
    if isinstance(first_item, Iterable) and not isinstance(first_item, (str, bytes)):
        return encode_repeated_component(component, encoding)

    return COMPONENT_SEP.join(_iter_items(component))


def encode_repeated_component(components: Iterable[Any], encoding: str) -> bytes:
    """Encodes repeated components."""
    return REPEAT_SEP.join(encode_component(item, encoding) for item in components)


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
    return [b"".join(item) for item in zip_longest(*[iter_bytes] * n, fillvalue=b"")]


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


def join(chunks: Iterable[bytes]) -> bytes:
    """
    Merges ASTM message chunks into a single message.

    :param chunks: An iterable of ASTM message chunks.
    :return: A single, complete ASTM message.
    """
    # Assuming first chunk determines the initial frame number
    first_frame_num = int(chunks[0][1:2])
    
    # Extract message body from each chunk
    body = b"".join(c[2:-5] for c in chunks)
    
    # Construct the full message frame for checksum calculation
    full_frame = str(first_frame_num).encode() + body.replace(ETB, b"")
    
    # Construct the final message
    return b"".join((STX, full_frame, make_checksum(full_frame), CRLF))


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
