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
client = TestClient(app)


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
    assert found.json()["status"] == "pending"


def test_refund_is_rejected_until_payment_is_successful():
    response = client.post("/payments", json={"amount": "50.00", "currency": "USD", "provider": "AcmePay"})
    refund = client.post(f"/payments/{response.json()['id']}/refunds", json={"amount": "10.00"})
    assert refund.status_code == 409
    assert refund.json()["detail"] == "Only succeeded payments can be refunded."


def test_partial_refund_cannot_exceed_original_payment():
    response = client.post("/payments", json={"amount": "50.00", "currency": "USD", "provider": "AcmePay"})
    with TestingSession() as session:
        payment = session.get(Payment, uuid.UUID(response.json()["id"]))
        payment.status = PaymentStatus.SUCCEEDED
        session.commit()

    first_refund = client.post(f"/payments/{response.json()['id']}/refunds", json={"amount": "30.00"})
    too_large = client.post(f"/payments/{response.json()['id']}/refunds", json={"amount": "25.00"})
    assert first_refund.status_code == 201
    assert too_large.status_code == 409


def test_health_check_reports_service_is_available():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_payment_uses_a_generated_correlation_id_when_header_is_missing():
    response = client.post(
        "/payments",
        json={"amount": "1.00", "currency": "USD", "provider": "AcmePay"},
    )

    assert response.status_code == 201
    assert response.headers["X-Correlation-ID"] == response.json()["correlation_id"]
    assert uuid.UUID(response.json()["correlation_id"])


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

    assert invalid_payment.status_code == 422
    assert invalid_refund.status_code == 422
