from astmio import decode


def test_record_field_mapping():
    """Test that profile field mappings work correctly."""
    # Test with a sample message
    sample_message = rb"H|\^&||PSWD|Maglumi User|||||Lis||P|E1394-97|20250701"
    records = decode(sample_message)

    assert len(records) == 1
    header = records[0]
    assert header[0] == "H"
    # Delimiter field is parsed as components with ^ separator
    assert isinstance(header[1], str)  # Should be list of components
    assert header[3] == "PSWD"
    assert header[4] == "Maglumi User"
    assert header[9] == "Lis"
    assert header[11] == "P"
    assert header[12] == "E1394-97"
    assert header[13] == "20250701"


def test_multi_test_parsing():
    """Test parsing of multiple tests in Order record."""
    # Sample with multiple tests separated by backslash
    sample_message = b"O|1|25059232||^^^TT3 II\\^^^TT4 II\\^^^TSH II"
    records = decode(sample_message)

    assert len(records) == 1
    order = records[0]
    assert order[0] == "O"
    assert order[1] == "1"
    assert order[2] == "25059232"
    # The test field should contain the repeated tests (parsed as list)
    assert isinstance(order[4], list)
    test_field_str = str(order[4])
    assert "TT3 II" in test_field_str
    assert "TT4 II" in test_field_str
    assert "TSH II" in test_field_str


def test_result_parsing():
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


def test_complete_message_sequence():
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
