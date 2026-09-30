import uuid
from typing import Any, Literal
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models import PaymentStatus, RefundStatus
from app.providers import SimulationCase


class PaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(min_length=3, max_length=3, pattern="^[A-Z]{3}$")
    provider: str = Field(min_length=1, max_length=100)
    simulation_case: SimulationCase | None = None


class RefundCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class RetryCreate(BaseModel):
    simulation_case: SimulationCase = SimulationCase.NORMAL


class WebhookEventCreate(BaseModel):
    event_id: str = Field(min_length=1, max_length=128)
    payment_id: uuid.UUID
    event_type: Literal["payment.succeeded", "payment.failed"]
    provider_reference: str | None = Field(default=None, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)


class RefundRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    amount: Decimal
    status: RefundStatus
    created_at: datetime


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    amount: Decimal
    currency: str
    provider: str
    status: PaymentStatus
    correlation_id: str
    provider_reference: str | None
    failure_code: str | None
    failure_message: str | None
    retryable: bool | None
    created_at: datetime
    updated_at: datetime
    refunds: list[RefundRead] = []


class OperationLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    event_type: str
    detail: str | None
    created_at: datetime


class IntegrationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    display_name: str
    description: str
    is_simulated: bool = True
