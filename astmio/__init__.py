# -*- coding: utf-8 -*-
#
# ASTM Library - Simple, Robust, and Easy to Use
#
# Enhanced API with comprehensive modernization features
#
from .client import Client, ClientConfig, create_client, astm_client
from .server import Server, ServerConfig, create_server, astm_server

# Enhanced codec functions
from .codec import (
    decode,
    decode_message,
    decode_record,
    decode_with_metadata,
    encode,
    encode_message,
    encode_record,
    make_checksum,
    MessageType,
    DecodingResult,
    EncodingOptions,
)

# Enhanced configuration system
from .config import (
    ConfigManager,
    TransportConfig,
    FrameConfig,
    RecordConfig,
    ParserConfig,
    ProfileFormat,
    TransportMode,
    default_config_manager,
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

# Enhanced exceptions
from .exceptions import (
    BaseASTMError,
    InvalidState,
    NotAccepted,
    ProtocolError,
    ValidationError,
    ConnectionError,
    TimeoutError,
    ParseError,
    ChecksumError,
    ConfigurationError,
    ResourceError,
    SecurityError,
    Rejected,
    AggregateError,
    ErrorContext,
    ErrorRecovery,
)

# Metrics and monitoring
from .metrics import (
    MetricsCollector,
    Counter,
    Gauge,
    Histogram,
    Timer,
    MetricPoint,
    MetricSummary,
    MetricType,
    default_metrics,
    prometheus_exporter,
    json_exporter,
    count_calls,
    time_calls,
    async_time_calls,
)

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
from .version import __version__, __version_info__

# High-level convenience functions for common use cases
async def send_astm_data(
    records,
    host="localhost", 
    port=15200,
    timeout=5.0,
    encoding="latin-1"
) -> bool:
    """
    Send ASTM records with a simple one-liner.
    
    Example:
        success = await send_astm_data(
            records=[
                ['H', '|||||', '20230507'],
                ['L', '1', 'N']
            ],
            host="192.168.1.100"
        )
    """
    async with astm_client(host, port, timeout, encoding=encoding) as client:
        return await client.send_records(records)


async def run_astm_server(
    handlers,
    host="localhost",
    port=15200,
    timeout=10.0,
    duration=None
):
    """
    Run an ASTM server with simple configuration.
    
    Example:
        def handle_header(record):
            print(f"Received header: {record}")
            
        def handle_result(record):
            print(f"Received result: {record}")
            
        await run_astm_server({
            'H': handle_header,
            'R': handle_result
        }, duration=60)  # Run for 60 seconds
    """
    async with astm_server(handlers, host, port, timeout) as server:
        if duration:
            await server.serve_for(duration)
        else:
            await server.serve_forever()


# Enhanced exports with all modernization features
__all__ = [
    # Core classes
    "Client", "Server",
    
    # Configuration system
    "ClientConfig", "ServerConfig", "ConnectionConfig", "DeviceProfile",
    "ConfigManager", "TransportConfig", "FrameConfig", "RecordConfig",
    "ParserConfig", "ProfileFormat", "TransportMode", "default_config_manager",
    
    # High-level functions
    "create_client", "create_server", "astm_client", "astm_server",
    "send_astm_data", "run_astm_server",
    
    # Enhanced codec functions
    "decode", "decode_message", "decode_record", "decode_with_metadata",
    "encode", "encode_message", "encode_record", "make_checksum",
    "MessageType", "DecodingResult", "EncodingOptions",
    
    # Modern records (preferred)
    "ASTMBaseRecord", "ModernHeaderRecord", "ModernPatientRecord",
    "ModernOrderRecord", "ModernResultRecord", "ModernCommentRecord",
    "ModernTerminatorRecord",
    
    # Legacy records (backward compatibility)
    "HeaderRecord", "PatientRecord", "OrderRecord", "ResultRecord",
    "CommentRecord", "TerminatorRecord",
    
    # Enums and types
    "AbnormalFlag", "CommentType", "ConnectionState", "ErrorCode",
    "Priority", "ProcessingId", "RecordType", "ResultStatus", "Sex",
    "TerminationCode",
    
    # Data structures
    "ConnectionStatus", "MessageMetrics", "PerformanceMetrics",
    "SecurityConfig", "ValidationResult",
    
    # Enhanced exceptions
    "BaseASTMError", "InvalidState", "NotAccepted", "ProtocolError",
    "ValidationError", "ConnectionError", "TimeoutError", "ParseError",
    "ChecksumError", "ConfigurationError", "ResourceError", "SecurityError",
    "Rejected", "AggregateError", "ErrorContext", "ErrorRecovery",
    
    # Metrics and monitoring
    "MetricsCollector", "Counter", "Gauge", "Histogram", "Timer",
    "MetricPoint", "MetricSummary", "MetricType", "default_metrics",
    "prometheus_exporter", "json_exporter", "count_calls", "time_calls",
    "async_time_calls",
    
    # Utilities
    "Component", "Record",
    
    # Version info
    "__version__", "__version_info__"
]

import logging

try:
    from logging import NullHandler
except ImportError:

    class NullHandler(logging.Handler):
        def emit(self, record):
            pass


logging.getLogger(__name__).addHandler(NullHandler())
