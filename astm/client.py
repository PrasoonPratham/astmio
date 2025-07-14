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
from .codec import encode
from .constants import ACK, ENQ, EOT, NAK, ENCODING
from .exceptions import NotAccepted
from .mapping import Record

log = logging.getLogger(__name__)

__all__ = ['Client']


class Client:
    """
    Asynchronous ASTM client.

    :param host: Server IP address or hostname.
    :type host: str

    :param port: Server port number.
    :type port: int

    :param encoding: Data encoding.
    :type encoding: str

    :param timeout: Time to wait for response from server in seconds.
    :type timeout: int
    """
    encoding = ENCODING

    def __init__(self, host='localhost', port=15200,
                 encoding=None, timeout=10):
        self.host = host
        self.port = port
        self.encoding = encoding or self.encoding
        self.timeout = timeout
        self._reader = None
        self._writer = None

    async def connect(self):
        """
        Connects to the server.
        """
        self._reader, self._writer = await asyncio.open_connection(
            self.host, self.port)
        peername = self._writer.get_extra_info('peername')
        log.info('Connection established to %s', peername)

    async def _read(self):
        try:
            return await asyncio.wait_for(self._reader.read(1), self.timeout)
        except asyncio.TimeoutError:
            log.error('Connection timed out.')
            self.close()
            await self.wait_closed()
            return None

    async def send(self, records, chunk_size=None):
        """
        Sends ASTM records to the server.

        :param records: An iterable of ASTM records. Each record should be a
                        list or a :class:`~astm.mapping.Record` object.
        :param chunk_size: The size of each data chunk in bytes. If `None`,
                           the data will not be chunked.
        :type chunk_size: int or None

        :return: `True` if all records were sent and acknowledged, `False`
                 otherwise.
        :rtype: bool
        """
        if not (self._reader and self._writer):
            await self.connect()

        self._writer.write(ENQ)
        await self._writer.drain()

        response = await self._read()
        if response != ACK:
            log.error('Server did not acknowledge session start.')
            self._writer.write(EOT)
            await self._writer.drain()
            return False

        messages = encode(records, encoding=self.encoding, chunk_size=chunk_size)

        for message in messages:
            self._writer.write(message)
            await self._writer.drain()
            response = await self._read()
            if response != ACK:
                log.error('Server did not acknowledge message: %r', message)
                self._writer.write(EOT)
                await self._writer.drain()
                return False
        
        self._writer.write(EOT)
        await self._writer.drain()
        log.info('Session finished successfully.')
        return True

    def close(self):
        """
        Closes the connection to the server.
        """
        if self._writer:
            self._writer.close()

    async def wait_closed(self):
        """
        Waits until the connection is fully closed.
        """
        if self._writer:
            await self._writer.wait_closed()
            self._reader = None
            self._writer = None
            log.info('Connection closed.')
