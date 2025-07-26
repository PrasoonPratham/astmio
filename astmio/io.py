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
from .exceptions import ValidationError
from .profile import DeviceProfile

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
