import base64
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.main import app, database_session
from app.models import Payment, PaymentStatus

test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)


def override_session():
    with TestingSession() as session:
        yield session


app.dependency_overrides[database_session] = override_session
operator_token = base64.b64encode(b"operator:local-development-only").decode()
client = TestClient(app, headers={"Authorization": f"Basic {operator_token}"})


def setup_function():
    Base.metadata.drop_all(test_engine)
    Base.metadata.create_all(test_engine)


def test_create_and_read_payment_preserves_correlation_id():
    created = client.post(
        "/payments",
        headers={"X-Correlation-ID": "payment-42"},
        json={"amount": "150.00", "currency": "ARS", "provider": "AcmePay"},
    )

    assert created.status_code == 201
    assert created.headers["X-Correlation-ID"] == "payment-42"
    payment_id = created.json()["id"]
    found = client.get(f"/payments/{payment_id}")
    assert found.status_code == 200
    assert found.json()["correlation_id"] == "payment-42"
    assert found.json()["status"] == "succeeded"


def test_payment_list_and_operations_expose_operator_context():
    created = client.post(
        "/payments",
        headers={"X-Correlation-ID": "operator-context-42"},
        json={"amount": "150.00", "currency": "ARS", "provider": "AcmePay"},
    )

    payments = client.get("/payments")
    operations = client.get(f"/payments/{created.json()['id']}/operations")

    assert payments.status_code == 200
    assert [payment["id"] for payment in payments.json()] == [created.json()["id"]]
    assert operations.status_code == 200
    assert operations.json()[0]["event_type"] == "payment.created"
    assert '"correlation_id": "operator-context-42"' in operations.json()[0]["detail"]
    assert operations.json()[1]["event_type"] == "payment.provider_succeeded"


def test_integrations_are_listed_and_can_be_retrieved():
    integrations = client.get("/integrations")
    integration = client.get("/integrations/acmepay")
    missing_integration = client.get("/integrations/unknown")

    assert integrations.status_code == 200
    assert [item["name"] for item in integrations.json()] == [
        "acmepay",
        "bancox",
        "walletpro",
        "slowpay",
        "brokenpay",
    ]
    assert integration.json()["display_name"] == "AcmePay"
    assert missing_integration.status_code == 404


def test_refund_is_rejected_for_a_failed_payment():
    response = client.post("/payments", json={"amount": "50.00", "currency": "USD", "provider": "WalletPro"})
    refund = client.post(f"/payments/{response.json()['id']}/refunds", json={"amount": "10.00"})
    assert refund.status_code == 409
    assert refund.json()["detail"] == "Only succeeded payments can be refunded."


def test_partial_refund_cannot_exceed_original_payment():
    response = client.post("/payments", json={"amount": "50.00", "currency": "USD", "provider": "AcmePay"})
    first_refund = client.post(f"/payments/{response.json()['id']}/refunds", json={"amount": "30.00"})
    too_large = client.post(f"/payments/{response.json()['id']}/refunds", json={"amount": "25.00"})
    assert first_refund.status_code == 201
    assert too_large.status_code == 409


def test_successful_payment_can_be_fully_refunded():
    payment = client.post(
        "/payments", json={"amount": "50.00", "currency": "USD", "provider": "AcmePay"}
    )

    refund = client.post(f"/payments/{payment.json()['id']}/refunds", json={"amount": "50.00"})

    assert refund.status_code == 201
    assert refund.json()["status"] == "refunded"
    assert refund.json()["refunds"] == [
        {**refund.json()["refunds"][0], "amount": "50.00", "status": "succeeded"}
    ]


def test_health_check_reports_service_is_available():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_frontend_origin_is_allowed_to_read_the_api():
    response = client.options(
        "/payments",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_operator_api_requires_basic_authentication():
    response = TestClient(app).get("/payments")

    assert response.status_code == 401


def test_payment_uses_a_generated_correlation_id_when_header_is_missing():
    response = client.post(
        "/payments",
        json={"amount": "1.00", "currency": "USD", "provider": "AcmePay"},
    )

    assert response.status_code == 201
    assert response.headers["X-Correlation-ID"] == response.json()["correlation_id"]
    assert uuid.UUID(response.json()["correlation_id"])


def test_payment_creation_is_idempotent_for_the_same_request():
    payload = {"amount": "20.00", "currency": "USD", "provider": "AcmePay"}
    headers = {"Idempotency-Key": "payment-create-42"}

    created = client.post("/payments", headers=headers, json=payload)
    replayed = client.post("/payments", headers=headers, json=payload)
    operations = client.get(f"/payments/{created.json()['id']}/operations")

    assert created.status_code == 201
    assert replayed.status_code == 200
    assert replayed.headers["Idempotency-Replayed"] == "true"
    assert replayed.json()["id"] == created.json()["id"]
    assert [operation["event_type"] for operation in operations.json()] == [
        "payment.created",
        "payment.provider_succeeded",
    ]


def test_idempotency_key_cannot_be_reused_for_a_different_request():
    headers = {"Idempotency-Key": "payment-create-conflict"}
    client.post("/payments", headers=headers, json={"amount": "20.00", "currency": "USD", "provider": "AcmePay"})

    conflict = client.post(
        "/payments",
        headers=headers,
        json={"amount": "21.00", "currency": "USD", "provider": "AcmePay"},
    )

    assert conflict.status_code == 409
    assert conflict.json()["detail"] == "Idempotency key was already used with a different payment request."


def test_payment_list_supports_offset_pagination():
    for amount in ("10.00", "20.00", "30.00"):
        client.post("/payments", json={"amount": amount, "currency": "USD", "provider": "AcmePay"})

    first_page = client.get("/payments?limit=2&offset=0")
    second_page = client.get("/payments?limit=2&offset=2")

    assert len(first_page.json()) == 2
    assert first_page.headers["X-Total-Count"] == "3"
    assert first_page.headers["X-Next-Offset"] == "2"
    assert len(second_page.json()) == 1
    assert "X-Next-Offset" not in second_page.headers


def test_integration_api_key_authenticates_a_service_client():
    response = TestClient(app, headers={"X-API-Key": "local-integration-api-key"}).get("/integrations")

    assert response.status_code == 200
    assert response.headers["X-RateLimit-Remaining"]


def test_manual_retry_can_recover_a_retryable_provider_failure():
    created = client.post(
        "/payments",
        json={"amount": "25.00", "currency": "USD", "provider": "BrokenPay"},
    )

    retried = client.post(f"/payments/{created.json()['id']}/retry", json={"simulation_case": "normal"})

    assert created.json()["failure_code"] == "provider_unavailable"
    assert retried.status_code == 200
    assert retried.json()["status"] == "succeeded"


def test_webhook_is_authenticated_idempotent_and_updates_payment_status():
    payment = client.post(
        "/payments",
        json={"amount": "25.00", "currency": "USD", "provider": "BrokenPay"},
    )
    webhook_client = TestClient(app, headers={"X-API-Key": "local-integration-api-key"})
    payload = {
        "event_id": "brokenpay-event-42",
        "payment_id": payment.json()["id"],
        "event_type": "payment.succeeded",
        "provider_reference": "brokenpay-reconciled-42",
        "payload": {"source": "provider"},
    }

    delivered = webhook_client.post("/webhooks/brokenpay", json=payload)
    replayed = webhook_client.post("/webhooks/brokenpay", json=payload)

    assert delivered.status_code == 200
    assert delivered.json()["status"] == "succeeded"
    assert delivered.json()["provider_reference"] == "brokenpay-reconciled-42"
    assert replayed.headers["Idempotency-Replayed"] == "true"


def test_unknown_payment_and_refund_requests_return_not_found():
    payment_id = uuid.uuid4()

    payment = client.get(f"/payments/{payment_id}")
    refund = client.post(f"/payments/{payment_id}/refunds", json={"amount": "10.00"})

    assert payment.status_code == 404
    assert payment.json() == {"detail": "Payment not found."}
    assert refund.status_code == 404
    assert refund.json() == {"detail": "Payment not found."}


def test_payment_and_refund_payloads_are_validated():
    invalid_payment = client.post(
        "/payments",
        json={"amount": "0", "currency": "usd", "provider": ""},
    )
    payment = client.post(
        "/payments",
        json={"amount": "10.00", "currency": "USD", "provider": "AcmePay"},
    )
    invalid_refund = client.post(f"/payments/{payment.json()['id']}/refunds", json={"amount": "0"})
    invalid_simulation_case = client.post(
        "/payments",
        json={
            "amount": "10.00",
            "currency": "USD",
            "provider": "AcmePay",
            "simulation_case": "not-a-scenario",
        },
    )

    assert invalid_payment.status_code == 422
    assert invalid_refund.status_code == 422
    assert invalid_simulation_case.status_code == 422


def test_provider_authentication_failure_is_normalized_in_the_payment_response():
    response = client.post(
        "/payments",
        json={"amount": "10.00", "currency": "USD", "provider": "WalletPro"},
    )

    assert response.status_code == 201
    assert response.json()["status"] == "failed"
    assert response.json()["failure_code"] == "provider_authentication_failed"
    assert response.json()["failure_message"] == "The provider rejected the integration credentials."
    assert response.json()["retryable"] is False


def test_provider_timeout_is_normalized_as_retryable():
    response = client.post(
        "/payments",
        json={
            "amount": "10.00",
            "currency": "USD",
            "provider": "SlowPay",
            "simulation_case": "timeout",
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == "failed"
    assert response.json()["failure_code"] == "provider_timeout"
    assert response.json()["retryable"] is True


def test_rate_limited_provider_response_is_normalized():
    response = client.post(
        "/payments",
        json={
            "amount": "10.00",
            "currency": "USD",
            "provider": "BrokenPay",
            "simulation_case": "rate_limited",
        },
    )

    assert response.json()["failure_code"] == "provider_rate_limited"
    assert response.json()["retryable"] is True
