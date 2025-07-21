#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ASTM Library - Modern, Clean API with Optional Plugin Support

A Python library for handling ASTM communication.
Install plugins with: pip install astmio[hipaa] or pip install astmio[metrics]
"""
import logging
from typing import Dict, List, Optional, Callable, Any

# Core functionality
from .client import Client, ClientConfig, create_client as _create_client, astm_client
from .server import Server, ServerConfig, create_server as _create_server, astm_server
from .codec import (
    encode,
    decode,
    encode_message,
    decode_message,
    decode_record,
    encode_record,
    decode_component,
    encode_component,
    make_checksum,
    decode_with_metadata,
    Decoder,
    Encoder,
    iter_decode,
    STX,
    ETX,
    ETB,
    ENQ,
    ACK,
    NAK,
    EOT,
    LF,
    CR,
    RECORD_SEP,
    FIELD_SEP,
    REPEAT_SEP,
    COMPONENT_SEP,
    ESCAPE_SEP,
)
from .logging import setup_logging, get_logger
from .exceptions import ASTMError, ProtocolError, ValidationError, ConfigurationError

# Data structures and records
from .records import (
    Record,
    HeaderRecord,
    PatientRecord,
    OrderRecord,
    ResultRecord,
    CommentRecord,
    TerminatorRecord,
    ScientificRecord,
    MessageHeaderRecord,
    MessageTerminatorRecord,
)
from .dataclasses import (
    DeviceProfile,
    ConnectionStatus,
    MessageMetrics,
    AuditContext,
    SecurityContext,
    MiddlewareInput,
    MiddlewareOutput,
)
from .enums import RecordType, MessageType, ErrorCode, EventType

# Configuration
from .config import CoreConfig

try:
    from .config import load_profile, validate_profile
except ImportError:

    def load_profile(path):
        raise ImportError(
            "Profile support requires PyYAML: pip install astmio[profiles]"
        )

    def validate_profile(profile):
        raise ImportError(
            "Profile support requires PyYAML: pip install astmio[profiles]"
        )


__version__ = "1.0.1"
__all__ = [
    # High-level API
    "send_astm_data",
    "run_astm_server",
    "create_comprehensive_handlers",
    # Context managers
    "astm_client",
    "astm_server",
    # Core classes
    "create_client",
    "create_server",
    "Client",
    "Server",
    "ClientConfig",
    "ServerConfig",
    # Codec
    "encode",
    "decode",
    "encode_message",
    "decode_message",
    "decode_record",
    "encode_record",
    "decode_component",
    "encode_component",
    "make_checksum",
    "decode_with_metadata",
    "Decoder",
    "Encoder",
    "iter_decode",
    # ASTM constants
    "STX",
    "ETX",
    "ETB",
    "ENQ",
    "ACK",
    "NAK",
    "EOT",
    "LF",
    "CR",
    # Separators
    "RECORD_SEP",
    "FIELD_SEP",
    "REPEAT_SEP",
    "COMPONENT_SEP",
    "ESCAPE_SEP",
    # Logging
    "setup_logging",
    "get_logger",
    # Exceptions
    "ASTMError",
    "ProtocolError",
    "ValidationError",
    "ConfigurationError",
    # Data structures
    "Record",
    "HeaderRecord",
    "PatientRecord",
    "OrderRecord",
    "ResultRecord",
    "CommentRecord",
    "TerminatorRecord",
    "ScientificRecord",
    "MessageHeaderRecord",
    "MessageTerminatorRecord",
    "DeviceProfile",
    "ConnectionStatus",
    "MessageMetrics",
    "AuditContext",
    "SecurityContext",
    "MiddlewareInput",
    "MiddlewareOutput",
    # Enums
    "RecordType",
    "MessageType",
    "ErrorCode",
    "EventType",
    # Configuration
    "ServerConfig",
    "ClientConfig",
    "CoreConfig",
]

_logger = get_logger(__name__)


def create_client(
    host: str = "localhost",
    port: int = 15200,
    timeout: float = 5.0,
    encoding: str = "latin-1",
    **kwargs,
) -> Client:
    """
    Create an ASTM client with clean API.

    Args:
        host: Server hostname
        port: Server port
        timeout: Connection timeout
        encoding: Character encoding
        **kwargs: Additional ClientConfig parameters

    Returns:
        Configured Client instance
    """
    return _create_client(host, port, timeout, encoding, **kwargs)


def create_server(
    handlers: Dict[str, Callable],
    host: str = "localhost",
    port: int = 15200,
    timeout: float = 10.0,
    plugins: Optional[List[Any]] = None,
    profile: Optional[str] = None,
    **kwargs,
) -> Server:
    """
    Create an ASTM server with clean API and plugin support.

    Args:
        handlers: Dictionary of record type handlers
        host: Server hostname
        port: Server port
        timeout: Connection timeout
        plugins: List of plugin instances (not names)
        profile: Path to profile configuration file
        **kwargs: Additional ServerConfig parameters

    Returns:
        Configured Server instance

    Examples:
        >>> from astmio.plugins.hipaa import HIPAAAuditPlugin
        >>> handlers = create_comprehensive_handlers()
        >>> server = create_server(
        ...     handlers=handlers,
        ...     plugins=[HIPAAAuditPlugin(db_path="audit.db")],
        ...     profile="profiles/mindray.yaml"
        ... )
    """
    server = _create_server(handlers, host, port, timeout, **kwargs)

    # Install plugins if specified
    if plugins:
        for plugin in plugins:
            server.install_plugin(plugin)

    # Load profile if specified
    if profile:
        try:
            profile_config = load_profile(profile)
            server.set_profile(profile_config)
        except Exception as e:
            _logger.error(f"Failed to load profile {profile}: {e}")

    return server


def create_comprehensive_handlers() -> Dict[str, Callable]:
    """
    Create comprehensive handlers for all ASTM record types.

    Returns:
        Dictionary of handlers that can be customized

    Examples:
        >>> handlers = create_comprehensive_handlers()
        >>>
        >>> # Customize patient handler
        >>> original_patient_handler = handlers['P']
        >>> def my_patient_handler(record, server):
        ...     print(f"Custom patient processing: {record}")
        ...     return original_patient_handler(record, server)
        >>> handlers['P'] = my_patient_handler
        >>>
        >>> server = create_server(handlers)
    """

    def handle_header(record, server):
        """Handle header records."""
        sender_name = record[4] if len(record) > 4 else "Unknown"
        timestamp = record[6] if len(record) > 6 else "Unknown"
        _logger.info(f"Header from {sender_name} at {timestamp}")
        return True

    def handle_patient(record, server):
        """Handle patient records."""
        if len(record) > 1:
            patient_id = record[1] if record[1] else "Unknown"
            patient_name = record[5] if len(record) > 5 else "Unknown"
            _logger.info(f"Patient: {patient_name} (ID: {patient_id})")
        return True

    def handle_order(record, server):
        """Handle order records."""
        if len(record) > 2:
            sample_id = record[1] if record[1] else "Unknown"
            test_code = record[4] if len(record) > 4 else "Unknown"
            _logger.info(f"Order: {test_code} (Sample: {sample_id})")
        return True

    def handle_result(record, server):
        """Handle result records."""
        if len(record) > 3:
            test_id = record[2] if record[2] else "Unknown"
            value = record[3] if record[3] else "Unknown"
            units = record[4] if len(record) > 4 else ""
            _logger.info(f"Result: {test_id} = {value} {units}")
        return True

    def handle_comment(record, server):
        """Handle comment records."""
        if len(record) > 2:
            comment_text = record[2] if record[2] else ""
            _logger.info(f"Comment: {comment_text}")
        return True

    def handle_terminator(record, server):
        """Handle terminator records."""
        termination_code = record[1] if len(record) > 1 else "Unknown"
        _logger.info(f"Session terminated (Code: {termination_code})")
        return True

    return {
        "H": handle_header,
        "P": handle_patient,
        "O": handle_order,
        "R": handle_result,
        "C": handle_comment,
        "L": handle_terminator,
    }


async def send_astm_data(
    records: List[List[str]],
    host: str = "localhost",
    port: int = 15200,
    timeout: float = 5.0,
    **kwargs,
) -> bool:
    """
    Send ASTM data with a single function call.

    Args:
        records: List of ASTM records to send
        host: Server hostname
        port: Server port
        timeout: Connection timeout
        **kwargs: Additional client configuration

    Returns:
        True if successful

    Examples:
        >>> records = [
        ...     ['H', '|||||', '20250701'],
        ...     ['P', '1', None, None, None, 'John Doe'],
        ...     ['L', '1', 'N']
        ... ]
        >>> success = await send_astm_data(records)
    """
    try:
        async with astm_client(host, port, timeout, **kwargs) as client:
            return await client.send_records(records)
    except Exception as e:
        _logger.error(f"Failed to send ASTM data: {e}")
        return False


async def run_astm_server(
    handlers: Dict[str, Callable],
    host: str = "localhost",
    port: int = 15200,
    timeout: float = 10.0,
    duration: Optional[float] = None,
    plugins: Optional[List[Any]] = None,
    **kwargs,
) -> None:
    """
    Run an ASTM server with clean API.

    Args:
        handlers: Dictionary of record type handlers
        host: Server hostname
        port: Server port
        timeout: Connection timeout
        duration: How long to run (None = forever)
        plugins: List of plugin instances
        **kwargs: Additional server configuration

    Examples:
        >>> from astmio.plugins.hipaa import HIPAAAuditPlugin
        >>> handlers = create_comprehensive_handlers()
        >>> await run_astm_server(
        ...     handlers=handlers,
        ...     plugins=[HIPAAAuditPlugin(db_path="audit.db")],
        ...     duration=60.0  # Run for 1 minute
        ... )
    """
    server = create_server(handlers, host, port, timeout, plugins, **kwargs)

    try:
        if duration:
            await server.serve_for(duration)
        else:
            await server.serve_forever()
    finally:
        await server.close()


# Plugin availability checks
def is_hipaa_available() -> bool:
    """Check if HIPAA plugin is available."""
    try:
        import importlib.util

        return importlib.util.find_spec("astmio.plugins.hipaa") is not None
    except ImportError:
        return False


def is_metrics_available() -> bool:
    """Check if metrics plugin is available."""
    try:
        import importlib.util

        return importlib.util.find_spec("astmio.plugins.metrics") is not None
    except ImportError:
        return False


def get_available_plugins() -> List[str]:
    """Get list of available plugins based on installed dependencies."""
    plugins = []

    if is_hipaa_available():
        plugins.append("hipaa")
    if is_metrics_available():
        plugins.append("metrics")

    return plugins


def print_plugin_status():
    """Print status of all plugins."""
    print("🔌 ASTM Library Plugin Status")
    print("=" * 40)

    plugins = [
        ("hipaa", "HIPAA Audit Plugin", "pip install astmio[hipaa]"),
        ("metrics", "Metrics Plugin", "pip install astmio[metrics]"),
        ("prometheus", "Prometheus Plugin", "pip install astmio[prometheus]"),
    ]

    for name, description, install_cmd in plugins:
        if name == "hipaa":
            available = is_hipaa_available()
        elif name in ["metrics", "prometheus"]:
            available = is_metrics_available()
        else:
            available = False

        status = "✅ Available" if available else "❌ Not installed"
        print(f"{name}: {status}")
        print(f"  {description}")
        if not available:
            print(f"  Install with: {install_cmd}")
        print()


# Set default logging handler to avoid "No handler found" warnings.
logging.getLogger(__name__).addHandler(logging.NullHandler())
