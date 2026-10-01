# Integration mapping

| Provider | Default outcome | Response format | Normalized outcome |
| --- | --- | --- | --- |
| AcmePay | Success | JSON approval/reference | `succeeded` |
| BancoX | Success | Pipe-delimited approval/reference | `succeeded` |
| WalletPro | Authentication failure | JSON error | `provider_authentication_failed` |
| SlowPay | Slow response | JSON approval/reference | Success or `provider_timeout`, depending on configured timeout. |
| BrokenPay | HTTP 500 | JSON error | `provider_unavailable` and retryable. |

## Controlled simulation cases

`normal`, `auth_failure`, `timeout`, `http_500`, `rate_limited`, `malformed_response`, `slow_response`, and `duplicate_request` force deterministic provider behavior during tests or local exploration.

The provider adapter converts provider-specific raw status/body/latency into canonical payment state and normalized error fields. It also emits a sanitized request/response snapshot for operator inspection.
