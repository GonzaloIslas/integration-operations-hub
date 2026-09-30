import logging
import uuid
from collections.abc import Generator

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import Base, engine, get_session
from app.providers import get_integration, list_integrations
from app.schemas import (
    IntegrationRead,
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
    get_payment_operations,
    list_payments,
    process_webhook,
    retry_payment,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Integration Operations Hub", version="0.0.4")
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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/payments",
    response_model=PaymentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_rate_limit)],
)
def post_payment(
    payload: PaymentCreate,
    response: Response,
    x_correlation_id: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: Session = Depends(database_session),
) -> PaymentRead:
    correlation_id = x_correlation_id or str(uuid.uuid4())
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
