from .. import BasePlugin

# Import the modern records plugin
from .modern_records import ASTMBaseRecord, ModernRecordsPlugin, RecordMetadata


class RecordPlugin(BasePlugin):
    """
    Base class for record plugins.
    """

    name = "RecordPlugin"

    def __init__(self, record_type, wrapper):
        self.record_type = record_type
        self.wrapper = wrapper
        super().__init__()

    def install(self, manager):
        """
        Installs the record plugin by adding its wrapper to the dispatcher.
        """
        super().install(manager)
        dispatcher = manager.server.dispatcher
        if not hasattr(dispatcher, "wrappers"):
            dispatcher.wrappers = {}
        dispatcher.wrappers[self.record_type] = self.wrapper


__all__ = [
    "RecordPlugin",
    "ModernRecordsPlugin",
    "ASTMBaseRecord",
    "RecordMetadata",
]
