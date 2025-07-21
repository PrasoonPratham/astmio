import asyncio
import time
from typing import Set, Dict, Any

from .client import Client
from .logging import get_logger

log = get_logger(__name__)


class ConnectionPool:
    """
    A connection pool for managing ASTM clients.

    This class provides a way to manage a pool of `astmio.Client` instances,
    reducing the overhead of creating new connections for each request. It
    handles connection creation, borrowing, and releasing, as well as basic
    health checks and metrics collection.

    :param host: The server host address.
    :param port: The server port number.
    :param pool_size: The maximum number of connections to keep in the pool.
    :param client_options: Keyword arguments to be passed to the `Client`
                           constructor.
    """

    def __init__(self, host: str, port: int, pool_size: int = 10, **client_options):
        self.host = host
        self.port = port
        self.pool_size = pool_size
        self.client_options = client_options
        self._pool: asyncio.Queue = asyncio.Queue(maxsize=pool_size)
        self._connections: Set[Client] = set()
        self._lock = asyncio.Lock()
        self.metrics: Dict[str, Any] = {
            "created": 0,
            "released": 0,
            "borrowed": 0,
            "failed": 0,
            "last_used": {},
            "connection_status": {},
        }

    async def get_connection(self) -> Client:
        """
        Gets a connection from the pool.

        If the pool is empty and has not reached its maximum size, a new
        connection will be created. Otherwise, this method will wait until a
        connection becomes available.

        :return: A `Client` instance from the pool.
        """
        async with self._lock:
            if self._pool.empty() and len(self._connections) < self.pool_size:
                await self._create_connection()
        conn = await self._pool.get()
        self.metrics["borrowed"] += 1
        self.metrics["last_used"][id(conn)] = time.monotonic()
        self.metrics["connection_status"][id(conn)] = "in_use"
        return conn

    async def release_connection(self, conn: Client):
        """
        Releases a connection back to the pool, making it available for reuse.

        :param conn: The `Client` instance to release.
        """
        await self._pool.put(conn)
        self.metrics["released"] += 1
        self.metrics["connection_status"][id(conn)] = "idle"

    async def _create_connection(self):
        """
        Creates a new client connection and adds it to the pool.
        """
        log.info("Creating new connection", host=self.host, port=self.port)
        try:
            client = Client(host=self.host, port=self.port, **self.client_options)
            await client.connect()
            self._connections.add(client)
            await self._pool.put(client)
            self.metrics["created"] += 1
            self.metrics["connection_status"][id(client)] = "idle"
        except Exception as e:
            self.metrics["failed"] += 1
            log.error("Failed to create connection", error=str(e))
            raise

    async def close(self):
        """
        Closes all connections in the pool and clears the pool.
        """
        async with self._lock:
            for conn in self._connections:
                conn_id = id(conn)
                conn.close()
                await conn.wait_closed()
                if conn_id in self.metrics["connection_status"]:
                    self.metrics["connection_status"][conn_id] = "closed"
            self._connections.clear()
            self._pool = asyncio.Queue(maxsize=self.pool_size)

    async def health_check(self):
        """
        Performs a health check on all connections in the pool.

        If a connection is found to be unhealthy (e.g., closed by the peer),
        it is removed from the pool, and a new connection is created to
        replace it.
        """
        async with self._lock:
            for conn in list(self._connections):
                if not await self._is_healthy(conn):
                    self._connections.remove(conn)
                    conn_id = id(conn)
                    if conn_id in self.metrics["connection_status"]:
                        self.metrics["connection_status"][conn_id] = "unhealthy"
                    self.metrics["failed"] += 1
                    # Attempt to create a new connection to replace the unhealthy one
                    try:
                        await self._create_connection()
                    except Exception as e:
                        log.error(
                            "Failed to create replacement connection", error=str(e)
                        )

    @staticmethod
    async def _is_healthy(conn: Client) -> bool:
        """
        Checks if a single connection is healthy.

        :param conn: The `Client` instance to check.
        :return: `True` if the connection is healthy, `False` otherwise.
        """
        if conn._writer is None or conn._writer.is_closing():
            return False
        # A simple health check could be to see if we can still write to the socket
        try:
            conn._writer.write(b"")
            await conn._writer.drain()
            return True
        except (ConnectionResetError, BrokenPipeError):
            return False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
