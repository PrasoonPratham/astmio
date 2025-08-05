from datetime import datetime
from typing import Annotated, Any, Dict, Optional, Type, Union

from pydantic import BaseModel, Field, PrivateAttr, field_validator

from astmio.logging import get_logger
from astmio.models import RecordConfig, SerialConfig, TCPConfig, UDPConfig
from astmio.modern_records import ASTMBaseRecord
from astmio.record_factory import RecordFactory

try:
    import yaml
except ImportError:
    yaml = None
try:
    import toml
except ImportError:
    toml = None


log = get_logger(__name__)

TransportConfigUnion = Annotated[
    Union[TCPConfig, SerialConfig, UDPConfig], Field(discriminator="mode")
]


class DeviceProfile(BaseModel):
    """
    The root Pydantic model for parsing and validating an entire device
    profile YAML file. This is the single entry point for configuration loading.
    """

    device: str
    vendor: Optional[str] = None
    model: Optional[str] = None
    protocol: str = "ASTM E1394"
    encoding: str = "latin-1"
    version: Optional[str] = None
    description: Optional[str] = None

    transport: TransportConfigUnion
    records: Dict[str, RecordConfig] = {}
    _record_classes: Dict[str, Type[ASTMBaseRecord]] = PrivateAttr(
        default_factory=dict
    )

    quirks: Dict[str, Any] = {}
    custom_extensions: Dict[str, Any] = {}

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None

    @field_validator("records", mode="before")
    @classmethod
    def inject_record_type_from_key(
        cls, records_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Injects the record type (e.g., 'H') from the YAML dictionary key
        into the RecordConfig model's data before validation.
        """
        if not isinstance(records_data, dict):
            raise TypeError("The 'records' configuration must be a dictionary.")

        for record_type, record_config in records_data.items():
            if (
                isinstance(record_config, dict)
                and "record_type" not in record_config
            ):
                record_config["record_type"] = record_type

        return records_data

    @field_validator("quirks", mode="before")
    @classmethod
    def handle_none_for_quirks(cls, v: Any) -> Any:
        """If 'quirks' is None in the YAML, convert it to an empty dict."""
        if v is None:
            return {}
        return v

    def generate_record_models(self) -> None:
        """
        Orchestrates the creation of all dynamic Pydantic record models based
        on the validated configuration in `self.records`.

        This method iterates through the record configurations, calls the
        RecordFactory to build and cache each model, and stores the resulting
        class in the private `_record_classes` dictionary for runtime use.
        """
        if not self.records:
            log.warning(
                "No record configurations found in profile. No models will be generated."
            )
            return

        log.info(
            "Generating dynamic record models for device '%s'...", self.device
        )
        for record_type, record_config in self.records.items():
            try:
                # Use the factory to create (or get from cache) the dynamic class
                record_class = RecordFactory.create_record_class(
                    record_type, record_config
                )
                self._record_classes[record_type] = record_class
            except Exception as e:
                log.error(
                    "Failed to create record model for type '%s'. This record type will be unavailable. Error: %s",
                    record_type,
                    e,
                    exc_info=True,
                )

        log.info(
            f"Successfully generated {len(self._record_classes)} record models."
        )

    def get_record_class(
        self, record_type: str
    ) -> Optional[Type[ASTMBaseRecord]]:
        """
        Safely retrieves a dynamically generated record class for runtime parsing.

        Args:
            record_type: The record identifier (e.g., 'H', 'P').

        Returns:
            The generated Pydantic class, or None if no class exists for that type.
        """
        return self._record_classes.get(record_type.upper())
