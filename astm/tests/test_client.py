# -*- coding: utf-8 -*-
#
# Copyright (C) 2012 Alexander Shorin
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#
import asyncio
import unittest
from astm.client import Client
from astm import records, constants


class MockServer:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self._server = None
        self.requests = []
        self.response_map = {}

    async def handle_connection(self, reader, writer):
        peername = writer.get_extra_info('peername')
        self.requests.append(('connect', peername))
        while True:
            try:
                data = await reader.read(1024)
                if not data:
                    break
                self.requests.append(('data', data))
                
                response = self.get_response(data)
                if response:
                    writer.write(response)
                    await writer.drain()

            except ConnectionResetError:
                break
        writer.close()
        await writer.wait_closed()

    def get_response(self, data):
        if data == constants.ENQ:
            return self.response_map.get('enq', constants.ACK)
        if data.endswith(b'\r'):
             return self.response_map.get('message', constants.ACK)
        if data == constants.EOT:
            return self.response_map.get('eot', None)
        return None

    async def start(self):
        self._server = await asyncio.start_server(
            self.handle_connection, self.host, self.port)

    async def stop(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()


class ClientTestCase(unittest.IsolatedAsyncioTestCase):
    host = '127.0.0.1'
    port = 0

    async def asyncSetUp(self):
        self.server = MockServer(self.host, self.port)
        await self.server.start()
        self.host, self.port = self.server._server.sockets[0].getsockname()
        self.client = Client(host=self.host, port=self.port)

    async def asyncTearDown(self):
        await self.server.stop()
        self.client.close()
        await self.client.wait_closed()

    async def test_send_records(self):
        recs = [
            records.HeaderRecord().to_astm(),
            records.TerminatorRecord().to_astm()
        ]
        
        # Expect server to ACK all messages
        self.server.response_map = {
            'enq': constants.ACK,
            'message': constants.ACK,
            'eot': None
        }
        
        result = await self.client.send(recs)
        self.assertTrue(result)
        
        # Verify the sequence of requests received by the mock server
        self.assertEqual(self.server.requests[0][0], 'connect')
        self.assertEqual(self.server.requests[1], ('data', constants.ENQ))
        self.assertIn(b'H|', self.server.requests[2][1])
        self.assertIn(b'L|', self.server.requests[3][1])
        self.assertEqual(self.server.requests[4], ('data', constants.EOT))

    async def test_server_naks_message(self):
        recs = [
            records.HeaderRecord().to_astm(),
        ]

        # Expect server to NAK the message
        self.server.response_map = {
            'enq': constants.ACK,
            'message': constants.NAK
        }
        
        result = await self.client.send(recs)
        self.assertFalse(result)
        
        # Verify the client sends EOT after a NAK
        self.assertEqual(self.server.requests[3], ('data', constants.EOT))


if __name__ == '__main__':
    unittest.main()
