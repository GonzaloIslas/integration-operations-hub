import json
import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.models import OperationLog, Payment, PaymentStatus, Refund, RefundStatus, WebhookEvent
from app.providers import (
    NormalizedProviderError,
    ProviderChargeRequest,
    SimulationCase,
    get_payment_provider,
    list_provider_definitions,
)
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


def get_dashboard(session: Session, recent_limit: int = 5) -> dict[str, object]:
    payments = list(
        session.scalars(select(Payment).options(selectinload(Payment.refunds)).order_by(Payment.created_at.desc()))
    )
    operations = list(session.scalars(select(OperationLog).order_by(OperationLog.created_at.desc())))
    providers = {
        definition.name: {
            "name": definition.name,
            "display_name": definition.display_name,
            "total_payments": 0,
            "successful_payments": 0,
            "failed_payments": 0,
            "retryable_failures": 0,
            "latencies": [],
        }
        for definition in list_provider_definitions()
    }

    for payment in payments:
        provider = providers.setdefault(
            payment.provider.lower(),
            {
                "name": payment.provider.lower(),
                "display_name": payment.provider,
                "total_payments": 0,
                "successful_payments": 0,
                "failed_payments": 0,
                "retryable_failures": 0,
                "latencies": [],
            },
        )
        provider["total_payments"] += 1
        if payment.status in {PaymentStatus.SUCCEEDED, PaymentStatus.REFUNDED}:
            provider["successful_payments"] += 1
        elif payment.status == PaymentStatus.FAILED:
            provider["failed_payments"] += 1
            if payment.retryable:
                provider["retryable_failures"] += 1

    for operation in operations:
        if operation.event_type not in {
            "payment.provider_succeeded",
            "payment.provider_failed",
            "payment.retry_succeeded",
            "payment.retry_failed",
        } or not operation.detail:
            continue
        detail = json.loads(operation.detail)
        provider_name = detail.get("provider")
        latency_ms = detail.get("latency_ms")
        if provider_name and isinstance(latency_ms, int | float) and provider_name.lower() in providers:
            providers[provider_name.lower()]["latencies"].append(latency_ms)

    provider_health = []
    for provider in providers.values():
        total = provider["total_payments"]
        success_rate = round(provider["successful_payments"] / total * 100, 1) if total else 0.0
        error_rate = round(provider["failed_payments"] / total * 100, 1) if total else 0.0
        latencies = provider["latencies"]
        average_latency = round(sum(latencies) / len(latencies), 1) if latencies else None
        provider_health.append(
            {
                "name": provider["name"],
                "display_name": provider["display_name"],
                "health": _health_status(total, error_rate),
                "total_payments": total,
                "success_rate": success_rate,
                "error_rate": error_rate,
                "average_latency_ms": average_latency,
                "retryable_failures": provider["retryable_failures"],
            }
        )

    total_payments = len(payments)
    successful_payments = sum(payment.status in {PaymentStatus.SUCCEEDED, PaymentStatus.REFUNDED} for payment in payments)
    failed_payments = sum(payment.status == PaymentStatus.FAILED for payment in payments)
    refunded_payments = sum(payment.status == PaymentStatus.REFUNDED for payment in payments)
    retryable_failures = sum(payment.status == PaymentStatus.FAILED and bool(payment.retryable) for payment in payments)
    all_latencies = [latency for provider in providers.values() for latency in provider["latencies"]]

    return {
        "summary": {
            "total_payments": total_payments,
            "successful_payments": successful_payments,
            "failed_payments": failed_payments,
            "refunded_payments": refunded_payments,
            "success_rate": round(successful_payments / total_payments * 100, 1) if total_payments else 0.0,
            "error_rate": round(failed_payments / total_payments * 100, 1) if total_payments else 0.0,
            "retryable_failures": retryable_failures,
            "average_latency_ms": round(sum(all_latencies) / len(all_latencies), 1) if all_latencies else None,
        },
        "providers": sorted(provider_health, key=lambda provider: provider["display_name"]),
        "recent_payments": payments[:recent_limit],
        "recent_failures": [payment for payment in payments if payment.status == PaymentStatus.FAILED][:recent_limit],
    }


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
                        "provider": payment.provider,
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


def _health_status(total_payments: int, error_rate: float) -> str:
    if total_payments == 0:
        return "unknown"
    if error_rate == 0:
        return "healthy"
    if error_rate < 25:
        return "degraded"
    return "down"
