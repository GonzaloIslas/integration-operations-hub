from decimal import Decimal
from uuid import uuid4

import pytest

from app.providers import (
    NormalizedProviderError,
    ProviderChargeRequest,
    SimulationCase,
    get_payment_provider,
    list_provider_definitions,
)


def request_for(simulation_case: SimulationCase | None = None) -> ProviderChargeRequest:
    return ProviderChargeRequest(
        payment_id=uuid4(),
        amount=Decimal("42.00"),
        currency="USD",
        correlation_id="provider-contract-test",
        simulation_case=simulation_case,
    )


def test_provider_catalog_matches_the_v3_simulation_plan():
    assert [provider.name for provider in list_provider_definitions()] == [
        "acmepay",
        "bancox",
        "walletpro",
        "slowpay",
        "brokenpay",
    ]


@pytest.mark.parametrize("provider_name", ["acmepay", "bancox"])
def test_successful_providers_normalize_different_response_formats(provider_name: str):
    result = get_payment_provider(provider_name).charge(request_for())

    assert result.reference.startswith(f"{provider_name}_")
    assert result.http_status == 201
    assert result.latency_ms == 80
    assert result.raw_response


def test_slowpay_preserves_slow_response_timing_without_waiting_in_tests():
    result = get_payment_provider("slowpay").charge(request_for())

    assert result.reference.startswith("slowpay_")
    assert result.latency_ms == 1_500


@pytest.mark.parametrize(
    ("provider_name", "simulation_case", "code", "retryable", "http_status"),
    [
        ("walletpro", None, "provider_authentication_failed", False, 401),
        ("slowpay", SimulationCase.TIMEOUT, "provider_timeout", True, None),
        ("brokenpay", None, "provider_unavailable", True, 500),
        ("acmepay", SimulationCase.RATE_LIMITED, "provider_rate_limited", True, 429),
        ("bancox", SimulationCase.MALFORMED_RESPONSE, "provider_malformed_response", False, 201),
        ("acmepay", SimulationCase.DUPLICATE_REQUEST, "duplicate_request", False, 409),
    ],
)
def test_failure_scenarios_are_normalized_consistently(
    provider_name: str,
    simulation_case: SimulationCase | None,
    code: str,
    retryable: bool,
    http_status: int | None,
):
    with pytest.raises(NormalizedProviderError) as raised_error:
        get_payment_provider(provider_name).charge(request_for(simulation_case))

    error = raised_error.value
    assert error.code == code
    assert error.retryable is retryable
    assert error.http_status == http_status


def test_unsupported_provider_is_normalized_without_a_transport_response():
    with pytest.raises(NormalizedProviderError) as raised_error:
        get_payment_provider("not-a-provider")

    assert raised_error.value.code == "unsupported_provider"
    assert raised_error.value.raw_response is None
