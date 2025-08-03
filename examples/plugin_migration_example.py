#!/usr/bin/env python3
"""
Plugin Migration Example for ASTM Library

This comprehensive example demonstrates how to use the new plugin architecture
in the ASTM library. It shows:

1. How to install and configure built-in plugins
2. How to create custom plugins for your specific LIS needs
3. How to migrate from the old system to the new plugin-based architecture
4. Real-world examples of plugin usage in a LIS environment

The plugin system provides a modular, extensible way to add functionality
to your ASTM processing pipeline without modifying core library code.
"""

import json
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

# Core ASTM imports
from astmio.constants import ENCODING, RECORD_SEP
from astmio.decoder import decode_frame
from astmio.exceptions import BaseASTMError, NotAccepted
from astmio.io import load_profile_from_file
from astmio.logging import get_logger
from astmio.modern_records import ASTMBaseRecord

# Plugin system imports
from astmio.plugins import (
    BasePlugin,
    PluginManager,
    install_plugin,
    list_available_plugins,
    print_plugin_catalog,
)
from astmio.plugins.registry import (
    get_plugin_info,
)
from astmio.profile import DeviceProfile

log = get_logger(__name__)


# ============================================================================
# CUSTOM PLUGIN EXAMPLES
# ============================================================================


class LISIntegrationPlugin(BasePlugin):
    """
    Custom plugin for LIS integration.

    This plugin demonstrates how to create a custom plugin that integrates
    with your Laboratory Information System (LIS) to:
    - Send results to the LIS database
    - Validate against LIS business rules
    - Handle LIS-specific data transformations
    """

    name = "lis_integration"
    version = "1.0.0"
    description = "Custom LIS integration plugin for laboratory workflows"

    def __init__(
        self,
        lis_endpoint: str = "http://localhost:8080/api",
        api_key: str = "",
        timeout: int = 30,
        retry_attempts: int = 3,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.lis_endpoint = lis_endpoint
        self.api_key = api_key
        self.timeout = timeout
        self.retry_attempts = retry_attempts

        # Statistics
        self.records_sent = 0
        self.failed_sends = 0
        self.validation_errors = 0

    def install(self, manager):
        """Install the LIS integration plugin."""
        super().install(manager)

        # Register for relevant events
        manager.on("record_processed", self.on_record_processed)
        manager.on("patient_record_validated", self.on_patient_record)
        manager.on("result_record_validated", self.on_result_record)
        manager.on("order_record_validated", self.on_order_record)

        log.info(
            f"LIS Integration plugin installed - endpoint: {self.lis_endpoint}"
        )

    def on_record_processed(self, record: ASTMBaseRecord, *args, **kwargs):
        """Handle any processed record."""
        log.debug(f"LIS Integration: Processing {type(record).__name__}")

        # Apply LIS-specific business rules
        if not self._validate_lis_rules(record):
            self.validation_errors += 1
            log.warning(
                f"Record failed LIS validation: {type(record).__name__}"
            )
            return

        # Send to LIS (simulated)
        success = self._send_to_lis(record)
        if success:
            self.records_sent += 1
        else:
            self.failed_sends += 1

    def on_patient_record(self, record: ASTMBaseRecord):
        """Handle patient-specific records."""
        log.info("Processing patient record for LIS integration")

        # Extract patient data for LIS
        patient_data = self._extract_patient_data(record)

        # Check if patient exists in LIS
        if not self._patient_exists_in_lis(patient_data.get("patient_id")):
            log.info("Creating new patient in LIS")
            self._create_patient_in_lis(patient_data)
        else:
            log.info("Updating existing patient in LIS")
            self._update_patient_in_lis(patient_data)

    def on_result_record(self, record: ASTMBaseRecord):
        """Handle result-specific records."""
        log.info("Processing result record for LIS integration")

        # Extract result data
        result_data = self._extract_result_data(record)

        # Apply result validation rules
        if self._validate_result_ranges(result_data):
            self._store_result_in_lis(result_data)
        else:
            log.warning("Result failed range validation")

    def on_order_record(self, record: ASTMBaseRecord):
        """Handle order-specific records."""
        log.info("Processing order record for LIS integration")

        # Extract order data
        order_data = self._extract_order_data(record)

        # Update order status in LIS
        self._update_order_status(order_data)

    def _validate_lis_rules(self, record: ASTMBaseRecord) -> bool:
        """Apply LIS-specific validation rules."""
        # Example: Check required fields based on record type
        if hasattr(record, "patient_id") and not record.patient_id:
            return False

        # Example: Validate data formats
        if hasattr(record, "birth_date") and record.birth_date:
            try:
                datetime.strptime(str(record.birth_date), "%Y%m%d")
            except ValueError:
                return False

        return True

    def _send_to_lis(self, record: ASTMBaseRecord) -> bool:
        """Send record to LIS system (simulated)."""
        try:
            # In a real implementation, this would make HTTP requests
            # to your LIS API endpoints

            record_data = {
                "record_type": type(record).__name__,
                "data": record.model_dump(),
                "timestamp": datetime.now().isoformat(),
                "source": "ASTM_INTERFACE",
            }

            log.debug(f"Sending to LIS: {json.dumps(record_data, indent=2)}")

            # Simulate API call delay
            time.sleep(0.1)

            # Simulate success/failure
            return True

        except Exception as e:
            log.error(f"Failed to send record to LIS: {e}")
            return False

    def _extract_patient_data(self, record: ASTMBaseRecord) -> Dict[str, Any]:
        """Extract patient data for LIS."""
        return {
            "patient_id": getattr(record, "patient_id", None),
            "patient_name": getattr(record, "patient_name", None),
            "birth_date": getattr(record, "birth_date", None),
            "gender": getattr(record, "gender", None),
        }

    def _extract_result_data(self, record: ASTMBaseRecord) -> Dict[str, Any]:
        """Extract result data for LIS."""
        return {
            "test_id": getattr(record, "test_id", None),
            "result_value": getattr(record, "result_value", None),
            "units": getattr(record, "units", None),
            "reference_range": getattr(record, "reference_range", None),
        }

    def _extract_order_data(self, record: ASTMBaseRecord) -> Dict[str, Any]:
        """Extract order data for LIS."""
        return {
            "sample_id": getattr(record, "sample_id", None),
            "test_code": getattr(record, "test_code", None),
            "order_status": getattr(record, "order_status", None),
        }

    def _patient_exists_in_lis(self, patient_id: str) -> bool:
        """Check if patient exists in LIS (simulated)."""
        # In real implementation, query your LIS database
        return patient_id in ["PAT001", "PAT002", "PAT003"]

    def _create_patient_in_lis(self, patient_data: Dict[str, Any]):
        """Create new patient in LIS (simulated)."""
        log.info(f"Creating patient: {patient_data}")

    def _update_patient_in_lis(self, patient_data: Dict[str, Any]):
        """Update existing patient in LIS (simulated)."""
        log.info(f"Updating patient: {patient_data}")

    def _validate_result_ranges(self, result_data: Dict[str, Any]) -> bool:
        """Validate result against reference ranges."""
        # Example validation logic
        return True

    def _store_result_in_lis(self, result_data: Dict[str, Any]):
        """Store result in LIS database (simulated)."""
        log.info(f"Storing result: {result_data}")

    def _update_order_status(self, order_data: Dict[str, Any]):
        """Update order status in LIS (simulated)."""
        log.info(f"Updating order: {order_data}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get plugin statistics."""
        return {
            "records_sent": self.records_sent,
            "failed_sends": self.failed_sends,
            "validation_errors": self.validation_errors,
            "success_rate": (
                self.records_sent / (self.records_sent + self.failed_sends)
                if (self.records_sent + self.failed_sends) > 0
                else 0
            ),
        }


class DataValidationPlugin(BasePlugin):
    """
    Custom plugin for enhanced data validation.

    This plugin adds additional validation layers beyond the standard
    ASTM validation, including:
    - Custom business rules
    - Data quality checks
    - Cross-record validation
    """

    name = "data_validation"
    version = "1.0.0"
    description = "Enhanced data validation plugin with custom business rules"

    def __init__(
        self,
        strict_mode: bool = True,
        custom_rules: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.strict_mode = strict_mode
        self.custom_rules = custom_rules or {}

        # Validation statistics
        self.total_validations = 0
        self.validation_failures = 0
        self.rule_violations = {}

    def install(self, manager):
        """Install the data validation plugin."""
        super().install(manager)

        # Register for validation events
        manager.on("record_parsed", self.on_record_parsed)
        manager.on("validation_requested", self.on_validation_requested)

        log.info("Data Validation plugin installed")

    def on_record_parsed(self, record: ASTMBaseRecord, *args, **kwargs):
        """Validate parsed records."""
        self.total_validations += 1

        validation_result = self._validate_record(record)

        if not validation_result["valid"]:
            self.validation_failures += 1

            # Track rule violations
            for rule in validation_result["violations"]:
                self.rule_violations[rule] = (
                    self.rule_violations.get(rule, 0) + 1
                )

            # Emit validation failure event
            if self.manager:
                self.manager.emit(
                    "validation_failed", record, validation_result["violations"]
                )

    def on_validation_requested(self, record: ASTMBaseRecord):
        """Handle explicit validation requests."""
        return self._validate_record(record)

    def _validate_record(self, record: ASTMBaseRecord) -> Dict[str, Any]:
        """Perform comprehensive record validation."""
        violations = []

        # Check required fields
        violations.extend(self._check_required_fields(record))

        # Check data formats
        violations.extend(self._check_data_formats(record))

        # Check business rules
        violations.extend(self._check_business_rules(record))

        # Check data quality
        violations.extend(self._check_data_quality(record))

        return {
            "valid": len(violations) == 0,
            "violations": violations,
            "record_type": type(record).__name__,
        }

    def _check_required_fields(self, record: ASTMBaseRecord) -> List[str]:
        """Check for required fields based on record type."""
        violations = []

        # Example: Patient records must have patient_id
        if hasattr(record, "patient_id") and not record.patient_id:
            violations.append("missing_patient_id")

        return violations

    def _check_data_formats(self, record: ASTMBaseRecord) -> List[str]:
        """Check data format compliance."""
        violations = []

        # Example: Check date formats
        if hasattr(record, "birth_date") and record.birth_date:
            if not self._is_valid_date_format(str(record.birth_date)):
                violations.append("invalid_birth_date_format")

        return violations

    def _check_business_rules(self, record: ASTMBaseRecord) -> List[str]:
        """Check custom business rules."""
        violations = []

        # Apply custom rules from configuration
        for rule_name, rule_config in self.custom_rules.items():
            if not self._apply_custom_rule(record, rule_config):
                violations.append(f"business_rule_{rule_name}")

        return violations

    def _check_data_quality(self, record: ASTMBaseRecord) -> List[str]:
        """Check data quality metrics."""
        violations = []

        # Example: Check for suspicious data patterns
        if hasattr(record, "patient_name") and record.patient_name:
            if str(record.patient_name).upper() in ["TEST", "UNKNOWN", "NULL"]:
                violations.append("suspicious_patient_name")

        return violations

    def _is_valid_date_format(self, date_str: str) -> bool:
        """Validate date format."""
        try:
            datetime.strptime(date_str, "%Y%m%d")
            return True
        except ValueError:
            return False

    def _apply_custom_rule(
        self, record: ASTMBaseRecord, rule_config: Dict[str, Any]
    ) -> bool:
        """Apply a custom validation rule."""
        # Example implementation of custom rule engine
        return True

    def get_validation_report(self) -> Dict[str, Any]:
        """Get validation statistics report."""
        return {
            "total_validations": self.total_validations,
            "validation_failures": self.validation_failures,
            "failure_rate": (
                self.validation_failures / self.total_validations
                if self.total_validations > 0
                else 0
            ),
            "rule_violations": self.rule_violations,
        }


# ============================================================================
# ENHANCED DATA HANDLER WITH PLUGIN SUPPORT
# ============================================================================


@dataclass
class DecodedTuple:
    """Result of frame decoding."""

    frame_no: int
    frame_content: List[str | List | None]
    frame_type: str


class PluginAwareDataHandler:
    """
    Enhanced DataHandler that integrates with the plugin system.

    This handler demonstrates how to integrate plugins into your
    existing ASTM processing workflow.
    """

    def __init__(self, profile: DeviceProfile, enable_plugins: bool = True):
        """Initialize handler with plugin support."""
        self.profile = profile
        self.enable_plugins = enable_plugins

        # Initialize plugin manager
        self.plugin_manager = (
            PluginManager(server=self) if enable_plugins else None
        )

        # Install plugins if enabled
        if self.plugin_manager:
            self._install_plugins()

        log.info(
            "PluginAwareDataHandler initialized with profile for device '%s' (v%s)",
            self.profile.device,
            self.profile.version,
        )

    def _install_plugins(self):
        """Install and configure plugins."""
        try:
            # Install built-in plugins

            # 1. Modern Records Plugin (for enhanced record handling)
            modern_records = install_plugin(
                "modern_records",
                enable_audit_trail=True,
                validation_mode="strict",
            )
            self.plugin_manager.register_plugin(modern_records)

            # 2. Metrics Plugin (for monitoring)
            metrics = install_plugin("metrics")
            self.plugin_manager.register_plugin(metrics)

            # 3. HIPAA Plugin (for compliance)
            hipaa = install_plugin(
                "hipaa",
                db_path="audit_logs.db",
                retention_days=2555,  # 7 years
                auto_backup=True,
            )
            self.plugin_manager.register_plugin(hipaa)

            # Install custom plugins

            # 4. LIS Integration Plugin
            lis_plugin = LISIntegrationPlugin(
                lis_endpoint="http://your-lis-server:8080/api",
                api_key="your-api-key",
                timeout=30,
            )
            self.plugin_manager.register_plugin(lis_plugin)

            # 5. Data Validation Plugin
            validation_plugin = DataValidationPlugin(
                strict_mode=True,
                custom_rules={
                    "patient_id_format": {"pattern": r"^PAT\d{6}$"},
                    "result_range_check": {"enabled": True},
                },
            )
            self.plugin_manager.register_plugin(validation_plugin)

            log.info("All plugins installed successfully")

        except Exception as e:
            log.error(f"Failed to install plugins: {e}")

    def split_record(self, record_message: bytes) -> List[bytes]:
        """Split records based on record separator."""
        record_splitter: bytes = RECORD_SEP
        records = record_message.split(record_splitter)

        if not records:
            log.warning("No records found returning empty list")
            return []

        return records

    def clean_records(self, uncleaned_records: List[bytes]) -> List[bytes]:
        """Clean records and remove empty ones."""
        cleaned_records: List[bytes] = []

        for record in uncleaned_records:
            if not record or record == b"":
                continue
            cleaned_records.append(record)

        return cleaned_records

    def decode_frame(self, cleaned_records: List[bytes]) -> DecodedTuple:
        """Decode frame and emit events."""
        frame_no, frame_content = decode_frame(cleaned_records[0], ENCODING)

        result = DecodedTuple(
            frame_no=frame_no,
            frame_content=frame_content[0],
            frame_type=frame_content[0][0],
        )

        # Emit frame decoded event
        if self.plugin_manager:
            self.plugin_manager.emit("frame_decoded", result)

        return result

    def validate_record(self, result: DecodedTuple) -> ASTMBaseRecord:
        """Validate record and emit events."""
        record_class: ASTMBaseRecord = self.profile.get_record_class(
            result.frame_type
        )

        if not record_class:
            error = NotAccepted(
                f"No parser defined for record type '{result.frame_type}'."
            )

            # Emit validation error event
            if self.plugin_manager:
                self.plugin_manager.emit("validation_error", result, error)

            raise error

        try:
            # Parse the record
            validated_record = record_class.from_astm_record(
                result.frame_content
            )

            # Emit successful validation events
            if self.plugin_manager:
                self.plugin_manager.emit(
                    "record_parsed", validated_record, result.frame_content
                )
                self.plugin_manager.emit(
                    "record_processed", validated_record, self
                )

                # Emit record-type specific events
                record_type = result.frame_type.lower()
                if record_type == "p":
                    self.plugin_manager.emit(
                        "patient_record_validated", validated_record
                    )
                elif record_type == "r":
                    self.plugin_manager.emit(
                        "result_record_validated", validated_record
                    )
                elif record_type == "o":
                    self.plugin_manager.emit(
                        "order_record_validated", validated_record
                    )

            return validated_record

        except Exception as e:
            # Emit validation failure event
            if self.plugin_manager:
                self.plugin_manager.emit(
                    "record_validation_failed",
                    record_class,
                    result.frame_content,
                    e,
                )

            raise

    def process_message(self, raw_data: bytes) -> List[ASTMBaseRecord]:
        """Process complete ASTM message with plugin integration."""
        processed_records = []

        try:
            # Emit message processing start event
            if self.plugin_manager:
                self.plugin_manager.emit("message_processing_start", raw_data)

            # Process the message
            splitted_records = self.split_record(raw_data)
            cleaned_records = self.clean_records(splitted_records)

            for record_bytes in cleaned_records:
                try:
                    decoded_frame = self.decode_frame([record_bytes])
                    validated_record = self.validate_record(decoded_frame)
                    processed_records.append(validated_record)

                except Exception as e:
                    log.error(f"Failed to process record: {e}")

                    # Emit record processing error
                    if self.plugin_manager:
                        self.plugin_manager.emit(
                            "record_processing_error", record_bytes, e
                        )

            # Emit message processing complete event
            if self.plugin_manager:
                self.plugin_manager.emit(
                    "message_processing_complete", processed_records
                )

            return processed_records

        except Exception as e:
            # Emit message processing error
            if self.plugin_manager:
                self.plugin_manager.emit(
                    "message_processing_error", raw_data, e
                )

            raise

    def get_plugin_statistics(self) -> Dict[str, Any]:
        """Get statistics from all installed plugins."""
        if not self.plugin_manager:
            return {}

        stats = {}

        for plugin_name in self.plugin_manager.list_plugins():
            plugin = self.plugin_manager.get_plugin(plugin_name)

            if hasattr(plugin, "get_statistics"):
                stats[plugin_name] = plugin.get_statistics()
            elif hasattr(plugin, "get_validation_report"):
                stats[plugin_name] = plugin.get_validation_report()
            elif hasattr(plugin, "get_metrics"):
                stats[plugin_name] = plugin.get_metrics()

        return stats


# ============================================================================
# MIGRATION HELPER FUNCTIONS
# ============================================================================


def migrate_from_old_system():
    """
    Helper function to migrate from the old ASTM system to the new plugin-based system.

    This function demonstrates how to:
    1. Identify existing functionality that can be replaced by plugins
    2. Configure plugins to match existing behavior
    3. Gradually migrate to the new system
    """

    print("🔄 ASTM Library Migration Guide")
    print("=" * 50)

    print("\n1. Available Plugins:")
    print("-" * 20)

    # Show available plugins
    available_plugins = list_available_plugins()
    for plugin_name, description in available_plugins.items():
        info = get_plugin_info(plugin_name)
        print(f"  • {plugin_name} (v{info.get('version', 'unknown')})")
        print(f"    {description}")
        print()

    print("\n2. Migration Steps:")
    print("-" * 20)
    print("  a) Replace manual audit logging with HIPAA plugin")
    print("  b) Replace custom metrics collection with Metrics plugin")
    print("  c) Replace manual record validation with Modern Records plugin")
    print("  d) Add custom plugins for LIS integration")
    print("  e) Configure plugins to match existing behavior")

    print("\n3. Configuration Examples:")
    print("-" * 20)

    # Show configuration examples
    config_examples = {
        "hipaa": {
            "db_path": "audit_logs.db",
            "retention_days": 2555,
            "auto_backup": True,
        },
        "metrics": {"enable_prometheus": True, "metrics_port": 9090},
        "modern_records": {
            "enable_audit_trail": True,
            "validation_mode": "strict",
        },
    }

    for plugin_name, config in config_examples.items():
        print(f"  {plugin_name}:")
        print(f"    {json.dumps(config, indent=4)}")
        print()


def create_custom_lis_plugin_template():
    """
    Create a template for a custom LIS plugin.

    This function generates a template that users can customize
    for their specific LIS integration needs.
    """

    template = '''
class CustomLISPlugin(BasePlugin):
    """
    Custom LIS integration plugin template.

    Customize this template for your specific LIS system:
    - Replace API endpoints with your LIS URLs
    - Modify data mapping functions for your data model
    - Add your specific business rules and validations
    """

    name = "custom_lis"
    version = "1.0.0"
    description = "Custom LIS integration plugin"

    def __init__(self, lis_config: Dict[str, Any], **kwargs):
        super().__init__(**kwargs)
        self.lis_config = lis_config

        # TODO: Initialize your LIS client/connection here
        # self.lis_client = YourLISClient(lis_config)

    def install(self, manager):
        super().install(manager)

        # Register for events you want to handle
        manager.on("patient_record_validated", self.handle_patient)
        manager.on("result_record_validated", self.handle_result)
        manager.on("order_record_validated", self.handle_order)

    def handle_patient(self, record: ASTMBaseRecord):
        """Handle patient records - customize for your LIS."""
        # TODO: Extract patient data
        patient_data = self._extract_patient_data(record)

        # TODO: Send to your LIS
        # self.lis_client.create_or_update_patient(patient_data)

    def handle_result(self, record: ASTMBaseRecord):
        """Handle result records - customize for your LIS."""
        # TODO: Extract result data
        result_data = self._extract_result_data(record)

        # TODO: Send to your LIS
        # self.lis_client.store_result(result_data)

    def handle_order(self, record: ASTMBaseRecord):
        """Handle order records - customize for your LIS."""
        # TODO: Extract order data
        order_data = self._extract_order_data(record)

        # TODO: Update order in your LIS
        # self.lis_client.update_order_status(order_data)

    def _extract_patient_data(self, record: ASTMBaseRecord) -> Dict[str, Any]:
        """Extract patient data - customize field mapping."""
        return {
            "patient_id": getattr(record, 'patient_id', None),
            "name": getattr(record, 'patient_name', None),
            "dob": getattr(record, 'birth_date', None),
            "gender": getattr(record, 'gender', None),
            # TODO: Add more fields as needed
        }

    def _extract_result_data(self, record: ASTMBaseRecord) -> Dict[str, Any]:
        """Extract result data - customize field mapping."""
        return {
            "test_id": getattr(record, 'test_id', None),
            "value": getattr(record, 'result_value', None),
            "units": getattr(record, 'units', None),
            "range": getattr(record, 'reference_range', None),
            # TODO: Add more fields as needed
        }

    def _extract_order_data(self, record: ASTMBaseRecord) -> Dict[str, Any]:
        """Extract order data - customize field mapping."""
        return {
            "sample_id": getattr(record, 'sample_id', None),
            "test_code": getattr(record, 'test_code', None),
            "status": getattr(record, 'order_status', None),
            # TODO: Add more fields as needed
        }
'''

    print("📝 Custom LIS Plugin Template")
    print("=" * 50)
    print(template)

    return template


# ============================================================================
# MAIN DEMONSTRATION
# ============================================================================


def main():
    """
    Main demonstration of the plugin system.

    This function shows a complete workflow using the new plugin architecture.
    """

    print("🔌 ASTM Library Plugin System Demonstration")
    print("=" * 60)

    # 1. Show available plugins
    print("\n1. Available Plugins:")
    print_plugin_catalog()

    # 2. Show migration guide
    print("\n" + "=" * 60)
    migrate_from_old_system()

    # 3. Demonstrate plugin usage
    print("\n" + "=" * 60)
    print("3. Plugin Usage Demonstration")
    print("-" * 30)

    try:
        # Load device profile (you'll need to adjust the path)
        profile_path = "profiles/mindray_bs240.yaml"  # Adjust path as needed

        try:
            profile: DeviceProfile = load_profile_from_file(profile_path)
        except (FileNotFoundError, BaseASTMError):
            print(f"⚠️  Profile not found at {profile_path}")
            print("   Using mock profile for demonstration...")
            profile = None  # In real usage, you'd need a valid profile
            return

        # Create plugin-aware handler
        handler = PluginAwareDataHandler(profile, enable_plugins=True)

        print("✅ Plugin-aware handler created successfully")

        # Process sample data
        print("\n4. Processing Sample ASTM Data:")
        print("-" * 30)

        sample_data = (
            b"1H|\\^&|||Mindray^1.0^SN123|||||||PR|1394-97|20250731193000\r"
            b"2P|1||PID123|Doe^John^M|19900101|M|||||||||||||||||||||||||\r"
            b"3R|1|^^^GLU^|150|mg/dL|70-110|H|||F|||\r"
        )

        try:
            processed_records = handler.process_message(sample_data)
            print(f"✅ Successfully processed {len(processed_records)} records")

            # Show plugin statistics
            print("\n5. Plugin Statistics:")
            print("-" * 20)

            stats = handler.get_plugin_statistics()
            for plugin_name, plugin_stats in stats.items():
                print(f"  {plugin_name}:")
                for key, value in plugin_stats.items():
                    print(f"    {key}: {value}")
                print()

        except Exception as e:
            print(f"❌ Error processing records: {e}")
            log.error(f"Record processing failed: {e}")

    except Exception as e:
        print(f"❌ Demonstration failed: {e}")
        log.error(f"Plugin demonstration failed: {e}")

    # 4. Show custom plugin template
    print("\n" + "=" * 60)
    print("4. Custom Plugin Template")
    create_custom_lis_plugin_template()

    print("\n" + "=" * 60)
    print("🎉 Plugin System Demonstration Complete!")
    print("\nNext Steps:")
    print("1. Install required plugins for your use case")
    print("2. Create custom plugins for LIS integration")
    print("3. Configure plugins to match your requirements")
    print("4. Test the complete workflow with your data")
    print("5. Monitor plugin performance and statistics")


if __name__ == "__main__":
    main()
