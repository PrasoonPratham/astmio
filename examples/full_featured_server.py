
import asyncio
from astmio.server import create_server
from astmio.records import PatientRecord, OrderRecord, HeaderRecord, ResultRecord, TerminatorRecord
from astmio.plugins.hipaa import HIPAAAuditPlugin
from astmio.logging import get_logger

log = get_logger(__name__)

# 1. Simple handler functions, now with no manual plugin calls
def handle_patient(record, server: "Server"):
    if isinstance(record, PatientRecord):
        patient_name = record.patient_name
        patient_id = record.patient_id or "Unknown"
        if patient_name and hasattr(patient_name, 'first_name'):
            name = f"{patient_name.first_name} {patient_name.last_name}"
        else:
            name = str(patient_name) if patient_name else "Unknown"
    else:
        # Handle raw list format
        patient_id = record[1] if len(record) > 1 and record[1] else "Unknown"
        name = "Unknown"
    
    log.info(
        "Patient Record Processed",
        patient_name=name,
        patient_id=patient_id,
    )

def handle_order(record: OrderRecord, server: "Server"):
    log.info("Received Order Record", sample_id=record.sample_id)

def handle_result(record: ResultRecord, server: "Server"):
    log.info("Received Result", test=record.test_id, value=record.result_value)

def handle_header(record: HeaderRecord, server: "Server"):
    log.info("Received Header", version=record.version)

def handle_terminator(record: TerminatorRecord, server: "Server"):
    log.info("Session terminated", code=record.termination_code)

async def main():
    # 2. The final, perfect API
    server = await create_server(
        profile_file="etc/profiles/mindray_bs240.yaml",
        handlers={
            "P": handle_patient,
            "O": handle_order,
            "H": handle_header,
            "R": handle_result,
            "L": handle_terminator,
        },
        plugins=[HIPAAAuditPlugin(db_path="hipaa_audit.db")],
        log_level="DEBUG"
    )

    print("Starting full-featured, event-driven server.")
    await server.serve_forever()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server shutting down.") 