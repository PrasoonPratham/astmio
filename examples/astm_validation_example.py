#!/usr/bin/env python3
"""
Demonstrates the final, robust workflow of the Astmio ASTM parsing engine.

This script shows the complete, modern process:
1.  Load a device profile from a single function call, which handles all
    initialization and dynamic parser generation.
2.  Instantiate a DataHandler with the prepared profile.
3.  Process raw, real-world ASTM byte strings.
4.  Correctly handle and log both valid and invalid data, showcasing the
    engine's validation rules in action.
"""

from dataclasses import dataclass
from typing import List

from astmio.constants import ENCODING, RECORD_SEP
from astmio.decoder import decode_frame
from astmio.exceptions import BaseASTMError, NotAccepted

# Import the modern, unified I/O function and custom exceptions
from astmio.io import load_profile_from_file

# Import the logger
from astmio.logging import get_logger
from astmio.modern_records import ASTMBaseRecord

# Import the core models needed for type hinting and functionality
from astmio.profile import DeviceProfile
from astmio.types import ASTMRecord

log = get_logger(__name__)


@dataclass
class DecodedTuple:
    """
    Result of frame decoding
    """

    frame_no: int
    frame_content: List[str | List | None]
    frame_type: str


class DataHandler:
    """
    The primary runtime class that uses a prepared DeviceProfile to parse and
    process incoming ASTM data.
    """

    def __init__(self, profile: DeviceProfile):
        """
        Initializes the handler with the fully prepared validation engine.
        """

        self.profile = profile
        log.info(
            "DataHandler initialized with profile for device '%s' (v%s).",
            self.profile.device,
            self.profile.version,
        )

    def split_record(self, record_message: bytes) -> List[bytes]:
        """
        Splits the records based on the record seperator(\r)
        """
        record_splitter: bytes = RECORD_SEP
        records = record_message.split(record_splitter)

        if not records:
            log.warning("No records found returning empty list")
            return []

        return records

    def clean_records(self, uncleaned_records: List[bytes]) -> List[bytes]:
        """
        Here we will clean the records and remove the empty records
        """
        cleaned_records: List[bytes] = []

        for record in uncleaned_records:
            if not record or record == b"":
                continue
            cleaned_records.append(record)

        return cleaned_records

    def decode_records(self, cleaned_records: List[bytes]) -> List[ASTMRecord]:
        """
        decode the list of records through the `decoder` and return it
        returns: List[ASTMRecord]
        """
        decoded_records: List[ASTMRecord] = []

        for record in cleaned_records:
            decoded_records.append(decode_frame(record, ENCODING))

        return decoded_records

    def decode_frame(self, cleaned_records: List[bytes]) -> DecodedTuple:
        frame_no, frame_content = decode_frame(cleaned_records[0], ENCODING)
        tuple_dict = {
            "frame_no": frame_no,
            "frame_content": frame_content[0],
            "frame_type": frame_content[0][0],
        }
        return DecodedTuple(**tuple_dict)

    def validate_record(self, result: DecodedTuple) -> None:
        record_class: ASTMBaseRecord = self.profile.get_record_class(
            result.frame_type
        )
        if not record_class:
            raise NotAccepted(
                f"No parser defined for record type '{result.frame_type}'."
            )

        return record_class.from_astm_record(result.frame_content)


def main():
    """
    Main function to demonstrate the engine's workflow.
    """

    print("--- Initializing Engine and Loading Profile ---")
    try:
        profile_path = "C://Users/Sheve/Desktop/crazy/Astmio/astmio/profiles/mindray_bs240.yaml"
        profile: DeviceProfile = load_profile_from_file(profile_path)
    except BaseASTMError as e:
        log.critical(
            "Failed to initialize validation engine. Application cannot start.",
            exc_info=e,
        )
        return

    handler = DataHandler(profile)

    print("\n--- Processing a Valid Message ---")
    valid_raw_data = (
        b"1H|\\^&|||Mindry^1.0^SN123|||||||PR|1394-97|20250731193000\r"
        b"2P|1||PID123|Doe^John^M|19900101|M|||||||||||||||||||||||||\r"
    )

    splitted_records: List[bytes] = handler.split_record(valid_raw_data)
    cleaned_record_list: List[bytes] = handler.clean_records(splitted_records)
    decoded_frame: DecodedTuple = handler.decode_frame(cleaned_record_list)
    validated_record: ASTMBaseRecord = handler.validate_record(decoded_frame)

    log.info(f"{decoded_frame.frame_type} is a valid record")

    print(validated_record)


if __name__ == "__main__":
    main()
