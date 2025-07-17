#!/usr/bin/env python3
"""
HIPAA Audit Plugin for ASTM Library

A comprehensive HIPAA-compliant audit trail plugin that logs all patient data access
and security events to a SQLite database using BLOB format for efficient JSON storage.

Install with: pip install astmio[hipaa]
"""

import os
import sqlite3
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, asdict
from contextlib import contextmanager
from pathlib import Path

from . import BasePlugin
from ..logging import get_logger
from ..records import PatientRecord

log = get_logger(__name__)


@dataclass
class AuditEvent:
    """Represents a HIPAA audit event."""
    timestamp: str
    event_type: str
    user_id: str
    session_id: Optional[str] = None
    patient_id: Optional[str] = None
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    risk_level: str = "LOW"  # LOW, MEDIUM, HIGH, CRITICAL
    data_classification: str = "PHI"  # PHI, PII, GENERAL
    compliance_flags: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON storage."""
        return asdict(self)


class HIPAADatabase:
    """Handles SQLite database operations with BLOB JSON storage support."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize the audit database with proper schema using JSONB."""
        try:
            # Ensure directory exists
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            
            with sqlite3.connect(self.db_path) as conn:
                # Enable foreign keys and JSON support (JSON1 is built-in in modern SQLite)
                conn.execute("PRAGMA foreign_keys = ON")
                
                cursor = conn.cursor()
                
                # Create audit_events table with BLOB columns for JSON data
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS audit_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        session_id TEXT,
                        patient_id TEXT,
                        client_ip TEXT,
                        user_agent TEXT,
                        success BOOLEAN NOT NULL,
                        error_message TEXT,
                        details BLOB,
                        risk_level TEXT DEFAULT 'LOW',
                        data_classification TEXT DEFAULT 'PHI',
                        compliance_flags BLOB,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        checksum TEXT
                    )
                ''')
                
                # Create indexes for better performance
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_audit_timestamp 
                    ON audit_events(timestamp)
                ''')
                
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_audit_patient_id 
                    ON audit_events(patient_id)
                ''')
                
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_audit_event_type 
                    ON audit_events(event_type)
                ''')
                
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_audit_risk_level 
                    ON audit_events(risk_level)
                ''')
                
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_audit_session_id 
                    ON audit_events(session_id)
                ''')
                
                # Note: BLOB columns cannot be indexed directly for JSON queries
                # This is a limitation of the BLOB approach compared to TEXT columns
                
                # Create audit_trail table for tamper detection
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS audit_trail (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_id INTEGER NOT NULL,
                        action TEXT NOT NULL,
                        previous_hash TEXT,
                        current_hash TEXT NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (event_id) REFERENCES audit_events(id)
                    )
                ''')
                
                # Create compliance_reports table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS compliance_reports (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        report_date TEXT NOT NULL,
                        report_type TEXT NOT NULL,
                        total_events INTEGER,
                        high_risk_events INTEGER,
                        failed_access_attempts INTEGER,
                        unique_patients INTEGER,
                        unique_sessions INTEGER,
                        report_data BLOB,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Create data_access_log for detailed PHI access tracking
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS data_access_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        patient_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        session_id TEXT,
                        access_type TEXT NOT NULL,
                        data_elements BLOB,
                        purpose TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        duration INTEGER,
                        source_ip TEXT,
                        authorized BOOLEAN DEFAULT TRUE
                    )
                ''')
                
                conn.commit()
                log.info(f"HIPAA audit database initialized with BLOB JSON storage: {self.db_path}")
                
        except Exception as e:
            log.error(f"Failed to initialize HIPAA audit database: {e}")
            raise
    
    def insert_audit_event(self, event: AuditEvent) -> int:
        """Insert audit event using BLOB format for JSON data."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Convert JSON to binary format following the BLOB approach
                details_blob = None
                if event.details:
                    json_data = json.dumps(event.details)
                    details_blob = bytes(json_data, 'utf-8')
                
                compliance_flags_blob = None
                if event.compliance_flags:
                    json_data = json.dumps(event.compliance_flags)
                    compliance_flags_blob = bytes(json_data, 'utf-8')
                
                # Calculate checksum for integrity
                checksum = self._calculate_checksum(event)
                
                cursor.execute('''
                    INSERT INTO audit_events (
                        timestamp, event_type, user_id, session_id, patient_id, 
                        client_ip, user_agent, success, error_message, details, 
                        risk_level, data_classification, compliance_flags, checksum
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    event.timestamp, event.event_type, event.user_id, event.session_id,
                    event.patient_id, event.client_ip, event.user_agent, event.success,
                    event.error_message, details_blob, event.risk_level, 
                    event.data_classification, compliance_flags_blob, checksum
                ))
                
                event_id = cursor.lastrowid
                
                # Insert into audit trail for tamper detection
                cursor.execute('''
                    INSERT INTO audit_trail (event_id, action, current_hash)
                    VALUES (?, 'INSERT', ?)
                ''', (event_id, checksum))
                
                conn.commit()
                return event_id
                
        except Exception as e:
            log.error(f"Failed to insert audit event: {e}")
            raise
    
    def _calculate_checksum(self, event: AuditEvent) -> str:
        """Calculate checksum for audit event integrity."""
        import hashlib
        event_str = json.dumps(event.to_dict(), sort_keys=True)
        return hashlib.sha256(event_str.encode()).hexdigest()
    
    def query_events(self, filters: Dict[str, Any], limit: int = 1000) -> List[Dict[str, Any]]:
        """Query audit events with BLOB JSON data."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                where_clauses = []
                params = []
                
                # Build WHERE clauses
                if filters.get('patient_id'):
                    where_clauses.append("patient_id = ?")
                    params.append(filters['patient_id'])
                
                if filters.get('event_type'):
                    where_clauses.append("event_type = ?")
                    params.append(filters['event_type'])
                
                if filters.get('risk_level'):
                    where_clauses.append("risk_level = ?")
                    params.append(filters['risk_level'])
                
                if filters.get('start_date'):
                    where_clauses.append("timestamp >= ?")
                    params.append(filters['start_date'])
                
                if filters.get('end_date'):
                    where_clauses.append("timestamp <= ?")
                    params.append(filters['end_date'])
                
                # Note: JSON filtering on BLOB requires converting back to JSON first
                # This is less efficient than TEXT columns but follows the BLOB approach
                
                where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
                params.append(limit)
                
                cursor.execute(f'''
                    SELECT * FROM audit_events 
                    WHERE {where_clause}
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', params)
                
                rows = cursor.fetchall()
                
                # Convert to dictionaries and parse BLOB JSON data
                results = []
                for row in rows:
                    event_dict = dict(row)
                    
                    # Convert BLOB back to JSON following the article approach
                    if event_dict['details']:
                        # Convert binary data back to JSON string
                        json_data = event_dict['details'].decode('utf-8')
                        # Convert JSON string back to Python object
                        event_dict['details'] = json.loads(json_data)
                    
                    if event_dict['compliance_flags']:
                        # Convert binary data back to JSON string
                        json_data = event_dict['compliance_flags'].decode('utf-8')
                        # Convert JSON string back to Python object
                        event_dict['compliance_flags'] = json.loads(json_data)
                    
                    results.append(event_dict)
                
                return results
                
        except Exception as e:
            log.error(f"Failed to query audit events: {e}")
            return []


class HIPAAAuditPlugin(BasePlugin):
    """
    HIPAA Audit Plugin for comprehensive audit trail logging.
    
    Features:
    - Patient data access logging with BLOB JSON storage
    - Security event tracking
    - Automatic risk assessment
    - Comprehensive audit trail with tamper detection
    - HIPAA-compliant database schema
    - Data retention policies
    - Compliance reporting
    """
    
    name = "hipaa"
    version = "1.0.3"
    description = "HIPAA-compliant audit trail plugin with BLOB JSON storage and comprehensive audit features"
    
    def __init__(self, 
                 db_path: str = "hipaa_audit.db",
                 retention_days: int = 2555,  # 7 years as per HIPAA
                 auto_backup: bool = True,
                 encryption_key: Optional[str] = None,
                 session_timeout: int = 3600,  # 1 hour
                 **kwargs):
        """
        Initialize HIPAA audit plugin.
        
        Args:
            db_path: Path to SQLite database for audit logs
            retention_days: Number of days to retain audit records
            auto_backup: Whether to automatically backup audit logs
            encryption_key: Optional encryption key for sensitive data
            session_timeout: Session timeout in seconds
            **kwargs: Additional configuration options
        """
        super().__init__(**kwargs)
        
        self.db_path = db_path
        self.retention_days = retention_days
        self.auto_backup = auto_backup
        self.encryption_key = encryption_key
        self.session_timeout = session_timeout
        
        # Initialize database
        self.db = HIPAADatabase(db_path)
        
        # Session tracking
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        
    def install(self, manager: "PluginManager"):
        """Install the HIPAA audit plugin."""
        super().install(manager)
        
        # Register event listeners
        manager.on("record_processed", self.on_record_processed)
        manager.on("connection_established", self.on_connection_established)
        manager.on("connection_failed", self.on_connection_failed)
        manager.on("authentication_failed", self.on_authentication_failed)
        manager.on("data_access", self.on_data_access)
        manager.on("security_violation", self.on_security_violation)
        
        # Start background tasks
        self._start_background_tasks()
        
        log.info("HIPAA audit plugin installed successfully with JSONB support")
    
    def uninstall(self, manager: "PluginManager"):
        """Uninstall the HIPAA audit plugin."""
        super().uninstall(manager)
        
        # Stop background tasks
        self._stop_background_tasks()
        
        log.info("HIPAA audit plugin uninstalled successfully")
    
    def _start_background_tasks(self):
        """Start background tasks for maintenance."""
        # In a real implementation, you'd start background tasks here
        log.debug("HIPAA audit background tasks started")
    
    def _stop_background_tasks(self):
        """Stop background tasks."""
        log.debug("HIPAA audit background tasks stopped")
    
    def log_event(self, event: AuditEvent) -> int:
        """Log an audit event to the database."""
        try:
            event_id = self.db.insert_audit_event(event)
            
            # Log high-risk events
            if event.risk_level in ["HIGH", "CRITICAL"]:
                log.warning(f"High-risk HIPAA event logged: {event.event_type}", 
                           patient_id=event.patient_id, 
                           risk_level=event.risk_level)
            
            return event_id
            
        except Exception as e:
            log.error(f"Failed to log HIPAA audit event: {e}")
            return 0
    
    def on_record_processed(self, record: Any, server: Any = None):
        """Handle record processing events."""
        client_ip = self._get_client_ip(server)
        session_id = self._get_or_create_session(client_ip)
        
        # Handle different record types
        if isinstance(record, PatientRecord):
            patient_id = record.patient_id or "Unknown"
            event = AuditEvent(
                timestamp=datetime.now(timezone.utc).isoformat(),
                event_type="PATIENT_DATA_ACCESS",
                user_id="LIS-System",
                session_id=session_id,
                patient_id=patient_id,
                client_ip=client_ip,
                success=True,
                details={
                    "record_type": "PatientRecord",
                    "patient_name": str(record.patient_name) if record.patient_name else None,
                    "access_method": "ASTM_PROTOCOL",
                    "data_elements": ["patient_id", "patient_name", "demographics"]
                },
                risk_level="MEDIUM",
                data_classification="PHI",
                compliance_flags=["HIPAA_PATIENT_ACCESS"]
            )
            
        elif isinstance(record, list) and len(record) > 0:
            record_type = record[0] if record else "Unknown"
            
            if record_type == 'P':  # Patient record
                patient_id = record[1] if len(record) > 1 and record[1] else "Unknown"
                event = AuditEvent(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    event_type="PATIENT_DATA_ACCESS",
                    user_id="LIS-System",
                    session_id=session_id,
                    patient_id=patient_id,
                    client_ip=client_ip,
                    success=True,
                    details={
                        "record_type": "Patient",
                        "raw_record_length": len(record),
                        "access_method": "ASTM_PROTOCOL",
                        "data_elements": self._extract_data_elements(record)
                    },
                    risk_level="MEDIUM",
                    data_classification="PHI",
                    compliance_flags=["HIPAA_PATIENT_ACCESS"]
                )
                
            elif record_type == 'O':  # Order record
                sample_id = record[1] if len(record) > 1 and record[1] else "Unknown"
                event = AuditEvent(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    event_type="ORDER_DATA_ACCESS",
                    user_id="LIS-System",
                    session_id=session_id,
                    patient_id=None,
                    client_ip=client_ip,
                    success=True,
                    details={
                        "record_type": "Order",
                        "sample_id": sample_id,
                        "access_method": "ASTM_PROTOCOL",
                        "data_elements": ["sample_id", "test_code", "order_info"]
                    },
                    risk_level="LOW",
                    data_classification="PHI",
                    compliance_flags=["HIPAA_ORDER_ACCESS"]
                )
                
            elif record_type == 'R':  # Result record
                test_id = record[2] if len(record) > 2 and record[2] else "Unknown"
                event = AuditEvent(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    event_type="RESULT_DATA_ACCESS",
                    user_id="LIS-System",
                    session_id=session_id,
                    patient_id=None,
                    client_ip=client_ip,
                    success=True,
                    details={
                        "record_type": "Result",
                        "test_id": test_id,
                        "access_method": "ASTM_PROTOCOL",
                        "data_elements": ["test_id", "result_value", "units", "reference_range"]
                    },
                    risk_level="LOW",
                    data_classification="PHI",
                    compliance_flags=["HIPAA_RESULT_ACCESS"]
                )
            else:
                return  # Don't audit other record types
        else:
            return  # Unknown record type
        
        self.log_event(event)
    
    def _extract_data_elements(self, record: List[str]) -> List[str]:
        """Extract data elements from raw record."""
        elements = []
        if len(record) > 1 and record[1]:
            elements.append("patient_id")
        if len(record) > 5 and record[5]:
            elements.append("patient_name")
        if len(record) > 7 and record[7]:
            elements.append("birth_date")
        if len(record) > 8 and record[8]:
            elements.append("gender")
        return elements
    
    def _get_or_create_session(self, client_ip: str) -> str:
        """Get or create session ID for client."""
        import uuid
        session_id = f"session_{uuid.uuid4().hex[:8]}"
        
        if session_id not in self.active_sessions:
            self.active_sessions[session_id] = {
                "client_ip": client_ip,
                "created_at": datetime.now(timezone.utc),
                "last_activity": datetime.now(timezone.utc)
            }
        
        return session_id
    
    def _get_client_ip(self, server: Any) -> Optional[str]:
        """Extract client IP from server context."""
        # This would be implemented based on the server implementation
        return "127.0.0.1"
    
    def generate_compliance_report(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """Generate a comprehensive HIPAA compliance report."""
        try:
            filters = {
                'start_date': start_date,
                'end_date': end_date
            }
            
            events = self.db.query_events(filters, limit=10000)
            
            # Calculate statistics
            total_events = len(events)
            high_risk_events = len([e for e in events if e['risk_level'] in ['HIGH', 'CRITICAL']])
            failed_attempts = len([e for e in events if not e['success']])
            unique_patients = len(set(e['patient_id'] for e in events if e['patient_id']))
            unique_sessions = len(set(e['session_id'] for e in events if e['session_id']))
            
            # Event type breakdown
            event_types = {}
            for event in events:
                event_types[event['event_type']] = event_types.get(event['event_type'], 0) + 1
            
            # Risk level breakdown
            risk_levels = {}
            for event in events:
                risk_levels[event['risk_level']] = risk_levels.get(event['risk_level'], 0) + 1
            
            report = {
                "period": {"start": start_date, "end": end_date},
                "summary": {
                    "total_events": total_events,
                    "high_risk_events": high_risk_events,
                    "failed_attempts": failed_attempts,
                    "unique_patients": unique_patients,
                    "unique_sessions": unique_sessions
                },
                "breakdowns": {
                    "event_types": event_types,
                    "risk_levels": risk_levels
                },
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "compliance_status": "COMPLIANT" if high_risk_events == 0 else "REVIEW_REQUIRED"
            }
            
            # Store report in database using BLOB format
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Convert report to BLOB format
                report_json = json.dumps(report)
                report_blob = bytes(report_json, 'utf-8')
                
                cursor.execute('''
                    INSERT INTO compliance_reports (
                        report_date, report_type, total_events, high_risk_events,
                        failed_access_attempts, unique_patients, unique_sessions, report_data
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    start_date, "COMPLIANCE_REPORT", total_events, high_risk_events,
                    failed_attempts, unique_patients, unique_sessions, report_blob
                ))
                conn.commit()
            
            return report
            
        except Exception as e:
            log.error(f"Failed to generate compliance report: {e}")
            return {}
    
    def get_patient_access_history(self, patient_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get comprehensive access history for a specific patient."""
        try:
            filters = {'patient_id': patient_id}
            return self.db.query_events(filters, limit)
            
        except Exception as e:
            log.error(f"Failed to get patient access history: {e}")
            return []
    
    def verify_audit_integrity(self) -> Dict[str, Any]:
        """Verify the integrity of audit trail using checksums."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check for tampered records
                cursor.execute('''
                    SELECT COUNT(*) as tampered_count
                    FROM audit_events ae
                    LEFT JOIN audit_trail at ON ae.id = at.event_id
                    WHERE at.current_hash != ae.checksum
                ''')
                
                tampered_count = cursor.fetchone()[0]
                
                # Check for missing trail entries
                cursor.execute('''
                    SELECT COUNT(*) as missing_trail_count
                    FROM audit_events ae
                    LEFT JOIN audit_trail at ON ae.id = at.event_id
                    WHERE at.event_id IS NULL
                ''')
                
                missing_trail_count = cursor.fetchone()[0]
                
                integrity_status = "INTACT" if tampered_count == 0 and missing_trail_count == 0 else "COMPROMISED"
                
                return {
                    "integrity_status": integrity_status,
                    "tampered_records": tampered_count,
                    "missing_trail_entries": missing_trail_count,
                    "verified_at": datetime.now(timezone.utc).isoformat()
                }
                
        except Exception as e:
            log.error(f"Failed to verify audit integrity: {e}")
            return {"integrity_status": "ERROR", "error": str(e)}
    
    def cleanup_old_records(self):
        """Clean up old audit records based on retention policy."""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.retention_days)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Archive old records before deletion (if auto_backup is enabled)
                if self.auto_backup:
                    self._archive_old_records(cursor, cutoff_date)
                
                # Delete old records
                cursor.execute('''
                    DELETE FROM audit_events
                    WHERE timestamp < ?
                ''', (cutoff_date.isoformat(),))
                
                deleted_count = cursor.rowcount
                
                # Clean up orphaned trail entries
                cursor.execute('''
                    DELETE FROM audit_trail
                    WHERE event_id NOT IN (SELECT id FROM audit_events)
                ''')
                
                conn.commit()
                
                if deleted_count > 0:
                    log.info(f"Cleaned up {deleted_count} old audit records")
                    
        except Exception as e:
            log.error(f"Failed to cleanup old audit records: {e}")
    
    def _archive_old_records(self, cursor, cutoff_date):
        """Archive old records to separate file."""
        # Implementation for archiving would go here
        pass
    
    # Event handlers
    def on_connection_established(self, client_ip: str, user_id: str = "Unknown"):
        """Handle successful connection events."""
        session_id = self._get_or_create_session(client_ip)
        event = AuditEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type="CONNECTION_ESTABLISHED",
            user_id=user_id,
            session_id=session_id,
            client_ip=client_ip,
            success=True,
            details={"connection_type": "ASTM"},
            risk_level="LOW",
            data_classification="GENERAL"
        )
        self.log_event(event)
    
    def on_connection_failed(self, client_ip: str, reason: str, user_id: str = "Unknown"):
        """Handle failed connection events."""
        event = AuditEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type="CONNECTION_FAILED",
            user_id=user_id,
            client_ip=client_ip,
            success=False,
            error_message=reason,
            details={"reason": reason, "connection_type": "ASTM"},
            risk_level="HIGH",
            data_classification="GENERAL",
            compliance_flags=["SECURITY_INCIDENT"]
        )
        self.log_event(event)
    
    def on_authentication_failed(self, client_ip: str, user_id: str = "Unknown"):
        """Handle authentication failure events."""
        event = AuditEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type="AUTHENTICATION_FAILED",
            user_id=user_id,
            client_ip=client_ip,
            success=False,
            details={"auth_type": "ASTM"},
            risk_level="CRITICAL",
            data_classification="GENERAL",
            compliance_flags=["SECURITY_INCIDENT", "AUTH_FAILURE"]
        )
        self.log_event(event)
    
    def on_data_access(self, data_type: str, client_ip: str, user_id: str = "Unknown"):
        """Handle general data access events."""
        session_id = self._get_or_create_session(client_ip)
        event = AuditEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type="DATA_ACCESS",
            user_id=user_id,
            session_id=session_id,
            client_ip=client_ip,
            success=True,
            details={"data_type": data_type},
            risk_level="LOW",
            data_classification="PHI"
        )
        self.log_event(event)
    
    def on_security_violation(self, violation_type: str, client_ip: str, 
                            details: Dict[str, Any], user_id: str = "Unknown"):
        """Handle security violation events."""
        event = AuditEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type="SECURITY_VIOLATION",
            user_id=user_id,
            client_ip=client_ip,
            success=False,
            details={"violation_type": violation_type, **details},
            risk_level="CRITICAL",
            data_classification="GENERAL",
            compliance_flags=["SECURITY_INCIDENT", "VIOLATION"]
        )
        self.log_event(event) 