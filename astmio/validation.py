from typing import Any, Dict, Union

from astmio.exceptions import ConfigurationError, ValidationError

from .logging import get_logger

# Assume these are imported from your project structure
from .models import FrameConfig, SerialConfig, TCPConfig, UDPConfig
from .record_factory import create_transport_config

log = get_logger(__name__)


def validate_transport_configuration(
    data: Dict[str, Any],
) -> Union[TCPConfig, SerialConfig, UDPConfig]:
    """
    Extracts and validates the transport configuration from a main config dictionary.
    This is the public-facing function you should call.
    """
    if "transport" not in data:
        raise ConfigurationError(
            message="The required 'transport' key is missing in the configuration.",
            config_key="transport",
        )

    transport_data = data["transport"]
    if not isinstance(transport_data, dict):
        raise TypeError("The 'transport' configuration must be a dictionary.")

    try:
        transport_config = create_transport_config(transport_data)
        return transport_config
    except (ConfigurationError, ValidationError, ValueError) as e:
        log.error("Failed to validate transport configuration: %s", e)
        raise


def validate_device_info(data: Dict[str, Any]) -> str:
    device_name = data.get("device")
    if not device_name:
        log.error("Device not found")

        raise ConfigurationError(
            message="Device name is required in the profile.",
            config_key="device",
        )
    return device_name


def validate_frame_configuration(frame_data: Dict[str, Any]) -> FrameConfig:
    """
    Validates the optional 'frame' configuration.

    - If the data is valid, it returns a FrameConfig instance based on it.
    - If the data is invalid (or missing), it logs a warning and returns a
      default Frame-Config instance.

    This function will not raise an exception.
    """
    try:
        return FrameConfig.model_validate(frame_data)
    except (ValidationError, ConfigurationError) as e:
        log.warning(
            "Invalid 'frame' configuration detected. Details: %s. "
            "Falling back to default frame settings.",
            e,
        )
        return FrameConfig()
