# ASTMIO Test Suite

This directory contains comprehensive tests for the ASTMIO library, ensuring all ASTM data from different analyzers can be parsed correctly.

## Test Structure

- **test_astm_parser.py** - Tests for parsing ASTM data from all example files
  - Tests for Access 2 analyzer data
  - Tests for BS-240 analyzer data  
  - Tests for Erba analyzer data
  - Tests for Snibe Maglumi analyzer data
  - Tests for multi-test parsing and complete message sequences

- **test_records.py** - Tests for individual ASTM record types
  - Modern Pydantic-based record tests (Header, Patient, Order, Result, Comment, Terminator)
  - Legacy mapping-based record tests
  - Record encoding/decoding tests
  - Field validation tests

- **test_integration.py** - Integration tests for end-to-end ASTM processing
  - Client-server communication tests
  - Message framing tests (STX/ETX/EOT)
  - Multi-frame message handling
  - Real-world message parsing
  - Error handling tests
  - Bidirectional communication tests

- **test_profiles.py** - Tests for device profile functionality
  - Profile loading and validation
  - Field mapping using profiles
  - Profile-based encoding
  - Profile compatibility tests
  - Dynamic profile loading

## Running Tests

To run all tests:
```bash
python -m pytest tests/ -v
```

To run specific test files:
```bash
python -m pytest tests/test_astm_parser.py -v
python -m pytest tests/test_records.py -v
python -m pytest tests/test_integration.py -v
python -m pytest tests/test_profiles.py -v
```

To run with coverage:
```bash
python -m pytest tests/ --cov=astmio --cov-report=html
```

## Test Data

The tests use real ASTM data from the `example_astm/` directory:
- Access 2 analyzer logs
- BS-240 analyzer data
- Erba analyzer data
- Snibe Maglumi analyzer data

## Device Profiles

YAML configuration profiles for each analyzer type are located in `etc/profiles/`:
- `access2.yaml` - Access 2 analyzer profile
- `mindray_bs240.yaml` - Mindray BS-240 analyzer profile
- `erba.yaml` - Erba analyzer profile
- `snibe_maglumi.yaml` - Snibe Maglumi analyzer profile

Each profile defines:
- Device information
- Transport configuration (TCP/Serial)
- Record structure and field mappings
- Parser settings

## Test Requirements

- Python 3.8+
- pytest
- pytest-asyncio
- PyYAML

Install test dependencies:
```bash
pip install -e ".[dev]"
``` 