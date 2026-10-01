# API reference

## Authentication

`/health`, `/ready`, and `/metrics` are operational endpoints. All other endpoints require one of:

- HTTP Basic: local operator credentials.
- `X-API-Key`: local integration-client credential.

Configuration names are `OPERATOR_USERNAME`, `OPERATOR_PASSWORD`, and `INTEGRATION_API_KEY`. Do not use real production secrets in the local Compose defaults.

## Cross-cutting headers

| Header | Behavior |
| --- | --- |
| `X-Correlation-ID` | Optional inbound correlation ID. If absent, the API generates one and returns it. |
| `Idempotency-Key` | Optional payment-create key. Identical replays return the original payment; conflicting reuse returns `409`. |
| `X-API-Key` | Integration-client authentication. |

Payment creation returns `Idempotency-Key` and `Idempotency-Replayed`. Paginated lists return `X-Total-Count` and, when applicable, `X-Next-Offset`.

## Endpoints

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/health` | Process liveness. |
| GET | `/ready` | Database connectivity readiness. |
| GET | `/metrics` | Prometheus-style API request metrics. |
| GET | `/dashboard` | Aggregate provider health, rate, latency, recent activity, and retry state. |
| POST | `/payments` | Creates and synchronously processes a payment. `simulation_case` is V3/V8 test control. |
| GET | `/payments?limit=&offset=` | Bounded payment pagination. |
| GET | `/payments/{payment_id}` | Payment and refunds. |
| GET | `/payments/{payment_id}/operations` | Lifecycle events and sanitized context. |
| GET | `/payments/{payment_id}/inspections` | Sanitized request/response snapshots. |
| POST | `/payments/{payment_id}/retry` | Creates or replays an active durable retry job; normally returns `202`. |
| GET | `/payments/{payment_id}/retries` | Retry-job status/history. |
| POST | `/payments/{payment_id}/refunds` | Validated refund. |
| POST | `/webhooks/{provider}` | Idempotent provider webhook receipt. |
| GET | `/integrations` | Provider catalog. |
| GET | `/integrations/{integration_name}` | Provider detail. |

## Error shape

FastAPI validation failures use standard `422` details. Domain conflicts return `409`, unavailable retry messaging returns `503`, and API rate limits return `429` with `Retry-After`. Provider failures are persisted on a payment through `failure_code`, `failure_message`, and `retryable` fields.
