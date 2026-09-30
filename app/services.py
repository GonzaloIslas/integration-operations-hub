import json
import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.models import OperationLog, Payment, PaymentStatus, Refund, RefundStatus, WebhookEvent
from app.providers import NormalizedProviderError, ProviderChargeRequest, SimulationCase, get_payment_provider
from app.schemas import PaymentCreate, RefundCreate, RetryCreate, WebhookEventCreate


class PaymentNotFoundError(Exception):
    pass


class InvalidRefundError(Exception):
    pass


class IdempotencyConflictError(Exception):
    pass


class InvalidRetryError(Exception):
    pass


class InvalidWebhookError(Exception):
    pass


def create_payment(
    session: Session,
    request: PaymentCreate,
    correlation_id: str,
    idempotency_key: str,
) -> tuple[Payment, bool]:
    existing_payment = session.scalar(select(Payment).where(Payment.idempotency_key == idempotency_key))
    if existing_payment is not None:
        if not _matches_idempotent_request(existing_payment, request):
            raise IdempotencyConflictError("Idempotency key was already used with a different payment request.")
        return get_payment(session, existing_payment.id), True

    payment = Payment(
        **request.model_dump(exclude={"simulation_case"}),
        correlation_id=correlation_id,
        idempotency_key=idempotency_key,
        simulation_case=_simulation_case_value(request.simulation_case),
    )
    session.add(payment)
    session.flush()
    session.add(
        OperationLog(
            payment_id=payment.id,
            event_type="payment.created",
            detail=json.dumps(
                {
                    "amount": str(request.amount),
                    "currency": request.currency,
                    "provider": request.provider,
                    "correlation_id": correlation_id,
                    "idempotency_key": idempotency_key,
                    "simulation_case": request.simulation_case,
                }
            ),
        )
    )
    _apply_provider_outcome(
        session,
        payment,
        correlation_id=correlation_id,
        simulation_case=request.simulation_case,
        success_event="payment.provider_succeeded",
        failure_event="payment.provider_failed",
    )
    session.commit()
    session.refresh(payment)
    return payment, False


def get_payment(session: Session, payment_id: uuid.UUID) -> Payment:
    statement = select(Payment).options(selectinload(Payment.refunds)).where(Payment.id == payment_id)
    payment = session.scalar(statement)
    if payment is None:
        raise PaymentNotFoundError
    return payment


def list_payments(session: Session, limit: int, offset: int) -> tuple[list[Payment], int]:
    total = session.scalar(select(func.count()).select_from(Payment)) or 0
    statement = (
        select(Payment)
        .options(selectinload(Payment.refunds))
        .order_by(Payment.created_at.desc(), Payment.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(session.scalars(statement)), total


def get_payment_operations(session: Session, payment_id: uuid.UUID) -> list[OperationLog]:
    get_payment(session, payment_id)
    statement = select(OperationLog).where(OperationLog.payment_id == payment_id).order_by(OperationLog.created_at.asc())
    return list(session.scalars(statement))


def retry_payment(session: Session, payment_id: uuid.UUID, request: RetryCreate) -> Payment:
    payment = get_payment(session, payment_id)
    if payment.status != PaymentStatus.FAILED or not payment.retryable:
        raise InvalidRetryError("Only retryable failed payments can be retried.")
    payment.simulation_case = request.simulation_case.value
    session.add(
        OperationLog(
            payment_id=payment.id,
            event_type="payment.retry_requested",
            detail=json.dumps({"simulation_case": request.simulation_case}),
        )
    )
    _apply_provider_outcome(
        session,
        payment,
        correlation_id=payment.correlation_id,
        simulation_case=request.simulation_case,
        success_event="payment.retry_succeeded",
        failure_event="payment.retry_failed",
    )
    session.commit()
    session.expire(payment, ["refunds"])
    return get_payment(session, payment_id)


def process_webhook(session: Session, provider: str, event: WebhookEventCreate) -> tuple[Payment, bool]:
    existing_event = session.scalar(
        select(WebhookEvent).where(WebhookEvent.provider == provider.lower(), WebhookEvent.event_id == event.event_id)
    )
    if existing_event is not None:
        return get_payment(session, existing_event.payment_id), True

    payment = get_payment(session, event.payment_id)
    if payment.provider.lower() != provider.lower():
        raise InvalidWebhookError("Webhook provider does not match the payment provider.")

    if event.event_type == "payment.succeeded":
        payment.status = PaymentStatus.SUCCEEDED
        payment.provider_reference = event.provider_reference or payment.provider_reference
        payment.failure_code = None
        payment.failure_message = None
        payment.retryable = None
    else:
        payment.status = PaymentStatus.FAILED
        payment.failure_code = "provider_webhook_failed"
        payment.failure_message = "The provider reported a failed payment through a webhook."
        payment.retryable = False

    session.add(
        WebhookEvent(
            provider=provider.lower(),
            event_id=event.event_id,
            payment_id=payment.id,
            event_type=event.event_type,
            payload=json.dumps(event.payload),
        )
    )
    session.add(
        OperationLog(
            payment_id=payment.id,
            event_type="payment.webhook_received",
            detail=json.dumps(
                {
                    "provider": provider.lower(),
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "correlation_id": payment.correlation_id,
                }
            ),
        )
    )
    session.commit()
    session.expire(payment, ["refunds"])
    return get_payment(session, payment.id), False


def create_refund(session: Session, payment_id: uuid.UUID, request: RefundCreate) -> Payment:
    payment = get_payment(session, payment_id)
    if payment.status not in {PaymentStatus.SUCCEEDED, PaymentStatus.REFUNDED}:
        raise InvalidRefundError("Only succeeded payments can be refunded.")

    refunded_amount = session.scalar(
        select(func.coalesce(func.sum(Refund.amount), 0)).where(
            Refund.payment_id == payment_id, Refund.status != RefundStatus.FAILED
        )
    )
    if Decimal(refunded_amount) + request.amount > payment.amount:
        raise InvalidRefundError("Refund amount exceeds the remaining refundable balance.")

    refund = Refund(payment_id=payment.id, amount=request.amount, status=RefundStatus.SUCCEEDED)
    session.add(refund)
    session.flush()
    session.add(
        OperationLog(
            payment_id=payment.id,
            event_type="refund.provider_succeeded",
            detail=json.dumps({"amount": str(request.amount), "status": RefundStatus.SUCCEEDED}),
        )
    )
    if Decimal(refunded_amount) + request.amount == payment.amount:
        payment.status = PaymentStatus.REFUNDED
    session.commit()
    session.expire(payment, ["refunds"])
    return get_payment(session, payment_id)


def _apply_provider_outcome(
    session: Session,
    payment: Payment,
    *,
    correlation_id: str,
    simulation_case: SimulationCase | None,
    success_event: str,
    failure_event: str,
) -> None:
    try:
        result = get_payment_provider(payment.provider).charge(
            ProviderChargeRequest(
                payment_id=payment.id,
                amount=payment.amount,
                currency=payment.currency,
                correlation_id=correlation_id,
                simulation_case=simulation_case,
                timeout_ms=get_settings().provider_timeout_ms,
            )
        )
        payment.status = PaymentStatus.SUCCEEDED
        payment.provider_reference = result.reference
        payment.failure_code = None
        payment.failure_message = None
        payment.retryable = None
        session.add(
            OperationLog(
                payment_id=payment.id,
                event_type=success_event,
                detail=json.dumps(
                    {
                        "provider": payment.provider,
                        "reference": result.reference,
                        "http_status": result.http_status,
                        "latency_ms": result.latency_ms,
                        "raw_response": result.raw_response,
                        "correlation_id": correlation_id,
                    }
                ),
            )
        )
    except NormalizedProviderError as error:
        payment.status = PaymentStatus.FAILED
        payment.failure_code = error.code
        payment.failure_message = error.message
        payment.retryable = error.retryable
        session.add(
            OperationLog(
                payment_id=payment.id,
                event_type=failure_event,
                detail=json.dumps(
                    {
                        "code": error.code,
                        "message": error.message,
                        "retryable": error.retryable,
                        "http_status": error.http_status,
                        "latency_ms": error.latency_ms,
                        "raw_response": error.raw_response,
                        "correlation_id": correlation_id,
                    }
                ),
            )
        )


def _matches_idempotent_request(payment: Payment, request: PaymentCreate) -> bool:
    return (
        payment.amount == request.amount
        and payment.currency == request.currency
        and payment.provider.lower() == request.provider.lower()
        and payment.simulation_case == _simulation_case_value(request.simulation_case)
    )


def _simulation_case_value(simulation_case: SimulationCase | None) -> str | None:
    return simulation_case.value if simulation_case is not None else None
