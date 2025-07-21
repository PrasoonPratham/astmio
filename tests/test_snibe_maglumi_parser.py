"""
Tests for parsing Snibe Maglumi analyzer data.
"""

import pytest
from pathlib import Path

from astmio import decode
from tests.test_parsing_logic import extract_astm_messages, load_profile


class TestSnibeMaglumiParser:
    """Test ASTM data parsing for Snibe Maglumi analyzers."""

    @pytest.fixture
    def example_data_dir(self):
        """Get the example ASTM data directory."""
        return Path(__file__).parent.parent / "example_astm"

    @pytest.fixture
    def profiles_dir(self):
        """Get the profiles directory."""
        return Path(__file__).parent.parent / "profiles"

    def test_parse_snibe_maglumi_data(self, example_data_dir, profiles_dir):
        """Test parsing Snibe Maglumi analyzer data."""
        data_file = example_data_dir / "Snibe" / "malglumi edata logs.txt"
        with open(data_file, "r") as f:
            raw_data = f.read()

        load_profile(profiles_dir, "snibe_maglumi.yaml")

        messages = extract_astm_messages(raw_data)
        assert len(messages) > 0, "Should extract at least one message from Snibe data"

        parsed_count = 0
        for i, message in enumerate(messages):
            try:
                message_bytes = message.encode("latin-1")
                records = decode(message_bytes)

                assert len(records) > 0, f"Message {i} should have at least one record"

                for record in records:
                    if record[0] == "H":
                        if len(record) > 4:
                            assert (
                                record[3] == "PSWD" or record[3] is None
                            ), "Password field should be PSWD"
                            if len(record) > 5:
                                assert (
                                    "Maglumi" in str(record[4]) or record[4] is None
                                ), "Sender should contain Maglumi"
                    elif record[0] == "R":
                        assert (
                            len(record) >= 4
                        ), "Result record should have at least 4 fields"
                        if len(record) > 2 and record[2]:
                            assert str(record[2]).startswith(
                                "^^^"
                            ), f"Test ID should start with ^^^, got {record[2]}"

                parsed_count += 1

            except Exception:
                continue

        assert parsed_count > 0, "Should successfully parse at least one Snibe message"
