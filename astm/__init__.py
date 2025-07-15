# -*- coding: utf-8 -*-
#
# Copyright (C) 2013 Alexander Shorin
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#
from .client import Client
from .codec import (
    decode,
    decode_message,
    decode_record,
    encode,
    encode_message,
    encode_record,
    make_checksum,
)
from .dataclasses import (
    ConnectionConfig,
    ConnectionStatus,
    DeviceProfile,
    MessageMetrics,
    PerformanceMetrics,
    SecurityConfig,
    ValidationResult,
)
from .enums import (
    AbnormalFlag,
    CommentType,
    ConnectionState,
    ErrorCode,
    Priority,
    ProcessingId,
    RecordType,
    ResultStatus,
    Sex,
    TerminationCode,
)
from .exceptions import BaseASTMError, InvalidState, NotAccepted
from .mapping import Component, Record
from .modern_records import (
    ASTMBaseRecord,
    CommentRecord as ModernCommentRecord,
    HeaderRecord as ModernHeaderRecord,
    OrderRecord as ModernOrderRecord,
    PatientRecord as ModernPatientRecord,
    ResultRecord as ModernResultRecord,
    TerminatorRecord as ModernTerminatorRecord,
)
from .records import (
    CommentRecord,
    HeaderRecord,
    OrderRecord,
    PatientRecord,
    ResultRecord,
    TerminatorRecord,
)
from .server import Server
from .version import __version__, __version_info__

__all__ = [
    "__version__",
    "__version_info__",
    "BaseASTMError",
    "NotAccepted",
    "InvalidState",
    "decode",
    "decode_message",
    "decode_record",
    "encode",
    "encode_message",
    "encode_record",
    "make_checksum",
    "Record",
    "Component",
    "HeaderRecord",
    "PatientRecord",
    "OrderRecord",
    "ResultRecord",
    "CommentRecord",
    "TerminatorRecord",
    "Client",
    "Server",
    # Modern enums
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
    # Modern dataclasses
    "ConnectionConfig",
    "ConnectionStatus",
    "DeviceProfile",
    "MessageMetrics",
    "ValidationResult",
    "SecurityConfig",
    "PerformanceMetrics",
    # Modern records
    "ASTMBaseRecord",
    "ModernHeaderRecord",
    "ModernPatientRecord",
    "ModernOrderRecord",
    "ModernResultRecord",
    "ModernCommentRecord",
    "ModernTerminatorRecord",
]

import logging

try:
    from logging import NullHandler
except ImportError:

    class NullHandler(logging.Handler):
        def emit(self, record):
            pass


logging.getLogger(__name__).addHandler(NullHandler())
