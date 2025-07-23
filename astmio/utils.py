#
# Copyright (C) 2013 Alexander Shorin
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#
from itertools import zip_longest
from typing import Iterable, Iterator, List

from .constants import CR, CRLF, ETB, ETX, STX
from .exceptions import ValidationError
from .logging import get_logger

log = get_logger(__name__)


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
