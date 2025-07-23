#
# Comprehensive metrics and monitoring system for ASTM library
#
import logging
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Deque, Dict, List, Optional, Union

from .exceptions import ValidationError

log = logging.getLogger(__name__)


class MetricType(str, Enum):
    """Types of metrics that can be collected."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"
    RATE = "rate"


@dataclass
class MetricPoint:
    """A single metric data point."""

    timestamp: datetime
    value: Union[int, float]
    labels: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "value": self.value,
            "labels": self.labels,
        }


@dataclass
class MetricSummary:
    """Summary statistics for a metric."""

    name: str
    metric_type: MetricType
    count: int
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    avg_value: Optional[float] = None
    sum_value: Optional[float] = None
    last_value: Optional[float] = None
    last_updated: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "type": self.metric_type.value,
            "count": self.count,
            "min": self.min_value,
            "max": self.max_value,
            "avg": self.avg_value,
            "sum": self.sum_value,
            "last": self.last_value,
            "last_updated": (
                self.last_updated.isoformat() if self.last_updated else None
            ),
        }


class Metric:
    """Base metric class with common functionality."""

    def __init__(
        self,
        name: str,
        metric_type: MetricType,
        description: str = "",
        max_points: int = 1000,
        labels: Optional[Dict[str, str]] = None,
    ):
        self.name = name
        self.metric_type = metric_type
        self.description = description
        self.max_points = max_points
        self.default_labels = labels or {}
        self._points: Deque[MetricPoint] = deque(maxlen=max_points)
        self._lock = threading.RLock()

    def add_point(
        self, value: Union[int, float], labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Add a data point to the metric."""
        with self._lock:
            combined_labels = {**self.default_labels}
            if labels:
                combined_labels.update(labels)

            point = MetricPoint(
                timestamp=datetime.now(),
                value=float(value),
                labels=combined_labels,
            )
            self._points.append(point)

    def get_points(
        self,
        since: Optional[datetime] = None,
        labels: Optional[Dict[str, str]] = None,
    ) -> List[MetricPoint]:
        """Get metric points with optional filtering."""
        with self._lock:
            points = list(self._points)

        if since:
            points = [p for p in points if p.timestamp >= since]

        if labels:
            points = [
                p
                for p in points
                if all(p.labels.get(k) == v for k, v in labels.items())
            ]

        return points

    def get_summary(self, since: Optional[datetime] = None) -> MetricSummary:
        """Get summary statistics for the metric."""
        points = self.get_points(since=since)

        if not points:
            return MetricSummary(
                name=self.name, metric_type=self.metric_type, count=0
            )

        values = [p.value for p in points]
        return MetricSummary(
            name=self.name,
            metric_type=self.metric_type,
            count=len(values),
            min_value=min(values),
            max_value=max(values),
            avg_value=sum(values) / len(values),
            sum_value=sum(values),
            last_value=values[-1],
            last_updated=points[-1].timestamp,
        )

    def clear(self) -> None:
        """Clear all data points."""
        with self._lock:
            self._points.clear()


class Counter(Metric):
    """Counter metric that only increases."""

    def __init__(self, name: str, description: str = "", **kwargs):
        super().__init__(name, MetricType.COUNTER, description, **kwargs)
        self._value = 0.0

    def increment(
        self, amount: float = 1.0, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Increment the counter."""
        with self._lock:
            self._value += amount
            self.add_point(self._value, labels)

    def get_value(self) -> float:
        """Get current counter value."""
        return self._value

    def reset(self) -> None:
        """Reset counter to zero."""
        with self._lock:
            self._value = 0.0
            self.add_point(self._value)


class Gauge(Metric):
    """Gauge metric that can go up and down."""

    def __init__(self, name: str, description: str = "", **kwargs):
        super().__init__(name, MetricType.GAUGE, description, **kwargs)
        self._value = 0.0

    def set(
        self, value: float, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Set the gauge value."""
        with self._lock:
            self._value = value
            self.add_point(self._value, labels)

    def increment(
        self, amount: float = 1.0, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Increment the gauge."""
        with self._lock:
            self._value += amount
            self.add_point(self._value, labels)

    def decrement(
        self, amount: float = 1.0, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Decrement the gauge."""
        with self._lock:
            self._value -= amount
            self.add_point(self._value, labels)

    def get_value(self) -> float:
        """Get current gauge value."""
        return self._value


class Histogram(Metric):
    """Histogram metric for tracking distributions."""

    def __init__(
        self,
        name: str,
        description: str = "",
        buckets: Optional[List[float]] = None,
        **kwargs,
    ):
        super().__init__(name, MetricType.HISTOGRAM, description, **kwargs)
        self.buckets = buckets or [
            0.1,
            0.5,
            1.0,
            2.5,
            5.0,
            10.0,
            25.0,
            50.0,
            100.0,
        ]
        self._bucket_counts = defaultdict(int)
        self._sum = 0.0
        self._count = 0

    def observe(
        self, value: float, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Observe a value."""
        with self._lock:
            self._sum += value
            self._count += 1

            # Update bucket counts
            for bucket in self.buckets:
                if value <= bucket:
                    self._bucket_counts[bucket] += 1

            self.add_point(value, labels)

    def get_buckets(self) -> Dict[float, int]:
        """Get bucket counts."""
        return dict(self._bucket_counts)

    def get_percentile(self, percentile: float) -> Optional[float]:
        """Calculate percentile from histogram data."""
        points = self.get_points()
        if not points:
            return None

        values = sorted([p.value for p in points])
        index = int(len(values) * percentile / 100)
        return values[min(index, len(values) - 1)]


class Timer(Metric):
    """Timer metric for measuring durations."""

    def __init__(self, name: str, description: str = "", **kwargs):
        super().__init__(name, MetricType.TIMER, description, **kwargs)

    def time(self, labels: Optional[Dict[str, str]] = None):
        """Context manager for timing operations."""
        return TimerContext(self, labels)

    def record(
        self, duration: float, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a duration."""
        self.add_point(duration, labels)


class TimerContext:
    """Context manager for timing operations."""

    def __init__(self, timer: Timer, labels: Optional[Dict[str, str]] = None):
        self.timer = timer
        self.labels = labels
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            duration = time.time() - self.start_time
            self.timer.record(duration, self.labels)


class AsyncTimerContext:
    """Async context manager for timing operations."""

    def __init__(self, timer: Timer, labels: Optional[Dict[str, str]] = None):
        self.timer = timer
        self.labels = labels
        self.start_time = None

    async def __aenter__(self):
        self.start_time = time.time()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            duration = time.time() - self.start_time
            self.timer.record(duration, self.labels)


class MetricsCollector:
    """Central metrics collection and management."""

    def __init__(self):
        self._metrics: Dict[str, Metric] = {}
        self._lock = threading.RLock()
        self._enabled = True
        self._exporters: List[Callable[[Dict[str, Metric]], None]] = []

        # Built-in ASTM metrics
        self._init_astm_metrics()

    def _init_astm_metrics(self) -> None:
        """Initialize standard ASTM metrics."""
        # Message metrics
        self.register_counter(
            "astm_messages_sent_total", "Total ASTM messages sent"
        )
        self.register_counter(
            "astm_messages_received_total", "Total ASTM messages received"
        )
        self.register_counter(
            "astm_messages_failed_total", "Total ASTM message failures"
        )

        # Connection metrics
        self.register_gauge(
            "astm_active_connections", "Number of active ASTM connections"
        )
        self.register_counter(
            "astm_connections_total", "Total ASTM connections established"
        )
        self.register_counter(
            "astm_connection_errors_total", "Total ASTM connection errors"
        )

        # Performance metrics
        self.register_timer(
            "astm_message_processing_duration", "Time to process ASTM messages"
        )
        self.register_timer(
            "astm_connection_duration", "Duration of ASTM connections"
        )
        self.register_histogram(
            "astm_message_size_bytes", "Size of ASTM messages in bytes"
        )

        # Error metrics
        self.register_counter(
            "astm_checksum_errors_total", "Total checksum validation errors"
        )
        self.register_counter(
            "astm_timeout_errors_total", "Total timeout errors"
        )
        self.register_counter("astm_parse_errors_total", "Total parsing errors")

        # Record type metrics
        for record_type in ["H", "P", "O", "R", "C", "L"]:
            self.register_counter(
                f"astm_records_{record_type.lower()}_total",
                f"Total {record_type} records processed",
            )

    def register_counter(
        self,
        name: str,
        description: str = "",
        labels: Optional[Dict[str, str]] = None,
    ) -> Counter:
        """Register a new counter metric."""
        with self._lock:
            if name in self._metrics:
                metric = self._metrics[name]
                if not isinstance(metric, Counter):
                    raise ValidationError(
                        f"Metric {name} already exists with different type"
                    )
                return metric

            counter = Counter(name, description, labels=labels)
            self._metrics[name] = counter
            return counter

    def register_gauge(
        self,
        name: str,
        description: str = "",
        labels: Optional[Dict[str, str]] = None,
    ) -> Gauge:
        """Register a new gauge metric."""
        with self._lock:
            if name in self._metrics:
                metric = self._metrics[name]
                if not isinstance(metric, Gauge):
                    raise ValidationError(
                        f"Metric {name} already exists with different type"
                    )
                return metric

            gauge = Gauge(name, description, labels=labels)
            self._metrics[name] = gauge
            return gauge

    def register_histogram(
        self,
        name: str,
        description: str = "",
        buckets: Optional[List[float]] = None,
        labels: Optional[Dict[str, str]] = None,
    ) -> Histogram:
        """Register a new histogram metric."""
        with self._lock:
            if name in self._metrics:
                metric = self._metrics[name]
                if not isinstance(metric, Histogram):
                    raise ValidationError(
                        f"Metric {name} already exists with different type"
                    )
                return metric

            histogram = Histogram(
                name, description, buckets=buckets, labels=labels
            )
            self._metrics[name] = histogram
            return histogram

    def register_timer(
        self,
        name: str,
        description: str = "",
        labels: Optional[Dict[str, str]] = None,
    ) -> Timer:
        """Register a new timer metric."""
        with self._lock:
            if name in self._metrics:
                metric = self._metrics[name]
                if not isinstance(metric, Timer):
                    raise ValidationError(
                        f"Metric {name} already exists with different type"
                    )
                return metric

            timer = Timer(name, description, labels=labels)
            self._metrics[name] = timer
            return timer

    def get_metric(self, name: str) -> Optional[Metric]:
        """Get a metric by name."""
        return self._metrics.get(name)

    def get_all_metrics(self) -> Dict[str, Metric]:
        """Get all registered metrics."""
        with self._lock:
            return self._metrics.copy()

    def get_summaries(
        self, since: Optional[datetime] = None
    ) -> Dict[str, MetricSummary]:
        """Get summaries for all metrics."""
        summaries = {}
        for name, metric in self._metrics.items():
            summaries[name] = metric.get_summary(since=since)
        return summaries

    def clear_all(self) -> None:
        """Clear all metric data."""
        with self._lock:
            for metric in self._metrics.values():
                metric.clear()

    def enable(self) -> None:
        """Enable metrics collection."""
        self._enabled = True

    def disable(self) -> None:
        """Disable metrics collection."""
        self._enabled = False

    def is_enabled(self) -> bool:
        """Check if metrics collection is enabled."""
        return self._enabled

    def add_exporter(
        self, exporter: Callable[[Dict[str, Metric]], None]
    ) -> None:
        """Add a metrics exporter."""
        self._exporters.append(exporter)

    def remove_exporter(
        self, exporter: Callable[[Dict[str, Metric]], None]
    ) -> None:
        """Remove a metrics exporter."""
        if exporter in self._exporters:
            self._exporters.remove(exporter)

    def export_metrics(self) -> None:
        """Export metrics to all registered exporters."""
        if not self._enabled:
            return

        metrics = self.get_all_metrics()
        for exporter in self._exporters:
            try:
                exporter(metrics)
            except Exception as e:
                log.error(f"Metrics exporter failed: {e}")

    # Convenience methods for common operations
    def increment_counter(
        self,
        name: str,
        amount: float = 1.0,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Increment a counter metric."""
        if not self._enabled:
            return

        metric = self.get_metric(name)
        if isinstance(metric, Counter):
            metric.increment(amount, labels)

    def set_gauge(
        self, name: str, value: float, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Set a gauge metric value."""
        if not self._enabled:
            return

        metric = self.get_metric(name)
        if isinstance(metric, Gauge):
            metric.set(value, labels)

    def observe_histogram(
        self, name: str, value: float, labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Observe a value in a histogram."""
        if not self._enabled:
            return

        metric = self.get_metric(name)
        if isinstance(metric, Histogram):
            metric.observe(value, labels)

    def time_operation(
        self, name: str, labels: Optional[Dict[str, str]] = None
    ):
        """Time an operation with a timer metric."""
        if not self._enabled:
            return NullTimerContext()

        metric = self.get_metric(name)
        if isinstance(metric, Timer):
            return metric.time(labels)
        return NullTimerContext()

    def async_time_operation(
        self, name: str, labels: Optional[Dict[str, str]] = None
    ):
        """Async time an operation with a timer metric."""
        if not self._enabled:
            return NullAsyncTimerContext()

        metric = self.get_metric(name)
        if isinstance(metric, Timer):
            return AsyncTimerContext(metric, labels)
        return NullAsyncTimerContext()


class NullTimerContext:
    """Null timer context for when metrics are disabled."""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class NullAsyncTimerContext:
    """Null async timer context for when metrics are disabled."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


# Metrics exporters
def prometheus_exporter(metrics: Dict[str, Metric]) -> str:
    """Export metrics in Prometheus format."""
    lines = []

    for name, metric in metrics.items():
        # Add help text
        if metric.description:
            lines.append(f"# HELP {name} {metric.description}")

        # Add type
        prom_type = {
            MetricType.COUNTER: "counter",
            MetricType.GAUGE: "gauge",
            MetricType.HISTOGRAM: "histogram",
            MetricType.TIMER: "histogram",
        }.get(metric.metric_type, "gauge")
        lines.append(f"# TYPE {name} {prom_type}")

        # Add data points
        if isinstance(metric, (Counter, Gauge)):
            value = metric.get_value()
            lines.append(f"{name} {value}")
        elif isinstance(metric, Histogram):
            summary = metric.get_summary()
            if summary.count > 0:
                lines.append(f"{name}_sum {summary.sum_value}")
                lines.append(f"{name}_count {summary.count}")

                # Add buckets
                buckets = metric.get_buckets()
                for bucket, count in sorted(buckets.items()):
                    lines.append(f'{name}_bucket{{le="{bucket}"}} {count}')
                lines.append(f'{name}_bucket{{le="+Inf"}} {summary.count}')
        elif isinstance(metric, Timer):
            points = metric.get_points()
            if points:
                durations = [p.value for p in points]
                lines.append(f"{name}_sum {sum(durations)}")
                lines.append(f"{name}_count {len(durations)}")

    return "\n".join(lines)


def json_exporter(metrics: Dict[str, Metric]) -> str:
    """Export metrics in JSON format."""
    import json

    data = {}
    for name, metric in metrics.items():
        summary = metric.get_summary()
        data[name] = summary.to_dict()

    return json.dumps(data, indent=2)


# Global metrics collector instance
default_metrics = MetricsCollector()


# Decorators for automatic metrics collection
def count_calls(metric_name: str, labels: Optional[Dict[str, str]] = None):
    """Decorator to count function calls."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            default_metrics.increment_counter(metric_name, labels=labels)
            return func(*args, **kwargs)

        return wrapper

    return decorator


def time_calls(metric_name: str, labels: Optional[Dict[str, str]] = None):
    """Decorator to time function calls."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            with default_metrics.time_operation(metric_name, labels=labels):
                return func(*args, **kwargs)

        return wrapper

    return decorator


def async_time_calls(metric_name: str, labels: Optional[Dict[str, str]] = None):
    """Decorator to time async function calls."""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            async with default_metrics.async_time_operation(
                metric_name, labels=labels
            ):
                return await func(*args, **kwargs)

        return wrapper

    return decorator


# Export main classes and functions
__all__ = [
    "MetricsCollector",
    "Counter",
    "Gauge",
    "Histogram",
    "Timer",
    "MetricPoint",
    "MetricSummary",
    "MetricType",
    "prometheus_exporter",
    "json_exporter",
    "default_metrics",
    "count_calls",
    "time_calls",
    "async_time_calls",
]
