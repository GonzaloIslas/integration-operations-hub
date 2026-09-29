import logging
import uuid
from collections.abc import Generator

from fastapi import Depends, FastAPI, Header, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database import Base, engine, get_session
from app.schemas import PaymentCreate, PaymentRead, RefundCreate
from app.services import InvalidRefundError, PaymentNotFoundError, create_payment, create_refund, get_payment

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Integration Operations Hub", version="0.1.0")


@app.on_event("startup")
def create_tables() -> None:
    Base.metadata.create_all(bind=engine)


def database_session() -> Generator[Session, None, None]:
    yield from get_session()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/payments", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
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


@app.get("/payments/{payment_id}", response_model=PaymentRead)
def read_payment(payment_id: uuid.UUID, session: Session = Depends(database_session)) -> PaymentRead:
    try:
        return PaymentRead.model_validate(get_payment(session, payment_id))
    except PaymentNotFoundError as error:
        raise HTTPException(status_code=404, detail="Payment not found.") from error


@app.post("/payments/{payment_id}/refunds", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
def post_refund(
    payment_id: uuid.UUID, payload: RefundCreate, session: Session = Depends(database_session)
) -> PaymentRead:
    try:
        return PaymentRead.model_validate(create_refund(session, payment_id, payload))
    except PaymentNotFoundError as error:
        raise HTTPException(status_code=404, detail="Payment not found.") from error
    except InvalidRefundError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
