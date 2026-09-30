# V3 provider simulation

V3 turns the earlier limited provider stub into a deliberate integration-simulation boundary. The simulators are deterministic and in-process so they run quickly in unit and API tests, while still behaving like incompatible external HTTP APIs at the adapter boundary.

## Provider catalog

| Provider | Default behavior | Success format |
| --- | --- | --- |
| AcmePay | Successful approval | JSON |
| BancoX | Successful approval | Pipe-delimited text |
| WalletPro | Authentication failure | JSON error |
| SlowPay | Slow successful response | JSON |
| BrokenPay | HTTP 500 failure | JSON error |

## Simulation control

`POST /payments` accepts an optional `simulation_case` field for deterministic scenario selection:

```json
{
  "amount": "150.00",
  "currency": "ARS",
  "provider": "BrokenPay",
  "simulation_case": "rate_limited"
}
```

Supported cases are `normal`, `auth_failure`, `timeout`, `http_500`, `rate_limited`, `malformed_response`, `slow_response`, and `duplicate_request`.

The field is V3-only simulation control. It makes failure behavior explicit in tests and manual exploration; it is not a real payment-provider request attribute.

## Integration boundary

`ProviderSimulator` emits raw HTTP-like status/body/latency results. `SimulatedProvider` owns provider-specific response parsing and converts failures into `NormalizedProviderError` values. The payment service remains provider-agnostic: it records normalized outcome data and sanitized raw protocol context in the operation log.

This gives us an integration seam to test without prematurely introducing real credentials, network infrastructure, background workers, or retry policies. V4 will build actual integration concepts on top of this boundary.

## Test strategy

Provider contract tests cover all named providers, JSON and pipe-delimited parsing, authentication failure, timeout, HTTP 500, HTTP 429, malformed response, slow response, duplicate request, and unsupported providers. API/service tests verify those normalized outcomes are persisted with operator-safe context.
