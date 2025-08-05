import argparse
import asyncio
import importlib.resources
import logging

import astmio
from astmio.plugins import BasePlugin
from astmio.plugins.records import ASTMBaseRecord, ModernRecordsPlugin

# from astmio.plugins.registry import _registry
from astmio.server import Server

# --- Configuration ---
HOST, PORT = "localhost", 15200
LOG_FORMAT = "%(asctime)s [%(levelname)-5.5s]  %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)


# --- TestState Class (this is good) ---
class TestState:
    received_records = []
    test_passed = True
    validation_failures = []


# --- NEW: Create a custom plugin specifically for testing ---
class TestAssertionPlugin(BasePlugin):
    """
    A simple plugin that hooks into the 'record_parsed' event to run
    our test assertions.
    """

    name = "test_assertion_plugin"

    def on_record_parsed(self, record: ASTMBaseRecord, server_instance):
        """
        This method is automatically called when the 'record_parsed' event is emitted.
        This is where our test logic now lives.
        """
        logging.info(
            f"EVENT 'record_parsed' received by TestPlugin for type: {getattr(record, 'record_type', 'Component')}"
        )
        print(f"✅ Parsed Object: {record.model_dump_json(indent=2)}")

        try:
            assert isinstance(record, ASTMBaseRecord)
            if hasattr(record, "record_type") and record.record_type == "P":
                assert (
                    record.patient_name is not None
                ), "Patient record is missing a name"
        except AssertionError as e:
            logging.error(
                f"⛔️ VALIDATION FAILED for record: {record}", exc_info=True
            )
            TestState.test_passed = False
            TestState.validation_failures.append(str(e))

        TestState.received_records.append(record)


async def main():
    """
    Main function to run the test harness server.
    """
    parser = argparse.ArgumentParser(description="ASTM Test Harness Server")
    parser.add_argument(
        "profile_name",
        type=str,
        help="The name of the machine profile to load (e.g., 'bs240').",
    )
    args: argparse.Namespace = parser.parse_args()

    logging.info(
        f"--- Initializing Test Harness Server for profile: {args.profile_name} ---"
    )

    try:
        PROFILE_PATH = str(
            importlib.resources.files("profiles").joinpath(
                f"{args.profile_name}.yaml"
            )
        )
        logging.info(f"Loading profile from: {PROFILE_PATH}")
    except FileNotFoundError:
        logging.error(
            f"❌ CRITICAL: Profile file not found for '{args.profile_name}'. Please ensure '{args.profile_name}.yaml' exists in the 'astmio/profiles' directory."
        )
        return
    except Exception as e:
        logging.error(
            f"Could not find profile for '{args.profile_name}'. Error: {e}"
        )
        return

    modern_records_plugin = ModernRecordsPlugin(enable_audit_trail=True)

    test_plugin = TestAssertionPlugin()

    server: Server = astmio.create_server(
        handlers=None,
        host=HOST,
        port=PORT,
        plugins=[modern_records_plugin, test_plugin],
        profile=PROFILE_PATH,
        log_level="INFO",
    )

    logging.info(
        f"🚀 Test server listening on {HOST}:{PORT}. Waiting for connections..."
    )
    logging.info(f"Loaded plugins: {server.list_plugins()}")

    try:
        await server.serve_forever()
    except asyncio.CancelledError:
        logging.info("Server shutdown requested.")
    finally:
        logging.info("--- Test Run Finished ---")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Server stopped manually.")
