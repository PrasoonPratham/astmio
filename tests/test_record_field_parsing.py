"""
Tests for parsing specific record fields in ASTM messages.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
try:
    from astmio.codec import decode

    print("Got the decode implementation")
except ImportError:
    print("Error: decode")


class TestRecordFieldParsing:
    """Test parsing of specific fields within ASTM records."""

    def test_record_field_mapping(self):
        """Test that profile field mappings work correctly."""
        # Test with a sample message
        sample_message = (
            b"H|\\^&||PSWD|Maglumi User|||||Lis||P|E1394-97|20250701"
        )
        records = decode(sample_message)
        header = records[0]

        assert len(records) == 1

        assert header[0] == "H"
        # Delimiter field contains separators
        assert header[1] == "\\^&"  # Field separator definition
        assert header[3] == "PSWD"
        assert header[4] == "Maglumi User"
        assert header[9] == "Lis"
        assert header[11] == "P"
        assert header[12] == "E1394-97"
        assert header[13] == "20250701"

    def test_multi_test_parsing(self):
        """Test parsing of multiple tests in Order record."""
        # Sample with multiple tests separated by backslash
        sample_message = b"O|1|25059232||^^^TT3 II\\^^^TT4 II\\^^^TSH II"
        records = decode(sample_message)

        assert len(records) == 1
        order = records[0]
        assert order[0] == "O"
        assert order[1] == "1"
        assert order[2] == "25059232"
        # The test field should contain the repeated tests
        test_field = order[4]
        test_field_str = str(test_field)
        assert "TT3 II" in test_field_str
        assert "TT4 II" in test_field_str
        assert "TSH II" in test_field_str

    def test_result_parsing(self):
        """Test parsing of result records."""
        sample_message = (
            b"R|1|^^^TT3 II|1.171|ng/mL|0.75 to 2.1|N||||||20250630151157"
        )
        records = decode(sample_message)

        assert len(records) == 1
        result = records[0]
        assert result[0] == "R"
        assert result[1] == "1"
        # Test ID field is parsed as components
        assert isinstance(result[2], list) or result[2] == "^^^TT3 II"
        if isinstance(result[2], list):
            assert "TT3 II" in str(result[2])
        else:
            assert result[2] == "^^^TT3 II"
        assert result[3] == "1.171"
        assert result[4] == "ng/mL"
        assert result[5] == "0.75 to 2.1"
        assert result[6] == "N"
        # Check timestamp field
        assert len(result) > 12 and result[12] == "20250630151157"
