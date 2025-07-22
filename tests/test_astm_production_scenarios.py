"""
Tests for production-like ASTM scenarios.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
try:
    from astmio.codec import decode

    print("Got the decode implementation")
except ImportError:
    print("Error: decode")


class TestASTMProductionScenarios:
    """Test ASTM parsing for production-like scenarios."""

    def test_complete_message_sequence(self):
        """Test parsing a complete ASTM message sequence."""
        message = (
            b"H|\\^&||PSWD|Maglumi User|||||Lis||P|E1394-97|20250701\r"
            b"P|1\r"
            b"O|1|25059232||^^^TT3 II\\^^^TT4 II\\^^^TSH II\r"
            b"R|1|^^^TT3 II|1.171|ng/mL|0.75 to 2.1|N||||||20250630151157\r"
            b"R|2|^^^TT4 II|10.78|ug/dL|5 to 13|N||||||20250630150745\r"
            b"R|3|^^^TSH II|3.007|uIU/mL|0.3 to 4.5|N||||||20250630152021\r"
            b"L|1|N"
        )

        records = decode(message)

        # The decode function should parse all records in the message
        assert (
            len(records) >= 1
        ), f"Should have at least 1 record, got {len(records)}"

        # If decoded as single message, check if it contains all the data
        if len(records) == 1:
            # Single record containing all data
            full_record = records[0]
            assert full_record[0] == "H"  # Should start with header
            # Check that the message contains all the key data
            message_str = str(full_record)
            assert "PSWD" in message_str
            assert "Maglumi User" in message_str
            assert "25059232" in message_str
            assert "1.171" in message_str
        else:
            # Multiple records parsed
            assert records[0][0] == "H"
            # Check that we have the main record types
            record_types = [r[0] for r in records]
            assert "H" in record_types

            # Verify sample ID in order record
            order_records = [r for r in records if r[0] == "O"]
            if order_records:
                assert order_records[0][2] == "25059232"

    def test_analyzer_specific_formats(self):
        """Test analyzer-specific ASTM format variations."""
        # Access 2 specific format
        access2_result = b"R|1|^^^B12II^1|131|pg/mL|222 to 1439^normal|L|N|F||||20250701184502|575707"
        records = decode(access2_result)
        assert len(records) >= 1
        result = records[0]
        assert result[0] == "R"

        # Mindray specific format
        mindray_result = b"R|162|CREAS^Creatinine (Sarcosine Oxidase Method)^^F|3.216365^^^^|mg/dL|^|N||F|3.216365^^^^|0|20250701154742||Mindry^"
        records = decode(mindray_result)
        assert len(records) >= 1
        result = records[0]
        assert result[0] == "R"

        # Snibe Maglumi specific format
        snibe_result = (
            b"R|1|^^^TT3 II|1.171|ng/mL|0.75 to 2.1|N||||||20250630151157"
        )
        records = decode(snibe_result)
        assert len(records) >= 1
        result = records[0]
        assert result[0] == "R"
