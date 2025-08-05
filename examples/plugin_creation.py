from astmio.logging import get_logger
from astmio.plugins import BasePlugin
from astmio.plugins.registry import register_plugin

log = get_logger(__name__)


class CustomLoggerPlugin(BasePlugin):
    """
    Example custom plugin that logs all events to a file.
    """

    name = "custom_logger"
    version = "1.0.0"
    description = "Custom plugin that logs all events to a file"

    def __init__(self, log_file: str = "astm_events.log", **kwargs):
        super().__init__(**kwargs)
        self.log_file = log_file
        self.event_count = 0

    def install(self, manager):
        """Install the custom logger plugin."""
        super().install(manager)

        # Register for all events
        manager.on("record_processed", self.on_any_event)
        manager.on("connection_established", self.on_any_event)
        manager.on("connection_failed", self.on_any_event)

        log.info(f"Custom logger plugin installed, logging to: {self.log_file}")

    def on_any_event(self, *args, **kwargs):
        """Log any event to file."""
        self.event_count += 1

        with open(self.log_file, "a") as f:
            f.write(f"Event {self.event_count}: {args} {kwargs}\n")


register_plugin("custom_logger", CustomLoggerPlugin, "custom")
