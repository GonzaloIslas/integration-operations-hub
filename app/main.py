import logging
import secrets
import uuid
from collections.abc import Generator

from fastapi import Depends, FastAPI, Header, HTTPException, Response, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import Base, engine, get_session
from app.providers import get_integration, list_integrations
from app.schemas import IntegrationRead, OperationLogRead, PaymentCreate, PaymentRead, RefundCreate
from app.services import (
    InvalidRefundError,
    PaymentNotFoundError,
    create_payment,
    create_refund,
    get_payment,
    get_payment_operations,
    list_payments,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Integration Operations Hub", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().frontend_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-Correlation-ID"],
)
operator_security = HTTPBasic()


@app.on_event("startup")
def create_tables() -> None:
    Base.metadata.create_all(bind=engine)


def database_session() -> Generator[Session, None, None]:
    yield from get_session()


def require_operator(credentials: HTTPBasicCredentials = Depends(operator_security)) -> str:
    settings = get_settings()
    has_valid_username = secrets.compare_digest(credentials.username, settings.operator_username)
    has_valid_password = secrets.compare_digest(credentials.password, settings.operator_password)
    if not (has_valid_username and has_valid_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid operator credentials.")
    return credentials.username


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/payments",
    response_model=PaymentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_operator)],
)
def post_payment(
    payload: PaymentCreate,
    response: Response,
    x_correlation_id: str | None = Header(default=None),
    session: Session = Depends(database_session),
) -> PaymentRead:
    correlation_id = x_correlation_id or str(uuid.uuid4())
    response.headers["X-Correlation-ID"] = correlation_id
    payment = create_payment(session, payload, correlation_id)
    logger.info("payment.created payment_id=%s correlation_id=%s", payment.id, correlation_id)
    return PaymentRead.model_validate(payment)


@app.get("/payments", response_model=list[PaymentRead], dependencies=[Depends(require_operator)])
def read_payments(session: Session = Depends(database_session)) -> list[PaymentRead]:
    return [PaymentRead.model_validate(payment) for payment in list_payments(session)]


@app.get("/payments/{payment_id}", response_model=PaymentRead, dependencies=[Depends(require_operator)])
def read_payment(payment_id: uuid.UUID, session: Session = Depends(database_session)) -> PaymentRead:
    try:
        return PaymentRead.model_validate(get_payment(session, payment_id))
    except PaymentNotFoundError as error:
        raise HTTPException(status_code=404, detail="Payment not found.") from error


@app.get(
    "/payments/{payment_id}/operations",
    response_model=list[OperationLogRead],
    dependencies=[Depends(require_operator)],
)
def read_payment_operations(
    payment_id: uuid.UUID, session: Session = Depends(database_session)
) -> list[OperationLogRead]:
    try:
        return [OperationLogRead.model_validate(operation) for operation in get_payment_operations(session, payment_id)]
    except PaymentNotFoundError as error:
        raise HTTPException(status_code=404, detail="Payment not found.") from error


@app.post(
    "/payments/{payment_id}/refunds",
    response_model=PaymentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_operator)],
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


@app.get("/integrations", response_model=list[IntegrationRead], dependencies=[Depends(require_operator)])
def read_integrations() -> list[IntegrationRead]:
    return [IntegrationRead.model_validate(integration) for integration in list_integrations()]


@app.get(
    "/integrations/{integration_name}", response_model=IntegrationRead, dependencies=[Depends(require_operator)]
)
def read_integration(integration_name: str) -> IntegrationRead:
    integration = get_integration(integration_name)
    if integration is None:
        raise HTTPException(status_code=404, detail="Integration not found.")
    return IntegrationRead.model_validate(integration)
