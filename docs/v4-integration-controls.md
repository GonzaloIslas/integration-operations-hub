# V4 integration controls

V4 adds real control semantics around the in-process provider adapters without claiming they are production infrastructure.

## Authentication

Operations endpoints accept either local HTTP Basic credentials for the React console or `X-API-Key` for service/provider clients. Both use development-only configuration and are intentionally not a replacement for a production identity system or managed secrets store.

OAuth is deferred because the project does not yet integrate a real third-party authorization server. A fabricated token flow would add ceremony without teaching the actual integration boundary.

## Idempotency and correlation

`POST /payments` accepts `Idempotency-Key`. Repeating the identical request returns the original payment with `Idempotency-Replayed: true`; reusing the key for a different request returns `409 Conflict`. The response also returns the effective key and a correlation ID.

Correlation IDs are included in payment-creation, provider-outcome, retry, and webhook lifecycle logs so an operator can follow one integration operation through the current synchronous flow.

## Rate limiting and pagination

The API uses an in-memory fixed-window limiter per authenticated principal. It returns remaining-budget headers and `429` with `Retry-After` when the budget is exhausted. This is appropriate for local learning only; V5 should use distributed enforcement if the API runs across multiple processes.

`GET /payments` uses bounded `limit` and `offset` query parameters and exposes `X-Total-Count` plus `X-Next-Offset` when another page exists.

## Timeouts, retries, and webhooks

Provider requests carry `PROVIDER_TIMEOUT_MS`. A simulated response whose reported latency exceeds that budget is normalized as a retryable timeout before response parsing.

`POST /payments/{payment_id}/retry` is a manual synchronous recovery path for retryable failed payments. It is intentionally not an automatic retry policy. V8 will add queues, backoff, and dead-letter handling.

`POST /webhooks/{provider}` accepts provider event IDs and stores a durable receipt. Repeating a provider/event pair returns the existing payment with `Idempotency-Replayed: true`. Provider-specific webhook signatures and asynchronous delivery handling are later work.
