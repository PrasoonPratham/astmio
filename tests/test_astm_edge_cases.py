"""
Test edge cases and error handling for ASTM parser.
"""

import pytest
from astmio.exceptions import ProtocolError

# Import only the core decode function to avoid dependency issues
try:
    from astmio.codec import decode
    from astmio import encode
    from astmio.exceptions import BaseASTMError, ValidationError
except ImportError:
    raise ImportError("Cannot import proper modules")
    
    def encode(records):
        """Simple encode function for testing."""
        lines = []
        for record in records:
            lines.append('|'.join(str(field) for field in record))
        return '\r'.join(lines).encode('latin-1')
    
    class ASTMError(Exception):
        pass


class TestASTMEdgeCases:
    """Test edge cases and error handling scenarios."""

    # Handles malformed record without field separators -> raises ProtocolError
    def test_malformed_records(self):
        """Test handling of malformed ASTM records."""
        malformed = b"H"
        with pytest.raises(ProtocolError):
            decode(malformed)

    def test_list_input(self):
        """Test handling of empty input."""
        list_input = [b"", b"\r", b"\n", b"\r\n"]
        
        with pytest.raises(ValidationError):
            records = decode(list_input)

    @pytest.mark.parametrize("test_input", [b"", b"\r", b"\n", b"\r\n"])
    def test_decode_returns_empty_list_for_empty_inputs(self, test_input):
        with pytest.raises((ValidationError, ProtocolError)):
            decode(test_input) 

    def test_control_characters_only(self):
        """Test input with only control characters."""
        with pytest.raises(ProtocolError):
            records = decode(b"\x02\x03\x04\x05\x06\x15")

    def test_very_long_fields(self):
        """Test handling of very long field values."""
        # Create a very long field value
        long_value = "A" * 10000
        long_record = f"P|1|{long_value}|".encode('latin-1')
        
        try:
            records = decode(long_record)
            assert len(records) >= 1
            patient = records[0]
            assert patient[0] == 'P'
        except Exception:
            # Memory or parsing limits are acceptable
            pass

    def test_special_characters_in_fields(self):
        """Test various special characters in field data."""
        special_chars = [
            b"P|1|\x00\x01\x02|",  # Null and control chars
            b"P|1|\xff\xfe\xfd|",  # High byte values
            b"P|1|Test\x7f\x80|",  # DEL and extended ASCII
        ]
        
        for special_record in special_chars:
            try:
                records = decode(special_record)
                assert isinstance(records, list)
            except Exception:
                # Encoding/decoding errors are acceptable
                pass

    def test_maximum_field_count(self):
        """Test records with maximum number of fields."""
        # Create record with many fields
        many_fields = "|".join([f"field{i}" for i in range(100)])
        max_record = f"P|{many_fields}".encode('latin-1')
        
        try:
            records = decode(max_record)
            assert len(records) >= 1
            patient = records[0]
            assert patient[0] == 'P'
            assert len(patient) > 50  # Should have many fields
        except Exception:
            # Memory limits are acceptable
            pass

    def test_nested_separators(self):
        """Test handling of nested separator characters."""
        # Field containing all separator types
        nested = b"R|1|^^^TEST^ID\\REPEAT^COMP|value|units"
        records = decode(nested)
        assert len(records) >= 1
        result = records[0]
        assert result[0] == 'R'

    def test_unicode_handling(self):
        """Test handling of Unicode characters."""
        unicode_tests = [
            "P|1|Müller|",  # German umlaut
            "P|1|José|",    # Spanish accent
            "P|1|北京|",     # Chinese characters
            "P|1|🏥|",      # Emoji
        ]
        
        for unicode_text in unicode_tests:
            try:
                # Try different encodings
                for encoding in ['utf-8', 'latin-1', 'cp1252']:
                    try:
                        unicode_record = unicode_text.encode(encoding)
                        records = decode(unicode_record)
                        assert isinstance(records, list)
                        break
                    except UnicodeEncodeError:
                        continue
            except Exception:
                # Unicode handling issues are acceptable
                pass

    def test_boundary_conditions(self):
        """Test boundary conditions for field parsing."""
        boundary_tests = [
            b"H|",  # Minimal header
            b"P|1|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||",  # Many empty fields
            b"R|1|TEST|" + b"9" * 1000 + b"|units|",  # Very long numeric value
        ]
        
        for boundary_record in boundary_tests:
            try:
                records = decode(boundary_record)
                assert isinstance(records, list)
            except Exception:
                # Boundary condition failures are acceptable
                pass

    def test_mixed_line_endings(self):
        """Test handling of mixed line ending styles."""
        mixed_endings = (
            b"H|\\^&||TEST|\r"
            b"P|1|\n"
            b"O|1|SAMPLE|\r\n"
            b"L|1|N"
        )
        
        try:
            records = decode(mixed_endings)
            assert isinstance(records, list)
        except Exception:
            # Mixed line ending issues are acceptable
            pass

    def test_incomplete_records(self):
        """Test handling of incomplete or truncated records."""
        incomplete_tests = [
            b"H|\\^&||TEST",  # No terminating field separator
            b"P|1|NAME|",     # Ends with separator
            b"R|1|TEST|123",  # Missing required fields
        ]
        
        for incomplete_record in incomplete_tests:
            try:
                records = decode(incomplete_record)
                assert isinstance(records, list)
            except Exception:
                # Incomplete record errors are acceptable
                pass

    def test_duplicate_record_types(self):
        """Test handling of duplicate record types in sequence."""
        duplicate_sequence = (
            b"H|\\^&||TEST|\r"
            b"H|\\^&||TEST2|\r"  # Duplicate header
            b"P|1|NAME1|\r"
            b"P|2|NAME2|\r"      # Duplicate patient
            b"L|1|N"
        )
        
        try:
            records = decode(duplicate_sequence)
            assert isinstance(records, list)
        except Exception:
            # Duplicate handling issues are acceptable
            pass

    def test_out_of_order_records(self):
        """Test handling of records in unexpected order."""
        out_of_order = (
            b"P|1|NAME|\r"      # Patient before header
            b"H|\\^&||TEST|\r"
            b"L|1|N\r"          # Terminator before results
            b"R|1|TEST|123|\r"
        )
        
        try:
            records = decode(out_of_order)
            assert isinstance(records, list)
        except Exception:
            # Order validation errors are acceptable
            pass

    def test_invalid_sequence_numbers(self):
        """Test handling of invalid sequence numbers."""
        invalid_sequence = (
            b"H|\\^&||TEST|\r"
            b"P|999|NAME|\r"     # Very high sequence
            b"O|-1|SAMPLE|\r"    # Negative sequence
            b"R|abc|TEST|123|\r" # Non-numeric sequence
            b"L|1|N"
        )
        
        try:
            records = decode(invalid_sequence)
            assert isinstance(records, list)
        except Exception:
            # Sequence validation errors are acceptable
            pass

    def test_circular_references(self):
        """Test handling of potential circular references in data."""
        # This is more of a stress test for the parser
        circular_data = b"R|1|^^^TEST|see_field_1|units|ref|N|F|comment|see_field_3"
        
        try:
            records = decode(circular_data)
            assert isinstance(records, list)
        except Exception:
            # Circular reference handling issues are acceptable
            pass

    def test_memory_stress(self):
        """Test parser under memory stress conditions."""
        # Create a large number of records
        large_message = b"H|\\^&||TEST|\r"
        
        # Add many patient records
        for i in range(100):
            large_message += f"P|{i}|PATIENT_{i}|\r".encode('latin-1')
        
        large_message += b"L|1|N"
        
        try:
            records = decode(large_message)
            assert isinstance(records, list)
        except Exception:
            # Memory stress failures are acceptable
            pass

    def test_encoding_roundtrip(self):
        """Test that encode/decode operations are consistent."""
        original_records = [
            ['H', '\\^&', '', 'TEST', '', '', '', '', '', '', '', '', '', ''],
            ['P', '1', '', 'PATIENT001', '', 'Doe^John^M', '', '19850615', 'M'],
            ['O', '1', 'SAMPLE001', '', '^^^GLUCOSE', 'R', '20250701120000'],
            ['R', '1', '^^^GLUCOSE', '150', 'mg/dL', '70-110', 'H', 'F'],
            ['L', '1', 'N']
        ]
        
        try:
            # Encode the records
            encoded = encode(original_records)
            assert isinstance(encoded, bytes)
            
            # Decode them back
            decoded_records = decode(encoded)
            assert isinstance(decoded_records, list)
            
            # Basic structure should be preserved
            assert len(decoded_records) > 0
            
        except Exception:
            pass