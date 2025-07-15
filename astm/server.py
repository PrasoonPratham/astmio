# -*- coding: utf-8 -*-
#
# Copyright (C) 2013 Alexander Shorin
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#
import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Type, Union

from .codec import decode_message, is_chunked_message, join, ASTMRecord
from .constants import ACK, EOT, NAK, ENQ, ENCODING

log = logging.getLogger(__name__)

__all__ = ["BaseRecordsDispatcher", "Server"]


class BaseRecordsDispatcher:
    """Abstract dispatcher of received ASTM records.
    You need to override its handlers or extend the dispatcher for your needs.
    """

    encoding = ENCODING

    def __init__(self, encoding: Optional[str] = None) -> None:
        self.encoding = encoding or self.encoding
        self.dispatch: Dict[str, Callable[[Any], None]] = {
            "H": self.on_header,
            "C": self.on_comment,
            "P": self.on_patient,
            "O": self.on_order,
            "R": self.on_result,
            "S": self.on_scientific,
            "M": self.on_manufacturer_info,
            "L": self.on_terminator,
        }
        self.wrappers: Dict[str, Type[Any]] = {}

    def __call__(self, message: bytes) -> None:
        """
        Decodes and dispatches incoming message.

        :param message: Message to dispatch.
        :type message: bytes
        """
        seq, records, cs = decode_message(message, self.encoding)
        for record in records:
            handler = self.dispatch.get(record[0], self.on_unknown)
            handler(self.wrap(record))

    def wrap(self, record: ASTMRecord) -> Any:
        """
        Wraps record to high-level object if wrapper is defined.

        :param record: ASTM record.
        :type record: list

        :return: High-level wrapper or raw record.
        """
        rtype = record[0]
        if rtype in self.wrappers:
            return self.wrappers[rtype](*record)
        return record

    def _default_handler(self, record: Any) -> None:
        log.warning("Record remains unprocessed: %s", record)

    def on_header(self, record: Any) -> None:
        """Header record handler."""
        self._default_handler(record)

    def on_comment(self, record: Any) -> None:
        """Comment record handler."""
        self._default_handler(record)

    def on_patient(self, record: Any) -> None:
        """Patient record handler."""
        self._default_handler(record)

    def on_order(self, record: Any) -> None:
        """Order record handler."""
        self._default_handler(record)

    def on_result(self, record: Any) -> None:
        """Result record handler."""
        self._default_handler(record)

    def on_scientific(self, record: Any) -> None:
        """Scientific record handler."""
        self._default_handler(record)

    def on_manufacturer_info(self, record: Any) -> None:
        """Manufacturer information record handler."""
        self._default_handler(record)

    def on_terminator(self, record: Any) -> None:
        """Terminator record handler."""
        self._default_handler(record)

    def on_unknown(self, record: Any) -> None:
        """Fallback handler for dispatcher."""
        self._default_handler(record)


async def handle_connection(
    reader: asyncio.StreamReader, 
    writer: asyncio.StreamWriter, 
    dispatcher: BaseRecordsDispatcher, 
    encoding: Optional[str], 
    timeout: Optional[Union[int, float]]
) -> None:
    """
    Handles single client connection.
    """
    chunks: List[bytes] = []
    is_transfer_state = False
    peername = writer.get_extra_info("peername")
    log.info("Connection from %s", peername)

    async def read(n: int = 1) -> Optional[bytes]:
        try:
            return await asyncio.wait_for(reader.read(n), timeout)
        except asyncio.TimeoutError:
            log.warning("Connection timed out for %s", peername)
            writer.close()
            await writer.wait_closed()
            return None

    while True:
        data = await read()
        if not data:
            break

        if data == ENQ:
            if not is_transfer_state:
                is_transfer_state = True
                writer.write(ACK)
                await writer.drain()
            else:
                log.error("ENQ is not expected.")
                writer.write(NAK)
                await writer.drain()

        elif data == EOT:
            if is_transfer_state:
                is_transfer_state = False
            else:
                log.error("EOT is not expected.")

        elif data in (ACK, NAK):
            log.warning("%r is not expected on server side.", data)

        else:  # Message frame
            if not is_transfer_state:
                log.error("Message frame is not expected.")
                writer.write(NAK)
                await writer.drain()
                continue

            frame = data + await reader.readuntil(b"\r")

            try:
                if is_chunked_message(frame):
                    chunks.append(frame)
                elif chunks:
                    chunks.append(frame)
                    dispatcher(join(chunks))
                    chunks = []
                else:
                    dispatcher(frame)
                writer.write(ACK)
                await writer.drain()
            except Exception:
                log.exception("Error handling message: %r", frame)
                writer.write(NAK)
                await writer.drain()

    log.info("Connection closed for %s", peername)


class Server:
    """
    Asynchronous ASTM server.

    :param host: Server IP address or hostname.
    :type host: str

    :param port: Server port number.
    :type port: int

    :param dispatcher: Custom request handler records dispatcher.
                       If omitted the :class:`BaseRecordsDispatcher` will be
                       used by default.
    :type dispatcher: :class:`BaseRecordsDispatcher`

    :param timeout: Connection timeout in seconds.
    :type timeout: int

    :param encoding: Dispatcher's encoding.
    :type encoding: str
    """

    dispatcher = BaseRecordsDispatcher

    def __init__(
        self, 
        host: str = "localhost", 
        port: int = 15200, 
        dispatcher: Optional[Type[BaseRecordsDispatcher]] = None, 
        timeout: Optional[Union[int, float]] = None, 
        encoding: Optional[str] = None
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.encoding = encoding
        if dispatcher is not None:
            self.dispatcher = dispatcher
        self._server: Optional[asyncio.Server] = None

    async def start(self) -> None:
        """Starts the server."""
        self._server = await asyncio.start_server(
            lambda r, w: handle_connection(
                r,
                w,
                self.dispatcher(encoding=self.encoding),
                self.encoding,
                self.timeout,
            ),
            self.host,
            self.port,
        )
        addrs = ", ".join(str(s.getsockname()) for s in self._server.sockets)
        log.info("Serving on %s", addrs)

    async def serve_forever(self) -> None:
        """Starts the server and waits until it is stopped."""
        if self._server is None:
            await self.start()
        async with self._server:
            await self._server.serve_forever()

    def close(self) -> None:
        """Stops the server."""
        if self._server:
            self._server.close()

    async def wait_closed(self) -> None:
        """Waits until server is fully closed."""
        if self._server:
            await self._server.wait_closed()
