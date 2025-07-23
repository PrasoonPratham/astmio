#
# Enhanced ASTM Server with robust resource management
#
import asyncio
import ssl
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from .codec import decode_message
from .constants import ACK, ENQ, EOT, ETB, ETX, NAK, STX
from .logging import get_logger, setup_logging
from .plugins import BasePlugin, PluginManager

log = get_logger(__name__)

__all__ = ["Server", "ServerConfig", "create_server", "astm_server"]


@dataclass
class ServerConfig:
    """Enhanced server configuration with better defaults."""

    host: str = "localhost"
    port: int = 15200
    timeout: float = 10.0  # Connection timeout
    encoding: str = "latin-1"
    max_connections: int = 100
    ssl_context: Optional[ssl.SSLContext] = None
    log_level: str = "INFO"

    @classmethod
    def from_dict(cls, data: dict) -> "ServerConfig":
        """Create config from dictionary, ignoring unknown fields."""
        valid_fields = {
            field.name for field in cls.__dataclass_fields__.values()
        }
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)


async def handle_connection(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    handlers: Dict[str, Callable],
    config: ServerConfig,
    server: "Server",
) -> None:
    """
    Enhanced connection handler with better timeout and error handling.
    """
    peername = writer.get_extra_info("peername")
    conn_log = log.bind(peername=peername)
    conn_log.info("Connection established")

    # Emit connection established event
    client_ip = peername[0] if peername else "unknown"
    server.emit_event("connection_established", client_ip)

    is_transfer_state = False
    buffer = b""

    try:
        while True:
            try:
                # Read with timeout to prevent hanging
                data = await asyncio.wait_for(
                    reader.read(1024), timeout=config.timeout
                )

                if not data:
                    conn_log.debug("Connection closed by client")
                    break

                buffer += data

                # Handle ENQ (start transfer)
                if not is_transfer_state and ENQ in buffer:
                    is_transfer_state = True
                    writer.write(ACK)
                    await writer.drain()
                    buffer = buffer[buffer.find(ENQ) + 1 :]
                    conn_log.debug("Transfer state started")
                    continue

                # Handle EOT (end transfer)
                if is_transfer_state and EOT in buffer:
                    is_transfer_state = False
                    eot_index = buffer.find(EOT)

                    # Process any message before EOT
                    if eot_index > 0:
                        message = buffer[:eot_index]
                        await process_message(
                            message, handlers, config, writer, conn_log, server
                        )

                    buffer = buffer[eot_index + 1 :]
                    conn_log.debug("Transfer state ended")
                    continue

                # Process complete messages
                if is_transfer_state:
                    while STX in buffer and (ETX in buffer or ETB in buffer):
                        stx_index = buffer.find(STX)

                        # Find frame end
                        frame_end_pos = buffer.find(ETX, stx_index)
                        if frame_end_pos == -1:
                            frame_end_pos = buffer.find(ETB, stx_index)

                        if frame_end_pos != -1:
                            # Extract complete message (including checksum)
                            message = buffer[stx_index : frame_end_pos + 5]
                            await process_message(
                                message,
                                handlers,
                                config,
                                writer,
                                conn_log,
                                server,
                            )
                            buffer = buffer[frame_end_pos + 5 :]
                        else:
                            break  # Incomplete message

            except asyncio.TimeoutError:
                conn_log.warning("Connection timeout", timeout=config.timeout)
                break
            except Exception as e:
                conn_log.error("Connection error", error=str(e))
                break

    finally:
        # Ensure cleanup
        conn_log.info("Connection closing")
        if not writer.is_closing():
            writer.close()
            try:
                await asyncio.wait_for(writer.wait_closed(), timeout=1.0)
            except asyncio.TimeoutError:
                pass  # Ignore cleanup timeout


async def process_message(
    message: bytes,
    handlers: Dict[str, Callable],
    config: ServerConfig,
    writer: asyncio.StreamWriter,
    logger,
    server: "Server",
) -> None:
    """Process a single ASTM message."""
    try:
        if not message.startswith(STX):
            return

        seq, records, checksum = decode_message(
            message, encoding=config.encoding
        )

        for record_list in records:
            if not record_list:
                continue

            record_type = record_list[0]

            # Emit record processing event for plugins
            server.emit_event("record_processed", record_list, server)

            if record_type in handlers:
                try:
                    handler = handlers[record_type]

                    # Check if handler is async
                    if asyncio.iscoroutinefunction(handler):
                        await asyncio.wait_for(
                            handler(record_list, server),
                            timeout=5.0,  # Handler timeout
                        )
                    else:
                        # Run sync handler in executor to avoid blocking
                        loop = asyncio.get_event_loop()
                        await asyncio.wait_for(
                            loop.run_in_executor(
                                None, handler, record_list, server
                            ),
                            timeout=5.0,
                        )
                except asyncio.TimeoutError:
                    logger.warning("Handler timeout", record_type=record_type)
                except Exception as e:
                    logger.error(
                        "Handler error", record_type=record_type, error=str(e)
                    )
            else:
                logger.debug(
                    "No handler for record type", record_type=record_type
                )

        # Send ACK
        if not writer.is_closing():
            writer.write(ACK)
            await writer.drain()

    except Exception as e:
        logger.error("Message processing error", error=str(e))
        if not writer.is_closing():
            writer.write(NAK)
            await writer.drain()


class Server:
    """
    Enhanced ASTM server with robust resource management.

    Key improvements:
    - Automatic timeouts on all operations
    - Better resource cleanup
    - Context manager support
    - Simplified configuration
    - Connection limits
    """

    def __init__(
        self,
        handlers: Dict[str, Callable],
        config: Optional[ServerConfig] = None,
        **kwargs,
    ):
        """Initialize server with handlers and configuration."""
        if config is None:
            config = ServerConfig(**kwargs)
        elif kwargs:
            config_dict = config.__dict__.copy()
            config_dict.update(kwargs)
            config = ServerConfig.from_dict(config_dict)

        self.config = config
        self.handlers = handlers
        self._server: Optional[asyncio.Server] = None
        self._connections: set = set()
        self._log = log.bind(server_id=f"{config.host}:{config.port}")

        # Initialize plugin manager
        self.plugin_manager = PluginManager(self)

        # Setup logging
        setup_logging(log_level=config.log_level)

    async def start(self) -> None:
        """Start the server with proper error handling."""
        if self._server:
            return

        try:
            self._log.info(
                "Starting server", host=self.config.host, port=self.config.port
            )

            self._server = await asyncio.start_server(
                self._handle_client,
                self.config.host,
                self.config.port,
                ssl=self.config.ssl_context,
            )

            addrs = ", ".join(
                str(s.getsockname()) for s in self._server.sockets
            )
            self._log.info("Server started", addresses=addrs)

        except Exception as e:
            self._log.error("Failed to start server", error=str(e))
            raise

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle individual client connections with limits."""
        if len(self._connections) >= self.config.max_connections:
            self._log.warning(
                "Connection limit reached", limit=self.config.max_connections
            )
            writer.close()
            await writer.wait_closed()
            return

        connection_task = asyncio.create_task(
            handle_connection(reader, writer, self.handlers, self.config, self)
        )

        self._connections.add(connection_task)

        try:
            await connection_task
        finally:
            self._connections.discard(connection_task)

    async def serve_forever(self) -> None:
        """Start and serve forever."""
        await self.start()
        async with self._server:
            await self._server.serve_forever()

    async def serve_for(self, duration: float) -> None:
        """Serve for a specific duration (useful for testing)."""
        await self.start()
        async with self._server:
            try:
                await asyncio.wait_for(
                    self._server.serve_forever(), timeout=duration
                )
            except asyncio.TimeoutError:
                pass  # Expected timeout

    async def close(self) -> None:
        """Close server and all connections."""
        if not self._server:
            return

        self._log.info("Shutting down server")

        # Close server
        self._server.close()

        # Cancel all connections
        for connection in self._connections:
            connection.cancel()

        # Wait for connections to close
        if self._connections:
            await asyncio.gather(*self._connections, return_exceptions=True)

        # Wait for server to close
        try:
            await asyncio.wait_for(self._server.wait_closed(), timeout=2.0)
        except asyncio.TimeoutError:
            self._log.warning("Server close timeout")

        self._server = None
        self._log.info("Server shutdown complete")

    def install_plugin(self, plugin: BasePlugin):
        """Install a plugin into the server."""
        self.plugin_manager.register_plugin(plugin)
        self._log.info(f"Plugin installed: {plugin.name}")

    def uninstall_plugin(self, plugin_name: str):
        """Uninstall a plugin from the server."""
        self.plugin_manager.unregister_plugin(plugin_name)
        self._log.info(f"Plugin uninstalled: {plugin_name}")

    def get_plugin(self, plugin_name: str) -> Optional[BasePlugin]:
        """Get a plugin by name."""
        return self.plugin_manager.get_plugin(plugin_name)

    def list_plugins(self) -> List[str]:
        """List all installed plugins."""
        return self.plugin_manager.list_plugins()

    def emit_event(self, event_name: str, *args, **kwargs):
        """Emit an event to all plugins."""
        self.plugin_manager.emit(event_name, *args, **kwargs)

    def set_profile(self, profile_config):
        """Set server profile configuration."""
        self.profile_config = profile_config
        self._log.info("Server profile configuration set")

    async def __aenter__(self):
        """Context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with guaranteed cleanup."""
        await self.close()


def create_server(
    handlers: Dict[str, Callable],
    host: str = "localhost",
    port: int = 15200,
    timeout: float = 10.0,
    encoding: str = "latin-1",
    ssl_context: Optional[ssl.SSLContext] = None,
    **kwargs,
) -> Server:
    """
    Create a server with simple, sensible defaults.

    This is the recommended way to create servers for most use cases.
    """
    config = ServerConfig(
        host=host,
        port=port,
        timeout=timeout,
        encoding=encoding,
        ssl_context=ssl_context,
        **kwargs,
    )
    return Server(handlers, config)


@asynccontextmanager
async def astm_server(
    handlers: Dict[str, Callable],
    host: str = "localhost",
    port: int = 15200,
    timeout: float = 10.0,
    **kwargs,
):
    """
    Async context manager for ASTM servers.

    Usage:
        async with astm_server(handlers, "localhost", 15200) as server:
            # Server is running
            await asyncio.sleep(10)  # Server runs for 10 seconds
    """
    server = create_server(handlers, host, port, timeout, **kwargs)
    try:
        await server.start()
        yield server
    finally:
        await server.close()
