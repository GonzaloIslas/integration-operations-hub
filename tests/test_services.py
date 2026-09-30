from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import OperationLog, PaymentStatus
from app.schemas import PaymentCreate, RefundCreate
from app.services import InvalidRefundError, create_payment, create_refund, get_payment


@pytest.fixture
def session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with session_factory() as database_session:
        yield database_session
    Base.metadata.drop_all(engine)


def _create_payment(session: Session):
    return create_payment(
        session,
        PaymentCreate(amount=Decimal("50.00"), currency="USD", provider="AcmePay"),
        "service-test-correlation-id",
    )


def test_create_payment_persists_payment_and_lifecycle_log(session: Session):
    payment = _create_payment(session)

    stored = get_payment(session, payment.id)
    events = session.scalars(select(OperationLog.event_type).where(OperationLog.payment_id == payment.id)).all()

    assert stored.amount == Decimal("50.00")
    assert stored.status == PaymentStatus.SUCCEEDED
    assert events == ["payment.created", "payment.provider_succeeded"]


def test_successful_refund_is_persisted_and_logged(session: Session):
    payment = _create_payment(session)
    refunded_payment = create_refund(session, payment.id, RefundCreate(amount=Decimal("50.00")))
    events = session.scalars(select(OperationLog.event_type).where(OperationLog.payment_id == payment.id)).all()

    assert [(refund.amount, str(refund.status)) for refund in refunded_payment.refunds] == [
        (Decimal("50.00"), "succeeded")
    ]
    assert refunded_payment.status == PaymentStatus.REFUNDED
    assert events == ["payment.created", "payment.provider_succeeded", "refund.provider_succeeded"]


def test_failed_refunds_do_not_reduce_the_remaining_refundable_balance(session: Session):
    payment = _create_payment(session)
    create_refund(session, payment.id, RefundCreate(amount=Decimal("50.00")))
    refund = get_payment(session, payment.id).refunds[0]
    refund.status = "failed"
    session.commit()

    result = create_refund(session, payment.id, RefundCreate(amount=Decimal("50.00")))

    assert len(result.refunds) == 2


def test_refund_cannot_exceed_payment_when_existing_refund_is_pending(session: Session):
    payment = _create_payment(session)
    create_refund(session, payment.id, RefundCreate(amount=Decimal("40.00")))

    with pytest.raises(InvalidRefundError, match="remaining refundable balance"):
        create_refund(session, payment.id, RefundCreate(amount=Decimal("10.01")))


def test_provider_failure_is_persisted_as_a_normalized_operation_log(session: Session):
    payment = create_payment(
        session,
        PaymentCreate(
            amount=Decimal("50.00"),
            currency="USD",
            provider="SlowPay",
            simulation_case="timeout",
        ),
        "provider-failure-correlation-id",
    )
    failure_log = session.scalar(
        select(OperationLog).where(
            OperationLog.payment_id == payment.id, OperationLog.event_type == "payment.provider_failed"
        )
    )

    assert payment.status == PaymentStatus.FAILED
    assert payment.failure_code == "provider_timeout"
    assert payment.retryable is True
    assert failure_log is not None
    assert '"retryable": true' in failure_log.detail


def test_provider_log_preserves_sanitized_protocol_context(session: Session):
    payment = create_payment(
        session,
        PaymentCreate(
            amount=Decimal("50.00"),
            currency="USD",
            provider="BrokenPay",
            simulation_case="rate_limited",
        ),
        "rate-limit-correlation-id",
    )
    failure_log = session.scalar(
        select(OperationLog).where(
            OperationLog.payment_id == payment.id, OperationLog.event_type == "payment.provider_failed"
        )
    )

    assert payment.failure_code == "provider_rate_limited"
    assert failure_log is not None
    assert '"http_status": 429' in failure_log.detail
    assert '"raw_response": "{\\"error\\":\\"rate_limit_exceeded\\"}"' in failure_log.detail
