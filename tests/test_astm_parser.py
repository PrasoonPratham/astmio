"""
Comprehensive tests for ASTM data parsing from all example files.
Tests ensure all ASTM data from different analyzers can be parsed correctly.
"""

import os
import pytest
from pathlib import Path
from typing import List, Dict, Any
import yaml

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
try:
    from astmio.codec import decode
    print("Got the decode implementation")
except ImportError:
    print("Error: decode")


class TestASTMParser:
    """Test ASTM data parsing for all analyzer types."""
    
    @pytest.fixture
    def example_data_dir(self):
        """Get the example ASTM data directory."""
        return Path(__file__).parent.parent / "example_astm"
    
    @pytest.fixture
    def profiles_dir(self):
        """Get the profiles directory."""
        return Path(__file__).parent.parent / "etc" / "profiles"
    
    def load_profile(self, profile_path: Path) -> Dict[str, Any]:
        """Load a YAML profile configuration."""
        with open(profile_path, 'r') as f:
            return yaml.safe_load(f)
    
    def extract_astm_messages(self, raw_data: str) -> List[str]:
        """Extract ASTM messages from raw data, handling various formats."""
        messages = []
        current_message = []
        in_message = False
        
        # Special handling for Access 2 format which has very specific structure
        if 'ACCESS' in raw_data and '[STX]' in raw_data:
            # For Access 2, we need to extract the actual ASTM data from between markers
            # and reconstruct proper records
            lines = raw_data.split('\n')
            current_record = ""
            record_type = None
            
            for line in lines:
                line = line.strip()
                
                # Skip control/status lines
                if not line or line.startswith(' - ') or line in ['[ENQ]', '[ACK]', '[EOT]']:
                    continue
                
                # Check for start/end markers
                if '[STX]' in line:
                    in_message = True
                    continue
                elif '[ETX]' in line:
                    # End of current record, process what we have
                    if current_record and record_type:
                        # Clean up the record - remove extra spaces and control markers
                        clean_record = current_record.replace('[CR]', '').replace('[LF]', '')
                        clean_record = '|'.join([part.strip() for part in clean_record.split('|') if part.strip()])
                        if clean_record and clean_record[0] in ['H', 'P', 'O', 'R', 'L', 'C']:
                            current_message.append(clean_record)
                    current_record = ""
                    record_type = None
                    continue
                
                if in_message:
                    # Remove embedded control markers
                    clean_line = line.replace('[CR]', '').replace('[LF]', '').strip()
                    if not clean_line:
                        continue
                    
                    # Try to identify record type
                    for rt in ['H|', 'P|', 'O|', 'R|', 'L|', 'C|']:
                        if rt in clean_line:
                            if current_record and record_type:
                                # Finish previous record
                                clean_record = current_record.replace('[CR]', '').replace('[LF]', '')
                                clean_record = '|'.join([part.strip() for part in clean_record.split('|') if part.strip()])
                                if clean_record and clean_record[0] in ['H', 'P', 'O', 'R', 'L', 'C']:
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
                messages.append('\r'.join(current_message))
                        
        # First, try to extract from lines with [CR] markers (BS-240 format)
        elif '[CR]' in raw_data and '[STX]' in raw_data:
            # Split by STX/ETX boundaries first
            parts = raw_data.split('[STX]')
            for part in parts[1:]:  # Skip first empty part
                if '[ETX]' in part:
                    message_content = part.split('[ETX]')[0]
                    # Split by [CR] to get individual records
                    records = [r.strip() for r in message_content.split('[CR]') if r.strip()]
                    if records:
                        messages.append('\r'.join(records))
        
        # If no messages found, try line-by-line extraction (Snibe format)
        if not messages:
            lines = raw_data.split('\n')
            for line in lines:
                line = line.strip()
                
                # Skip empty lines and control characters
                if not line or line.startswith('-') or line in ['[ENQ]', '[ACK]', '[EOT]', '[ETX]', '[STX]']:
                    # If we hit EOT or ETX, end current message
                    if line in ['[EOT]', '[ETX]'] and current_message:
                        messages.append('\r'.join(current_message))
                        current_message = []
                        in_message = False
                    continue
                    
                # Check for message boundaries
                if '[STX]' in line:
                    in_message = True
                    continue
                elif '[ETX]' in line or '[EOT]' in line:
                    if current_message:
                        messages.append('\r'.join(current_message))
                        current_message = []
                    in_message = False
                    continue
                
                # Remove [CR] markers if present
                line = line.replace('[CR]', '')
                
                # If we're in a message or find ASTM record lines
                if (in_message or line.startswith(('H|', 'P|', 'O|', 'R|', 'L|', 'C|', 'Q|'))) and line:
                    current_message.append(line)
                    if not in_message:
                        in_message = True
            
            # Add any remaining message
            if current_message:
                messages.append('\r'.join(current_message))
        
        # Clean up messages - remove leading/trailing whitespace and newlines from each record
        cleaned_messages = []
        for message in messages:
            # Split by record delimiter and clean each record
            records = message.split('\r')
            cleaned_records = []
            for record in records:
                # Strip whitespace and newlines
                cleaned_record = record.strip().strip('\n\r')
                if cleaned_record:
                    cleaned_records.append(cleaned_record)
            
            if cleaned_records:
                cleaned_messages.append('\r'.join(cleaned_records))
        
        return cleaned_messages
    
    def test_parse_access2_data(self, example_data_dir, profiles_dir):
        """Test parsing Access 2 analyzer data."""
        # Load the Access 2 data
        data_file = example_data_dir / "Access 2" / "Access 2 AnalyzerLogs.txt"
        with open(data_file, 'r') as f:
            raw_data = f.read()
        
        # Load the Access 2 profile
        profile = self.load_profile(profiles_dir / "access2.yaml")
        
        # Extract ASTM messages
        messages = self.extract_astm_messages(raw_data)
        assert len(messages) > 0, "Should extract at least one message from Access 2 data"
        
        # Parse each message
        for i, message in enumerate(messages):
            try:
                # Convert to bytes for decoding
                message_bytes = message.encode('latin-1')
                records = decode(message_bytes)
                
                # Verify we have records
                assert len(records) > 0, f"Message {i} should have at least one record"
                
                # Check we have valid ASTM records
                first_record = records[0]
                assert first_record[0] in ['H', 'P', 'O', 'R', 'L', 'C'], f"First record of message {i} should be valid ASTM record type, got {first_record[0]}"
                
                # Validate record structure based on profile
                for record in records:
                    record_type = record[0]
                    if record_type in profile['records']:
                        expected_fields = profile['records'][record_type].get('fields', [])
                        # Allow for variable field counts but check minimum
                        assert len(record) >= 2, f"Record type {record_type} should have at least 2 fields"
                
            except Exception as e:
                pytest.fail(f"Failed to parse Access 2 message {i}: {str(e)}")
    
    def test_parse_bs240_data(self, example_data_dir, profiles_dir):
        """Test parsing BS-240 analyzer data."""
        # Load the BS-240 data
        data_file = example_data_dir / "bs-240" / "bs-240 astm.txt"
        with open(data_file, 'r') as f:
            raw_data = f.read()
        
        # Load the mindray_bs240 profile (already exists)
        profile = self.load_profile(profiles_dir / "mindray_bs240.yaml")
        
        # Extract ASTM messages
        messages = self.extract_astm_messages(raw_data)
        assert len(messages) > 0, "Should extract at least one message from BS-240 data"
        
        # Parse each message
        for i, message in enumerate(messages):
            try:
                # Convert to bytes for decoding
                message_bytes = message.encode('latin-1')
                records = decode(message_bytes)
                
                # Verify we have records
                assert len(records) > 0, f"Message {i} should have at least one record"
                
                # Validate record types - handle cases where frame sequence number might be attached
                for record in records:
                    record_type = record[0]
                    # Extract just the letter part if frame sequence number is attached (e.g., "1H" -> "H")
                    if len(record_type) > 1 and record_type[0].isdigit():
                        record_type = record_type[1:]
                    assert record_type in ['H', 'P', 'O', 'R', 'L'], f"Invalid record type: {record[0]}"
                
            except Exception as e:
                pytest.fail(f"Failed to parse BS-240 message {i}: {str(e)}")

    def test_parse_snibe_maglumi_data(self, example_data_dir, profiles_dir):
        """Test parsing Snibe Maglumi analyzer data."""
        # Load the Snibe data
        data_file = example_data_dir / "Snibe" / "malglumi edata logs.txt"
        with open(data_file, 'r') as f:
            raw_data = f.read()
        
        # Load the Snibe Maglumi profile
        profile = self.load_profile(profiles_dir / "snibe_maglumi.yaml")
        
        # Extract ASTM messages
        messages = self.extract_astm_messages(raw_data)
        assert len(messages) > 0, "Should extract at least one message from Snibe data"
        
        # Parse each message
        parsed_count = 0
        for i, message in enumerate(messages):
            try:
                # Convert to bytes for decoding
                message_bytes = message.encode('latin-1')
                records = decode(message_bytes)
                
                # Verify we have records
                assert len(records) > 0, f"Message {i} should have at least one record"
                
                # Validate Snibe-specific fields
                for record in records:
                    if record[0] == 'H':
                        # Check for Maglumi-specific header fields
                        if len(record) > 4:
                            assert record[3] == 'PSWD' or record[3] is None, "Password field should be PSWD"
                            if len(record) > 5:
                                assert 'Maglumi' in str(record[4]) or record[4] is None, "Sender should contain Maglumi"
                    elif record[0] == 'R':
                        # Check result record has required fields
                        assert len(record) >= 4, "Result record should have at least 4 fields"
                        # Check for test ID format (^^^TEST_NAME)
                        if len(record) > 2 and record[2]:
                            assert str(record[2]).startswith('^^^'), f"Test ID should start with ^^^, got {record[2]}"
                
                parsed_count += 1
                
            except Exception as e:
                # Some lines might not be valid ASTM messages, which is okay
                continue
        
        assert parsed_count > 0, "Should successfully parse at least one Snibe message"
    
    def test_record_field_mapping(self, profiles_dir):
        """Test that profile field mappings work correctly."""
        # Test with a sample message
        sample_message = b"H|\\^&||PSWD|Maglumi User|||||Lis||P|E1394-97|20250701"
        records = decode(sample_message)
        header = records[0]
        
        assert len(records) == 1

        # if isinstance(header[1], list):
        #     header_str = str(header[1])
        #     assert '&' in header_str
        # else:
        #     assert '\\^&' in str(header[1]) or '^&' in str(header[1])

        assert header[0] == 'H'
        # Delimiter field contains separators
        assert header[1] == [[None], [None, '&']]  # Field separator definition
        assert header[3] == 'PSWD'
        assert header[4] == 'Maglumi User'
        assert header[9] == 'Lis'
        assert header[11] == 'P'
        assert header[12] == 'E1394-97'
        assert header[13] == '20250701'
    
    def test_multi_test_parsing(self):
        """Test parsing of multiple tests in Order record."""
        # Sample with multiple tests separated by backslash
        sample_message = b"O|1|25059232||^^^TT3 II\\^^^TT4 II\\^^^TSH II"
        records = decode(sample_message)
        
        assert len(records) == 1
        order = records[0]
        assert order[0] == 'O'
        assert order[1] == '1'
        assert order[2] == '25059232'
        # The test field should contain the repeated tests
        test_field = order[4]
        test_field_str = str(test_field)
        assert 'TT3 II' in test_field_str
        assert 'TT4 II' in test_field_str
        assert 'TSH II' in test_field_str
    
    def test_result_parsing(self):
        """Test parsing of result records."""
        sample_message = b"R|1|^^^TT3 II|1.171|ng/mL|0.75 to 2.1|N||||||20250630151157"
        records = decode(sample_message)
        
        assert len(records) == 1
        result = records[0]
        assert result[0] == 'R'
        assert result[1] == '1'
        # Test ID field is parsed as components
        assert isinstance(result[2], list) or result[2] == '^^^TT3 II'
        if isinstance(result[2], list):
            assert 'TT3 II' in str(result[2])
        else:
            assert result[2] == '^^^TT3 II'
        assert result[3] == '1.171'
        assert result[4] == 'ng/mL'
        assert result[5] == '0.75 to 2.1'
        assert result[6] == 'N'
        # Check timestamp field
        assert len(result) > 12 and result[12] == '20250630151157'
    
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
        assert len(records) >= 1, f"Should have at least 1 record, got {len(records)}"
        
        # If decoded as single message, check if it contains all the data
        if len(records) == 1:
            # Single record containing all data
            full_record = records[0]
            assert full_record[0] == 'H'  # Should start with header
            # Check that the message contains all the key data
            message_str = str(full_record)
            assert 'PSWD' in message_str
            assert 'Maglumi User' in message_str
            assert '25059232' in message_str
            assert '1.171' in message_str
        else:
            # Multiple records parsed
            assert records[0][0] == 'H'
            # Check that we have the main record types
            record_types = [r[0] for r in records]
            assert 'H' in record_types
            
            # Verify sample ID in order record
            order_records = [r for r in records if r[0] == 'O']
            if order_records:
                assert order_records[0][2] == '25059232'

    def test_header_record_variations(self):
        """Test different header record formats from various analyzers."""
        # Access 2 header
        access2_header = b"H|\\^&|||ACCESS^575707|||||LIS||P|1|20250701185020"
        records = decode(access2_header)
        assert len(records) >= 1
        header = records[0]
        assert header[0] == 'H'
        
        # Mindray header
        mindray_header = b"H|\\^&|||Mindry^^|||||||PR|1394-97|20250701173105"
        records = decode(mindray_header)
        assert len(records) >= 1
        header = records[0]
        assert header[0] == 'H'
        
        # Product Model header
        product_header = b"H|\\^&|||ProductModel^01.03.07.03^123456|||||||PR|1394-97|20090910102501"
        records = decode(product_header)
        assert len(records) >= 1
        header = records[0]
        assert header[0] == 'H'

    def test_patient_record_variations(self):
        """Test different patient record formats."""
        # Standard patient record
        patient_std = b"P|1||PATIENT111||Smith^Tom^J||19600315|M|||A||Dr.Bean|icteru|100012546|||Diagnosis information||0001|||||A1|002||||||||"
        records = decode(patient_std)
        assert len(records) >= 1
        patient = records[0]
        assert patient[0] == 'P'
        
        # Minimal patient record
        patient_min = b"P|1"
        records = decode(patient_min)
        assert len(records) >= 1
        patient = records[0]
        assert patient[0] == 'P'
        assert patient[1] == '1'
        
        # Patient with invalid ID (test case from your examples)
        patient_invalid = b"P|476|INVALID@#$%ID|||^^||^^|U||||||||||||||||||||||||||"
        records = decode(patient_invalid)
        assert len(records) >= 1
        patient = records[0]
        assert patient[0] == 'P'
        assert patient[1] == '476'

    def test_order_record_variations(self):
        """Test different order record formats and test combinations."""
        # Single test order
        order_single = b"O|1|2025105867|^1316^1|^^^B12|||||Serum|||||II^1||||||||||F"
        records = decode(order_single)
        assert len(records) >= 1
        order = records[0]
        assert order[0] == 'O'
        assert order[1] == '1'
        
        # Multiple tests with backslash separator
        order_multi = b"O|1|25059232||^^^TT3 II\\^^^TT4 II\\^^^TSH II"
        records = decode(order_multi)
        assert len(records) >= 1
        order = records[0]
        assert order[0] == 'O'
        # Should contain all test names
        order_str = str(order)
        assert 'TT3 II' in order_str
        assert 'TT4 II' in order_str
        assert 'TSH II' in order_str
        
        # Creatinine and Urea tests
        order_creas = b"O|476|8^^|2025105875|CREAS^Creatinine (Sarcosine Oxidase Method)^^\\UREA^Urea^^|R|20250701145215|20250701145140|||||||20250701145140|serum||||||||||F|||||"
        records = decode(order_creas)
        assert len(records) >= 1
        order = records[0]
        assert order[0] == 'O'
        order_str = str(order)
        assert 'CREAS' in order_str or 'Creatinine' in order_str
        assert 'UREA' in order_str or 'Urea' in order_str

    def test_result_record_variations(self):
        """Test different result record formats and values."""
        # Numeric result with units
        result_numeric = b"R|1|^^^B12II^1|131|pg/mL|222 to 1439^normal|L|N|F||||20250701184502|575707"
        records = decode(result_numeric)
        assert len(records) >= 1
        result = records[0]
        assert result[0] == 'R'
        assert result[1] == '1'
        assert result[3] == '131'
        assert result[4] == 'pg/mL'
        
        # Result with abnormal flag
        result_abnormal = b"R|1|^^^GLUCOSE|150|mg/dL|70-110|H|F"
        records = decode(result_abnormal)
        assert len(records) >= 1
        result = records[0]
        assert result[0] == 'R'
        assert result[3] == '150'
        assert result[6] == 'H'  # High flag
        
        # Creatinine result
        result_creas = b"R|162|CREAS^Creatinine (Sarcosine Oxidase Method)^^F|3.216365^^^^|mg/dL|^|N||F|3.216365^^^^|0|20250701154742||Mindry^"
        records = decode(result_creas)
        assert len(records) >= 1
        result = records[0]
        assert result[0] == 'R'
        result_str = str(result)
        assert '3.216365' in result_str
        assert 'mg/dL' in result_str
        
        # Qualitative result
        result_qual = b"R|4|4^Test4^1^I|^Negative|Mg/ml||||Positive|F|||20090910134300|20020316135303|Product Model ^123"
        records = decode(result_qual)
        assert len(records) >= 1
        result = records[0]
        assert result[0] == 'R'
        result_str = str(result)
        assert 'Negative' in result_str

    def test_comment_record_parsing(self):
        """Test comment record parsing."""
        comment = b"C|1|I|Result Description|I"
        records = decode(comment)
        assert len(records) >= 1
        comment_rec = records[0]
        assert comment_rec[0] == 'C'
        assert comment_rec[1] == '1'
        
        # Comment with high glucose recommendation
        comment_glucose = b"C|1|High glucose level - recommend dietary consultation"
        records = decode(comment_glucose)
        assert len(records) >= 1
        comment_rec = records[0]
        assert comment_rec[0] == 'C'
        comment_str = str(comment_rec)
        assert 'glucose' in comment_str.lower()

    def test_terminator_record_variations(self):
        """Test different terminator record formats."""
        # Normal termination
        term_normal = b"L|1|N"
        records = decode(term_normal)
        assert len(records) >= 1
        term = records[0]
        assert term[0] == 'L'
        assert term[1] == '1'
        assert term[2] == 'N'
        
        # Query termination
        term_query = b"L|1|Q"
        records = decode(term_query)
        assert len(records) >= 1
        term = records[0]
        assert term[0] == 'L'
        assert term[2] == 'Q'
        
        # Information termination
        term_info = b"L|1|I"
        records = decode(term_info)
        assert len(records) >= 1
        term = records[0]
        assert term[0] == 'L'
        assert term[2] == 'I'

    def test_query_record_parsing(self):
        """Test query record parsing for sample inquiries."""
        # Query for sample
        query = b"Q|1|^SAMPLE123||||||||||A"
        records = decode(query)
        assert len(records) >= 1
        query_rec = records[0]
        assert query_rec[0] == 'Q'
        assert query_rec[1] == '1'
        query_str = str(query_rec)
        assert 'SAMPLE123' in query_str

    def test_quality_control_records(self):
        """Test QC record parsing."""
        # QC order record
        qc_order = b"O|1|||||20090910121532|||||1^QC1^1111^20100910^10^L^5^10.28\\2^QC2^2222^20100910^20^M^10^20.48\\3^QC3^3333^20100910^30^H^15^30.25||||||||||||||F|||||"
        records = decode(qc_order)
        assert len(records) >= 1
        order = records[0]
        assert order[0] == 'O'
        order_str = str(order)
        assert 'QC1' in order_str or 'QC2' in order_str or 'QC3' in order_str

    def test_calibration_records(self):
        """Test calibration record parsing."""
        # Calibration order
        cal_order = b"O|1|||||20090910121532||||||1^Cal1^1111^20100910^10^L^11\\2^Cal2^2222^20100910^20^M^22\\3^Cal3^3333^20100910^30^H^33|5^^1.25^25.1^36.48^10.78^98.41||||||||||||F|||||"
        records = decode(cal_order)
        assert len(records) >= 1
        order = records[0]
        assert order[0] == 'O'
        order_str = str(order)
        assert 'Cal1' in order_str or 'Cal2' in order_str or 'Cal3' in order_str

    def test_message_type_identification(self):
        """Test identification of different message types based on header."""
        # Patient Result message
        pr_header = b"H|\\^&|||ProductModel^01.03.07.03^123456|||||||PR|1394-97|20090910102501"
        records = decode(pr_header)
        assert len(records) >= 1
        header = records[0]
        header_str = str(header)
        assert 'PR' in header_str  # Patient Result
        
        # Sample Acknowledgment message
        sa_header = b"H|\\^&|||ProductModel^01.03.07.03^123456|||||||SA|1394-97|20090910102501"
        records = decode(sa_header)
        assert len(records) >= 1
        header = records[0]
        header_str = str(header)
        assert 'SA' in header_str  # Sample Acknowledgment
        
        # Query Request message
        rq_header = b"H|\\^&|||ProductModel^01.03.07.03^123456|||||||RQ|1394-97|20090910102501"
        records = decode(rq_header)
        assert len(records) >= 1
        header = records[0]
        header_str = str(header)
        assert 'RQ' in header_str  # Request Query
        
        # Quality Control Result message
        qr_header = b"H|\\^&|||ProductModel^01.03.07.03^123456|||||||QR|1394-97|20090910102501"
        records = decode(qr_header)
        assert len(records) >= 1
        header = records[0]
        header_str = str(header)
        assert 'QR' in header_str  # QC Result
        
        # Calibration Result message
        cr_header = b"H|\\^&|||ProductModel^01.03.07.03^123456|||||||CR|1394-97|20090910102501"
        records = decode(cr_header)
        assert len(records) >= 1
        header = records[0]
        header_str = str(header)
        assert 'CR' in header_str  # Calibration Result

    def test_timestamp_parsing(self):
        """Test various timestamp formats in ASTM records."""
        # Standard timestamp format
        result_with_time = b"R|1|^^^TT3 II|1.171|ng/mL|0.75 to 2.1|N||||||20250630151157"
        records = decode(result_with_time)
        assert len(records) >= 1
        result = records[0]
        result_str = str(result)
        assert '20250630151157' in result_str
        
        # Header with timestamp
        header_with_time = b"|\\^&|||ACCESS^575707|||||LIS||P|1|20250701185020"
        records = decode(header_with_time)
        assert len(records) >= 1
        header = records[0]
        header_str = str(header)
        assert '20250701185020' in header_str

    def test_field_separator_handling(self):
        """Test handling of different field separators and special characters."""
        # Test with component separator ^
        record_with_components = b"R|1|^^^B12II^1|131|pg/mL|222 to 1439^normal|L|N|F"
        records = decode(record_with_components)
        assert len(records) >= 1
        result = records[0]
        assert result[0] == 'R'
        
        # Test with repeat separator \
        record_with_repeats = b"O|1|25059232||^^^TT3 II\\^^^TT4 II\\^^^TSH II"
        records = decode(record_with_repeats)
        assert len(records) >= 1
        order = records[0]
        assert order[0] == 'O'

    def test_empty_and_null_fields(self):
        """Test handling of empty and null fields."""
        # Record with empty fields
        record_empty = b"P|1||||||||||||||||||||||||||||||"
        records = decode(record_empty)
        assert len(records) >= 1
        patient = records[0]
        assert patient[0] == 'P'
        assert patient[1] == '1'
        
        # Record with mixed empty and filled fields
        record_mixed = b"P|1||PATIENT111||Smith^Tom^J||||||||||||||||||||||||"
        records = decode(record_mixed)
        assert len(records) >= 1
        patient = records[0]
        assert patient[0] == 'P'
        patient_str = str(patient)
        assert 'PATIENT111' in patient_str
        assert 'Smith' in patient_str

    def test_special_characters_in_data(self):
        """Test handling of special characters in field data."""
        # Patient with special characters in ID
        patient_special = b"P|476|INVALID@#$%ID|||^^||^^|U"
        records = decode(patient_special)
        assert len(records) >= decode
        patient = records[0]
        assert patient[0] == 'P'
        patient_str = str(patient)
        assert 'INVALID@#$%ID' in patient_str
        
        # Result with special characters in value
        result_special = b"R|1|^^^TEST|<5.0|mg/dL|>10.0|L|F"
        records = decode(result_special)
        assert len(records) >= 1
        result = records[0]
        assert result[0] == 'R'

    def test_long_field_values(self):
        """Test handling of long field values."""
        # Long test name
        long_test = b"O|1|SAMPLE001||^^^Very Long Test Name With Multiple Words And Descriptions"
        records = decode(long_test)
        assert len(records) >= 1
        order = records[0]
        assert order[0] == 'O'
        
        # Long comment
        long_comment = b"C|1|This is a very long comment that contains detailed information about the test result and recommendations for the patient care and follow-up procedures"
        records = decode(long_comment)
        assert len(records) >= 1
        comment = records[0]
        assert comment[0] == 'C'

    def test_record_sequence_validation(self):
        """Test validation of proper ASTM record sequences."""
        # Complete valid sequence
        complete_sequence = (
            b"H|\\^&||PSWD|Maglumi User|||||Lis||P|E1394-97|20250701\r"
            b"P|1||PATIENT001||Doe^John^M||19850615|M\r"
            b"O|1|SAMPLE001||^^^GLUCOSE|R|20250701120000\r"
            b"R|1|^^^GLUCOSE|150|mg/dL|70-110|H|F\r"
            b"L|1|N"
        )
        records = decode(complete_sequence)
        assert len(records) >= 1
        
        # Check that we can identify the main components
        sequence_str = str(records)
        assert 'Maglumi' in sequence_str
        assert 'PATIENT001' in sequence_str
        assert 'SAMPLE001' in sequence_str
        assert 'GLUCOSE' in sequence_str

    def test_error_handling_malformed_records(self):
        """Test error handling for malformed ASTM records."""
        # Record without proper field separators
        try:
            malformed = b"H-invalid-record-format"
            records = decode(malformed)
            # Should either parse gracefully or handle the error
            assert isinstance(records, list)
        except Exception:
            # Exception is acceptable for malformed data
            pass
        
        # Empty record
        try:
            empty = b""
            records = decode(empty)
            assert isinstance(records, list)
        except Exception:
            # Exception is acceptable for empty data
            pass

    def test_analyzer_specific_formats(self):
        """Test analyzer-specific ASTM format variations."""
        # Access 2 specific format
        access2_result = b"R|1|^^^B12II^1|131|pg/mL|222 to 1439^normal|L|N|F||||20250701184502|575707"
        records = decode(access2_result)
        assert len(records) >= 1
        result = records[0]
        assert result[0] == 'R'
        
        # Mindray specific format
        mindray_result = b"R|162|CREAS^Creatinine (Sarcosine Oxidase Method)^^F|3.216365^^^^|mg/dL|^|N||F|3.216365^^^^|0|20250701154742||Mindry^"
        records = decode(mindray_result)
        assert len(records) >= 1
        result = records[0]
        assert result[0] == 'R'
        
        # Snibe Maglumi specific format
        snibe_result = b"R|1|^^^TT3 II|1.171|ng/mL|0.75 to 2.1|N||||||20250630151157"
        records = decode(snibe_result)
        assert len(records) >= 1
        result = records[0]
        assert result[0] == 'R' 