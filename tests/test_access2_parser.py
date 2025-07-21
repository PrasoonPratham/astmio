"""
Tests for parsing Access 2 analyzer data.
"""

import pytest
from pathlib import Path

from astmio import decode
from tests.test_parsing_logic import extract_astm_messages, load_profile


class TestAccess2Parser:
    """Test ASTM data parsing for Access 2 analyzers."""

    @pytest.fixture
    def example_data_dir(self):
        """Get the example ASTM data directory."""
        return Path(__file__).parent.parent / "example_astm"

    @pytest.fixture
    def profiles_dir(self):
        """Get the profiles directory."""
        return Path(__file__).parent.parent / "profiles"

    def test_parse_access2_data(self, example_data_dir, profiles_dir):
        """Test parsing Access 2 analyzer data."""
        data_file = example_data_dir / "Access 2" / "Access 2 AnalyzerLogs.txt"
        with open(data_file, "r") as f:
            raw_data = f.read()

        profile = load_profile(profiles_dir, "access2.yaml")
        messages = extract_astm_messages(raw_data)
        assert (
            len(messages) > 0
        ), "Should extract at least one message from Access 2 data"

        for i, message in enumerate(messages):
            try:
                message_bytes = message.encode("latin-1")
                records = decode(message_bytes)

                assert len(records) > 0, f"Message {i} should have at least one record"

                first_record = records[0]
                assert first_record[0] in [
                    "H",
                    "P",
                    "O",
                    "R",
                    "L",
                    "C",
                ], (
                    f"First record of message {i} should be valid ASTM record "
                    f"type, got {first_record[0]}"
                )

                for record in records:
                    record_type = record[0]
                    if record_type in profile["records"]:
                        profile["records"][record_type].get("fields", [])
                        assert (
                            len(record) >= 2
                        ), f"Record type {record_type} should have at least 2 fields"

            except Exception as e:
                pytest.fail(f"Failed to parse Access 2 message {i}: {str(e)}")
