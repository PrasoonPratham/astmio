#!/usr/bin/env python3
"""
Modern ASTM Library Example - Clean API with Plugins

This example demonstrates the new clean API with pip-like plugin installation.
It's as easy as using pip!
"""

import asyncio
import astmio

# Install plugins like pip commands
print("🚀 Installing plugins...")
astmio.install("hipaa", db_path="medical_audit.db")
astmio.install("metrics")

print(f"✅ Installed plugins: {astmio.list_installed()}")


# Define clean, simple handlers
def handle_patient(record, server):
    """Handle patient records with full server context."""
    if len(record) > 1:
        patient_id = record[1]
        patient_name = record[5] if len(record) > 5 else "Unknown"
        print(f"👤 Patient: {patient_name} (ID: {patient_id})")
        
        # Get HIPAA plugin for custom logging
        hipaa_plugin = server.get_plugin("hipaa")
        if hipaa_plugin:
            print(f"   📋 HIPAA audit logging active")


def handle_order(record, server):
    """Handle order records."""
    if len(record) > 2:
        sample_id = record[1]
        test_name = record[4] if len(record) > 4 else "Unknown"
        print(f"🧪 Order: {test_name} (Sample: {sample_id})")


def handle_result(record, server):
    """Handle result records."""
    if len(record) > 3:
        test_id = record[2]
        value = record[3]
        units = record[4] if len(record) > 4 else ""
        print(f"📊 Result: {test_id} = {value} {units}")


def handle_header(record, server):
    """Handle header records."""
    timestamp = record[6] if len(record) > 6 else "Unknown"
    print(f"📋 Header: Session started at {timestamp}")


def handle_terminator(record, server):
    """Handle terminator records."""
    print(f"🔚 Session terminated")


async def demo_clean_api():
    """Demonstrate the clean API with plugins."""
    print("\n" + "="*50)
    print("🎯 Modern ASTM Library Demo")
    print("="*50)
    
    # Define handlers
    handlers = {
        'H': handle_header,
        'P': handle_patient,
        'O': handle_order,
        'R': handle_result,
        'L': handle_terminator,
    }
    
    # Create server with plugins (super clean!)
    server = astmio.create_server(
        handlers=handlers,
        port=15203,
        plugins=["hipaa", "metrics"]  # Just plugin names!
    )
    
    print(f"🔌 Server plugins: {server.list_plugins()}")
    
    # Start server in background
    server_task = asyncio.create_task(server.serve_for(5.0))
    
    # Give server time to start
    await asyncio.sleep(0.5)
    
    # Send some test data
    test_data = [
        ['H', '\\^&|||', 'MedDevice^1.0', '', '', '', '20250101120000', ''],
        ['P', '1', '', '', '', 'John^Doe^M', '19800101', 'M'],
        ['O', '1', '12345', '^^^GLUCOSE', 'R', '20250101120000'],
        ['R', '1', '^^^GLUCOSE', '95', 'mg/dL', '70-110', 'N', 'F'],
        ['L', '1', 'N']
    ]
    
    print("\n📤 Sending test data...")
    success = await astmio.send_astm_data(test_data, port=15203)
    print(f"✅ Data sent: {success}")
    
    # Wait for server to finish
    await server_task
    
    # Generate HIPAA compliance report
    hipaa_plugin = server.get_plugin("hipaa")
    if hipaa_plugin:
        report = hipaa_plugin.generate_compliance_report(
            "2025-01-01T00:00:00Z",
            "2025-01-02T00:00:00Z"
        )
        print(f"\n📊 HIPAA Report: {report.get('summary', {})}")


async def demo_simple_usage():
    """Show how simple the library is to use."""
    print("\n" + "="*50)
    print("💡 Simple Usage Examples")
    print("="*50)
    
    # Example 1: One-liner to send data
    print("\n1️⃣ One-liner to send data:")
    records = [
        ['H', '\\^&|||', 'TestDevice'],
        ['P', '1', '', '', '', 'Jane^Smith'],
        ['L', '1', 'N']
    ]
    
    # This will fail because no server is running, but shows the API
    success = await astmio.send_astm_data(records, timeout=1.0)
    print(f"   Result: {success} (expected failure - no server)")
    
    # Example 2: Context manager client
    print("\n2️⃣ Context manager client:")
    try:
        async with astmio.astm_client(host="localhost", port=12345, timeout=1.0) as client:
            await client.send_records(records)
    except Exception as e:
        print(f"   Expected error: {type(e).__name__}")
    
    # Example 3: Simple server
    print("\n3️⃣ Simple server (2 seconds):")
    
    def simple_handler(record, server):
        print(f"   Received: {record[0]} record")
    
    handlers = {'H': simple_handler, 'P': simple_handler, 'L': simple_handler}
    
    await astmio.run_astm_server(
        handlers=handlers,
        port=15204,
        duration=2.0,
        plugins=["hipaa"]  # Even simpler plugin installation!
    )
    
    print("   Server finished")


async def demo_plugin_management():
    """Show plugin management features."""
    print("\n" + "="*50)
    print("🔌 Plugin Management Demo")
    print("="*50)
    
    # List available plugins
    print(f"📦 Available plugins: {astmio.list_installed()}")
    
    # Install a plugin with custom config
    print("\n📥 Installing HIPAA plugin with custom config...")
    astmio.install("hipaa", 
                   db_path="custom_audit.db",
                   retention_days=365,
                   auto_backup=True)
    
    # Create server and access plugin
    server = astmio.create_server(
        handlers={'H': lambda r, s: print(f"Header: {r}")},
        plugins=["hipaa"]
    )
    
    # Access plugin directly
    hipaa_plugin = server.get_plugin("hipaa")
    if hipaa_plugin:
        print(f"   HIPAA plugin version: {hipaa_plugin.version}")
        print(f"   HIPAA plugin config: {hipaa_plugin.config}")
    
    # Uninstall plugin
    print("\n📤 Uninstalling plugin...")
    astmio.uninstall("hipaa")
    print(f"   Remaining plugins: {astmio.list_installed()}")


async def main():
    """Run all demos."""
    print("🌟 Welcome to the Modern ASTM Library!")
    print("   - Clean API like requests or asyncio")
    print("   - Plugin system like pip")
    print("   - No more hanging connections")
    print("   - Fully async and robust")
    
    await demo_clean_api()
    await demo_simple_usage()
    await demo_plugin_management()
    
    print("\n" + "="*50)
    print("🎉 All demos completed!")
    print("="*50)
    
    print("\n💡 Key Features:")
    print("   • astmio.install('plugin_name') - Install plugins like pip")
    print("   • astmio.send_astm_data(records) - One-liner to send data")
    print("   • astmio.create_server(handlers, plugins=[...]) - Clean server creation")
    print("   • async with astmio.astm_client(...) - Context manager client")
    print("   • Automatic timeouts and resource cleanup")
    print("   • Full HIPAA compliance with audit plugin")
    print("   • Prometheus metrics support")
    print("   • No more hanging connections!")


if __name__ == "__main__":
    asyncio.run(main()) 