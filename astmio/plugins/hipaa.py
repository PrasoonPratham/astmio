
import dataset
from structlog.types import WrappedLogger
from logging import getLogger, INFO
from logging.handlers import RotatingFileHandler
from . import BasePlugin
from ..logging import SQLiteHandler
from ..records import PatientRecord

class HIPAAAuditPlugin(BasePlugin):
    """
    A plugin for creating a HIPAA-compliant audit trail by listening to events.
    """
    name: str = "HIPAAAudit"

    def __init__(self, db_path: str = "hipaa_audit.db"):
        self.db_path = db_path
        self.audit_log: WrappedLogger = None
        super().__init__()

    def install(self, manager: "PluginManager"):
        """
        Installs the audit plugin, sets up its dedicated logger, and
        registers its event listeners.
        """
        super().install(manager)
        # Setup dedicated logger
        handler = SQLiteHandler(self.db_path)
        logger = getLogger("hipaa_audit")
        logger.setLevel(INFO)
        logger.addHandler(handler)
        logger.propagate = False
        self.audit_log = logger
        
        # Register event listeners
        manager.on("record_processed", self.on_record_processed)
        manager.on("secure_connection_failed", self.on_secure_connection_failed)

    def on_record_processed(self, record: "ASTMModel", server: "Server"):
        """
        Event handler for when a record is successfully processed.
        """
        if isinstance(record, PatientRecord):
            patient_id = record.patient_id or "Unknown"
            self.audit_log.info(
                "Patient Data Accessed",
                extra={
                    "user_id": "LIS-System",
                    "patient_id": patient_id,
                    "success": True,
                },
            )
        elif isinstance(record, list) and len(record) > 0 and record[0] == 'P':
            # Handle raw Patient record list
            patient_id = record[1] if len(record) > 1 and record[1] else "Unknown"
            self.audit_log.info(
                "Patient Data Accessed",
                extra={
                    "user_id": "LIS-System", 
                    "patient_id": patient_id,
                    "success": True,
                },
            )

    def on_secure_connection_failed(self, client_ip: str, reason: str):
        """
        Logs an event when a secure connection attempt fails.
        """
        self.audit_log.info(
            "Secure Connection Failure",
            extra={"client_ip": client_ip, "reason": reason},
        )

    def uninstall(self, manager: "PluginManager"):
        """
        Called when the plugin is uninstalled.
        """
        super().uninstall(manager)
        # Here you might want to close the database connection if dataset supports it
        # and unregister event listeners.
        pass 