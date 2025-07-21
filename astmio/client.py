# -*- coding: utf-8 -*-
#
# Enhanced ASTM Client with robust timeout and resource management
#
import asyncio
import ssl
from typing import Iterable, Optional
from contextlib import asynccontextmanager
from dataclasses import dataclass

from .codec import ASTMRecord, iter_encode
from .constants import ACK, ENQ, EOT
from .logging import get_logger
from .exceptions import ConnectionError, TimeoutError as ASTMTimeoutError
from .dataclasses import ConnectionConfig

log = get_logger(__name__)

__all__ = ["Client", "create_client", "ConnectionConfig"]


@dataclass
class ClientConfig:
    """Enhanced client configuration with better defaults."""

    host: str = "localhost"
    port: int = 15200
    encoding: str = "latin-1"
    timeout: float = 5.0  # Shorter default timeout
    connect_timeout: float = 3.0  # Separate connect timeout
    read_timeout: float = 2.0  # Separate read timeout
    max_retries: int = 2  # Fewer retries by default
    retry_delay: float = 0.5  # Shorter retry delay
    ssl_context: Optional[ssl.SSLContext] = None
    keepalive: bool = False  # Don't keep connections alive by default

    @classmethod
    def from_dict(cls, data: dict) -> "ClientConfig":
        """Create config from dictionary, ignoring unknown fields."""
        valid_fields = {field.name for field in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)


class Client:
    """
    Enhanced ASTM client with robust timeout handling and resource management.

    Key improvements:
    - Automatic timeouts on all operations
    - Better resource cleanup
    - Context manager support
    - Simplified API
    - Non-hanging operations
    """

    def __init__(self, config: Optional[ClientConfig] = None, **kwargs):
        """Initialize client with configuration."""
        if config is None:
            config = ClientConfig(**kwargs)
        elif kwargs:
            # Merge kwargs into config
            config_dict = config.__dict__.copy()
            config_dict.update(kwargs)
            config = ClientConfig.from_dict(config_dict)

        self.config = config
        self._log = log.bind(client_id=f"{config.host}:{config.port}")
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._connected = False
        self._connection_lock = asyncio.Lock()

    async def connect(self) -> None:
        """Connect to server with timeout and proper error handling."""
        if self._connected:
            return

        async with self._connection_lock:
            if self._connected:  # Double-check after acquiring lock
                return

            try:
                self._log.debug(
                    "Attempting connection",
                    host=self.config.host,
                    port=self.config.port,
                )

                # Connect with timeout
                connect_task = asyncio.open_connection(
                    self.config.host, self.config.port, ssl=self.config.ssl_context
                )

                self._reader, self._writer = await asyncio.wait_for(
                    connect_task, timeout=self.config.connect_timeout
                )

                self._connected = True
                peername = self._writer.get_extra_info("peername")
                self._log.info("Connected successfully", peername=peername)

            except asyncio.TimeoutError:
                self._log.error(
                    "Connection timeout", timeout=self.config.connect_timeout
                )
                raise ConnectionError(
                    f"Connection timeout after {self.config.connect_timeout}s"
                )
            except (OSError, ConnectionRefusedError) as e:
                self._log.error("Connection failed", error=str(e))
                raise ConnectionError(
                    f"Failed to connect to {self.config.host}:{self.config.port}: {e}"
                )

    async def _read_with_timeout(self) -> Optional[bytes]:
        """Read data with timeout and proper error handling."""
        if not self._reader:
            raise ConnectionError("Not connected")

        try:
            data = await asyncio.wait_for(
                self._reader.read(1), timeout=self.config.read_timeout
            )

            if not data:
                self._log.warning("Connection closed by peer")
                self._connected = False
                return None

            return data

        except asyncio.TimeoutError:
            self._log.error("Read timeout", timeout=self.config.read_timeout)
            self._connected = False
            raise ASTMTimeoutError(f"Read timeout after {self.config.read_timeout}s")

    async def send_records(self, records: Iterable[ASTMRecord]) -> bool:
        """
        Send ASTM records with proper timeout and error handling.

        Returns True if successful, False otherwise.
        Never hangs indefinitely.
        """
        if not self._connected:
            await self.connect()

        try:
            return await asyncio.wait_for(
                self._send_records_impl(records), timeout=self.config.timeout
            )
        except asyncio.TimeoutError:
            self._log.error("Send operation timeout", timeout=self.config.timeout)
            self._connected = False
            return False
        except Exception as e:
            self._log.error("Send failed", error=str(e))
            self._connected = False
            return False

    async def _send_records_impl(self, records: Iterable[ASTMRecord]) -> bool:
        """Internal implementation of record sending."""
        if not (self._reader and self._writer and not self._writer.is_closing()):
            return False

        # ENQ handshake
        self._log.debug("Starting ENQ handshake")
        self._writer.write(ENQ)
        await self._writer.drain()

        response = await self._read_with_timeout()
        if response != ACK:
            self._log.error("Server rejected session start", response=response)
            if self._writer and not self._writer.is_closing():
                self._writer.write(EOT)
                await self._writer.drain()
            return False

        # Send messages
        messages = list(iter_encode(records, encoding=self.config.encoding))

        for i, message in enumerate(messages):
            self._log.debug("Sending message", number=i + 1, total=len(messages))
            self._writer.write(message)
            await self._writer.drain()

            response = await self._read_with_timeout()
            if response != ACK:
                self._log.error("Message not acknowledged", message_number=i + 1)
                if self._writer and not self._writer.is_closing():
                    self._writer.write(EOT)
                    await self._writer.drain()
                return False

        # End session
        if self._writer and not self._writer.is_closing():
            self._writer.write(EOT)
            await self._writer.drain()

        self._log.info("Records sent successfully", count=len(messages))
        return True

    async def close(self) -> None:
        """Close connection with timeout to prevent hanging."""
        if not self._connected:
            return

        self._connected = False

        if self._writer:
            try:
                self._writer.close()
                await asyncio.wait_for(
                    self._writer.wait_closed(),
                    timeout=1.0,  # Short timeout for cleanup
                )
            except (asyncio.TimeoutError, Exception):
                pass  # Ignore cleanup errors
            finally:
                self._reader = None
                self._writer = None

        self._log.debug("Connection closed")

    async def __aenter__(self):
        """Context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with guaranteed cleanup."""
        await self.close()

    # Backward compatibility methods
    async def send(self, records: Iterable[ASTMRecord]) -> bool:
        """Legacy send method for backward compatibility."""
        return await self.send_records(records)

    def close_sync(self) -> None:
        """Synchronous close for cleanup in destructors."""
        if self._writer:
            try:
                self._writer.close()
            except Exception:
                pass
        self._connected = False
        self._reader = None
        self._writer = None


def create_client(
    host: str = "localhost",
    port: int = 15200,
    timeout: float = 5.0,
    encoding: str = "latin-1",
    ssl_context: Optional[ssl.SSLContext] = None,
    **kwargs,
) -> Client:
    """
    Create a client with simple, sensible defaults.

    This is the recommended way to create clients for most use cases.
    """
    config = ClientConfig(
        host=host,
        port=port,
        timeout=timeout,
        encoding=encoding,
        ssl_context=ssl_context,
        **kwargs,
    )
    return Client(config)


@asynccontextmanager
async def astm_client(
    host: str = "localhost", port: int = 15200, timeout: float = 5.0, **kwargs
):
    """
    Async context manager for ASTM client connections.

    Usage:
        async with astm_client("localhost", 15200) as client:
            success = await client.send_records(records)
    """
    client = create_client(host, port, timeout, **kwargs)
    try:
        await client.connect()
        yield client
    finally:
        await client.close()
