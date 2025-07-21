# ASTM Parser Test Suite

This directory contains comprehensive test cases for the ASTM parser library, covering various scenarios from real-world analyzer communications.

## Test Files Overview

### 1. `test_astm_parser.py`
**Main parser functionality tests**
- Tests parsing of different analyzer data formats (Access 2, BS-240, Erba, Snibe Maglumi)
- Validates record field mapping and component parsing
- Tests multi-test parsing and complete message sequences
- Covers various record types (Header, Patient, Order, Result, Terminator, Query, Comment)
- Tests analyzer-specific formats and message type identification

### 2. `test_astm_edge_cases.py`
**Edge cases and error handling**
- Malformed records and empty input handling
- Control characters and special character processing
- Very long fields and maximum field count scenarios
- Unicode handling and encoding roundtrip tests
- Boundary conditions and memory stress testing
- Mixed line endings and incomplete record handling

### 3. `test_astm_message_types.py`
**Different ASTM message types and communication patterns**
- Patient Result (PR) messages
- Sample Acknowledgment (SA) messages
- Query Request (RQ) and Query Acknowledgment (QA) messages
- Quality Control Result (QR) messages
- Calibration Result (CR) messages
- Comment messages and multi-message parsing
- Message sequence validation and termination codes

### 4. `test_astm_field_parsing.py`
**Detailed field parsing and component handling**
- Component separator parsing (^)
- Repeat separator parsing (\)
- Escape sequence handling
- Empty field and special character processing
- Numeric, date/time, and reference range parsing
- Patient name, address, and physician field parsing
- Units, abnormal flags, and status field parsing
- Field length limits and count validation

### 5. `test_astm_production_scenarios.py`
**Real-world production scenarios**
- Access 2 B12 test scenario
- Mindray creatinine and urea test workflow
- Snibe Maglumi thyroid panel testing
- Invalid patient ID handling workflow
- Quality control and calibration workflows
- Sample query and response patterns
- Complete patient result workflows with comments
- Multi-analyzer communication scenarios

## Test Coverage

The test suite covers:

### Analyzer Types
- **Access 2**: B12 testing, specific field formats
- **Mindray BS-240**: Multi-parameter chemistry panels
- **Snibe Maglumi**: Thyroid function tests (TT3, TT4, TSH)
- **Erba**: HL7 format detection and handling

### Record Types
- **H (Header)**: Various analyzer identification formats
- **P (Patient)**: Demographics, IDs, special characters
- **O (Order)**: Single and multi-test orders, priorities
- **R (Result)**: Numeric, qualitative, with flags and timestamps
- **L (Terminator)**: Normal, query, information termination
- **C (Comment)**: Result descriptions and recommendations
- **Q (Query)**: Sample inquiries and responses

### Communication Patterns
- Host to Instrument orders
- Instrument to Host results
- Query/Response workflows
- Error handling and recovery
- Quality control procedures
- Calibration workflows

### Field Parsing
- Component separators (^)
- Repeat separators (\)
- Field separators (|)
- Record separators (CR)
- Empty and null field handling
- Special characters and Unicode
- Long field values and limits

### Error Scenarios
- Malformed records
- Invalid patient IDs
- Missing required fields
- Encoding issues
- Memory stress conditions
- Boundary conditions

## Running Tests

To run all ASTM parser tests:
```bash
python -m pytest tests/test_astm_*.py -v
```

To run specific test categories:
```bash
# Main parser functionality
python -m pytest tests/test_astm_parser.py -v

# Production scenarios
python -m pytest tests/test_astm_production_scenarios.py -v

# Edge cases
python -m pytest tests/test_astm_edge_cases.py -v

# Field parsing
python -m pytest tests/test_astm_field_parsing.py -v

# Message types
python -m pytest tests/test_astm_message_types.py -v
```

## Test Data Sources

The tests are based on real production data from:
- Access 2 AnalyzerLogs.txt
- BS-240 ASTM communication logs
- Snibe Maglumi analyzer outputs
- Production example scenarios
- YAML profile configurations (access2.yaml, erba.yaml, snibe_maglumi.yaml)

## Key Features Tested

1. **Multi-analyzer support**: Tests handle different analyzer formats and protocols
2. **Robust parsing**: Handles malformed data, special characters, and edge cases
3. **Production scenarios**: Real-world communication patterns and workflows
4. **Field validation**: Comprehensive field parsing and component handling
5. **Error recovery**: Graceful handling of various error conditions
6. **Performance**: Memory stress testing and boundary condition handling

## Notes

- Tests use a fallback decode function for compatibility when the full astmio library isn't available
- Frame sequence numbers (e.g., "1H" instead of "H") are properly handled
- Unicode and encoding issues are tested across different character sets
- Production scenarios reflect actual analyzer communication patterns observed in healthcare environments