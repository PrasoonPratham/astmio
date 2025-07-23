
# ASTMIO: Modern Asynchronous ASTM E1394/E1381 Server and Client

ASTMIO is a completely modernized, asynchronous, and feature-rich Python library for handling the ASTM E1394/E1381 protocol, commonly used in clinical laboratories. This project is a ground-up rewrite of the original `python-astm` library, built on modern Python features like `asyncio`, `structlog`, and a robust plugin system.

## Key Features

- **Fully Asynchronous:** Built on `asyncio` for high-performance, non-blocking I/O.
- **Structured Logging:** Uses `structlog` for clear, configurable, and machine-readable logs, with support for JSON formatting and SQLite storage.
- **Robust Error Handling:** A comprehensive exception hierarchy and automatic reconnection with exponential backoff.
- **Connection Pooling:** A built-in connection pool for efficient management of client connections.
- **Device Profiles:** A flexible configuration system for managing different instrument profiles and their specific quirks.
- **TLS/SSL Support:** Secure communication with TLS/SSL encryption for both the client and server.
- **Extensible Plugin System:** Easily extend the server's functionality with custom plugins for new record types, codecs, or metrics.
- **Observability:** Built-in metrics collection and a Prometheus plugin for easy integration with monitoring systems.
- **Modern Testing:** A comprehensive test suite built on `pytest` and `hypothesis`.

## Installation

```bash
pip install astmio
```

To install with optional features:

```bash
# For structured logging with SQLite
pip install astmio[logging]

# For device profiles
pip install astmio[profiles]

# For Prometheus metrics
pip install astmio[metrics]
```

## Quick Start

### Server

```python
import asyncio
from astmio.server import Server

async def main():
    server = Server()
    await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
```

### Client

```python
import asyncio
from astmio.client import Client

async def main():
    records = [
        ['H', '|||||', '20230507'],
        ['L', '1', 'N']
    ]
    client = Client()
    await client.send(records)
    client.close()
    await client.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())
```

## Documentation

For more detailed information on the API, plugins, and configuration, please refer to the full documentation (link to be added).
