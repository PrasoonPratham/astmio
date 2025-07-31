import json
from pathlib import Path
from typing import Any, Callable, Dict, Union

try:
    import yaml
except ImportError:
    yaml = None
try:
    import toml
except ImportError:
    toml = None

from .enums import SerializationFormat
from .exceptions import BaseASTMError, ConfigurationError, ValidationError
from .logging import get_logger
from .profile import DeviceProfile

log = get_logger(__name__)

_LOADER_MAP: Dict[SerializationFormat, Callable] = {}
if yaml:
    _LOADER_MAP[SerializationFormat.YAML] = yaml.safe_load
if toml:
    _LOADER_MAP[SerializationFormat.TOML] = toml.load
if json:
    _LOADER_MAP[SerializationFormat.JSON] = json.load


Saver = Callable[[Dict[str, Any], Any], None]
_SAVER_MAP: Dict[SerializationFormat, Saver] = {}
if yaml:
    _SAVER_MAP[SerializationFormat.YAML] = lambda data, f: yaml.dump(
        data, f, default_flow_style=False, indent=2
    )
if toml:
    _SAVER_MAP[SerializationFormat.TOML] = lambda data, f: toml.dump(data, f)
if json:
    _SAVER_MAP[SerializationFormat.JSON] = lambda data, f: json.dump(
        data, f, indent=2, default=str
    )


# For maintaining backward compatibility
def from_file(filepath: Union[str, Path]) -> "DeviceProfile":
    return load_profile_from_file(filepath)


def load_profile_from_file(filepath: Union[str, Path]) -> "DeviceProfile":
    """Loads a device profile from a file."""
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"Profile file not found: {filepath}")

    try:
        profile_format = _get_format_from_path(filepath)
        loader = _get_loader(profile_format)

        with open(filepath, encoding="utf-8") as f:
            config_data = loader(f)

        return DeviceProfile.from_dict(config_data, source_file=str(filepath))
    except (OSError, ValueError, ImportError) as e:
        raise ValidationError(f"Error loading profile from {filepath}") from e


def load_profile_from_yaml(file_path: str) -> DeviceProfile:
    """
    Loads, validates, and prepares a complete device profile from a YAML file.

    This is the main entry point for the validation engine's initialization. It
    handles file reading, schema validation via Pydantic, and triggers the
    dynamic generation of runtime record parsers.

    Args:
        file_path: The path to the device profile YAML file.

    Returns:
        A fully initialized DeviceProfile instance with dynamic record parsers ready.

    Raises:
        ConfigurationError: If the YAML file is invalid, has structural errors,
                            or violates defined validation rules.
        FileNotFoundError: If the specified file path does not exist.
    """
    log.info("Loading device profile from: %s", file_path)
    try:
        with open(file_path, encoding="utf-8") as f:
            config_data = yaml.safe_load(f)
        if not isinstance(config_data, dict):
            raise ConfigurationError(
                message="Configuration file is not a valid dictionary (YAML mapping).",
                config_key="root",
            )
    except FileNotFoundError:
        log.error("Configuration file not found at path: %s", file_path)
        raise
    except yaml.YAMLError as e:
        # Wrap a generic YAML parsing error in our specific ConfigurationError
        raise ConfigurationError(
            message="Configuration file is not valid YAML and could not be parsed.",
            cause=e,
        )

    try:
        profile: DeviceProfile = DeviceProfile.model_validate(config_data)
        profile.generate_record_models()

        log.info(
            "Successfully loaded and prepared profile for device '%s'.",
            profile.device,
        )
        return profile
    except ValidationError as e:
        log.error("Device profile validation failed. See details below.")
        raise ConfigurationError(
            message=f"The device profile at '{file_path}' is invalid. Details: {e}",
            cause=e,
        )
    except BaseASTMError:
        raise


def _get_format_from_path(filepath: Path) -> SerializationFormat:
    """Determines the serialization format from the file extension."""
    format_map = {
        ".yaml": SerializationFormat.YAML,
        ".yml": SerializationFormat.YAML,
        ".json": SerializationFormat.JSON,
        ".toml": SerializationFormat.TOML,
    }
    file_ext = filepath.suffix.lower()
    profile_format = format_map.get(file_ext)
    if not profile_format:
        raise ValidationError(f"Unsupported file extension: '{file_ext}'")
    return profile_format


def _get_loader(profile_format: SerializationFormat) -> Callable:
    """Retrieves the loader function for a given format."""
    loader = _LOADER_MAP.get(profile_format)
    if not loader:
        raise ImportError(
            f"Support for '{profile_format.value}' format is not installed."
        )
    return loader


def _get_saver(profile_format: SerializationFormat) -> Saver:
    """Retrieves the saver function for a given format."""
    saver = _SAVER_MAP.get(profile_format)
    if not saver:
        raise ImportError(
            f"Support for '{profile_format.value}' format is not installed."
        )
    return saver


def save_profile_to_file(
    profile: "DeviceProfile",
    filepath: Union[str, Path],
    format: SerializationFormat,
) -> None:
    """Saves a device profile to a file."""
    filepath = Path(filepath)
    try:
        saver = _get_saver(format)
        data = profile.to_dict()
        with open(filepath, "w", encoding="utf-8") as f:
            saver(data, f)
    except (OSError, ValueError, ImportError) as e:
        raise ValidationError(f"Failed to save profile to {filepath}") from e
