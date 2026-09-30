import logging
import uuid
from collections.abc import Generator

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import Base, engine, get_session
from app.observability import configure_logging, elapsed_milliseconds, metrics, start_timer
from app.providers import get_integration, list_integrations
from app.schemas import (
    IntegrationRead,
    DashboardRead,
    OperationLogRead,
    PaymentCreate,
    PaymentRead,
    RefundCreate,
    RetryCreate,
    WebhookEventCreate,
)
from app.security import enforce_rate_limit
from app.services import (
    IdempotencyConflictError,
    InvalidRefundError,
    InvalidRetryError,
    InvalidWebhookError,
    PaymentNotFoundError,
    create_payment,
    create_refund,
    get_payment,
    get_dashboard,
    get_payment_operations,
    list_payments,
    process_webhook,
    retry_payment,
)

configure_logging(get_settings().log_level)
logger = logging.getLogger(__name__)

app = FastAPI(title="Integration Operations Hub", version="0.0.5")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().frontend_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-API-Key", "X-Correlation-ID"],
    expose_headers=["Idempotency-Key", "Idempotency-Replayed", "X-Next-Offset", "X-RateLimit-Remaining"],
)


@app.on_event("startup")
def create_tables() -> None:
    Base.metadata.create_all(bind=engine)


def database_session() -> Generator[Session, None, None]:
    yield from get_session()


@app.middleware("http")
async def observe_request(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    request.state.correlation_id = correlation_id
    started_at = start_timer()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = elapsed_milliseconds(started_at)
        metrics.record_request(request.method, request.url.path, 500, duration_ms)
        logger.exception(
            "http.request_failed",
            extra={
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": 500,
                "duration_ms": round(duration_ms, 3),
            },
        )
        raise
    duration_ms = elapsed_milliseconds(started_at)
    route = request.scope.get("route")
    metric_path = getattr(route, "path", request.url.path)
    metrics.record_request(request.method, metric_path, response.status_code, duration_ms)
    response.headers.setdefault("X-Correlation-ID", correlation_id)
    logger.info(
        "http.request_completed",
        extra={
            "correlation_id": correlation_id,
            "method": request.method,
            "path": metric_path,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 3),
        },
    )
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def readiness() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as error:
        logger.exception("readiness.database_failed")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database is unavailable.") from error
    return {"status": "ready", "database": "ok"}


@app.get("/metrics", response_class=PlainTextResponse)
def read_metrics() -> str:
    return metrics.render_prometheus()


@app.get("/dashboard", response_model=DashboardRead, dependencies=[Depends(enforce_rate_limit)])
def read_dashboard(session: Session = Depends(database_session)) -> DashboardRead:
    return DashboardRead.model_validate(get_dashboard(session))


@app.post(
    "/payments",
    response_model=PaymentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_rate_limit)],
)
def post_payment(
    payload: PaymentCreate,
    request: Request,
    response: Response,
    x_correlation_id: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: Session = Depends(database_session),
) -> PaymentRead:
    correlation_id = x_correlation_id or request.state.correlation_id
    effective_idempotency_key = idempotency_key or f"generated:{correlation_id}"
    try:
        payment, replayed = create_payment(session, payload, correlation_id, effective_idempotency_key)
    except IdempotencyConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    response.headers["X-Correlation-ID"] = payment.correlation_id
    response.headers["Idempotency-Key"] = effective_idempotency_key
    response.headers["Idempotency-Replayed"] = str(replayed).lower()
    if replayed:
        response.status_code = status.HTTP_200_OK
    logger.info(
        "payment.created payment_id=%s correlation_id=%s idempotency_replayed=%s",
        payment.id,
        payment.correlation_id,
        replayed,
    )
    return PaymentRead.model_validate(payment)


@app.get("/payments", response_model=list[PaymentRead], dependencies=[Depends(enforce_rate_limit)])
def read_payments(
    response: Response,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(database_session),
) -> list[PaymentRead]:
    payments, total = list_payments(session, limit, offset)
    response.headers["X-Total-Count"] = str(total)
    if offset + len(payments) < total:
        response.headers["X-Next-Offset"] = str(offset + len(payments))
    return [PaymentRead.model_validate(payment) for payment in payments]


@app.get("/payments/{payment_id}", response_model=PaymentRead, dependencies=[Depends(enforce_rate_limit)])
def read_payment(payment_id: uuid.UUID, session: Session = Depends(database_session)) -> PaymentRead:
    try:
        return PaymentRead.model_validate(get_payment(session, payment_id))
    except PaymentNotFoundError as error:
        raise HTTPException(status_code=404, detail="Payment not found.") from error


@app.get(
    "/payments/{payment_id}/operations",
    response_model=list[OperationLogRead],
    dependencies=[Depends(enforce_rate_limit)],
)
def read_payment_operations(
    payment_id: uuid.UUID, session: Session = Depends(database_session)
) -> list[OperationLogRead]:
    try:
        return [OperationLogRead.model_validate(operation) for operation in get_payment_operations(session, payment_id)]
    except PaymentNotFoundError as error:
        raise HTTPException(status_code=404, detail="Payment not found.") from error


@app.post(
    "/payments/{payment_id}/retry",
    response_model=PaymentRead,
    dependencies=[Depends(enforce_rate_limit)],
)
def post_payment_retry(
    payment_id: uuid.UUID,
    payload: RetryCreate,
    session: Session = Depends(database_session),
) -> PaymentRead:
    try:
        return PaymentRead.model_validate(retry_payment(session, payment_id, payload))
    except PaymentNotFoundError as error:
        raise HTTPException(status_code=404, detail="Payment not found.") from error
    except InvalidRetryError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@app.post(
    "/payments/{payment_id}/refunds",
    response_model=PaymentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_rate_limit)],
)
def post_refund(
    payment_id: uuid.UUID, payload: RefundCreate, session: Session = Depends(database_session)
) -> PaymentRead:
    try:
        return PaymentRead.model_validate(create_refund(session, payment_id, payload))
    except PaymentNotFoundError as error:
        raise HTTPException(status_code=404, detail="Payment not found.") from error
    except InvalidRefundError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post(
    "/webhooks/{provider}",
    response_model=PaymentRead,
    dependencies=[Depends(enforce_rate_limit)],
)
def post_webhook(
    provider: str,
    payload: WebhookEventCreate,
    response: Response,
    session: Session = Depends(database_session),
) -> PaymentRead:
    try:
        payment, replayed = process_webhook(session, provider, payload)
    except PaymentNotFoundError as error:
        raise HTTPException(status_code=404, detail="Payment not found.") from error
    except InvalidWebhookError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    response.headers["Idempotency-Replayed"] = str(replayed).lower()
    return PaymentRead.model_validate(payment)


@app.get("/integrations", response_model=list[IntegrationRead], dependencies=[Depends(enforce_rate_limit)])
def read_integrations() -> list[IntegrationRead]:
    return [IntegrationRead.model_validate(integration) for integration in list_integrations()]


@app.get(
    "/integrations/{integration_name}", response_model=IntegrationRead, dependencies=[Depends(enforce_rate_limit)]
)
def read_integration(integration_name: str) -> IntegrationRead:
    integration = get_integration(integration_name)
    if integration is None:
        raise HTTPException(status_code=404, detail="Integration not found.")
    return IntegrationRead.model_validate(integration)
