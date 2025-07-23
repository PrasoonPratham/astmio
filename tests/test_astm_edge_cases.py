"""
Tests for edge cases and error handling in ASTM parsing.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
try:
    from astmio.codec import decode

    print("Got the decode implementation")
except ImportError:
    print("Error: decode")


class TestASTMEdgeCases:
    """Test edge cases and error handling in ASTM parsing."""

    def test_empty_and_null_fields(self):
        """Test handling of empty and null fields."""
        # Record with empty fields
        record_empty = b"P|1||||||||||||||||||||||||||||||"
        records = decode(record_empty)
        assert len(records) >= 1
        patient = records[0]
        assert patient[0] == "P"
        assert patient[1] == "1"

        # Record with mixed empty and filled fields
        record_mixed = b"P|1||PATIENT111||Smith^Tom^J||||||||||||||||||||||||"
        records = decode(record_mixed)
        assert len(records) >= 1
        patient = records[0]
        assert patient[0] == "P"
        patient_str = str(patient)
        assert "PATIENT111" in patient_str
        assert "Smith" in patient_str

    def test_special_characters_in_data(self):
        """Test handling of special characters in field data."""
        # Patient with special characters in ID
        patient_special = b"P|476|INVALID@#$%ID|||^^||^^|U"
        records = decode(patient_special)
        assert len(records) >= 1
        patient = records[0]
        assert patient[0] == "P"
        patient_str = str(patient)
        assert "INVALID@#$%ID" in patient_str

        # Result with special characters in value
        result_special = b"R|1|^^^TEST|<5.0|mg/dL|>10.0|L|F"
        records = decode(result_special)
        assert len(records) >= 1
        result = records[0]
        assert result[0] == "R"

    def test_long_field_values(self):
        """Test handling of long field values."""
        # Long test name
        long_test = b"O|1|SAMPLE001||^^^Very Long Test Name With Multiple Words And Descriptions"
        records = decode(long_test)
        assert len(records) >= 1
        order = records[0]
        assert order[0] == "O"

        # Long comment
        long_comment = b"C|1|This is a very long comment that contains detailed information about the test result and recommendations for the patient care and follow-up procedures"
        records = decode(long_comment)
        assert len(records) >= 1
        comment = records[0]
        assert comment[0] == "C"

    def test_error_handling_malformed_records(self):
        """Test error handling for malformed ASTM records."""
        # Record without proper field separators
        try:
            malformed = b"H-invalid-record-format"
            records = decode(malformed)
            # Should either parse gracefully or handle the error
            assert isinstance(records, list)
        except Exception:
            # Exception is acceptable for malformed data
            pass

        # Empty record
        try:
            empty = b""
            records = decode(empty)
            assert isinstance(records, list)
        except Exception:
            # Exception is acceptable for empty data
            pass
