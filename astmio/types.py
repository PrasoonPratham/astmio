#
# Copyright (C) 2013 Alexander Shorin
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#
"""
Shared types and data structures for ASTM processing.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Any, List, Optional, Union

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

    encoding: str = "latin-1"  # Default ASTM encoding
    size: Optional[int] = None
    validate_checksum: bool = True
    strict_validation: bool = False
    include_metadata: bool = False
