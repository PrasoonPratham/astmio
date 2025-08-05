#!/usr/bin/env python3
"""
Modern Plugin Architecture Example for ASTM Library

This example demonstrates how to use the new plugin-based architecture for ASTM record processing.
It shows:
1. How to initialize and configure plugins
2. How to use the ModernRecordsPlugin for record processing
3. How to integrate with HIPAA audit logging
4. How to monitor performance with metrics
5. How to extend the system with custom plugins

This is designed to be a practical guide for LIS implementation.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from astmio.constants import ENCODING, RECORD_SEP
from astmio.decoder import decode_frame
from astmio.exceptions import BaseASTMError, NotAccepted, ValidationError
from astmio.io import load_profile_from_file
from astmio.logging import get_logger
from astmio.plugins import PluginManager, install_plugin
from astmio.profile import DeviceProfile

log = get_logger(__name__)


@dataclass
class ProcessingResult:
    """Result of ASTM record processing."""

    success: bool
    record_type: str
    record_data: Optional[Any] = None
    error_message: Optional[str] = None
    processing_time_ms: Optional[float] = None
    audit_event_id: Optional[int] = None


class ModernASTMProcessor:
    """
    Modern ASTM processor using the plugin architecture.

    This class demonstrates how to build a production-ready ASTM processor
    using the plugin system for modularity and extensibility.
    """

    def __init__(
        self,
        profile_path: str,
        enable_hipaa_audit: bool = True,
        enable_metrics: bool = True,
        enable_custom_logging: bool = False,
    ):
        """
        Initialize the modern ASTM processor with plugins.

        Args:
            profile_path: Path to device profile YAML file
            enable_hipaa_audit: Whether to enable HIPAA audit logging
            enable_metrics: Whether to enable metrics collection
            enable_custom_logging: Whether to enable custom logging plugin
        """
        self.profile_path = profile_path
        self.profile: Optional[DeviceProfile] = None

        # Initialize plugin manager
        self.plugin_manager = PluginManager()

        # Install and configure plugins
        self._setup_plugins(
            enable_hipaa_audit, enable_metrics, enable_custom_logging
        )

        # Load device profile
        self._load_profile()

        log.info("Modern ASTM Processor initialized with plugin architecture")

    def _setup_plugins(
        self,
        enable_hipaa_audit: bool,
        enable_metrics: bool,
        enable_custom_logging: bool,
    ):
        """Setup and configure all required plugins."""

        # 1. Install Modern Records Plugin (Core functionality)
        print("📦 Installing Modern Records Plugin...")
        modern_records_plugin = install_plugin(
            "modern_records",
            enable_audit_trail=True,
            validation_mode="strict",
            default_repeat_delimiter="~",
            default_component_delimiter="^",
        )
        self.plugin_manager.register_plugin(modern_records_plugin)

        # 2. Install HIPAA Audit Plugin (Optional but recommended for healthcare)
        if enable_hipaa_audit:
            print("🔒 Installing HIPAA Audit Plugin...")
            hipaa_plugin = install_plugin(
                "hipaa",
                db_path="audit_logs/hipaa_audit.db",
                retention_days=2555,  # 7 years as per HIPAA
                auto_backup=True,
                session_timeout=3600,
            )
            self.plugin_manager.register_plugin(hipaa_plugin)

        # 3. Install Metrics Plugin (For performance monitoring)
        if enable_metrics:
            print("📊 Installing Metrics Plugin...")
            metrics_plugin = install_plugin("prometheus")
            self.plugin_manager.register_plugin(metrics_plugin)

        # 4. Install Custom Logging Plugin (Example of extensibility)
        if enable_custom_logging:
            print("📝 Installing Custom Logging Plugin...")
            custom_logger = install_plugin(
                "custom_logger", log_file="logs/astm_processing.log"
            )
            self.plugin_manager.register_plugin(custom_logger)

        print(f"✅ Installed {len(self.plugin_manager.list_plugins())} plugins")

    def _load_profile(self):
        """Load the device profile."""
        try:
            print(f"📋 Loading device profile from: {self.profile_path}")
            self.profile = load_profile_from_file(self.profile_path)
            log.info(
                f"Profile loaded for device: {self.profile.device} v{self.profile.version}"
            )
        except BaseASTMError as e:
            log.critical("Failed to load device profile", exc_info=e)
            raise

    def process_astm_message(
        self, raw_data: bytes, client_ip: str = "127.0.0.1"
    ) -> List[ProcessingResult]:
        """
        Process a complete ASTM message using the plugin architecture.

        Args:
            raw_data: Raw ASTM message bytes
            client_ip: Client IP address for audit logging

        Returns:
            List of processing results for each record
        """
        start_time = datetime.now()
        results = []

        try:
            # Step 1: Split records
            records = self._split_records(raw_data)
            log.info(f"Split message into {len(records)} records")

            # Step 2: Process each record
            for i, record_bytes in enumerate(records):
                if not record_bytes:
                    continue

                result = self._process_single_record(
                    record_bytes, client_ip, i + 1
                )
                results.append(result)

            # Step 3: Generate summary metrics
            self._log_processing_summary(results, start_time)

            return results

        except Exception as e:
            log.error(f"Failed to process ASTM message: {e}", exc_info=True)

            # Emit security violation event if this looks suspicious
            self.plugin_manager.emit(
                "security_violation",
                violation_type="PROCESSING_FAILURE",
                client_ip=client_ip,
                details={"error": str(e), "data_length": len(raw_data)},
            )

            return [
                ProcessingResult(
                    success=False, record_type="UNKNOWN", error_message=str(e)
                )
            ]

    def _split_records(self, raw_data: bytes) -> List[bytes]:
        """Split raw ASTM data into individual records."""
        records = raw_data.split(RECORD_SEP)
        return [record for record in records if record and record != b""]

    def _process_single_record(
        self, record_bytes: bytes, client_ip: str, record_number: int
    ) -> ProcessingResult:
        """Process a single ASTM record using plugins."""

        processing_start = datetime.now()

        try:
            # Step 1: Decode the frame
            frame_no, frame_content = decode_frame(record_bytes, ENCODING)

            if not frame_content or not frame_content[0]:
                return ProcessingResult(
                    success=False,
                    record_type="EMPTY",
                    error_message="Empty frame content",
                )

            record_data = frame_content[0]
            record_type = record_data[0] if record_data else "UNKNOWN"

            # Step 2: Get the appropriate record class from profile
            modern_records_plugin = self.plugin_manager.get_plugin(
                "modern_records"
            )
            if not modern_records_plugin:
                raise RuntimeError("Modern Records plugin not available")

            record_class = self.profile.get_record_class(record_type)
            if not record_class:
                raise NotAccepted(
                    f"No parser defined for record type '{record_type}'"
                )

            # Step 3: Parse and validate using the plugin
            validated_record = modern_records_plugin.parse_record(
                record_class, record_data
            )

            # Step 4: Emit events for other plugins to handle
            self.plugin_manager.emit("record_processed", validated_record)
            self.plugin_manager.emit("connection_established", client_ip)

            # Step 5: Calculate processing time
            processing_time = (
                datetime.now() - processing_start
            ).total_seconds() * 1000

            # Step 6: Log success
            log.info(
                f"Successfully processed {record_type} record #{record_number}",
                extra={
                    "record_type": record_type,
                    "processing_time_ms": processing_time,
                    "client_ip": client_ip,
                },
            )

            return ProcessingResult(
                success=True,
                record_type=record_type,
                record_data=validated_record,
                processing_time_ms=processing_time,
            )

        except ValidationError as e:
            # Handle validation errors specifically
            error_msg = f"Validation failed for {record_type}: {e}"
            log.warning(error_msg)

            # Emit validation failure event
            self.plugin_manager.emit(
                "record_validation_failed",
                record_type,
                record_data if "record_data" in locals() else None,
                e,
            )

            return ProcessingResult(
                success=False,
                record_type=(
                    record_type if "record_type" in locals() else "UNKNOWN"
                ),
                error_message=error_msg,
                processing_time_ms=(
                    datetime.now() - processing_start
                ).total_seconds()
                * 1000,
            )

        except Exception as e:
            # Handle all other errors
            error_msg = f"Processing error: {e}"
            log.error(error_msg, exc_info=True)

            return ProcessingResult(
                success=False,
                record_type=(
                    record_type if "record_type" in locals() else "UNKNOWN"
                ),
                error_message=error_msg,
                processing_time_ms=(
                    datetime.now() - processing_start
                ).total_seconds()
                * 1000,
            )

    def _log_processing_summary(
        self, results: List[ProcessingResult], start_time: datetime
    ):
        """Log a summary of processing results."""
        total_time = (datetime.now() - start_time).total_seconds() * 1000
        successful = len([r for r in results if r.success])
        failed = len(results) - successful

        log.info(
            f"Processing complete: {successful} successful, {failed} failed, "
            f"total time: {total_time:.2f}ms"
        )

    def get_plugin_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics from all plugins."""
        stats = {
            "plugins_installed": self.plugin_manager.list_plugins(),
            "timestamp": datetime.now().isoformat(),
        }

        # Get Modern Records Plugin stats
        modern_records = self.plugin_manager.get_plugin("modern_records")
        if modern_records:
            stats["modern_records"] = modern_records.get_statistics()

        # Get Metrics Plugin stats
        metrics_plugin = self.plugin_manager.get_plugin("PrometheusMetrics")
        if metrics_plugin:
            stats["metrics"] = metrics_plugin.get_metrics()

        return stats

    def generate_hipaa_report(
        self, start_date: str, end_date: str
    ) -> Dict[str, Any]:
        """Generate HIPAA compliance report if audit plugin is enabled."""
        hipaa_plugin = self.plugin_manager.get_plugin("hipaa")
        if not hipaa_plugin:
            return {"error": "HIPAA plugin not installed"}

        return hipaa_plugin.generate_compliance_report(start_date, end_date)

    def get_patient_access_history(
        self, patient_id: str
    ) -> List[Dict[str, Any]]:
        """Get patient access history if HIPAA plugin is enabled."""
        hipaa_plugin = self.plugin_manager.get_plugin("hipaa")
        if not hipaa_plugin:
            return []

        return hipaa_plugin.get_patient_access_history(patient_id)


def demonstrate_basic_usage():
    """Demonstrate basic usage of the modern plugin architecture."""

    print("\n" + "=" * 60)
    print("🚀 BASIC USAGE DEMONSTRATION")
    print("=" * 60)

    # Initialize processor with all plugins enabled
    processor = ModernASTMProcessor(
        profile_path="profiles/mindray_bs240.yaml",  # Adjust path as needed
        enable_hipaa_audit=True,
        enable_metrics=True,
        enable_custom_logging=True,
    )

    # Sample ASTM data (Header and Patient records)
    sample_data = (
        b"1H|\\^&|||Mindray^1.0^SN123|||||||PR|1394-97|20250731193000\r"
        b"2P|1||PID123|Doe^John^M|19900101|M|||||||||||||||||||||||||\r"
        b"3O|1|SAMPLE001||GLU^Glucose||||||||||||||||||||||||||||\r"
        b"4R|1|GLU^Glucose|120|mg/dL|70-110|H|||F|||||||\r"
    )

    # Process the data
    print("\n📊 Processing ASTM message...")
    results = processor.process_astm_message(
        sample_data, client_ip="192.168.1.100"
    )

    # Display results
    print(f"\n✅ Processed {len(results)} records:")
    for i, result in enumerate(results, 1):
        status = "✅ SUCCESS" if result.success else "❌ FAILED"
        print(f"  {i}. {result.record_type}: {status}")
        if result.error_message:
            print(f"     Error: {result.error_message}")
        if result.processing_time_ms:
            print(f"     Processing time: {result.processing_time_ms:.2f}ms")

    # Show plugin statistics
    print("\n📈 Plugin Statistics:")
    stats = processor.get_plugin_statistics()
    print(json.dumps(stats, indent=2, default=str))


def demonstrate_custom_plugin():
    """Demonstrate how to create and use a custom plugin."""

    print("\n" + "=" * 60)
    print("🔧 CUSTOM PLUGIN DEMONSTRATION")
    print("=" * 60)

    from astmio.plugins import BasePlugin, register_available_plugin

    class LISIntegrationPlugin(BasePlugin):
        """
        Custom plugin for LIS integration.

        This demonstrates how you can create custom plugins for your specific
        LIS requirements, such as database integration, HL7 conversion, etc.
        """

        name = "lis_integration"
        version = "1.0.0"
        description = "Custom LIS integration plugin for database operations"

        def __init__(self, database_url: str = "sqlite:///lis.db", **kwargs):
            super().__init__(**kwargs)
            self.database_url = database_url
            self.processed_records = []

        def install(self, manager):
            super().install(manager)

            # Register for record processing events
            manager.on("record_processed", self.on_record_processed)
            manager.on("record_validation_failed", self.on_validation_failed)

            print(
                f"🔗 LIS Integration Plugin connected to: {self.database_url}"
            )

        def on_record_processed(self, record):
            """Handle successfully processed records."""
            # In a real implementation, you would save to database here
            self.processed_records.append(
                {
                    "type": type(record).__name__,
                    "timestamp": datetime.now().isoformat(),
                    "data": (
                        record.model_dump()
                        if hasattr(record, "model_dump")
                        else str(record)
                    ),
                }
            )

            print(f"💾 Saved {type(record).__name__} to LIS database")

        def on_validation_failed(self, record_class, values, error):
            """Handle validation failures."""
            print(f"⚠️  Validation failed for {record_class.__name__}: {error}")
            # In real implementation, you might log to error table or alert system

        def get_processed_count(self) -> int:
            """Get count of processed records."""
            return len(self.processed_records)

        def get_recent_records(self, limit: int = 5) -> List[Dict]:
            """Get recent processed records."""
            return self.processed_records[-limit:]

    # Register the custom plugin
    register_available_plugin("lis_integration", LISIntegrationPlugin)

    # Use the custom plugin
    processor = ModernASTMProcessor(
        profile_path="profiles/mindray_bs240.yaml",
        enable_hipaa_audit=False,  # Disable for this demo
        enable_metrics=False,
    )

    # Install our custom plugin
    lis_plugin = install_plugin(
        "lis_integration",
        database_url="postgresql://lis:password@localhost/lis_db",
    )
    processor.plugin_manager.register_plugin(lis_plugin)

    # Process some data
    sample_data = (
        b"2P|1||PID456|Smith^Jane^A|19850315|F|||||||||||||||||||||||||\r"
    )
    processor.process_astm_message(sample_data)

    # Show custom plugin results
    print("\n📊 Custom Plugin Results:")
    print(f"  Records processed: {lis_plugin.get_processed_count()}")
    print(f"  Recent records: {len(lis_plugin.get_recent_records())}")


def demonstrate_hipaa_compliance():
    """Demonstrate HIPAA compliance features."""

    print("\n" + "=" * 60)
    print("🔒 HIPAA COMPLIANCE DEMONSTRATION")
    print("=" * 60)

    processor = ModernASTMProcessor(
        profile_path="profiles/mindray_bs240.yaml",
        enable_hipaa_audit=True,
        enable_metrics=False,
        enable_custom_logging=False,
    )

    # Process patient data (this will be audited)
    patient_data = (
        b"2P|1||PID789|Johnson^Bob^R|19750620|M|||||||||||||||||||||||||\r"
    )
    processor.process_astm_message(patient_data, client_ip="10.0.0.50")

    # Generate compliance report
    print("\n📋 Generating HIPAA Compliance Report...")
    report = processor.generate_hipaa_report("2025-01-01", "2025-12-31")

    if "error" not in report:
        print(f"  Total events: {report['summary']['total_events']}")
        print(f"  High-risk events: {report['summary']['high_risk_events']}")
        print(f"  Unique patients: {report['summary']['unique_patients']}")
        print(f"  Compliance status: {report['compliance_status']}")
    else:
        print(f"  Error: {report['error']}")

    # Get patient access history
    print("\n👤 Patient Access History:")
    history = processor.get_patient_access_history("PID789")
    print(f"  Found {len(history)} access events for patient PID789")


def main():
    """Main demonstration function."""

    print("🏥 Modern ASTM Plugin Architecture Example")
    print(
        "This example shows how to use the new plugin-based system for LIS integration"
    )

    try:
        # Run all demonstrations
        demonstrate_basic_usage()
        demonstrate_custom_plugin()
        demonstrate_hipaa_compliance()

        print("\n" + "=" * 60)
        print("✅ ALL DEMONSTRATIONS COMPLETED SUCCESSFULLY!")
        print("=" * 60)

        print("\n💡 Key Takeaways for LIS Implementation:")
        print("  1. Use PluginManager for modular architecture")
        print("  2. Enable HIPAA plugin for healthcare compliance")
        print("  3. Use metrics plugin for performance monitoring")
        print("  4. Create custom plugins for specific LIS needs")
        print("  5. All plugins work together seamlessly")

    except Exception as e:
        log.error(f"Demonstration failed: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")
        print(
            "Make sure you have the correct profile path and all dependencies installed."
        )


if __name__ == "__main__":
    main()
