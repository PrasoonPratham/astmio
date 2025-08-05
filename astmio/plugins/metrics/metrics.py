import time
from collections import defaultdict

from prometheus_client import Counter, Gauge, Histogram

from astmio.plugins import BasePlugin


class MetricsPlugin(BasePlugin):
    """
    A plugin to collect metrics.
    """

    name = "Metrics"

    def __init__(self):
        self.metrics = {
            "messages": {
                "total": 0,
                "per_second": 0,
                "types": defaultdict(int),
            },
            "connections": {
                "total": 0,
                "active": 0,
                "errors": 0,
            },
            "processing_time": {
                "last": 0,
                "average": 0,
            },
        }
        self._last_message_time = time.monotonic()
        self._processing_times = []
        super().__init__()

    def install(self, manager):
        super().install(manager)
        # In a real implementation, you would hook into the server's
        # event system to update these metrics.
        # For example:
        # manager.server.on("message_received", self.on_message_received)
        # manager.server.on("connection_opened", self.on_connection_opened)
        # manager.server.on("connection_closed", self.on_connection_closed)

    def on_message_received(self, message):
        self.metrics["messages"]["total"] += 1
        self.metrics["messages"]["types"][message[0]] += 1

        now = time.monotonic()
        time_delta = now - self._last_message_time
        if time_delta > 0:
            self.metrics["messages"]["per_second"] = 1 / time_delta
        self._last_message_time = now

    def on_connection_opened(self):
        self.metrics["connections"]["total"] += 1
        self.metrics["connections"]["active"] += 1

    def on_connection_closed(self, error=None):
        self.metrics["connections"]["active"] -= 1
        if error:
            self.metrics["connections"]["errors"] += 1

    def on_processing_start(self):
        self._processing_start_time = time.monotonic()

    def on_processing_end(self):
        processing_time = time.monotonic() - self._processing_start_time
        self.metrics["processing_time"]["last"] = processing_time
        self._processing_times.append(processing_time)
        self.metrics["processing_time"]["average"] = sum(
            self._processing_times
        ) / len(self._processing_times)

    def get_metrics(self):
        return self.metrics


class PrometheusMetricsPlugin(MetricsPlugin):
    """
    A metrics plugin that exposes data in Prometheus format.
    """

    name = "PrometheusMetrics"

    def __init__(self):
        super().__init__()
        self.messages_total = Counter(
            "astm_messages_total", "Total number of messages received"
        )
        self.message_types_total = Counter(
            "astm_message_types_total",
            "Total number of messages received by type",
            ["type"],
        )
        self.connections_total = Counter(
            "astm_connections_total", "Total number of connections"
        )
        self.connections_active = Gauge(
            "astm_connections_active", "Number of active connections"
        )
        self.connections_errors_total = Counter(
            "astm_connections_errors_total", "Total number of connection errors"
        )
        self.processing_time_seconds = Histogram(
            "astm_processing_time_seconds", "Time spent processing messages"
        )

    def on_message_received(self, message):
        super().on_message_received(message)
        self.messages_total.inc()
        self.message_types_total.labels(type=message[0]).inc()

    def on_connection_opened(self):
        super().on_connection_opened()
        self.connections_total.inc()
        self.connections_active.inc()

    def on_connection_closed(self, error=None):
        super().on_connection_closed(error)
        self.connections_active.dec()
        if error:
            self.connections_errors_total.inc()

    def on_processing_end(self):
        super().on_processing_end()
        self.processing_time_seconds.observe(
            self.metrics["processing_time"]["last"]
        )
