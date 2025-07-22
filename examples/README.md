# ASTM Library Examples

This directory contains examples demonstrating the clean, modern API of the ASTM library.

## 🚀 Quick Start

The ASTM library now has a clean, pip-like API that's as easy to use as requests or asyncio:

```python
import asyncio
import astmio

# Install plugins like pip
astmio.install("hipaa", db_path="audit.db")
astmio.install("metrics")

# Send data with one line
async def send_data():
    records = [
        ['H', '\\^&|||', 'TestDevice'],
        ['P', '1', '', '', '', 'John^Doe'],
        ['L', '1', 'N']
    ]
    success = await astmio.send_astm_data(records)
    print(f"Data sent: {success}")

# Run a server with plugins
async def run_server():
    def handle_patient(record, server):
        print(f"Patient: {record}")

    await astmio.run_astm_server(
        handlers={'P': handle_patient},
        plugins=["hipaa", "metrics"],
        duration=30.0  # Run for 30 seconds
    )

asyncio.run(send_data())
asyncio.run(run_server())
```

## 📁 Examples Overview

### 1. `modern_astm_example.py` - **Start Here!**
The best place to start. Shows the complete modern API with:
- ✅ Pip-like plugin installation
- ✅ One-liner data sending
- ✅ Clean server creation
- ✅ Plugin management
- ✅ Context managers
- ✅ HIPAA compliance reporting

### 2. `full_featured_server.py` - Production Ready
A production-ready server example with:
- ✅ Comprehensive record handling
- ✅ HIPAA audit logging
- ✅ Metrics collection
- ✅ Error handling
- ✅ Profile support
- ✅ Graceful shutdown

### 3. `enhanced_usage.py` - Legacy Examples
Shows various usage patterns and backward compatibility features.

### 4. `secure_client.py` - Security Examples
Demonstrates secure client connections and SSL/TLS support.

## 🔌 Plugin System

The library now has a pip-like plugin system:

```python
# Install plugins
astmio.install("hipaa", db_path="audit.db", retention_days=2555)
astmio.install("metrics")
astmio.install("prometheus")

# List installed plugins
print(astmio.list_installed())

# Create server with plugins
server = astmio.create_server(
    handlers=my_handlers,
    plugins=["hipaa", "metrics"]  # Just names!
)

# Access plugins
hipaa_plugin = server.get_plugin("hipaa")
report = hipaa_plugin.generate_compliance_report("2025-01-01", "2025-01-02")
```

## 💡 Key Features

### Clean API
- **One-liner functions**: `astmio.send_astm_data(records)`
- **Context managers**: `async with astmio.astm_client(...) as client:`
- **Simple server creation**: `astmio.create_server(handlers, plugins=[...])`

### Plugin System
- **Pip-like installation**: `astmio.install("plugin_name")`
- **Auto-discovery**: Plugins are automatically available
- **Configuration**: Pass config during installation

### HIPAA Compliance
- **Audit logging**: All patient data access is logged
- **Compliance reports**: Generate reports for audits
- **Risk assessment**: Automatic risk level assignment
- **Data retention**: Configurable retention periods

### Robust & Reliable
- **No hanging connections**: Automatic timeouts everywhere
- **Resource cleanup**: Context managers ensure cleanup
- **Error handling**: Graceful error handling throughout
- **Async-first**: Built for modern Python async/await

## 🏃 Running Examples

```bash
# Run the main modern example
python examples/modern_astm_example.py

# Run the production server
python examples/full_featured_server.py

# Run enhanced usage examples
python examples/enhanced_usage.py
```

## 🔧 Common Usage Patterns

### Client Usage
```python
# One-liner (recommended)
success = await astmio.send_astm_data(records, host="device.local")

# Context manager
async with astmio.astm_client("device.local", 15200) as client:
    success = await client.send_records(records)

# Manual client
client = astmio.create_client("device.local", 15200)
await client.connect()
success = await client.send_records(records)
await client.close()
```

### Server Usage
```python
# Simple server
def handle_patient(record, server):
    print(f"Patient: {record}")

await astmio.run_astm_server(
    handlers={'P': handle_patient},
    plugins=["hipaa"],
    duration=60.0  # Run for 1 minute
)

# Production server
server = astmio.create_server(
    handlers=comprehensive_handlers,
    plugins=["hipaa", "metrics"],
    profile="profiles/device.yaml"
)
await server.serve_forever()
```

## 📊 HIPAA Compliance

All examples include HIPAA compliance features:

```python
# Install HIPAA plugin
astmio.install("hipaa", db_path="audit.db", retention_days=2555)

# Access plugin in handlers
def handle_patient(record, server):
    hipaa_plugin = server.get_plugin("hipaa")
    if hipaa_plugin:
        # Plugin automatically logs access
        print("HIPAA audit logging active")

# Generate compliance reports
report = hipaa_plugin.generate_compliance_report("2025-01-01", "2025-01-02")
print(f"Total events: {report['summary']['total_events']}")
```

## 🎯 Migration from Old API

The new API is backward compatible, but here's how to migrate:

### Old Way
```python
from astmio.server import Server
from astmio.plugins.hipaa import HIPAAAuditPlugin

server = Server(handlers)
plugin = HIPAAAuditPlugin()
server.plugin_manager.register_plugin(plugin)
```

### New Way
```python
import astmio

astmio.install("hipaa")
server = astmio.create_server(handlers, plugins=["hipaa"])
```

## 💪 Why This API is Better

1. **Simpler**: Like pip, requests, or asyncio
2. **Cleaner**: No manual plugin management
3. **Safer**: Automatic timeouts and cleanup
4. **Faster**: Optimized for common use cases
5. **More Pythonic**: Follows modern Python patterns

## 🆘 Need Help?

- Check the examples in this directory
- Read the main README.md
- Look at the test files for more usage patterns
- The API is designed to be intuitive - if it feels complicated, we can improve it!
