import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.models import OperationLog, Payment, PaymentStatus, Refund, RefundStatus, RetryJob, RetryJobStatus, WebhookEvent
from app.providers import (
    NormalizedProviderError,
    ProviderChargeRequest,
    SimulationCase,
    get_provider_definition,
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


class RetryJobNotFoundError(Exception):
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


def get_payment_inspections(session: Session, payment_id: uuid.UUID) -> list[dict[str, object]]:
    operations = get_payment_operations(session, payment_id)
    inspections = []
    for operation in operations:
        if operation.request_headers is None and operation.request_body is None:
            continue
        inspections.append(
            {
                "id": operation.id,
                "event_type": operation.event_type,
                "created_at": operation.created_at,
                "request": {
                    "headers": _decode_json(operation.request_headers, {}),
                    "body": _decode_json(operation.request_body, None),
                },
                "response_status": operation.response_status,
                "response": {
                    "headers": _decode_json(operation.response_headers, {}),
                    "body": _decode_json(operation.response_body, None),
                },
            }
        )
    return inspections


def create_retry_job(session: Session, payment_id: uuid.UUID, request: RetryCreate) -> tuple[RetryJob, bool]:
    payment = get_payment(session, payment_id)
    if payment.status != PaymentStatus.FAILED or not payment.retryable:
        raise InvalidRetryError("Only retryable failed payments can be queued for retry.")
    active_job = session.scalar(
        select(RetryJob).where(
            RetryJob.payment_id == payment_id,
            RetryJob.status.in_([RetryJobStatus.QUEUED, RetryJobStatus.PROCESSING, RetryJobStatus.RETRY_SCHEDULED]),
        )
    )
    if active_job is not None:
        return active_job, True
    simulation_case = request.simulation_case or _payment_simulation_case(payment)
    job = RetryJob(
        payment_id=payment.id,
        correlation_id=payment.correlation_id,
        simulation_case=simulation_case.value if simulation_case else None,
        max_attempts=get_settings().retry_max_attempts,
    )
    session.add(job)
    session.flush()
    session.add(
        OperationLog(
            payment_id=payment.id,
            event_type="payment.retry_queued",
            detail=json.dumps({"retry_job_id": str(job.id), "correlation_id": payment.correlation_id}),
        )
    )
    session.commit()
    session.refresh(job)
    return job, False


def get_retry_jobs(session: Session, payment_id: uuid.UUID) -> list[RetryJob]:
    get_payment(session, payment_id)
    statement = select(RetryJob).where(RetryJob.payment_id == payment_id).order_by(RetryJob.created_at.desc())
    return list(session.scalars(statement))


def process_retry_job(session: Session, job_id: uuid.UUID) -> RetryJob:
    job = session.get(RetryJob, job_id)
    if job is None:
        raise RetryJobNotFoundError
    if job.status in {RetryJobStatus.COMPLETED, RetryJobStatus.DEAD_LETTER}:
        return job
    job.status = RetryJobStatus.PROCESSING
    job.attempts += 1
    payment = get_payment(session, job.payment_id)
    simulation_case = SimulationCase(job.simulation_case) if job.simulation_case else _payment_simulation_case(payment)
    payment = retry_payment(session, payment.id, RetryCreate(simulation_case=simulation_case))

    if payment.status != PaymentStatus.FAILED or not payment.retryable:
        job.status = RetryJobStatus.COMPLETED
        job.next_attempt_at = None
        job.last_error = None
        event_type = "payment.retry_job_completed"
    elif job.attempts >= job.max_attempts:
        job.status = RetryJobStatus.DEAD_LETTER
        job.next_attempt_at = None
        job.last_error = payment.failure_message
        event_type = "payment.retry_job_dead_lettered"
    else:
        delay_seconds = get_settings().retry_initial_backoff_seconds * (2 ** (job.attempts - 1))
        job.status = RetryJobStatus.RETRY_SCHEDULED
        job.next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay_seconds)
        job.last_error = payment.failure_message
        event_type = "payment.retry_job_scheduled"
    session.add(
        OperationLog(
            payment_id=payment.id,
            event_type=event_type,
            detail=json.dumps(
                {
                    "retry_job_id": str(job.id),
                    "attempt": job.attempts,
                    "status": job.status,
                    "next_attempt_at": job.next_attempt_at,
                    "correlation_id": payment.correlation_id,
                },
                default=str,
            ),
        )
    )
    session.commit()
    session.refresh(job)
    return job


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
    queued_retries = session.scalar(
        select(func.count()).select_from(RetryJob).where(
            RetryJob.status.in_([RetryJobStatus.QUEUED, RetryJobStatus.PROCESSING, RetryJobStatus.RETRY_SCHEDULED])
        )
    ) or 0
    dead_letter_retries = session.scalar(
        select(func.count()).select_from(RetryJob).where(RetryJob.status == RetryJobStatus.DEAD_LETTER)
    ) or 0
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
            "queued_retries": queued_retries,
            "dead_letter_retries": dead_letter_retries,
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
    simulation_case = request.simulation_case or _payment_simulation_case(payment)
    payment.simulation_case = simulation_case.value if simulation_case else None
    session.add(
        OperationLog(
            payment_id=payment.id,
            event_type="payment.retry_requested",
            detail=json.dumps({"simulation_case": simulation_case}),
        )
    )
    _apply_provider_outcome(
        session,
        payment,
        correlation_id=payment.correlation_id,
        simulation_case=simulation_case,
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
            request_headers=_encode_json(_sanitize_headers({"X-API-Key": "local-integration-api-key"})),
            request_body=_encode_json(_sanitize_body(event.model_dump())),
            response_status=200,
            response_headers=_encode_json({"Content-Type": "application/json"}),
            response_body=_encode_json({"payment_id": str(payment.id), "status": payment.status}),
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
                request_headers=_encode_json(_sanitize_headers({"Authorization": "Bearer provider-api-key"})),
                request_body=_encode_json(
                    _sanitize_body(
                        {
                            "amount": str(payment.amount),
                            "currency": payment.currency,
                            "correlation_id": correlation_id,
                            "provider": payment.provider,
                        }
                    )
                ),
                response_status=result.http_status,
                response_headers=_encode_json({"Content-Type": _content_type(result.raw_response)}),
                response_body=result.raw_response,
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
                request_headers=_encode_json(_sanitize_headers({"Authorization": "Bearer provider-api-key"})),
                request_body=_encode_json(
                    _sanitize_body(
                        {
                            "amount": str(payment.amount),
                            "currency": payment.currency,
                            "correlation_id": correlation_id,
                            "provider": payment.provider,
                        }
                    )
                ),
                response_status=error.http_status,
                response_headers=_encode_json({"Content-Type": _content_type(error.raw_response)}),
                response_body=error.raw_response,
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


def _payment_simulation_case(payment: Payment) -> SimulationCase | None:
    if payment.simulation_case:
        return SimulationCase(payment.simulation_case)
    provider = get_provider_definition(payment.provider)
    return provider.default_case if provider else None


def _health_status(total_payments: int, error_rate: float) -> str:
    if total_payments == 0:
        return "unknown"
    if error_rate == 0:
        return "healthy"
    if error_rate < 25:
        return "degraded"
    return "down"


def _sanitize_headers(headers: dict[str, str]) -> dict[str, str]:
    sensitive_headers = {"authorization", "cookie", "set-cookie", "x-api-key"}
    return {
        name: "<redacted>" if name.lower() in sensitive_headers else value
        for name, value in headers.items()
    }


def _sanitize_body(value: object) -> object:
    sensitive_markers = ("authorization", "password", "secret", "token", "api_key", "apikey")
    if isinstance(value, dict):
        return {
            key: "<redacted>" if any(marker in key.lower() for marker in sensitive_markers) else _sanitize_body(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_body(item) for item in value]
    return value


def _encode_json(value: object) -> str:
    return json.dumps(value, default=str)


def _decode_json(value: str | None, fallback: object) -> object:
    if value is None:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _content_type(body: str | None) -> str:
    return "application/json" if body and body.lstrip().startswith("{") else "text/plain"
