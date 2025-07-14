# -*- coding: utf-8 -*-
#
# Copyright (C) 2013 Alexander Shorin
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#
import asyncio
import unittest
from astm.server import Server, BaseRecordsDispatcher
from astm import codec, constants, records
from astm.tests.utils import track_call


class TestDispatcher(BaseRecordsDispatcher):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []
        self.was_called = False

    def __call__(self, message):
        self.was_called = True
        super().__call__(message)

    def on_header(self, record):
        self.records.append(record)

    def on_patient(self, record):
        self.records.append(record)

    def on_order(self, record):
        self.records.append(record)

    def on_result(self, record):
        self.records.append(record)

    def on_comment(self, record):
        self.records.append(record)

    def on_terminator(self, record):
        self.records.append(record)


class ServerTestCase(unittest.IsolatedAsyncioTestCase):
    host = '127.0.0.1'
    port = 0

    async def asyncSetUp(self):
        self.dispatcher = TestDispatcher()
        self.server = Server(
            host=self.host, port=self.port, dispatcher=lambda *a, **kw: self.dispatcher
        )
        await self.server.start()
        self.host, self.port = self.server._server.sockets[0].getsockname()

    async def asyncTearDown(self):
        self.server.close()
        await self.server.wait_closed()

    async def test_full_session(self):
        reader, writer = await asyncio.open_connection(self.host, self.port)

        # Start session
        writer.write(constants.ENQ)
        await writer.drain()
        response = await reader.read(1)
        self.assertEqual(response, constants.ACK)

        # Send header
        header = records.HeaderRecord()
        message = codec.encode_message(1, [header.to_astm()])
        writer.write(message)
        await writer.drain()
        response = await reader.read(1)
        self.assertEqual(response, constants.ACK)
        
        # Send terminator
        terminator = records.TerminatorRecord()
        message = codec.encode_message(2, [terminator.to_astm()])
        writer.write(message)
        await writer.drain()
        response = await reader.read(1)
        self.assertEqual(response, constants.ACK)

        # End session
        writer.write(constants.EOT)
        await writer.drain()

        # Check dispatcher calls
        self.assertTrue(self.dispatcher.was_called)
        self.assertEqual(len(self.dispatcher.records), 2)
        self.assertEqual(self.dispatcher.records[0][0], 'H')
        self.assertEqual(self.dispatcher.records[1][0], 'L')
        
        writer.close()
        await writer.wait_closed()


class RecordsDispatcherTestCase(unittest.TestCase):

    def setUp(self):
        d = BaseRecordsDispatcher()
        for key, value in d.dispatch.items():
            d.dispatch[key] = track_call(value)
        d.on_unknown = track_call(d.on_unknown)
        self.dispatcher = d

    def test_dispatch_header(self):
        message = codec.encode_message(1, [['H']], 'ascii')
        self.dispatcher(message)
        self.assertTrue(self.dispatcher.dispatch['H'].was_called)

    def test_dispatch_comment(self):
        message = codec.encode_message(1, [['C']], 'ascii')
        self.dispatcher(message)
        self.assertTrue(self.dispatcher.dispatch['C'].was_called)

    def test_dispatch_patient(self):
        message = codec.encode_message(1, [['P']], 'ascii')
        self.dispatcher(message)
        self.assertTrue(self.dispatcher.dispatch['P'].was_called)

    def test_dispatch_order(self):
        message = codec.encode_message(1, [['O']], 'ascii')
        self.dispatcher(message)
        self.assertTrue(self.dispatcher.dispatch['O'].was_called)

    def test_dispatch_result(self):
        message = codec.encode_message(1, [['R']], 'ascii')
        self.dispatcher(message)
        self.assertTrue(self.dispatcher.dispatch['R'].was_called)

    def test_dispatch_scientific(self):
        message = codec.encode_message(1, [['S']], 'ascii')
        self.dispatcher(message)
        self.assertTrue(self.dispatcher.dispatch['S'].was_called)

    def test_dispatch_manufacturer_info(self):
        message = codec.encode_message(1, [['M']], 'ascii')
        self.dispatcher(message)
        self.assertTrue(self.dispatcher.dispatch['M'].was_called)

    def test_dispatch_terminator(self):
        message = codec.encode_message(1, [['L']], 'ascii')
        self.dispatcher(message)
        self.assertTrue(self.dispatcher.dispatch['L'].was_called)

    def test_wrap_before_dispatch(self):
        class Thing(object):
            def __init__(self, *args):
                self.args = args
        def handler(record):
            assert isinstance(record, Thing)
        message = codec.encode_message(1, [['H']], 'ascii')
        self.dispatcher.wrappers['H'] = Thing
        self.dispatcher.dispatch['H'] = track_call(handler)
        self.dispatcher(message)
        self.assertTrue(self.dispatcher.dispatch['H'].was_called)

    def test_provide_default_handler_for_unknown_message_type(self):
        message = codec.encode_message(1, [['FOO']], 'ascii')
        self.dispatcher(message)
        self.assertTrue(self.dispatcher.on_unknown.was_called)


if __name__ == '__main__':
    unittest.main()
