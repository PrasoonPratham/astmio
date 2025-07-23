"""
Tests for parsing Erba analyzer data.
"""

from pathlib import Path

import pytest

from astmio import decode
from tests.test_parsing_logic import extract_astm_messages, load_profile


class TestErbaParser:
    """Test ASTM data parsing for Erba analyzers."""

    @pytest.fixture
    def example_data_dir(self):
        """Get the example ASTM data directory."""
        return Path(__file__).parent.parent / "example_astm"

    @pytest.fixture
    def profiles_dir(self):
        """Get the profiles directory."""
        return Path(__file__).parent.parent / "profiles"

    def test_parse_erba_data(self, example_data_dir, profiles_dir):
        """Test parsing Erba analyzer data."""
        data_file = example_data_dir / "erba" / "erba_raw.txt"
        with open(data_file) as f:
            raw_data = f.read()

        load_profile(profiles_dir, "erba.yaml")

        if "MSH|" in raw_data and "OBX|" in raw_data:
            pytest.skip(
                "Erba data appears to be HL7 format, not ASTM - "
                "skipping ASTM parsing test"
            )

        messages = extract_astm_messages(raw_data)
        assert (
            len(messages) > 0
        ), "Should extract at least one message from Erba data"

        for i, message in enumerate(messages):
            try:
                message_bytes = message.encode("latin-1")
                records = decode(message_bytes)

                assert (
                    len(records) > 0
                ), f"Message {i} should have at least one record"

                record_types = [r[0] for r in records]
                assert "H" in record_types, "Should have Header record"

            except Exception as e:
                pytest.fail(f"Failed to parse Erba message {i}: {str(e)}")
