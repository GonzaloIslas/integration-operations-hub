import base64
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.main import app, database_session


def test_operator_workflow_covers_idempotency_retry_webhook_and_metrics():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)

    def override_session():
        with session_factory() as session:
            yield session

    previous_override = app.dependency_overrides.get(database_session)
    app.dependency_overrides[database_session] = override_session
    operator_token = base64.b64encode(b"operator:local-development-only").decode()
    operator_headers = {"Authorization": f"Basic {operator_token}", "Idempotency-Key": "system-workflow-42"}
    provider_headers = {"X-API-Key": "local-integration-api-key"}

    try:
        client = TestClient(app)
        created = client.post(
            "/payments",
            headers=operator_headers,
            json={"amount": "15.00", "currency": "USD", "provider": "BrokenPay"},
        )
        replayed = client.post(
            "/payments",
            headers=operator_headers,
            json={"amount": "15.00", "currency": "USD", "provider": "BrokenPay"},
        )
        retried = client.post(
            f"/payments/{created.json()['id']}/retry",
            headers={"Authorization": f"Basic {operator_token}"},
            json={"simulation_case": "normal"},
        )
        webhook = client.post(
            "/webhooks/brokenpay",
            headers=provider_headers,
            json={
                "event_id": str(uuid.uuid4()),
                "payment_id": created.json()["id"],
                "event_type": "payment.succeeded",
                "payload": {"system": "test"},
            },
        )
        operations = client.get(
            f"/payments/{created.json()['id']}/operations",
            headers={"Authorization": f"Basic {operator_token}"},
        )
        metrics = client.get("/metrics")

        assert created.status_code == 201
        assert replayed.headers["Idempotency-Replayed"] == "true"
        assert retried.status_code == 202
        assert retried.json()["status"] == "queued"
        assert webhook.json()["status"] == "succeeded"
        assert any("system-workflow-42" in operation["detail"] for operation in operations.json())
        assert "ioh_http_requests_total" in metrics.text
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(database_session, None)
        else:
            app.dependency_overrides[database_session] = previous_override
        Base.metadata.drop_all(engine)
