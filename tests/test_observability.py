import json
import logging

from fastapi.testclient import TestClient

from app.main import app
from app.observability import JsonFormatter, MetricsRegistry


def test_json_formatter_includes_request_context():
    record = logging.LogRecord("app.main", logging.INFO, "", 0, "http.request_completed", (), None)
    record.correlation_id = "correlation-42"
    record.method = "POST"
    record.path = "/payments"
    record.status_code = 201
    record.duration_ms = 12.5

    rendered = json.loads(JsonFormatter().format(record))

    assert rendered["event"] == "http.request_completed"
    assert rendered["correlation_id"] == "correlation-42"
    assert rendered["status_code"] == 201


def test_metrics_registry_renders_prometheus_text():
    registry = MetricsRegistry()
    registry.record_request("GET", "/health", 200, 3.5)

    rendered = registry.render_prometheus()

    assert 'ioh_http_requests_total{method="GET",path="/health",status="200"} 1' in rendered
    assert 'ioh_http_request_duration_ms_sum{method="GET",path="/health",status="200"} 3.500' in rendered


def test_operational_endpoints_expose_readiness_metrics_and_correlation():
    client = TestClient(app)

    health = client.get("/health")
    readiness = client.get("/ready")
    metrics = client.get("/metrics")

    assert health.headers["X-Correlation-ID"]
    assert readiness.json() == {"status": "ready", "database": "ok"}
    assert "ioh_http_requests_total" in metrics.text
