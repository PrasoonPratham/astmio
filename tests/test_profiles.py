"""
Tests for device profile loading, validation, and usage.
"""

import pytest
from pathlib import Path
import yaml
import tempfile
import os

from astmio.config import DeviceProfile, TransportConfig, FrameConfig, load_profile, validate_profile
from astmio import decode, encode_message, decode_message


class TestProfiles:
    """Test device profile functionality."""
    
    @pytest.fixture
    def profiles_dir(self):
        """Get the profiles directory."""
        return Path(__file__).parent.parent / "etc" / "profiles"
    
    @pytest.fixture
    def sample_profile(self):
        """Create a sample profile for testing."""
        return {
            "device": "Test Analyzer",
            "protocol": "ASTM_E1394-97",
            "transport": {
                "mode": "tcp",
                "port": 5001,
                "host": "0.0.0.0",
                "encoding": "ascii"
            },
            "records": {
                "H": {
                    "delimiter": "|\\^&",
                    "processing_id": "P",
                    "version": "E1394-97",
                    "fields": [
                        "type", "delimiter", "message_id", "password",
                        "sender", "address", "reserved", "phone",
                        "capabilities", "receiver", "comments",
                        "processing_id", "version", "timestamp"
                    ]
                },
                "P": {
                    "fields": ["type", "sequence", "patient_id", "name"]
                },
                "O": {
                    "fields": ["type", "sequence", "sample_id", "instrument", "test"]
                },
                "R": {
                    "fields": ["type", "sequence", "test", "value", "units", 
                              "references", "abnormal_flag"]
                },
                "L": {
                    "fields": ["type", "sequence", "termination_code"]
                }
            },
            "parser": {
                "patient_name_field": "P.3",
                "sample_id_field": "O.2",
                "test_separator": "\\",
                "component_separator": "^"
            }
        }
    
    def test_load_existing_profiles(self, profiles_dir):
        """Test loading all existing profile files."""
        profile_files = [
            "mindray_bs240.yaml",
            "access2.yaml",
            "erba.yaml",
            "snibe_maglumi.yaml"
        ]
        
        for profile_file in profile_files:
            profile_path = profiles_dir / profile_file
            assert profile_path.exists(), f"Profile {profile_file} should exist"
            
            # Load and validate profile
            with open(profile_path, 'r') as f:
                profile_data = yaml.safe_load(f)
            
            # Check required fields
            assert "device" in profile_data
            assert "protocol" in profile_data
            assert "transport" in profile_data
            assert "records" in profile_data
            
            # Validate transport config
            transport = profile_data["transport"]
            assert "mode" in transport
            assert "port" in transport
            assert "host" in transport
            assert "encoding" in transport
            
            # Validate record definitions
            records = profile_data["records"]
            assert "H" in records  # Header should always be defined
            assert "L" in records  # Terminator should always be defined
    
    def test_profile_validation(self, sample_profile):
        """Test profile validation logic."""
        # Valid profile should pass
        assert validate_profile(sample_profile) is True
        
        # Test missing required fields
        invalid_profile = sample_profile.copy()
        del invalid_profile["device"]
        with pytest.raises(ValueError, match="Device name is required"):
            validate_profile(invalid_profile)
        
        # Test invalid transport mode - create fresh copy
        invalid_profile = sample_profile.copy()
        invalid_profile["transport"] = invalid_profile["transport"].copy()
        invalid_profile["transport"]["mode"] = "invalid"
        with pytest.raises(ValueError, match="TransportMode|transport.*configuration"):
            validate_profile(invalid_profile)
        
        # Test invalid record type - create fresh copy
        # Note: Unknown record types are currently logged as warnings rather than errors
        # This maintains backward compatibility with existing profiles
        invalid_profile2 = sample_profile.copy()
        invalid_profile2["records"] = invalid_profile2["records"].copy()
        invalid_profile2["records"]["X"] = {"fields": ["type"]}
        # Should still validate successfully (unknown types are ignored)
        assert validate_profile(invalid_profile2) is True
    
    def test_profile_field_mapping(self, profiles_dir):
        """Test field mapping using profiles."""
        # Load Snibe profile
        with open(profiles_dir / "snibe_maglumi.yaml", 'r') as f:
            profile = yaml.safe_load(f)
        
        # Parse a Snibe message
        message = b"H|\\^&||PSWD|Maglumi User|||||Lis||P|E1394-97|20250701"
        records = decode(message)
        header = records[0]
        
        # Map fields using profile
        field_map = {}
        header_fields = profile["records"]["H"]["fields"]
        for i, field_name in enumerate(header_fields):
            if i < len(header):
                field_map[field_name] = header[i]
        
        # Verify mapping
        assert field_map["type"] == "H"
        assert field_map["password"] == "PSWD"
        assert field_map["sender"] == "Maglumi User"
        assert field_map["receiver"] == "Lis"
        assert field_map["processing_id"] == "P"
        assert field_map["version"] == "E1394-97"
        assert field_map["timestamp"] == "20250701"
    
    def test_profile_based_encoding(self, sample_profile):
        """Test encoding messages using profile definitions."""
        # Create records based on profile field definitions
        records = []
        
        # Header record
        header_fields = ['H', ['', '^&'], None, 'TEST', 'Test System',
                        None, None, None, None, 'LIS', None, 'P', 
                        'E1394-97', '20250701']
        records.append(header_fields)
        
        # Patient record
        patient_fields = ['P', '1', '12345', 'John Doe']
        records.append(patient_fields)
        
        # Order record
        order_fields = ['O', '1', 'SAMPLE001', None, '^^^GLUCOSE']
        records.append(order_fields)
        
        # Result record
        result_fields = ['R', '1', '^^^GLUCOSE', '95', 'mg/dL', '70-110', 'N']
        records.append(result_fields)
        
        # Terminator record
        term_fields = ['L', '1', 'N']
        records.append(term_fields)
        
        # Encode message
        data = encode_message(1, records, 'latin-1')
        
        # Decode and verify
        decoded_seq, decoded_records, decoded_checksum = decode_message(data, 'latin-1')
        assert len(decoded_records) == 5
        assert decoded_records[0][0] == 'H'
        assert decoded_records[1][0] == 'P'
        assert decoded_records[2][0] == 'O'
        assert decoded_records[3][0] == 'R'
        assert decoded_records[4][0] == 'L'
    
    def test_create_profile_from_scratch(self):
        """Test creating a new profile programmatically."""
        # Create a new profile
        new_profile = {
            "device": "Custom Analyzer",
            "protocol": "ASTM_E1394-97",
            "transport": {
                "mode": "tcp",
                "port": 6000,
                "host": "localhost",
                "encoding": "utf-8"
            },
            "records": {
                "H": {
                    "delimiter": "|\\^&",
                    "processing_id": "P",
                    "version": "E1394-97",
                    "fields": ["type", "delimiter", "sender", "receiver", 
                              "processing_id", "version", "timestamp"]
                },
                "P": {
                    "fields": ["type", "sequence", "patient_id"]
                },
                "O": {
                    "fields": ["type", "sequence", "sample_id", "test"]
                },
                "R": {
                    "fields": ["type", "sequence", "test", "value", "units"]
                },
                "L": {
                    "fields": ["type", "sequence", "code"]
                }
            }
        }
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(new_profile, f)
            temp_path = f.name
        
        try:
            # Load and validate
            with open(temp_path, 'r') as f:
                loaded_profile = yaml.safe_load(f)
            
            assert loaded_profile["device"] == "Custom Analyzer"
            assert loaded_profile["transport"]["port"] == 6000
            assert len(loaded_profile["records"]["H"]["fields"]) == 7
            
        finally:
            # Cleanup
            os.unlink(temp_path)
    
    def test_profile_compatibility(self, profiles_dir):
        """Test that all profiles follow the same structure."""
        profile_files = list(profiles_dir.glob("*.yaml"))
        
        # Load all profiles
        profiles = {}
        for profile_path in profile_files:
            with open(profile_path, 'r') as f:
                profiles[profile_path.stem] = yaml.safe_load(f)
        
        # Check common structure
        for name, profile in profiles.items():
            # All should have these top-level keys
            assert "device" in profile, f"{name} missing device"
            assert "protocol" in profile, f"{name} missing protocol"
            assert "transport" in profile, f"{name} missing transport"
            assert "records" in profile, f"{name} missing records"
            
            # All should define at least H and L records
            assert "H" in profile["records"], f"{name} missing H record"
            assert "L" in profile["records"], f"{name} missing L record"
            
            # Transport should have required fields
            transport = profile["transport"]
            assert "mode" in transport, f"{name} missing transport.mode"
            assert "port" in transport, f"{name} missing transport.port"
            assert "encoding" in transport, f"{name} missing transport.encoding"
    
    def test_profile_specific_features(self, profiles_dir):
        """Test profile-specific features and configurations."""
        # Test BS-240 specific features
        with open(profiles_dir / "mindray_bs240.yaml", 'r') as f:
            bs240_profile = yaml.safe_load(f)
        
        # BS-240 should have specific parser settings
        assert "parser" in bs240_profile
        assert bs240_profile["parser"]["patient_name_field"] == "P.5"
        assert bs240_profile["parser"]["sample_id_field"] == "O.3"
        
        # Test Snibe Maglumi specific features
        with open(profiles_dir / "snibe_maglumi.yaml", 'r') as f:
            snibe_profile = yaml.safe_load(f)
        
        # Snibe should handle multiple tests with backslash separator
        assert "parser" in snibe_profile
        assert snibe_profile["parser"]["test_separator"] == "\\"
        
        # Header should have password field defined
        header_fields = snibe_profile["records"]["H"]["fields"]
        assert "password" in header_fields
        
    def test_dynamic_profile_loading(self, sample_profile):
        """Test loading profiles dynamically at runtime."""
        # Use the proper from_dict method to create DeviceProfile
        device_profile = DeviceProfile.from_dict(sample_profile)
        
        # Verify dataclass fields
        assert device_profile.device == "Test Analyzer"
        assert device_profile.protocol == "ASTM_E1394-97"
        assert device_profile.transport.port == 5001
        assert "H" in device_profile.records
        assert "L" in device_profile.records 