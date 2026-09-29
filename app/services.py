import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import OperationLog, Payment, PaymentStatus, Refund, RefundStatus
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

    refund = Refund(payment_id=payment.id, amount=request.amount)
    session.add(refund)
    session.flush()
    session.add(OperationLog(payment_id=payment.id, event_type="refund.created"))
    session.commit()
    session.expire(payment, ["refunds"])
    return get_payment(session, payment_id)
