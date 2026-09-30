import json
import logging
import threading
from collections import Counter, defaultdict
from datetime import UTC, datetime
from time import perf_counter


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        for field in ("correlation_id", "method", "path", "status_code", "duration_ms"):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        return json.dumps(payload, default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level.upper())


class MetricsRegistry:
    def __init__(self) -> None:
        self._request_counts: Counter[tuple[str, str, str]] = Counter()
        self._durations: dict[tuple[str, str, str], list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def record_request(self, method: str, path: str, status_code: int, duration_ms: float) -> None:
        labels = (method, path, str(status_code))
        with self._lock:
            self._request_counts[labels] += 1
            self._durations[labels].append(duration_ms)

    def render_prometheus(self) -> str:
        lines = [
            "# HELP ioh_http_requests_total Completed HTTP requests.",
            "# TYPE ioh_http_requests_total counter",
        ]
        with self._lock:
            for (method, path, status_code), count in sorted(self._request_counts.items()):
                lines.append(
                    f'ioh_http_requests_total{{method="{method}",path="{path}",status="{status_code}"}} {count}'
                )
            lines.extend(
                [
                    "# HELP ioh_http_request_duration_ms_sum Total request duration in milliseconds.",
                    "# TYPE ioh_http_request_duration_ms_sum counter",
                ]
            )
            for (method, path, status_code), durations in sorted(self._durations.items()):
                lines.append(
                    f'ioh_http_request_duration_ms_sum{{method="{method}",path="{path}",status="{status_code}"}} {sum(durations):.3f}'
                )
        return "\n".join(lines) + "\n"


metrics = MetricsRegistry()


def start_timer() -> float:
    return perf_counter()


def elapsed_milliseconds(start: float) -> float:
    return (perf_counter() - start) * 1_000
