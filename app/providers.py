import json
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID


class SimulationCase(StrEnum):
    NORMAL = "normal"
    AUTH_FAILURE = "auth_failure"
    TIMEOUT = "timeout"
    HTTP_500 = "http_500"
    RATE_LIMITED = "rate_limited"
    MALFORMED_RESPONSE = "malformed_response"
    SLOW_RESPONSE = "slow_response"
    DUPLICATE_REQUEST = "duplicate_request"


@dataclass(frozen=True)
class ProviderChargeRequest:
    payment_id: UUID
    amount: Decimal
    currency: str
    correlation_id: str
    simulation_case: SimulationCase | None = None


@dataclass(frozen=True)
class SimulatedResponse:
    status_code: int
    body: str
    latency_ms: int = 0


@dataclass(frozen=True)
class ProviderPaymentResult:
    reference: str
    http_status: int
    latency_ms: int
    raw_response: str


@dataclass(frozen=True)
class ProviderDefinition:
    name: str
    display_name: str
    description: str
    response_format: str
    default_case: SimulationCase


PROVIDERS = (
    ProviderDefinition("acmepay", "AcmePay", "JSON approval response with a provider transaction reference.", "json", SimulationCase.NORMAL),
    ProviderDefinition("bancox", "BancoX", "Pipe-delimited bank authorization response.", "pipe", SimulationCase.NORMAL),
    ProviderDefinition("walletpro", "WalletPro", "Wallet API that defaults to an authentication failure.", "json", SimulationCase.AUTH_FAILURE),
    ProviderDefinition("slowpay", "SlowPay", "Slow provider response that succeeds but records high latency.", "json", SimulationCase.SLOW_RESPONSE),
    ProviderDefinition("brokenpay", "BrokenPay", "Unreliable provider that defaults to an HTTP 500 response.", "json", SimulationCase.HTTP_500),
)


class NormalizedProviderError(Exception):
    def __init__(self, code: str, message: str, retryable: bool, *, http_status: int | None = None, raw_response: str | None = None, latency_ms: int | None = None) -> None:
        self.code = code
        self.message = message
        self.retryable = retryable
        self.http_status = http_status
        self.raw_response = raw_response
        self.latency_ms = latency_ms
        super().__init__(message)


class PaymentProvider(Protocol):
    def charge(self, request: ProviderChargeRequest) -> ProviderPaymentResult: ...


class ProviderSimulator:
    """Produces deterministic, HTTP-like responses without network I/O."""

    def execute(self, definition: ProviderDefinition, request: ProviderChargeRequest) -> SimulatedResponse:
        simulation_case = request.simulation_case or definition.default_case
        reference = f"{definition.name}_{request.payment_id.hex[:12]}"

        if simulation_case in {SimulationCase.NORMAL, SimulationCase.SLOW_RESPONSE}:
            latency_ms = 1_500 if simulation_case is SimulationCase.SLOW_RESPONSE else 80
            return SimulatedResponse(201, self._success_body(definition, reference), latency_ms)
        if simulation_case is SimulationCase.TIMEOUT:
            raise NormalizedProviderError("provider_timeout", "The provider did not respond before the integration timeout.", retryable=True, latency_ms=3_000)

        responses = {
            SimulationCase.AUTH_FAILURE: SimulatedResponse(401, '{"error":"invalid_api_key"}'),
            SimulationCase.HTTP_500: SimulatedResponse(500, '{"error":"temporary_provider_failure"}'),
            SimulationCase.RATE_LIMITED: SimulatedResponse(429, '{"error":"rate_limit_exceeded"}'),
            SimulationCase.MALFORMED_RESPONSE: SimulatedResponse(201, "<approved reference=missing-json>"),
            SimulationCase.DUPLICATE_REQUEST: SimulatedResponse(409, '{"error":"duplicate_request","original_payment":"already_processed"}'),
        }
        return responses[simulation_case]

    @staticmethod
    def _success_body(definition: ProviderDefinition, reference: str) -> str:
        if definition.response_format == "pipe":
            return f"APPROVED|{reference}"
        return json.dumps({"result": "approved", "reference": reference})


class SimulatedProvider:
    def __init__(self, definition: ProviderDefinition, simulator: ProviderSimulator | None = None) -> None:
        self.definition = definition
        self.simulator = simulator or ProviderSimulator()

    def charge(self, request: ProviderChargeRequest) -> ProviderPaymentResult:
        response = self.simulator.execute(self.definition, request)
        if response.status_code != 201:
            raise self._normalize_failure(response)
        try:
            reference = self._parse_reference(response.body)
        except (KeyError, ValueError, json.JSONDecodeError) as error:
            raise NormalizedProviderError("provider_malformed_response", "The provider returned a response that could not be parsed.", retryable=False, http_status=response.status_code, raw_response=response.body, latency_ms=response.latency_ms) from error
        return ProviderPaymentResult(reference, response.status_code, response.latency_ms, response.body)

    def _parse_reference(self, body: str) -> str:
        if self.definition.response_format == "pipe":
            result, reference = body.split("|", maxsplit=1)
            if result != "APPROVED" or not reference:
                raise ValueError("Unexpected BancoX response.")
            return reference
        payload = json.loads(body)
        if payload["result"] != "approved":
            raise ValueError("Unexpected provider result.")
        return payload["reference"]

    @staticmethod
    def _normalize_failure(response: SimulatedResponse) -> NormalizedProviderError:
        errors = {
            401: ("provider_authentication_failed", "The provider rejected the integration credentials.", False),
            409: ("duplicate_request", "The provider reported a duplicate request.", False),
            429: ("provider_rate_limited", "The provider rate limit was reached.", True),
            500: ("provider_unavailable", "The provider returned an internal server error.", True),
        }
        code, message, retryable = errors[response.status_code]
        return NormalizedProviderError(code, message, retryable, http_status=response.status_code, raw_response=response.body, latency_ms=response.latency_ms)


def get_payment_provider(name: str) -> PaymentProvider:
    definition = get_provider_definition(name)
    if definition is None:
        raise NormalizedProviderError("unsupported_provider", f"Provider '{name}' is not configured.", retryable=False)
    return SimulatedProvider(definition)


def list_provider_definitions() -> tuple[ProviderDefinition, ...]:
    return PROVIDERS


def get_provider_definition(name: str) -> ProviderDefinition | None:
    normalized_name = name.lower()
    return next((definition for definition in PROVIDERS if definition.name == normalized_name), None)


def list_integrations() -> tuple[ProviderDefinition, ...]:
    return PROVIDERS


def get_integration(name: str) -> ProviderDefinition | None:
    return get_provider_definition(name)
