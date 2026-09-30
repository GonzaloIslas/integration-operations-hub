from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class ProviderPaymentResult:
    reference: str


@dataclass(frozen=True)
class IntegrationDefinition:
    name: str
    display_name: str
    description: str


INTEGRATIONS = (
    IntegrationDefinition("acmepay", "AcmePay", "Deterministic successful-payment simulator."),
    IntegrationDefinition("declinepay", "DeclinePay", "Deterministic permanent-decline simulator."),
    IntegrationDefinition("timeoutpay", "TimeoutPay", "Deterministic retryable-timeout simulator."),
)


class NormalizedProviderError(Exception):
    def __init__(self, code: str, message: str, retryable: bool) -> None:
        self.code = code
        self.message = message
        self.retryable = retryable
        super().__init__(message)


class PaymentProvider(Protocol):
    def charge(self, payment_id: UUID, amount: Decimal, currency: str) -> ProviderPaymentResult: ...


class SimulatedProvider:
    """Deterministic provider adapter used until real provider clients are added."""

    def __init__(self, name: str) -> None:
        self.name = name.lower()

    def charge(self, payment_id: UUID, amount: Decimal, currency: str) -> ProviderPaymentResult:
        if self.name == "acmepay":
            return ProviderPaymentResult(reference=f"acme_{payment_id.hex[:12]}")
        if self.name == "declinepay":
            raise NormalizedProviderError("card_declined", "The provider declined the payment.", retryable=False)
        if self.name == "timeoutpay":
            raise NormalizedProviderError("provider_timeout", "The provider did not respond in time.", retryable=True)
        raise NormalizedProviderError(
            "unsupported_provider", f"Provider '{self.name}' is not configured.", retryable=False
        )


def get_payment_provider(name: str) -> PaymentProvider:
    return SimulatedProvider(name)


def list_integrations() -> tuple[IntegrationDefinition, ...]:
    return INTEGRATIONS


def get_integration(name: str) -> IntegrationDefinition | None:
    normalized_name = name.lower()
    return next((integration for integration in INTEGRATIONS if integration.name == normalized_name), None)
