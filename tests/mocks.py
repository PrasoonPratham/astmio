import asyncio

from astmio import create_server


class MockASTMServer:
    """
    Enhanced mock ASTM server using the new simplified API.
    """

    def __init__(self, host="127.0.0.1", port=15200, handlers=None, **options):
        self.host = host
        self.port = port
        self.handlers = handlers or {}

        # Set reasonable defaults for testing
        options.setdefault("timeout", 2.0)

        self.server = create_server(
            handlers=self.handlers, host=host, port=port, **options
        )
        self._is_running = False

    async def start(self):
        """Start the mock server."""
        if self._is_running:
            return

        try:
            await self.server.start()
            self._is_running = True
            # Brief pause to let server fully start
            await asyncio.sleep(0.1)
        except Exception:
            self._is_running = False
            raise

    async def stop(self):
        """Stop the mock server."""
        if not self._is_running:
            return

        self._is_running = False

        try:
            await self.server.close()
        except Exception:
            pass  # Ignore cleanup errors

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()
