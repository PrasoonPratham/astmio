"""
Test production scenarios and real-world ASTM communication patterns.
"""

import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
try:
    from astmio.codec import decode
    print("Got the decode implementation")
except ImportError:
    print("Error: decode")

class TestASTMProductionScenarios:
    """Test real-world production scenarios from your examples."""

    def test_access2_b12_test_scenario(self):
        """Test Access 2 B12 test scenario from production logs."""
        # Based on your Access 2 AnalyzerLogs.txt example
        access2_b12 = (
            b"H|\\^&|||ACCESS^575707|||||LIS||P|1|20250701185020\r"
            b"P|1|\r"
            b"O|1|2025105867|^1316^1|^^^B12|||||Serum|||||II^1||||||||||F\r"
            b"R|1|^^^B12II^1|131|pg/mL|222 to 1439^normal|L|N|F||||20250701184502|575707\r"
            b"L|1|F"
        )
        
        records = decode(access2_b12)
        assert len(records) >= 1
        
        # Verify key components from the scenario
        message_str = str(records)
        assert 'ACCESS' in message_str
        assert '575707' in message_str  # Instrument ID
        assert '2025105867' in message_str  # Sample ID
        assert 'B12' in message_str  # Test name
        assert '131' in message_str  # Result value
        assert 'pg/mL' in message_str  # Units
        assert '222 to 1439' in message_str  # Reference range
        assert 'L' in message_str  # Low flag

    def test_mindray_creatinine_urea_scenario(self):
        """Test Mindray analyzer creatinine and urea test scenario."""
        # Host to instrument order
        host_order = (
            b"H|\\^&|||Mindry^^|||||||PR|1394-97|20250701173105\r"
            b"P|476||||^^||^^|U||||||||||||||||||||||||||\r"
            b"O|476|8^^|2025105875|CREAS^Creatinine (Sarcosine Oxidase Method)^^\\UREA^Urea^^|R|20250701145215|20250701145140|||||||20250701145140|serum||||||||||F|||||\r"
            b"L|1|N"
        )
        
        records = decode(host_order)
        assert len(records) >= 1
        
        message_str = str(records)
        assert 'Mindry' in message_str
        assert '2025105875' in message_str  # Sample ID
        assert 'CREAS' in message_str or 'Creatinine' in message_str
        assert 'UREA' in message_str or 'Urea' in message_str
        assert 'serum' in message_str.lower()
        
        # Instrument to host results
        instrument_results = (
            b"H|\\^&|||Mindry^^|||||||PR|1394-97|20250701173105\r"
            b"P|476||||^^||^^|U||||||||||||||||||||||||||\r"
            b"O|476|8^^|2025105875|CREAS^Creatinine (Sarcosine Oxidase Method)^^\\UREA^Urea^^|R|20250701145215|20250701145140|||||||20250701145140|serum||||||||||F|||||\r"
            b"R|162|CREAS^Creatinine (Sarcosine Oxidase Method)^^F|3.216365^^^^|mg/dL|^|N||F|3.216365^^^^|0|20250701154742||Mindry^\r"
            b"R|163|UREA^Urea^^F|72.506096^^^^|mg/dL|^|N||F|72.506096^^^^|0|20250701154406||Mindry^\r"
            b"L|475|N"
        )
        
        records = decode(instrument_results)
        assert len(records) >= 1
        
        message_str = str(records)
        assert '3.216365' in message_str  # Creatinine result
        assert '72.506096' in message_str  # Urea result
        assert 'mg/dL' in message_str  # Units

    def test_snibe_maglumi_thyroid_panel(self):
        """Test Snibe Maglumi thyroid panel scenario."""
        snibe_thyroid = (
            b"H|\\^&||PSWD|Maglumi User|||||Lis||P|E1394-97|20250701\r"
            b"P|1\r"
            b"O|1|25059232||^^^TT3 II\\^^^TT4 II\\^^^TSH II\r"
            b"R|1|^^^TT3 II|1.171|ng/mL|0.75 to 2.1|N||||||20250630151157\r"
            b"R|2|^^^TT4 II|10.78|ug/dL|5 to 13|N||||||20250630150745\r"
            b"R|3|^^^TSH II|3.007|uIU/mL|0.3 to 4.5|N||||||20250630152021\r"
            b"L|1|N"
        )
        
        records = decode(snibe_thyroid)
        assert len(records) >= 1
        
        message_str = str(records)
        assert 'Maglumi' in message_str
        assert '25059232' in message_str  # Sample ID
        assert 'TT3 II' in message_str  # T3 test
        assert 'TT4 II' in message_str  # T4 test
        assert 'TSH II' in message_str  # TSH test
        assert '1.171' in message_str  # T3 result
        assert '10.78' in message_str  # T4 result
        assert '3.007' in message_str  # TSH result

    def test_invalid_patient_id_workflow(self):
        """Test workflow when patient ID is invalid."""
        # Initial message with invalid patient ID
        invalid_patient = (
            b"H|\\^&|||Mindry^^|||||||PR|1394-97|20250701173105\r"
            b"P|476|INVALID@#$%ID|||^^||^^|U||||||||||||||||||||||||||\r"
            b"O|476|8^^|2025105875|CREAS^Creatinine (Sarcosine Oxidase Method)^^\r"
            b"L|1|N"
        )
        
        records = decode(invalid_patient)
        assert len(records) >= 1
        
        message_str = str(records)
        assert 'INVALID@#$%ID' in message_str
        
        # Follow-up query message
        query_response = (
            b"H|\\^&|||Mindry^^|||||||PR|1394-97|20250701173105\r"
            b"L|1|Q"
        )
        
        records = decode(query_response)
        assert len(records) >= 1
        
        # Should have query termination
        message_str = str(records)
        assert 'Q' in message_str

    def test_quality_control_workflow(self):
        """Test quality control workflow scenario."""
        qc_message = (
            b"H|\\^&|||ProductModel^01.03.07.03^123456|||||||QR|1394-97|20090910102501\r"
            b"P|1|||||||||||||||||||||||||||||||||\r"
            b"O|1|||||20090910121532|||||1^QC1^1111^20100910^10^L^5^10.28\\2^QC2^2222^20100910^20^M^10^20.48\\3^QC3^3333^20100910^30^H^15^30.25||||||||||||||F|||||\r"
            b"L|1|N"
        )
        
        records = decode(qc_message)
        assert len(records) >= 1
        
        message_str = str(records)
        assert 'QR' in message_str  # Quality Control Result
        assert 'QC1' in message_str
        assert 'QC2' in message_str
        assert 'QC3' in message_str
        assert '10.28' in message_str  # QC1 value
        assert '20.48' in message_str  # QC2 value
        assert '30.25' in message_str  # QC3 value

    def test_calibration_workflow(self):
        """Test calibration workflow scenario."""
        cal_message = (
            b"H|\\^&|||ProductModel^01.03.07.03^123456|||||||CR|1394-97|20090910102501\r"
            b"P|1|||||||||||||||||||||||||||||||||\r"
            b"O|1|||||20090910121532||||||1^Cal1^1111^20100910^10^L^11\\2^Cal2^2222^20100910^20^M^22\\3^Cal3^3333^20100910^30^H^33|5^^1.25^25.1^36.48^10.78^98.41||||||||||||F|||||\r"
            b"L|1|N"
        )
        
        records = decode(cal_message)
        assert len(records) >= 1
        
        message_str = str(records)
        assert 'CR' in message_str  # Calibration Result
        assert 'Cal1' in message_str
        assert 'Cal2' in message_str
        assert 'Cal3' in message_str
        assert '1.25' in message_str
        assert '25.1' in message_str
        assert '36.48' in message_str

    def test_sample_query_workflow(self):
        """Test sample query and response workflow."""
        # Query request
        query_request = (
            b"H|\\^&|||ProductModel^01.03.07.03^123456|||||||RQ|1394-97|20090910102501\r"
            b"Q|1|^SAMPLE123||||||||||A\r"
            b"L|1|N"
        )
        
        records = decode(query_request)
        assert len(records) >= 1
        
        message_str = str(records)
        assert 'RQ' in message_str  # Request Query
        assert 'SAMPLE123' in message_str
        
        # Sample not found response
        not_found_response = (
            b"H|\\^&|||ProductModel^01.03.07.03^123456|||||||QA|1394-97|20090910102501\r"
            b"L|1|I"
        )
        
        records = decode(not_found_response)
        assert len(records) >= 1
        
        message_str = str(records)
        assert 'QA' in message_str  # Query Acknowledgment
        
        # Sample found response
        found_response = (
            b"H|\\^&|||ProductModel^01.03.07.03^123456|||||||SA|1394-97|20090910102501\r"
            b"P|1||PATIENT111||Smith^Tom^J||19600315|M|||A|||icteru||||||01|||||A1|002||||||||\r"
            b"O|1|SAMPLE123^1^1||1^Test1^2^1\\2^Test2^2^1\\3^Test3^2^1\\4^Test4^2^1|R|20090910135300|20090910125300|||John|||||Urine|Dr.Who|Department1|1|Dr.Tom||||||Q|||||\r"
            b"L|1|N"
        )
        
        records = decode(found_response)
        assert len(records) >= 1
        
        message_str = str(records)
        assert 'SA' in message_str  # Sample Acknowledgment
        assert 'SAMPLE123' in message_str
        assert 'PATIENT111' in message_str

    def test_complete_patient_result_workflow(self):
        """Test complete patient result workflow with multiple tests."""
        complete_workflow = (
            b"H|\\^&|||ProductModel^01.03.07.03^123456|||||||PR|1394-97|20090910102501\r"
            b"P|1||PATIENT111||Smith^Tom^J||19600315|M|||A|||icteru||||||01|||||A1|002||||||||\r"
            b"O|1|1^1^1|SAMPLE123|1^Test1^2^1\\2^Test2^2^1\\3^Test3^2^1\\4^Test4^2^1|R|20090910135300|20090910125300|||John|||||Urine|Dr.Who|Department1|1|Dr.Tom||||||F|||||\r"
            b"R|1|1^Test1^1^F|14.5^|Mg/ml||5.6^99.9|N||F|||20090910134300|20090910135300|ProductModel^123\r"
            b"R|2|2^Test2^1^F|3.5^|Mg/ml||5.6^50.9|L||F|||20090910134300|20020316135301|ProductModel^123\r"
            b"R|3|3^Test3^1^F|24.5^|Mg/ml||1.1^20.9|H||F|||20090910134300|20020316135302|ProductModel^123\r"
            b"R|4|4^Test4^1^I|^Negative|Mg/ml||||Positive|F|||20090910134300|20020316135303|ProductModel^123\r"
            b"L|1|N"
        )
        
        records = decode(complete_workflow)
        assert len(records) >= 1
        
        message_str = str(records)
        assert 'PR' in message_str  # Patient Result
        assert 'PATIENT111' in message_str
        assert 'Smith^Tom^J' in message_str or 'Smith' in message_str
        assert 'SAMPLE123' in message_str
        assert '14.5' in message_str  # Test1 result (Normal)
        assert '3.5' in message_str   # Test2 result (Low)
        assert '24.5' in message_str  # Test3 result (High)
        assert 'Negative' in message_str  # Test4 result (Qualitative)

    def test_comment_with_result_workflow(self):
        """Test workflow with comments attached to results."""
        result_with_comment = (
            b"H|\\^&|||ProductModel^01.03.07.03^123456|||||||PR|1394-97|20090910102501\r"
            b"P|1||PATIENT111||Smith^Tom^J||19600315|M|||A|||icteru||||||01|||||A1|002||||||||\r"
            b"O|1|1^1^1|SAMPLE123|1^Test1^2^1|R|20090910135300|20090910125300|||John|||||Urine|Dr.Who|Department1|1|Dr.Tom||||||F|||||\r"
            b"R|1|1^Test1^1^F|14.5^|Mg/ml||5.6^99.9|N||F|||20090910134300|20090910135300|ProductModel^123\r"
            b"C|1|I|Result Description|I\r"
            b"L|1|N"
        )
        
        records = decode(result_with_comment)
        assert len(records) >= 1
        
        message_str = str(records)
        assert 'Result Description' in message_str
        assert '14.5' in message_str

    def test_high_glucose_scenario(self):
        """Test high glucose scenario from production example."""
        glucose_scenario = (
            b"H|\\^&|||ACME^LAB^1.0|||||||||||20250101120000|\r"
            b"P|1|PAT001|||Doe^John^M|19850615|M\r"
            b"O|1|SAMPLE001||^^^GLUCOSE|R|20250101120000\r"
            b"R|1|^^^GLUCOSE|150|mg/dL|70-110|H|F\r"
            b"C|1|High glucose level - recommend dietary consultation\r"
            b"L|1|N"
        )
        
        records = decode(glucose_scenario)
        assert len(records) >= 1
        
        message_str = str(records)
        assert 'ACME' in message_str
        assert 'PAT001' in message_str
        assert 'Doe^John^M' in message_str or 'John' in message_str
        assert 'GLUCOSE' in message_str
        assert '150' in message_str  # High glucose value
        assert 'H' in message_str    # High flag
        assert 'dietary consultation' in message_str

    def test_analyzer_communication_handshake(self):
        """Test typical analyzer communication handshake patterns."""
        # This would typically involve ENQ/ACK sequences, but we focus on ASTM content
        handshake_messages = [
            # Initial connection
            b"H|\\^&|||Mindry^^|||||||PR|1394-97|20250701173105",
            # Patient info request
            b"P|1||||^^||^^|U||||||||||||||||||||||||||",
            # Order acknowledgment
            b"O|1|SAMPLE||TEST|R|20250701120000",
            # Result transmission
            b"R|1|TEST|123|mg/dL|ref|N|F",
            # Termination
            b"L|1|N"
        ]
        
        for message in handshake_messages:
            records = decode(message)
            assert len(records) >= 1
            record = records[0]
            assert record[0] in ['H', 'P', 'O', 'R', 'L']

    def test_error_recovery_scenarios(self):
        """Test error recovery scenarios in production."""
        # Malformed record that should be handled gracefully
        error_scenarios = [
            b"H|\\^&|||TEST|||||||||||||",  # Incomplete header
            b"P|1|INVALID@#$%ID|||",        # Invalid patient ID
            b"R|1|TEST||mg/dL|ref|N|F",     # Missing result value
            b"L|1|",                        # Incomplete terminator
        ]
        
        for error_message in error_scenarios:
            try:
                records = decode(error_message)
                # Should handle gracefully
                assert isinstance(records, list)
            except Exception:
                # Exceptions are acceptable for error scenarios
                pass

    def test_multi_analyzer_scenario(self):
        """Test scenario with multiple analyzers sending data."""
        # Access 2 message
        access2_msg = b"H|\\^&|||ACCESS^575707|||||LIS||P|1|20250701185020\rR|1|^^^B12II^1|131|pg/mL|222 to 1439^normal|L|N|F\rL|1|N"
        
        # Mindray message
        mindray_msg = b"H|\\^&|||Mindry^^|||||||PR|1394-97|20250701173105\rR|162|CREAS^^F|3.216365|mg/dL|^|N\rL|1|N"
        
        # Snibe message
        snibe_msg = b"H|\\^&||PSWD|Maglumi User|||||Lis||P|E1394-97|20250701\rR|1|^^^TT3 II|1.171|ng/mL|0.75 to 2.1|N\rL|1|N"
        
        messages = [access2_msg, mindray_msg, snibe_msg]
        
        for i, message in enumerate(messages):
            records = decode(message)
            assert len(records) >= 1
            
            message_str = str(records)
            if i == 0:  # Access 2
                assert 'ACCESS' in message_str and 'B12' in message_str
            elif i == 1:  # Mindray
                assert 'Mindry' in message_str and 'CREAS' in message_str
            elif i == 2:  # Snibe
                assert 'Maglumi' in message_str and 'TT3' in message_str