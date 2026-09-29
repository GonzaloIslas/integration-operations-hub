import uuid
from decimal import Decimal
import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import OperationLog, Payment, PaymentStatus, Refund, RefundStatus
from app.providers import NormalizedProviderError, get_payment_provider
from app.schemas import PaymentCreate, RefundCreate


class PaymentNotFoundError(Exception):
    pass


class InvalidRefundError(Exception):
    pass


def create_payment(session: Session, request: PaymentCreate, correlation_id: str) -> Payment:
    payment = Payment(**request.model_dump(), correlation_id=correlation_id)
    session.add(payment)
    session.flush()
    session.add(OperationLog(payment_id=payment.id, event_type="payment.created"))
    try:
        result = get_payment_provider(request.provider).charge(payment.id, payment.amount, payment.currency)
        payment.status = PaymentStatus.SUCCEEDED
        payment.provider_reference = result.reference
        session.add(
            OperationLog(
                payment_id=payment.id,
                event_type="payment.provider_succeeded",
                detail=json.dumps({"provider": request.provider, "reference": result.reference}),
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
                event_type="payment.provider_failed",
                detail=json.dumps(
                    {"code": error.code, "message": error.message, "retryable": error.retryable}
                ),
            )
        )
    session.commit()
    session.refresh(payment)
    return payment


def get_payment(session: Session, payment_id: uuid.UUID) -> Payment:
    statement = select(Payment).options(selectinload(Payment.refunds)).where(Payment.id == payment_id)
    payment = session.scalar(statement)
    if payment is None:
        raise PaymentNotFoundError
    return payment


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
    session.add(OperationLog(payment_id=payment.id, event_type="refund.provider_succeeded"))
    if Decimal(refunded_amount) + request.amount == payment.amount:
        payment.status = PaymentStatus.REFUNDED
    session.commit()
    session.expire(payment, ["refunds"])
    return get_payment(session, payment_id)
