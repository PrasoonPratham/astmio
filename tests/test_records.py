"""
Tests for individual ASTM record types and their validation.
"""

import pytest
from datetime import datetime
from decimal import Decimal

from astmio.modern_records import (
    HeaderRecord,
    PatientRecord,
    OrderRecord,
    ResultRecord,
    CommentRecord,
    TerminatorRecord,
)
from astmio import decode_record, encode_record


class TestModernRecords:
    """Test modern Pydantic-based ASTM records."""

    def test_header_record_creation(self):
        """Test creating a header record with modern API."""
        header = HeaderRecord(
            delimiter=r"\^&",
            message_id="MSG001",
            password="PSWD",
            sender="Maglumi User",
            receiver="LIS",
            processing_id="P",
            version="E1394-97",
            timestamp=datetime(2025, 7, 1, 10, 30, 0),
        )

        assert header.record_type == "H"
        assert header.delimiter == r"\^&"
        assert header.message_id == "MSG001"
        assert header.password == "PSWD"
        assert header.sender == "Maglumi User"
        assert header.receiver == "LIS"
        assert header.processing_id == "P"
        assert header.version == "E1394-97"
        assert header.timestamp.year == 2025

    def test_header_record_validation(self):
        """Test header record validation."""
        # Test invalid processing_id
        with pytest.raises(ValueError) as exc_info:
            HeaderRecord(processing_id="X")
        assert "Input should be 'P', 'T' or 'D'" in str(exc_info.value)

        # Test phone validation
        header = HeaderRecord(phone="123-456-7890")
        assert header.phone == "123-456-7890"

        # Test invalid phone
        with pytest.raises(ValueError) as exc_info:
            HeaderRecord(phone="invalid-phone")
        assert "Phone number must contain only digits" in str(exc_info.value)

    def test_patient_record_creation(self):
        """Test creating a patient record."""
        patient = PatientRecord(
            sequence=1,
            patient_id="12345",
            name="John Doe",
            birthdate=datetime(1980, 5, 15),
            sex="M",
            height=Decimal("175.5"),
            weight=Decimal("70.2"),
        )

        assert patient.record_type == "P"
        assert patient.sequence == 1
        assert patient.patient_id == "12345"
        assert patient.name == "John Doe"
        assert patient.sex == "M"
        assert patient.height == Decimal("175.5")
        assert patient.weight == Decimal("70.2")

    def test_patient_record_validation(self):
        """Test patient record validation."""
        # Test sequence validation
        with pytest.raises(ValueError):
            PatientRecord(sequence=0)  # Too low

        with pytest.raises(ValueError):
            PatientRecord(sequence=100)  # Too high

        # Test sex validation
        patient = PatientRecord(sequence=1, sex="F")
        assert patient.sex == "F"

        patient = PatientRecord(sequence=1, sex="U")  # Unknown
        assert patient.sex == "U"

        # Test height/weight validation
        with pytest.raises(ValueError):
            PatientRecord(sequence=1, height=Decimal("-10"))  # Negative height

        with pytest.raises(ValueError):
            PatientRecord(sequence=1, weight=Decimal("-5"))  # Negative weight

    def test_order_record_creation(self):
        """Test creating an order record."""
        order = OrderRecord(
            sequence=1,
            sample_id="25059232",
            test="^^^TT3 II\\^^^TT4 II\\^^^TSH II",
            priority="R",
            created_at=datetime(2025, 6, 30, 9, 0, 0),  # Before sample collection
            sampled_at=datetime(2025, 6, 30, 9, 30, 0),
            volume=Decimal("5.0"),
            biomaterial="Serum",
        )

        assert order.record_type == "O"
        assert order.sequence == 1
        assert order.sample_id == "25059232"
        assert order.test == "^^^TT3 II\\^^^TT4 II\\^^^TSH II"
        assert order.priority == "R"
        assert order.volume == Decimal("5.0")
        assert order.biomaterial == "Serum"

    def test_order_record_priority_validation(self):
        """Test order record priority validation."""
        # Valid priorities
        for priority in ["S", "A", "R"]:
            order = OrderRecord(sequence=1, priority=priority)
            assert order.priority == priority

        # Test None is allowed
        order = OrderRecord(sequence=1, priority=None)
        assert order.priority is None

    def test_result_record_creation(self):
        """Test creating a result record."""
        result = ResultRecord(
            sequence=1,
            test="^^^TT3 II",
            value=Decimal("1.171"),
            units="ng/mL",
            references="0.75 to 2.1",
            abnormal_flag="N",
            status="F",
            completed_at=datetime(2025, 6, 30, 15, 11, 57),
        )

        assert result.record_type == "R"
        assert result.sequence == 1
        assert result.test == "^^^TT3 II"
        assert result.value == Decimal("1.171")
        assert result.units == "ng/mL"
        assert result.references == "0.75 to 2.1"
        assert result.abnormal_flag == "N"
        assert result.status == "F"

    def test_result_record_validation(self):
        """Test result record validation."""
        # Test abnormal flags
        valid_flags = ["N", "A", "H", "L", "HH", "LL"]
        for flag in valid_flags:
            result = ResultRecord(sequence=1, abnormal_flag=flag)
            assert result.abnormal_flag == flag

        # Test status codes
        valid_statuses = ["F", "P", "C", "X"]
        for status in valid_statuses:
            result = ResultRecord(sequence=1, status=status)
            assert result.status == status

        # Test value validation - empty string becomes None
        result = ResultRecord(sequence=1, value="")
        assert result.value is None

    def test_comment_record(self):
        """Test comment record creation."""
        comment = CommentRecord(
            sequence=1, source="I", data="Sample hemolyzed", comment_type="G"
        )

        assert comment.record_type == "C"
        assert comment.sequence == 1
        assert comment.source == "I"
        assert comment.data == "Sample hemolyzed"
        assert comment.comment_type == "G"

    def test_terminator_record(self):
        """Test terminator record creation."""
        terminator = TerminatorRecord(sequence=1, termination_code="N")

        assert terminator.record_type == "L"
        assert terminator.sequence == 1
        assert terminator.termination_code == "N"

        # Test other termination codes
        for code in ["T", "Q"]:
            term = TerminatorRecord(sequence=1, termination_code=code)
            assert term.termination_code == code

    def test_record_serialization(self):
        """Test converting records to different formats."""
        header = HeaderRecord(
            sender="Test Lab", receiver="LIS System", version="E1394-97"
        )

        # Test JSON serialization
        json_str = header.to_json()
        assert "Test Lab" in json_str
        assert "LIS System" in json_str

        # Test XML serialization
        xml_str = header.to_xml()
        assert "<sender>Test Lab</sender>" in xml_str
        assert "<receiver>LIS System</receiver>" in xml_str

        # Test CSV row
        csv_row = header.to_csv_row()
        assert "Test Lab" in csv_row
        assert "LIS System" in csv_row


class TestLegacyRecords:
    """Test legacy mapping-based ASTM records."""

    def test_legacy_header_encoding(self):
        """Test encoding legacy header record."""
        # Create a header record using the legacy system
        header_data = [
            "H",
            ["", "^&"],
            None,
            "PSWD",
            "Maglumi User",
            None,
            None,
            None,
            None,
            "Lis",
            None,
            "P",
            "E1394-97",
            "20250701",
        ]

        # Encode the record
        encoded = encode_record(header_data, "latin-1")
        # Check that key fields are encoded correctly
        assert encoded.startswith(b"H|")
        assert b"PSWD" in encoded
        assert b"Maglumi User" in encoded
        assert b"Lis" in encoded
        assert b"P" in encoded
        assert b"E1394-97" in encoded
        assert b"20250701" in encoded

    def test_legacy_patient_encoding(self):
        """Test encoding legacy patient record."""
        patient_data = ["P", "1"]
        encoded = encode_record(patient_data, "latin-1")
        assert encoded == b"P|1"

    def test_legacy_order_encoding(self):
        """Test encoding legacy order record."""
        order_data = [
            "O",
            "1",
            "25059232",
            None,
            ["^^^TT3 II", "^^^TT4 II", "^^^TSH II"],
        ]
        encoded = encode_record(order_data, "latin-1")
        assert b"O|1|25059232||" in encoded
        assert b"^^^TT3 II" in encoded

    def test_legacy_result_encoding(self):
        """Test encoding legacy result record."""
        result_data = [
            "R",
            "1",
            "^^^TT3 II",
            "1.171",
            "ng/mL",
            "0.75 to 2.1",
            "N",
            None,
            None,
            None,
            None,
            None,
            "20250630151157",
        ]
        encoded = encode_record(result_data, "latin-1")
        # Check that key fields are encoded correctly
        assert encoded.startswith(b"R|1|")
        assert b"TT3 II" in encoded
        assert b"1.171" in encoded
        assert b"ng/mL" in encoded
        assert b"0.75 to 2.1" in encoded
        assert b"N" in encoded
        assert b"20250630151157" in encoded

    def test_legacy_terminator_encoding(self):
        """Test encoding legacy terminator record."""
        term_data = ["L", "1", "N"]
        encoded = encode_record(term_data, "latin-1")
        assert encoded == b"L|1|N"


class TestRecordDecoding:
    """Test decoding ASTM records from bytes."""

    def test_decode_header(self):
        """Test decoding header record."""
        data = b"H|\\^&||PSWD|Maglumi User|||||Lis||P|E1394-97|20250701"
        record = decode_record(data, "latin-1")

        assert record[0] == "H"
        # The decode function parses ^& as components: [[empty], [empty, &]]
        assert record[1] == [[None], [None, "&"]]
        assert record[2] is None  # Empty field becomes None
        assert record[3] == "PSWD"
        assert record[4] == "Maglumi User"
        # Multiple empty fields
        assert record[5] is None
        assert record[6] is None
        assert record[7] is None
        assert record[8] is None
        assert record[9] == "Lis"
        assert record[10] is None
        assert record[11] == "P"
        assert record[12] == "E1394-97"
        assert record[13] == "20250701"

    def test_decode_patient(self):
        """Test decoding patient record."""
        data = b"P|1|12345^||Smith^John^||19900101|M|||||||||||||||||"
        record = decode_record(data, "latin-1")

        assert record[0] == "P"
        assert record[1] == "1"
        # Patient ID with component: 12345^
        assert record[2] == ["12345", None]
        assert record[3] is None  # Empty field
        # Patient name with components: Smith^John^
        assert record[4] == ["Smith", "John", None]
        assert record[5] is None  # Empty field
        assert record[6] == "19900101"
        assert record[7] == "M"

    def test_decode_order_with_multiple_tests(self):
        """Test decoding order record with multiple test codes."""
        data = b"O|1|SID123||^GLU\\^CHOL\\^HDL^R|||||||||20250701120000||||F"
        record = decode_record(data, "latin-1")

        assert record[0] == "O"
        assert record[1] == "1"
        assert record[2] == "SID123"
        assert record[3] is None  # Empty field
        # Universal test ID with multiple tests: ^GLU\^CHOL\^HDL^R
        # The repeat separators (\) create nested lists, components (^)
        # separate within each repeat
        assert record[4] == [[None, "GLU"], [None, "CHOL"], [None, "HDL", "R"]]
        # Multiple empty fields follow
        for i in range(5, 13):
            assert record[i] is None
        assert record[13] == "20250701120000"  # Field 13, not 12
        # More empty fields
        assert record[14] is None
        assert record[15] is None
        assert record[16] is None
        assert record[17] == "F"

    def test_decode_result(self):
        """Test decoding result record."""
        data = b"R|1|^GLU^mg/dL|150|mg/dL|70-110|H|||F||20250701120000|20250701120500"
        record = decode_record(data, "latin-1")

        assert record[0] == "R"
        assert record[1] == "1"
        # Universal test ID: ^GLU^mg/dL has components
        assert record[2] == [None, "GLU", "mg/dL"]
        assert record[3] == "150"
        assert record[4] == "mg/dL"
        assert record[5] == "70-110"
        assert record[6] == "H"  # Abnormal flag
        assert record[7] is None  # Empty field
        assert record[8] is None  # Empty field
        assert record[9] == "F"
        assert record[10] is None  # Empty field
        assert record[11] == "20250701120000"
        assert record[12] == "20250701120500"
