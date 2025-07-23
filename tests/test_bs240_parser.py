"""
Tests for parsing BS-240 analyzer data.
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
try:
    from astmio.codec import decode
except ImportError as ie:
    raise ie


class TestBS240Parser:
    """Test ASTM data parsing for BS-240 analyzer."""

    @pytest.fixture
    def example_data_dir(self):
        """Get the example ASTM data directory."""
        return Path(__file__).parent.parent / "example_astm"

    @pytest.fixture
    def profiles_dir(self):
        """Get the profiles directory."""
        return Path(__file__).parent.parent / "profiles"

    def load_profile(self, profile_path: Path) -> Dict[str, Any]:
        """Load a YAML profile configuration."""
        with open(profile_path) as f:
            return yaml.safe_load(f)

    def extract_astm_messages(self, raw_data: str) -> list[str]:
        """Extract ASTM messages from raw data, handling various formats."""
        messages = []
        current_message = []
        in_message = False

        # Special handling for Access 2 format which has very specific structure
        if "ACCESS" in raw_data and "[STX]" in raw_data:
            # For Access 2, we need to extract the actual ASTM data from between markers
            # and reconstruct proper records
            lines = raw_data.split("\n")
            current_record = ""
            record_type = None

            for line in lines:
                line = line.strip()

                # Skip control/status lines
                if (
                    not line
                    or line.startswith(" - ")
                    or line in ["[ENQ]", "[ACK]", "[EOT]"]
                ):
                    continue

                # Check for start/end markers
                if "[STX]" in line:
                    in_message = True
                    continue
                elif "[ETX]" in line:
                    # End of current record, process what we have
                    if current_record and record_type:
                        # Clean up the record - remove extra spaces and control markers
                        clean_record = current_record.replace(
                            "[CR]", ""
                        ).replace("[LF]", "")
                        clean_record = "|".join(
                            [
                                part.strip()
                                for part in clean_record.split("|")
                                if part.strip()
                            ]
                        )
                        if clean_record and clean_record[0] in [
                            "H",
                            "P",
                            "O",
                            "R",
                            "L",
                            "C",
                        ]:
                            current_message.append(clean_record)
                    current_record = ""
                    record_type = None
                    continue

                if in_message:
                    # Remove embedded control markers
                    clean_line = (
                        line.replace("[CR]", "").replace("[LF]", "").strip()
                    )
                    if not clean_line:
                        continue

                    # Try to identify record type
                    for rt in ["H|", "P|", "O|", "R|", "L|", "C|"]:
                        if rt in clean_line:
                            if current_record and record_type:
                                # Finish previous record
                                clean_record = current_record.replace(
                                    "[CR]", ""
                                ).replace("[LF]", "")
                                clean_record = "|".join(
                                    [
                                        part.strip()
                                        for part in clean_record.split("|")
                                        if part.strip()
                                    ]
                                )
                                if clean_record and clean_record[0] in [
                                    "H",
                                    "P",
                                    "O",
                                    "R",
                                    "L",
                                    "C",
                                ]:
                                    current_message.append(clean_record)

                            # Start new record
                            record_type = rt[0]
                            current_record = clean_line
                            break
                    else:
                        # Continuation of current record
                        if current_record:
                            current_record += clean_line

            # Add any remaining message
            if current_message:
                messages.append("\r".join(current_message))

        # First, try to extract from lines with [CR] markers (BS-240 format)
        elif "[CR]" in raw_data and "[STX]" in raw_data:
            # Split by STX/ETX boundaries first
            parts = raw_data.split("[STX]")
            for part in parts[1:]:  # Skip first empty part
                if "[ETX]" in part:
                    message_content = part.split("[ETX]")[0]
                    # Split by [CR] to get individual records
                    records = [
                        r.strip()
                        for r in message_content.split("[CR]")
                        if r.strip()
                    ]
                    if records:
                        messages.append("\r".join(records))

        # If no messages found, try line-by-line extraction (Snibe format)
        if not messages:
            lines = raw_data.split("\n")
            for line in lines:
                line = line.strip()

                # Skip empty lines and control characters
                if (
                    not line
                    or line.startswith("-")
                    or line in ["[ENQ]", "[ACK]", "[EOT]", "[ETX]", "[STX]"]
                ):
                    # If we hit EOT or ETX, end current message
                    if line in ["[EOT]", "[ETX]"] and current_message:
                        messages.append("\r".join(current_message))
                        current_message = []
                        in_message = False
                    continue

                # Check for message boundaries
                if "[STX]" in line:
                    in_message = True
                    continue
                elif "[ETX]" in line or "[EOT]" in line:
                    if current_message:
                        messages.append("\r".join(current_message))
                        current_message = []
                    in_message = False
                    continue

                # Remove [CR] markers if present
                line = line.replace("[CR]", "")

                # If we're in a message or find ASTM record lines
                if (
                    in_message
                    or line.startswith(
                        ("H|", "P|", "O|", "R|", "L|", "C|", "Q|")
                    )
                ) and line:
                    current_message.append(line)
                    if not in_message:
                        in_message = True

            # Add any remaining message
            if current_message:
                messages.append("\r".join(current_message))

        # Clean up messages - remove leading/trailing whitespace and newlines from each record
        cleaned_messages = []
        for message in messages:
            # Split by record delimiter and clean each record
            records = message.split("\r")
            cleaned_records = []
            for record in records:
                # Strip whitespace and newlines
                cleaned_record = record.strip().strip("\n\r")
                if cleaned_record:
                    cleaned_records.append(cleaned_record)

            if cleaned_records:
                cleaned_messages.append("\r".join(cleaned_records))

        return cleaned_messages

    def test_parse_bs240_data(self, example_data_dir, profiles_dir):
        """Test parsing BS-240 analyzer data."""
        # Load the BS-240 data
        data_file = example_data_dir / "bs-240" / "bs-240 astm.txt"
        with open(data_file) as f:
            raw_data = f.read()

        # Load the mindray_bs240 profile (already exists)
        self.load_profile(profiles_dir / "mindray_bs240.yaml")

        # Extract ASTM messages
        messages = self.extract_astm_messages(raw_data)
        assert (
            len(messages) > 0
        ), "Should extract at least one message from BS-240 data"

        # Parse each message
        for i, message in enumerate(messages):
            try:
                # Convert to bytes for decoding
                message_bytes = message.encode("latin-1")
                records = decode(message_bytes)

                # Verify we have records
                assert (
                    len(records) > 0
                ), f"Message {i} should have at least one record"

                # Validate record types - handle cases where frame sequence number might be attached
                for record in records:
                    record_type = record[0]
                    # Extract just the letter part if frame sequence number is attached (e.g., "1H" -> "H")
                    if len(record_type) > 1 and record_type[0].isdigit():
                        record_type = record_type[1:]
                    assert record_type in [
                        "H",
                        "P",
                        "O",
                        "R",
                        "L",
                    ], f"Invalid record type: {record[0]}"

            except Exception as e:
                pytest.fail(f"Failed to parse BS-240 message {i}: {str(e)}")
