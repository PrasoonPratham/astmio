#!/usr/bin/env python3
"""
Production ASTM Library Example

This example demonstrates the proper usage of the ASTM library with:
- Proper pip-style plugin installation: pip install astmio[hipaa]
- Full control over configuration and handlers
- JSONB-based HIPAA audit logging
- Comprehensive error handling
- Production-ready patterns

Installation:
    pip install astmio[hipaa]  # For HIPAA audit logging
    pip install astmio[metrics]  # For metrics collection
    pip install astmio[full]  # For all features
"""

import asyncio
import logging
from datetime import datetime, timezone

import astmio


def setup_production_logging():
    """Setup production-grade logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("astm_production.log"),
            logging.StreamHandler(),
        ],
    )


def create_production_handlers():
    """Create comprehensive handlers with proper error handling."""

    def handle_header(record, server):
        """Handle header records with full validation."""
        try:
            sender = record[4] if len(record) > 4 else "Unknown"
            timestamp = record[6] if len(record) > 6 else "Unknown"

            print(f"📋 Session started from {sender} at {timestamp}")

            # Access HIPAA plugin for additional auditing
            hipaa_plugin = server.get_plugin("hipaa") if server else None
            if hipaa_plugin:
                print("   🔒 HIPAA audit logging active")

            return True

        except Exception as e:
            logging.error(f"Error processing header record: {e}")
            return False

    def handle_patient(record, server):
        """Handle patient records with PHI protection."""
        try:
            patient_id = (
                record[1] if len(record) > 1 and record[1] else "Unknown"
            )

            # Parse patient name safely
            patient_name = "Unknown"
            if len(record) > 5 and record[5]:
                name_parts = record[5].split("^")
                if len(name_parts) >= 2:
                    patient_name = f"{name_parts[1]} {name_parts[0]}"
                else:
                    patient_name = record[5]

            print(f"👤 Patient: {patient_name} (ID: {patient_id})")

            # Additional processing for demographics
            if len(record) > 7 and record[7]:
                birth_date = record[7]
                print(f"   📅 Birth Date: {birth_date}")

            if len(record) > 8 and record[8]:
                gender = record[8]
                print(f"   ⚧ Gender: {gender}")

            return True

        except Exception as e:
            logging.error(f"Error processing patient record: {e}")
            return False

    def handle_order(record, server):
        """Handle order records with test validation."""
        try:
            sample_id = (
                record[1] if len(record) > 1 and record[1] else "Unknown"
            )

            # Parse test information
            test_info = "Unknown"
            if len(record) > 4 and record[4]:
                test_code = record[4]
                if "^^^" in test_code:
                    test_info = test_code.split("^^^")[1]
                else:
                    test_info = test_code

            print(f"🧪 Order: {test_info} (Sample: {sample_id})")

            # Parse collection date/time
            if len(record) > 6 and record[6]:
                collection_time = record[6]
                print(f"   ⏰ Collection Time: {collection_time}")

            return True

        except Exception as e:
            logging.error(f"Error processing order record: {e}")
            return False

    def handle_result(record, server):
        """Handle result records with clinical validation."""
        try:
            test_id = record[2] if len(record) > 2 and record[2] else "Unknown"
            value = record[3] if len(record) > 3 and record[3] else "Unknown"
            units = record[4] if len(record) > 4 else ""
            reference_range = record[5] if len(record) > 5 else ""
            abnormal_flag = record[6] if len(record) > 6 else "N"

            # Parse test name
            test_name = test_id
            if "^^^" in test_id:
                test_name = test_id.split("^^^")[1]

            # Determine clinical significance
            status_emoji = "🟢"  # Normal
            if abnormal_flag in ["H", "HH"]:
                status_emoji = "🔴"  # High
            elif abnormal_flag in ["L", "LL"]:
                status_emoji = "🔵"  # Low
            elif abnormal_flag in ["A", "AA"]:
                status_emoji = "🟡"  # Abnormal

            print(f"📊 Result: {test_name} = {value} {units} {status_emoji}")

            if reference_range:
                print(f"   📏 Reference Range: {reference_range}")

            if abnormal_flag != "N":
                print(f"   ⚠️  Abnormal Flag: {abnormal_flag}")

            return True

        except Exception as e:
            logging.error(f"Error processing result record: {e}")
            return False

    def handle_comment(record, server):
        """Handle comment records."""
        try:
            comment = record[2] if len(record) > 2 and record[2] else ""
            print(f"💬 Comment: {comment}")
            return True

        except Exception as e:
            logging.error(f"Error processing comment record: {e}")
            return False

    def handle_terminator(record, server):
        """Handle terminator records with session summary."""
        try:
            termination_code = (
                record[1] if len(record) > 1 and record[1] else "Unknown"
            )
            print(f"🔚 Session terminated (Code: {termination_code})")

            # Generate session summary if HIPAA plugin is available
            hipaa_plugin = server.get_plugin("hipaa") if server else None
            if hipaa_plugin:
                try:
                    end_time = datetime.now(timezone.utc).isoformat()
                    start_time = (
                        datetime.now(timezone.utc)
                        .replace(hour=0, minute=0, second=0, microsecond=0)
                        .isoformat()
                    )

                    report = hipaa_plugin.generate_compliance_report(
                        start_time, end_time
                    )
                    if report and report.get("summary"):
                        summary = report["summary"]
                        print("   📊 Session Summary:")
                        print(
                            f"      • Total Events: {summary.get('total_events', 0)}"
                        )
                        print(
                            "      • Unique Patients: "
                            f"{summary.get('unique_patients', 0)}"
                        )
                        print(
                            "      • High Risk Events: "
                            f"{summary.get('high_risk_events', 0)}"
                        )

                        # Check audit integrity
                        integrity = hipaa_plugin.verify_audit_integrity()
                        status = integrity.get("integrity_status", "UNKNOWN")
                        print(f"      • Audit Integrity: {status}")

                except Exception as e:
                    logging.error(f"Error generating HIPAA report: {e}")

            return True

        except Exception as e:
            logging.error(f"Error processing terminator record: {e}")
            return False

    return {
        "H": handle_header,
        "P": handle_patient,
        "O": handle_order,
        "R": handle_result,
        "C": handle_comment,
        "L": handle_terminator,
    }


async def run_production_server():
    """Run a production-ready ASTM server."""
    print("🏥 Starting Production ASTM Server")
    print("=" * 50)

    # Setup logging
    setup_production_logging()

    # Check available plugins
    print(f"📦 Available plugins: {astmio.get_available_plugins()}")

    # Create handlers
    handlers = create_production_handlers()

    # Create plugins list
    plugins = []

    # Add HIPAA plugin if available
    if astmio.is_hipaa_available():
        try:
            from astmio.plugins.hipaa import HIPAAAuditPlugin

            # Create HIPAA plugin with production settings
            hipaa_plugin = HIPAAAuditPlugin(
                db_path="production_hipaa_audit.db",
                retention_days=2555,  # 7 years
                auto_backup=True,
                session_timeout=3600,  # 1 hour
            )
            plugins.append(hipaa_plugin)
            print("✅ HIPAA audit plugin loaded")

        except ImportError:
            print(
                "❌ HIPAA plugin not available. Install with: pip install astmio[hipaa]"
            )

    # Add metrics plugin if available
    if astmio.is_metrics_available():
        try:
            from astmio.plugins.metrics import MetricsPlugin

            metrics_plugin = MetricsPlugin()
            plugins.append(metrics_plugin)
            print("✅ Metrics plugin loaded")

        except ImportError:
            print(
                "❌ Metrics plugin not available. "
                "Install with: pip install astmio[metrics]"
            )

    # Create server with full configuration
    server = astmio.create_server(
        handlers=handlers,
        host="0.0.0.0",  # Listen on all interfaces
        port=15200,
        timeout=30.0,  # 30 second timeout
        plugins=plugins,
        max_connections=50,
        log_level="INFO",
    )

    print(f"🔌 Loaded plugins: {server.list_plugins()}")
    print("🌐 Server listening on port 15200")
    print("📝 Ready to receive ASTM data")
    print("💡 Press Ctrl+C to stop the server")
    print("=" * 50)

    try:
        # Run server
        await server.serve_forever()

    except KeyboardInterrupt:
        print("\n⏹️  Server shutdown requested")

    except Exception as e:
        print(f"\n❌ Server error: {e}")
        logging.error(f"Server error: {e}")

    finally:
        # Cleanup
        await server.close()

        # Final reports
        hipaa_plugin = server.get_plugin("hipaa")
        if hipaa_plugin:
            print("\n📊 Final HIPAA Compliance Report:")
            try:
                end_time = datetime.now(timezone.utc).isoformat()
                start_time = (
                    datetime.now(timezone.utc)
                    .replace(hour=0, minute=0, second=0, microsecond=0)
                    .isoformat()
                )

                report = hipaa_plugin.generate_compliance_report(
                    start_time, end_time
                )
                if report and report.get("summary"):
                    summary = report["summary"]
                    print(
                        f"   📈 Total Events: {summary.get('total_events', 0)}"
                    )
                    print(
                        f"   👥 Unique Patients: {summary.get('unique_patients', 0)}"
                    )
                    print(
                        f"   🔴 High Risk Events: {summary.get('high_risk_events', 0)}"
                    )
                    print(
                        f"   ❌ Failed Attempts: {summary.get('failed_attempts', 0)}"
                    )
                    print(
                        "   🏛️ Compliance Status: "
                        f"{report.get('compliance_status', 'UNKNOWN')}"
                    )

            except Exception as e:
                print(f"   ⚠️ Could not generate final report: {e}")

        print("\n🔒 Server stopped safely")


async def demo_client_usage():
    """Demonstrate client usage with the production server."""
    print("\n📤 Sending test data to production server...")

    # Sample medical data
    test_records = [
        # Header record
        ["H", "\\^&|||", "ACME^LAB^1.0", "", "", "", "20250101120000", ""],
        # Patient record
        ["P", "1", "PAT001", "", "", "Doe^John^M", "19850615", "M"],
        # Order record
        ["O", "1", "SAMPLE001", "", "^^^GLUCOSE", "R", "20250101120000"],
        # Result record
        ["R", "1", "^^^GLUCOSE", "150", "mg/dL", "70-110", "H", "F"],
        # Comment record
        ["C", "1", "High glucose level - recommend dietary consultation"],
        # Terminator record
        ["L", "1", "N"],
    ]

    try:
        # Send data using the high-level API
        success = await astmio.send_astm_data(
            test_records, host="localhost", port=15200, timeout=10.0
        )

        if success:
            print("✅ Test data sent successfully")
        else:
            print("❌ Failed to send test data")

    except Exception as e:
        print(f"❌ Client error: {e}")


def main():
    """Main function."""
    print("🌟 Production ASTM Library Example")
    print("   Install plugins with:")
    print("   • pip install astmio[hipaa]  # HIPAA audit logging")
    print("   • pip install astmio[metrics]  # Metrics collection")
    print("   • pip install astmio[full]  # All features")
    print()

    # Print plugin status
    astmio.print_plugin_status()

    # Run the production server
    asyncio.run(run_production_server())


if __name__ == "__main__":
    main()
