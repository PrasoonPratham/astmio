import argparse
import asyncio
import logging

from astmio.constants import ACK, ENCODING, ENQ, EOT, NAK, STX

# --- Configuration ---
HOST, PORT = "localhost", 15200
LOG_FORMAT = "%(asctime)s | %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, datefmt="%H:%M:%S")


def parse_log_file(filepath: str) -> list:
    """
    Parses the cleaned log file into a list of (action, bytes) tuples.
    This function is confirmed to be working correctly.
    """
    actions = []
    token_map = {
        "[STX]": "\x02",
        "[ETX]": "\x03",
        "[ETB]": "\x17",
        "[CR]": "\r",
        "[LF]": "\n",
        "[ENQ]": "\x05",
        "[ACK]": "\x06",
        "[NAK]": "\x15",
        "[EOT]": "\x04",
    }
    try:
        with open(filepath, encoding=ENCODING) as f:
            for line in f:
                line = line.strip()
                if not line or ":" not in line:
                    continue
                action_type, data_str = line.split(":", 1)
                action_type = action_type.strip().upper()
                processed_str = data_str.strip().replace("\\\\", "\\")
                for token, char in token_map.items():
                    processed_str = processed_str.replace(token, char)
                final_byte_string = processed_str.encode(ENCODING)
                actions.append((action_type, final_byte_string))
    except FileNotFoundError:
        logging.error(f"Log file not found: {filepath}")
        return []
    return actions


async def main():
    """
    Connects to the test server and runs an interactive test session,
    clearly distinguishing between data and protocol signals.
    """
    parser = argparse.ArgumentParser(
        description="Advanced ASTM Device Simulator"
    )
    parser.add_argument(
        "log_file", type=str, help="Path to the cleaned log file to replay."
    )
    args = parser.parse_args()

    logging.info("--- ASTM Client Simulator ---")
    actions = parse_log_file(args.log_file)
    if not actions:
        return

    try:
        logging.info(f"Connecting to server at {HOST}:{PORT}...")
        reader, writer = await asyncio.open_connection(HOST, PORT)
        logging.info("Connection successful.")

        # --- NEW: More detailed results tracking ---
        results = {"passed": 0, "failed": 0, "signals": 0, "skipped": 0}

        for i, (action_type, data) in enumerate(actions[:25], 1):
            if action_type != "SEND":
                results["skipped"] += 1
                continue

            writer.write(data)
            await writer.drain()

            # --- NEW: Separate logic for each type of signal ---

            # Case 1: End of Transmission (no response expected)
            if data == EOT:
                logging.info(f"[{i:02d}] SIGNAL: Sent EOT.")
                results["signals"] += 1

            # Case 2: Enquiry (handshake, expects ACK)
            elif data == ENQ:
                try:
                    response = await asyncio.wait_for(
                        reader.read(1), timeout=2.0
                    )
                    if response == ACK:
                        logging.info(
                            f"[{i:02d}] SIGNAL: Handshake successful (ENQ -> ACK)."
                        )
                        results["signals"] += 1
                    else:
                        logging.error(
                            f"[{i:02d}] ❌ FAIL: Handshake failed. Expected ACK, got {response!r}"
                        )
                        results["failed"] += 1
                except asyncio.TimeoutError:
                    logging.error(
                        f"[{i:02d}] ❌ FAIL: Server did not respond to ENQ."
                    )
                    results["failed"] += 1

            # Case 3: Data Message (expects ACK for good data, NAK for bad)
            elif data.startswith(STX):
                try:
                    response = await asyncio.wait_for(
                        reader.read(1), timeout=2.0
                    )
                    if response == ACK:
                        logging.info(
                            f"[{i:02d}] ✅ PASS: Data message acknowledged."
                        )
                        results["passed"] += 1
                    elif response == NAK:
                        logging.error(
                            f"[{i:02d}] ❌ REJECTED: Server rejected message (NAK). (Checksum Error)"
                        )
                        results["failed"] += 1
                    else:
                        logging.error(
                            f"[{i:02d}] ❌ FAIL: Unexpected response to data: {response!r}"
                        )
                        results["failed"] += 1
                except asyncio.TimeoutError:
                    logging.error(
                        f"[{i:02d}] ❌ FAIL: Server did not respond to data message."
                    )
                    results["failed"] += 1

            # Allow for a small delay between transmissions
            await asyncio.sleep(0.05)

        logging.info("Log replay complete. Closing connection.")
        writer.close()
        await writer.wait_closed()

    except ConnectionRefusedError:
        logging.error("Connection failed. Is the server running?")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}", exc_info=True)

    # --- NEW: Clearer final summary ---
    logging.info("--- Test Summary ---")
    logging.info(f"Valid Data Messages (Passed):   {results['passed']}")
    logging.error(f"Rejected/Failed Messages:       {results['failed']}")
    logging.info(f"Protocol Signals (ENQ/EOT):     {results['signals']}")
    logging.info(f"Skipped (non-SEND actions):     {results['skipped']}")
    logging.info("--------------------")


if __name__ == "__main__":
    asyncio.run(main())
