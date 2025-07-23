"""
Tests for different ASTM message types.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
try:
    from astmio.codec import decode

    print("Got the decode implementation")
except ImportError:
    print("Error: decode")


class TestASTMMessageTypes:
    """Test parsing of different ASTM message types."""

    def test_header_record_variations(self):
        """Test different header record formats from various analyzers."""
        # Access 2 header
        access2_header = b"H|\\^&|||ACCESS^575707|||||LIS||P|1|20250701185020"
        records = decode(access2_header)
        assert len(records) >= 1
        header = records[0]
        assert header[0] == "H"

        # Mindray header
        mindray_header = b"H|\\^&|||Mindry^^|||||||PR|1394-97|20250701173105"
        records = decode(mindray_header)
        assert len(records) >= 1
        header = records[0]
        assert header[0] == "H"

        # Product Model header
        product_header = b"H|\\^&|||ProductModel^01.03.07.03^123456|||||||PR|1394-97|20090910102501"
        records = decode(product_header)
        assert len(records) >= 1
        header = records[0]
        assert header[0] == "H"

    def test_patient_record_variations(self):
        """Test different patient record formats."""
        # Standard patient record
        patient_std = b"P|1||PATIENT111||Smith^Tom^J||19600315|M|||A||Dr.Bean|icteru|100012546|||Diagnosis information||0001|||||A1|002||||||||"
        records = decode(patient_std)
        assert len(records) >= 1
        patient = records[0]
        assert patient[0] == "P"

        # Minimal patient record
        patient_min = b"P|1"
        records = decode(patient_min)
        assert len(records) >= 1
        patient = records[0]
        assert patient[0] == "P"
        assert patient[1] == "1"

        # Patient with invalid ID (test case from your examples)
        patient_invalid = (
            b"P|476|INVALID@#$%ID|||^^||^^|U||||||||||||||||||||||||||"
        )
        records = decode(patient_invalid)
        assert len(records) >= 1
        patient = records[0]
        assert patient[0] == "P"
        assert patient[1] == "476"

    def test_order_record_variations(self):
        """Test different order record formats and test combinations."""
        # Single test order
        order_single = (
            b"O|1|2025105867|^1316^1|^^^B12|||||Serum|||||II^1||||||||||F"
        )
        records = decode(order_single)
        assert len(records) >= 1
        order = records[0]
        assert order[0] == "O"
        assert order[1] == "1"

        # Multiple tests with backslash separator
        order_multi = b"O|1|25059232||^^^TT3 II\\^^^TT4 II\\^^^TSH II"
        records = decode(order_multi)
        assert len(records) >= 1
        order = records[0]
        assert order[0] == "O"
        # Should contain all test names
        order_str = str(order)
        assert "TT3 II" in order_str
        assert "TT4 II" in order_str
        assert "TSH II" in order_str

        # Creatinine and Urea tests
        order_creas = b"O|476|8^^|2025105875|CREAS^Creatinine (Sarcosine Oxidase Method)^^\\UREA^Urea^^|R|20250701145215|20250701145140|||||||20250701145140|serum||||||||||F|||||"
        records = decode(order_creas)
        assert len(records) >= 1
        order = records[0]
        assert order[0] == "O"
        order_str = str(order)
        assert "CREAS" in order_str or "Creatinine" in order_str
        assert "UREA" in order_str or "Urea" in order_str

    def test_result_record_variations(self):
        """Test different result record formats and values."""
        # Numeric result with units
        result_numeric = b"R|1|^^^B12II^1|131|pg/mL|222 to 1439^normal|L|N|F||||20250701184502|575707"
        records = decode(result_numeric)
        assert len(records) >= 1
        result = records[0]
        assert result[0] == "R"
        assert result[1] == "1"
        assert result[3] == "131"
        assert result[4] == "pg/mL"

        # Result with abnormal flag
        result_abnormal = b"R|1|^^^GLUCOSE|150|mg/dL|70-110|H|F"
        records = decode(result_abnormal)
        assert len(records) >= 1
        result = records[0]
        assert result[0] == "R"
        assert result[3] == "150"
        assert result[6] == "H"  # High flag

        # Creatinine result
        result_creas = b"R|162|CREAS^Creatinine (Sarcosine Oxidase Method)^^F|3.216365^^^^|mg/dL|^|N||F|3.216365^^^^|0|20250701154742||Mindry^"
        records = decode(result_creas)
        assert len(records) >= 1
        result = records[0]
        assert result[0] == "R"
        result_str = str(result)
        assert "3.216365" in result_str
        assert "mg/dL" in result_str

        # Qualitative result
        result_qual = b"R|4|4^Test4^1^I|^Negative|Mg/ml||||Positive|F|||20090910134300|20020316135303|Product Model ^123"
        records = decode(result_qual)
        assert len(records) >= 1
        result = records[0]
        assert result[0] == "R"
        result_str = str(result)
        assert "Negative" in result_str

    def test_comment_record_parsing(self):
        """Test comment record parsing."""
        comment = b"C|1|I|Result Description|I"
        records = decode(comment)
        assert len(records) >= 1
        comment_rec = records[0]
        assert comment_rec[0] == "C"
        assert comment_rec[1] == "1"

        # Comment with high glucose recommendation
        comment_glucose = (
            b"C|1|High glucose level - recommend dietary consultation"
        )
        records = decode(comment_glucose)
        assert len(records) >= 1
        comment_rec = records[0]
        assert comment_rec[0] == "C"
        comment_str = str(comment_rec)
        assert "glucose" in comment_str.lower()

    def test_terminator_record_variations(self):
        """Test different terminator record formats."""
        # Normal termination
        term_normal = b"L|1|N"
        records = decode(term_normal)
        assert len(records) >= 1
        term = records[0]
        assert term[0] == "L"
        assert term[1] == "1"
        assert term[2] == "N"

        # Query termination
        term_query = b"L|1|Q"
        records = decode(term_query)
        assert len(records) >= 1
        term = records[0]
        assert term[0] == "L"
        assert term[2] == "Q"

        # Information termination
        term_info = b"L|1|I"
        records = decode(term_info)
        assert len(records) >= 1
        term = records[0]
        assert term[0] == "L"
        assert term[2] == "I"

    def test_query_record_parsing(self):
        """Test query record parsing for sample inquiries."""
        # Query for sample
        query = b"Q|1|^SAMPLE123||||||||||A"
        records = decode(query)
        assert len(records) >= 1
        query_rec = records[0]
        assert query_rec[0] == "Q"
        assert query_rec[1] == "1"
        query_str = str(query_rec)
        assert "SAMPLE123" in query_str

    def test_quality_control_records(self):
        """Test QC record parsing."""
        # QC order record
        qc_order = b"O|1|||||20090910121532|||||1^QC1^1111^20100910^10^L^5^10.28\\2^QC2^2222^20100910^20^M^10^20.48\\3^QC3^3333^20100910^30^H^15^30.25||||||||||||||F|||||"
        records = decode(qc_order)
        assert len(records) >= 1
        order = records[0]
        assert order[0] == "O"
        order_str = str(order)
        assert "QC1" in order_str or "QC2" in order_str or "QC3" in order_str

    def test_calibration_records(self):
        """Test calibration record parsing."""
        # Calibration order
        cal_order = b"O|1|||||20090910121532||||||1^Cal1^1111^20100910^10^L^11\\2^Cal2^2222^20100910^20^M^22\\3^Cal3^3333^20100910^30^H^33|5^^1.25^25.1^36.48^10.78^98.41||||||||||||F|||||"
        records = decode(cal_order)
        assert len(records) >= 1
        order = records[0]
        assert order[0] == "O"
        order_str = str(order)
        assert "Cal1" in order_str or "Cal2" in order_str or "Cal3" in order_str

    def test_message_type_identification(self):
        """Test identification of different message types based on header."""
        # Patient Result message
        pr_header = b"H|\\^&|||ProductModel^01.03.07.03^123456|||||||PR|1394-97|20090910102501"
        records = decode(pr_header)
        assert len(records) >= 1
        header = records[0]
        header_str = str(header)
        assert "PR" in header_str  # Patient Result

        # Sample Acknowledgment message
        sa_header = b"H|\\^&|||ProductModel^01.03.07.03^123456|||||||SA|1394-97|20090910102501"
        records = decode(sa_header)
        assert len(records) >= 1
        header = records[0]
        header_str = str(header)
        assert "SA" in header_str  # Sample Acknowledgment

        # Query Request message
        rq_header = b"H|\\^&|||ProductModel^01.03.07.03^123456|||||||RQ|1394-97|20090910102501"
        records = decode(rq_header)
        assert len(records) >= 1
        header = records[0]
        header_str = str(header)
        assert "RQ" in header_str  # Request Query

        # Quality Control Result message
        qr_header = b"H|\\^&|||ProductModel^01.03.07.03^123456|||||||QR|1394-97|20090910102501"
        records = decode(qr_header)
        assert len(records) >= 1
        header = records[0]
        header_str = str(header)
        assert "QR" in header_str  # QC Result

        # Calibration Result message
        cr_header = b"H|\\^&|||ProductModel^01.03.07.03^123456|||||||CR|1394-97|20090910102501"
        records = decode(cr_header)
        assert len(records) >= 1
        header = records[0]
        header_str = str(header)
        assert "CR" in header_str  # Calibration Result
