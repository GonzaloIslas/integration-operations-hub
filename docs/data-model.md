# Data model

| Entity | Key data | Purpose |
| --- | --- | --- |
| `payments` | amount, provider, status, correlation ID, idempotency key, provider reference, failure state | Main payment lifecycle record. |
| `refunds` | payment ID, amount, status | Refund history and balance validation. |
| `operation_logs` | event type, detail, sanitized request/response snapshot | Lifecycle timeline and request inspector. |
| `webhook_events` | provider/event ID, payment ID, event type, payload | Durable idempotent webhook receipt. |
| `retry_jobs` | payment ID, attempt count, status, next attempt, last error | Durable asynchronous retry state. |

## Payment states

`pending` is reserved for an unprocessed state. Current provider processing results in `succeeded` or `failed`; a fully refunded payment becomes `refunded`. Failed payments can be retryable based on normalized provider error behavior.

## Retry-job states

| State | Meaning |
| --- | --- |
| `queued` | Durable job created and published to the retry queue. |
| `processing` | Worker is executing the retry. |
| `retry_scheduled` | Retryable failure; broker delay is pending. |
| `completed` | Retry completed or no retryable failure remains. |
| `dead_letter` | Maximum attempt count reached; job is published to the dead-letter queue. |

The schema is created automatically for local learning. V7 adds a non-destructive compatibility step for existing operation-log inspection columns. A proper migration framework remains a documented gap.
