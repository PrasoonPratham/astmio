"""
Tests for parsing BS-240 analyzer data.
"""

import pytest
from pathlib import Path

from astmio import decode
from tests.test_parsing_logic import extract_astm_messages, load_profile


class TestBS240Parser:
    """Test ASTM data parsing for BS-240 analyzers."""

    @pytest.fixture
    def example_data_dir(self):
        """Get the example ASTM data directory."""
        return Path(__file__).parent.parent / "example_astm"

    @pytest.fixture
    def profiles_dir(self):
        """Get the profiles directory."""
        return Path(__file__).parent.parent / "profiles"

    def test_parse_bs240_data(self, example_data_dir, profiles_dir):
        """Test parsing BS-240 analyzer data."""
        data_file = example_data_dir / "bs-240" / "bs-240 astm.txt"
        with open(data_file, "r") as f:
            raw_data = f.read()

        load_profile(profiles_dir, "mindray_bs240.yaml")
        messages = extract_astm_messages(raw_data)
        assert len(messages) > 0, "Should extract at least one message from BS-240 data"

        for i, message in enumerate(messages):
            try:
                message_bytes = message.encode("latin-1")
                records = decode(message_bytes)

                assert len(records) > 0, f"Message {i} should have at least one record"

                for record in records:
                    record_type = record[0]
                    assert record_type in [
                        "H",
                        "P",
                        "O",
                        "R",
                        "L",
                    ], f"Invalid record type: {record_type}"

            except Exception as e:
                pytest.fail(f"Failed to parse BS-240 message {i}: {str(e)}")
