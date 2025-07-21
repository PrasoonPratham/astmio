#!/usr/bin/env python3
"""
Enhanced ASTM Library Usage Examples

This demonstrates the improved, user-friendly API of the astmio library.
Key improvements:
- No more hanging connections
- Simple context managers
- Automatic timeouts
- One-liner functions for common tasks
- Better error handling
"""

import asyncio
from astmio import (
    # High-level functions (recommended)
    send_astm_data,
    run_astm_server,
    astm_client,
    astm_server,
    # Core classes for advanced use
    create_client,
    ClientConfig,
    decode,
    encode_message,
)


async def simple_client_example():
    """Example 1: Simple client usage with one-liner function."""
    print("=== Example 1: Simple Client (One-liner) ===")

    # Create some test data
    records = [
        ["H", "|||||", "20250701"],  # Header
        ["P", "1"],  # Patient
        ["O", "1", "TEST001", None, "^^^GLUCOSE"],  # Order
        ["R", "1", "^^^GLUCOSE", "95", "mg/dL", "70-110", "N"],  # Result
        ["L", "1", "N"],  # Terminator
    ]

    # Send data with a simple one-liner (will fail since no server is running)
    try:
        success = await send_astm_data(
            records,
            host="localhost",
            port=15200,
            timeout=2.0,  # Short timeout to fail quickly
        )
        print(f"Send successful: {success}")
    except Exception as e:
        print(f"Expected failure (no server): {e}")


async def context_manager_client_example():
    """Example 2: Client with context manager for resource management."""
    print("\n=== Example 2: Client with Context Manager ===")

    records = [["H", "|||||", "20250701"], ["L", "1", "N"]]

    # Using context manager ensures proper cleanup
    try:
        async with astm_client(host="localhost", port=15200, timeout=2.0) as client:
            success = await client.send_records(records)
            print(f"Send successful: {success}")
    except Exception as e:
        print(f"Expected failure (no server): {e}")


async def advanced_client_example():
    """Example 3: Advanced client configuration."""
    print("\n=== Example 3: Advanced Client Configuration ===")

    # Create custom configuration
    config = ClientConfig(
        host="localhost",
        port=15200,
        timeout=5.0,
        connect_timeout=2.0,
        read_timeout=1.0,
        max_retries=1,
        encoding="latin-1",
    )

    # Create client with custom config
    client = create_client(
        host=config.host,
        port=config.port,
        timeout=config.timeout,
        encoding=config.encoding,
    )

    try:
        await client.connect()
        print("Connected successfully")
    except Exception as e:
        print(f"Expected connection failure: {e}")
    finally:
        await client.close()


async def simple_server_example():
    """Example 4: Simple server with handlers."""
    print("\n=== Example 4: Simple Server ===")

    # Define handlers for different record types
    def handle_header(record):
        print(f"Received Header: {record[4] if len(record) > 4 else 'Unknown'}")

    def handle_patient(record):
        print(f"Received Patient: {record[1] if len(record) > 1 else 'Unknown'}")

    def handle_order(record):
        print(f"Received Order: {record[2] if len(record) > 2 else 'Unknown'}")

    def handle_result(record):
        test_id = record[2] if len(record) > 2 else "Unknown"
        value = record[3] if len(record) > 3 else "Unknown"
        units = record[4] if len(record) > 4 else "Unknown"
        print(f"Received Result: {test_id} = {value} {units}")

    def handle_terminator(record):
        print(f"Received Terminator: {record[1] if len(record) > 1 else 'Unknown'}")

    handlers = {
        "H": handle_header,
        "P": handle_patient,
        "O": handle_order,
        "R": handle_result,
        "L": handle_terminator,
    }

    # Run server for 3 seconds to demonstrate
    print("Starting server for 3 seconds...")
    try:
        await run_astm_server(
            handlers,
            host="localhost",
            port=15201,  # Different port to avoid conflicts
            timeout=5.0,
            duration=3.0,  # Run for 3 seconds
        )
        print("Server finished")
    except Exception as e:
        print(f"Server error: {e}")


async def client_server_demo():
    """Example 5: Complete client-server demo."""
    print("\n=== Example 5: Client-Server Demo ===")

    received_data = []

    # Server handlers that collect data
    def handle_any_record(record):
        received_data.append(record)
        print(f"Server received: {record[0]} record")

    handlers = {
        "H": handle_any_record,
        "P": handle_any_record,
        "O": handle_any_record,
        "R": handle_any_record,
        "L": handle_any_record,
    }

    # Run server and client together
    async with astm_server(handlers, port=15202, timeout=3.0):
        print("Server started, sending data...")

        # Give server time to start
        await asyncio.sleep(1)

        # Send data to our server
        records = [
            ["H", "|||||", "20250701"],
            ["P", "1", None, None, None, "John Doe"],
            ["O", "1", "TEST001", None, "^^^GLUCOSE"],
            ["R", "1", "^^^GLUCOSE", "95", "mg/dL", "70-110", "N"],
            ["L", "1", "N"],
        ]

        success = await send_astm_data(records, port=15202, timeout=3.0)
        print(f"Data sent successfully: {success}")

        # Wait for processing
        await asyncio.sleep(0.1)

        print(f"Server received {len(received_data)} records")


async def error_handling_example():
    """Example 6: Robust error handling."""
    print("\n=== Example 6: Error Handling ===")

    # Example of timeout handling
    print("Testing connection timeout...")
    try:
        async with astm_client(
            host="192.168.255.255",  # Non-routable IP
            port=12345,
            connect_timeout=0.5,  # Very short timeout
        ) as client:
            await client.send_records([["H", "|||||"], ["L", "1", "N"]])
    except Exception as e:
        print(f"Handled timeout gracefully: {type(e).__name__}")

    # Example of graceful degradation
    print("Testing graceful degradation...")
    success = await send_astm_data(
        [["H", "|||||"], ["L", "1", "N"]],
        host="nonexistent.host",
        port=12345,
        timeout=1.0,
    )
    print(f"Graceful failure result: {success}")


def codec_examples():
    """Example 7: Low-level codec usage."""
    print("\n=== Example 7: Codec Functions ===")

    # Encode some records
    records = [["H", "|||||", "20250701"], ["P", "1"], ["L", "1", "N"]]

    # Encode to ASTM message
    message = encode_message(1, records, "latin-1")
    print(f"Encoded message length: {len(message)} bytes")

    # Decode back
    decoded_records = decode(message)
    print(f"Decoded {len(decoded_records)} records")

    for i, record in enumerate(decoded_records):
        print(f"  Record {i}: {record[0]} (type)")


async def main():
    """Run all examples."""
    print("🚀 Enhanced ASTM Library Examples")
    print("=" * 50)

    # Run examples
    await simple_client_example()
    await context_manager_client_example()
    await advanced_client_example()
    await simple_server_example()
    await client_server_demo()
    await error_handling_example()
    codec_examples()

    print("\n✅ All examples completed!")
    print("\nKey benefits of the enhanced library:")
    print("  • No hanging connections (automatic timeouts)")
    print("  • Simple context managers for resource management")
    print("  • One-liner functions for common tasks")
    print("  • Robust error handling and graceful failures")
    print("  • Backward compatible with existing code")


if __name__ == "__main__":
    asyncio.run(main())
