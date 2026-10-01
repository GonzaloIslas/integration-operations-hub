from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import PaymentStatus, RetryJobStatus
from app.schemas import PaymentCreate, RetryCreate
from app.services import create_payment, create_retry_job, get_payment, process_retry_job


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with session_factory() as database_session:
        yield database_session
    Base.metadata.drop_all(engine)


def _failed_broken_payment(session: Session):
    payment, _ = create_payment(
        session,
        PaymentCreate(
            amount=Decimal("50.00"),
            currency="USD",
            provider="BrokenPay",
            simulation_case="http_500",
        ),
        "retry-job-correlation-id",
        "retry-job-idempotency-key",
    )
    return payment


def test_retry_job_uses_exponential_backoff_then_dead_letters(session: Session):
    payment = _failed_broken_payment(session)
    job, replayed = create_retry_job(session, payment.id, RetryCreate())

    assert replayed is False
    first_attempt = process_retry_job(session, job.id)
    first_status, first_attempt_count = first_attempt.status, first_attempt.attempts
    second_attempt = process_retry_job(session, job.id)
    second_status, second_attempt_count = second_attempt.status, second_attempt.attempts
    third_attempt = process_retry_job(session, job.id)

    assert first_status == RetryJobStatus.RETRY_SCHEDULED
    assert first_attempt_count == 1
    assert second_status == RetryJobStatus.RETRY_SCHEDULED
    assert second_attempt_count == 2
    assert third_attempt.status == RetryJobStatus.DEAD_LETTER
    assert third_attempt.attempts == 3
    assert third_attempt.last_error == "The provider returned an internal server error."


def test_retry_job_can_complete_with_an_operator_selected_recovery_case(session: Session):
    payment = _failed_broken_payment(session)
    job, _ = create_retry_job(session, payment.id, RetryCreate(simulation_case="normal"))

    completed_job = process_retry_job(session, job.id)

    assert completed_job.status == RetryJobStatus.COMPLETED
    assert get_payment(session, payment.id).status == PaymentStatus.SUCCEEDED


def test_active_retry_job_is_idempotent_for_the_same_payment(session: Session):
    payment = _failed_broken_payment(session)
    job, replayed = create_retry_job(session, payment.id, RetryCreate())
    duplicate_job, duplicate_replayed = create_retry_job(session, payment.id, RetryCreate())

    assert replayed is False
    assert duplicate_replayed is True
    assert duplicate_job.id == job.id
