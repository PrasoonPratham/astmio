#!/usr/bin/env python3
"""
Full-Featured ASTM Server Example - Modern API

This example demonstrates a production-ready ASTM server with:
- Clean, modern API
- Plugin system for HIPAA compliance and metrics
- Comprehensive logging
- Error handling
- Profile support
"""

import asyncio
import os

import astmio

# Load plugins with new API
print("🚀 Loading plugins...")
plugins = []

# Try to load HIPAA plugin
try:
    from astmio.plugins.hipaa.hipaa import HIPAAAuditPlugin

    hipaa_plugin = HIPAAAuditPlugin(
        db_path="production_audit.db", retention_days=2555
    )
    plugins.append(hipaa_plugin)
    print("✅ HIPAA plugin loaded")
except ImportError:
    print(
        "❌ HIPAA plugin not available. Install with: pip install astmio[hipaa]"
    )

# Try to load metrics plugin
try:
    from astmio.plugins.metrics import MetricsPlugin

    metrics_plugin = MetricsPlugin()
    plugins.append(metrics_plugin)
    print("✅ Metrics plugin loaded")
except ImportError:
    print(
        "❌ Metrics plugin not available. Install with: pip install astmio[metrics]"
    )

print(f"✅ Available plugins: {[p.name for p in plugins]}")


# Modern, clean handler functions
def handle_patient(record, server):
    """Handle patient records with full context."""
    if len(record) > 1:
        patient_id = record[1] if record[1] else "Unknown"
        patient_name = record[5] if len(record) > 5 else "Unknown"

        # Extract name components for better formatting
        if "^" in patient_name:
            name_parts = patient_name.split("^")
            formatted_name = (
                f"{name_parts[1]} {name_parts[0]}"
                if len(name_parts) >= 2
                else patient_name
            )
        else:
            formatted_name = patient_name

        print(f"👤 Patient Record: {formatted_name} (ID: {patient_id})")

        # Access HIPAA plugin for additional logging
        server_hipaa_plugin = server.get_plugin("hipaa")
        if server_hipaa_plugin:
            print(f"   🔒 HIPAA audit logging active for patient {patient_id}")


def handle_order(record, server):
    """Handle order records."""
    if len(record) > 2:
        sample_id = record[1] if record[1] else "Unknown"
        test_code = record[4] if len(record) > 4 else "Unknown"

        # Parse test code for better display
        if "^^^" in test_code:
            test_name = (
                test_code.split("^^^")[1] if "^^^" in test_code else test_code
            )
        else:
            test_name = test_code

        print(f"🧪 Order Record: {test_name} (Sample: {sample_id})")


def handle_result(record, server):
    """Handle result records with value interpretation."""
    if len(record) > 3:
        test_id = record[2] if record[2] else "Unknown"
        value = record[3] if record[3] else "Unknown"
        units = record[4] if len(record) > 4 else ""
        reference_range = record[5] if len(record) > 5 else ""
        abnormal_flag = record[6] if len(record) > 6 else "N"

        # Format test ID for display
        if "^^^" in test_id:
            test_name = test_id.split("^^^")[1] if "^^^" in test_id else test_id
        else:
            test_name = test_id

        # Determine status emoji
        status_emoji = "🔴" if abnormal_flag in ["A", "H", "L"] else "🟢"

        print(f"📊 Result: {test_name} = {value} {units} {status_emoji}")
        if reference_range:
            print(f"   📏 Reference: {reference_range}")


def handle_header(record, server):
    """Handle header records."""
    sender_name = record[4] if len(record) > 4 else "Unknown"
    timestamp = record[6] if len(record) > 6 else "Unknown"

    print(f"📋 Header: Session from {sender_name} at {timestamp}")
    print(f"   🔌 Active plugins: {', '.join(server.list_plugins())}")


def handle_terminator(record, server):
    """Handle terminator records."""
    termination_code = record[1] if len(record) > 1 else "Unknown"
    print(f"🔚 Session terminated (Code: {termination_code})")

    # Generate HIPAA compliance report
    server_hipaa_plugin = server.get_plugin("hipaa")
    if server_hipaa_plugin:
        try:
            from datetime import datetime, timezone

            end_time = datetime.now(timezone.utc).isoformat()
            start_time = (
                datetime.now(timezone.utc)
                .replace(hour=0, minute=0, second=0)
                .isoformat()
            )

            report = server_hipaa_plugin.generate_compliance_report(
                start_time, end_time
            )
            if report and report.get("summary"):
                summary = report["summary"]
                print(
                    f"   📊 Today's HIPAA summary: {summary['total_events']} events, "
                    f"{summary['unique_patients']} patients"
                )
        except Exception as e:
            print(f"   ⚠️ Could not generate HIPAA report: {e}")


async def main():
    """Run the production-ready server."""
    print("🏥 Starting Production ASTM Server")
    print("=" * 50)

    # Define comprehensive handlers
    handlers = {
        "H": handle_header,
        "P": handle_patient,
        "O": handle_order,
        "R": handle_result,
        "L": handle_terminator,
    }

    # Create server with plugins and profile support
    server = astmio.create_server(
        handlers=handlers,
        port=15200,
        plugins=plugins,
        profile=(
            "etc/profiles/mindray_bs240.yaml"
            if os.path.exists("etc/profiles/mindray_bs240.yaml")
            else None
        ),
        log_level="INFO",
    )

    print(f"🔌 Server plugins: {server.list_plugins()}")
    print("🌐 Server listening on port 15200")
    print("📝 Send ASTM data to this server for processing")
    print("💡 Press Ctrl+C to stop the server")
    print("=" * 50)

    try:
        # Start server and run forever
        await server.serve_forever()
    except KeyboardInterrupt:
        print("\n⏹️  Server shutdown requested")
    except Exception as e:
        print(f"\n❌ Server error: {e}")
    finally:
        # Cleanup
        await server.close()

        # Final HIPAA report
        hipaa_plugin = server.get_plugin("hipaa")
        if hipaa_plugin:
            try:
                from datetime import datetime, timezone

                end_time = datetime.now(timezone.utc).isoformat()
                start_time = (
                    datetime.now(timezone.utc)
                    .replace(hour=0, minute=0, second=0)
                    .isoformat()
                )

                report = hipaa_plugin.generate_compliance_report(
                    start_time, end_time
                )
                if report and report.get("summary"):
                    print("\n📊 Final HIPAA Report for today:")
                    summary = report["summary"]
                    print(f"   Total events: {summary['total_events']}")
                    print(f"   Unique patients: {summary['unique_patients']}")
                    print(f"   High-risk events: {summary['high_risk_events']}")
                    print(f"   Failed attempts: {summary['failed_attempts']}")
            except Exception as e:
                print(f"   ⚠️ Could not generate final HIPAA report: {e}")

        print("\n🔒 Server stopped safely")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
