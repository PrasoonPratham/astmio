from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from astmio.profile import DeviceProfile

from .enums import SerializationFormat
from .exceptions import ValidationError
from .io import from_file
from .logging import get_logger

log = get_logger(__name__)


class ConfigManager:
    """Enhanced configuration manager with advanced features."""

    def __init__(
        self, profile_directories: Optional[List[Union[str, Path]]] = None
    ):
        """Initialize with optional profile directories."""
        self._profiles: Dict[str, DeviceProfile] = {}
        self._profile_directories: List[Path] = []
        self._watchers: List[Callable[[str, DeviceProfile], None]] = []
        self._profile_cache: Dict[str, DeviceProfile] = {}
        self._validation_cache: Dict[str, List[str]] = {}
        self._load_stats = {"successful": 0, "failed": 0, "cached": 0}

        if profile_directories:
            for directory in profile_directories:
                self.add_profile_directory(directory)

    # Can add a directory where profiles have been defined
    def add_profile_directory(self, directory: Union[str, Path]) -> None:
        """Add a directory to search for profiles."""
        directory = Path(directory)
        if directory.exists() and directory.is_dir():
            self._profile_directories.append(directory)
            log.info(f"Added profile directory: {directory}")
        else:
            log.warning(f"Profile directory not found: {directory}")

    def discover_profiles(self) -> List[str]:
        """Changed here - Enhanced profile discovery with caching and validation."""
        discovered = []

        for directory in self._profile_directories:
            try:
                # Look for YAML, JSON, and TOML files
                patterns = ["*.yaml", "*.yml", "*.json", "*.toml"]
                for pattern in patterns:
                    for filepath in directory.glob(pattern):
                        profile = load_profile(filepath)
                        discovered.append(profile.device)
                        log.info(f"Discovered profile: {profile.device}")
            except Exception as e:
                log.error(f"Failed to scan directory {directory}: {e}")

        log.info(f"Profile discovery stats: {self._load_stats}")
        return discovered

    # Can load the profile directly
    def load_profile(self, filepath: Union[str, Path]) -> DeviceProfile:
        """Load a specific profile file."""
        try:
            # Convert the str into Path obj for consistency
            if isinstance(filepath, str):
                filepath = Path(filepath)

            cache_key = str(filepath.absolute())
            if cache_key in self._profile_cache:
                profile: DeviceProfile = self._profile_cache[cache_key]
                self._load_stats["cached"] += 1
                log.debug(f"Using cached profile: {profile.device}")
            else:
                profile: DeviceProfile = from_file(filepath)
                self._profile_cache[cache_key] = profile
                self._load_stats["successful"] += 1

            validation_errors = profile.validate()
            if validation_errors:
                self._validation_cache[profile.device] = validation_errors
                log.warning(
                    f"Profile {profile.device} has validation issues: {validation_errors}"
                )

            self.add_profile(profile)
            return profile
        except Exception as e:
            log.error(f"Failed to load profile from {filepath}: {e}")
            raise

    def add_profile(self, profile: DeviceProfile) -> None:
        """Add a profile to the manager."""
        if not isinstance(profile, DeviceProfile):
            raise ValidationError(
                f"Expected DeviceProfile, got {type(profile)}",
                value=profile,
                constraint="profile must be instance of device profile",
            )

        if not profile.is_valid():
            errors = profile.validate()
            log.warning(f"Adding invalid profile {profile.device}: {errors}")

        self._profiles.get(profile.device)
        self._profiles[profile.device] = profile

        # Notify watchers
        for watcher in self._watchers:
            try:
                watcher(profile.device, profile)
            except Exception as e:
                log.error(f"Profile watcher failed: {e}")

        log.info(f"Added profile: {profile.device}")

    def get_profile(self, device: str) -> Optional[DeviceProfile]:
        """Get a profile by device name."""
        return self._profiles.get(device)

    def remove_profile(self, device: str) -> bool:
        """Remove a profile by device name."""
        if device in self._profiles:
            del self._profiles[device]
            log.info(f"Removed profile: {device}")
            return True
        return False

    def list_profiles(self) -> List[str]:
        """List all available profile names."""
        return list(self._profiles.keys())

    def get_all_profiles(self) -> Dict[str, DeviceProfile]:
        """Get all loaded profiles."""
        return self._profiles.copy()

    def find_profiles_by_tag(self, tag: str) -> List[DeviceProfile]:
        """Find profiles with a specific tag."""
        return [
            profile
            for profile in self._profiles.values()
            if tag in profile.tags
        ]

    def find_profiles_by_vendor(self, vendor: str) -> List[DeviceProfile]:
        """Find profiles by vendor."""
        return [
            profile
            for profile in self._profiles.values()
            if profile.vendor and profile.vendor.lower() == vendor.lower()
        ]

    def validate_all_profiles(
        self, strict: bool = False
    ) -> Dict[str, List[str]]:
        """Validate all loaded profiles."""
        results = {}
        for device, profile in self._profiles.items():
            errors = profile.validate(strict=strict)
            if errors:
                results[device] = errors
        return results

    def add_watcher(
        self, callback: Callable[[str, DeviceProfile], None]
    ) -> None:
        """Add a callback to be notified when profiles change."""
        self._watchers.append(callback)

    def remove_watcher(
        self, callback: Callable[[str, DeviceProfile], None]
    ) -> None:
        """Remove a profile change watcher."""
        if callback in self._watchers:
            self._watchers.remove(callback)

    def export_profiles(
        self,
        directory: Union[str, Path],
        format: SerializationFormat = SerializationFormat.YAML,
    ) -> None:
        """Export all profiles to a directory."""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)

        for device, profile in self._profiles.items():
            # Sanitize filename
            safe_name = "".join(
                c for c in device if c.isalnum() or c in ("-", "_")
            ).lower()
            filename = f"{safe_name}.{format.value}"
            filepath = directory / filename

            try:
                profile.save_to_file(filepath, format)
                log.info(f"Exported profile {device} to {filepath}")
            except Exception as e:
                log.error(f"Failed to export profile {device}: {e}")

    def get_load_stats(self) -> Dict[str, int]:
        """Changed here - Get profile loading statistics."""
        return self._load_stats.copy()

    def get_validation_issues(self) -> Dict[str, List[str]]:
        """Changed here - Get validation issues for all profiles."""
        return self._validation_cache.copy()

    def clear_cache(self) -> None:
        """Changed here - Clear all caches."""
        self._profile_cache.clear()
        self._validation_cache.clear()
        self._load_stats = {"successful": 0, "failed": 0, "cached": 0}
        log.info("Cleared all caches")

    def reload_profile(self, device: str) -> Optional[DeviceProfile]:
        """Changed here - Reload a specific profile, bypassing cache."""
        if device not in self._profiles:
            log.warning(f"Profile {device} not found")
            return None

        # Find the original file path
        profile = self._profiles[device]
        source_file = profile.custom_extensions.get("source_file")

        if not source_file:
            log.warning(f"No source file found for profile {device}")
            return None

        try:
            # Remove from cache and reload
            cache_key = str(Path(source_file).absolute())
            if cache_key in self._profile_cache:
                del self._profile_cache[cache_key]

            new_profile = from_file(source_file)
            self.add_profile(new_profile)
            log.info(f"Reloaded profile: {device}")
            return new_profile

        except Exception as e:
            log.error(f"Failed to reload profile {device}: {e}")
            return None


default_config_manager = ConfigManager()


# Legacy compatibility method
def load_profile(filepath: str) -> DeviceProfile:
    """Legacy function for loading profiles."""
    return default_config_manager.load_profile(filepath)


def validate_profile(profile_data: Dict[str, Any]) -> bool:
    """Legacy validation function."""
    try:
        profile = DeviceProfile.from_dict(profile_data)
        return profile.is_valid(strict=True)
    except ValidationError as e:
        # Re-raise ValidationError as ValueError for backward compatibility
        raise ValueError(str(e))
    except Exception as e:
        log.error(f"Profile validation failed: {e}")
        raise ValueError(f"Profile validation failed: {e}")


def load_profile_by_directory(directory: Union[str, Path]):
    try:
        default_config_manager.add_profile_directory(directory)
        log.info(f"Loaded directory: {directory}")
        loaded_profiles: List[str] = default_config_manager.discover_profiles()
        log.info(f"Profiles discovered are: {loaded_profiles}")
        return loaded_profiles
    except Exception as e:
        log.error(f"Failed to scan directory {directory}: {e}")


# Export main classes and functions
__all__ = [
    "default_config_manager",
    "load_profile",
    "validate_profile",
]
