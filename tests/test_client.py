import pytest
from astmio import create_client, astm_client
from .mocks import MockASTMServer


@pytest.mark.asyncio
async def test_client_connection():
    """Test that the client can connect to the server using new API."""

    def handle_header(record):
        pass  # Simple handler for testing

    def handle_terminator(record):
        pass

    handlers = {"H": handle_header, "L": handle_terminator}

    async with MockASTMServer(handlers=handlers):
        # Test using create_client
        client = create_client(timeout=2.0)

        try:
            await client.connect()
            assert client._connected
            assert client._writer is not None
            assert client._reader is not None
        finally:
            await client.close()


@pytest.mark.asyncio
async def test_client_send():
    """Test that the client can send data using new API."""

    received_records = []

    def handle_header(record):
        received_records.append(record)

    def handle_terminator(record):
        received_records.append(record)

    handlers = {"H": handle_header, "L": handle_terminator}

    async with MockASTMServer(handlers=handlers):
        records = [["H", "|||||", "20230507"], ["L", "1", "N"]]

        # Test using context manager
        async with astm_client(timeout=3.0) as client:
            success = await client.send_records(records)
            assert success


@pytest.mark.asyncio
async def test_client_timeout_handling():
    """Test that client properly handles timeouts without hanging."""

    # Test connection to non-existent server
    client = create_client(
        host="192.168.255.255",  # Non-routable IP
        port=12345,
        connect_timeout=0.5,  # Very short timeout
    )

    try:
        with pytest.raises(Exception):  # Should raise ConnectionError or similar
            await client.connect()
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_high_level_send_function():
    """Test the high-level send_astm_data function."""
    from astmio import send_astm_data

    def handle_header(record):
        pass

    def handle_terminator(record):
        pass

    handlers = {"H": handle_header, "L": handle_terminator}

    async with MockASTMServer(handlers=handlers):
        records = [["H", "|||||", "20230507"], ["L", "1", "N"]]

        # Test the one-liner function
        success = await send_astm_data(records, timeout=3.0)
        assert success
