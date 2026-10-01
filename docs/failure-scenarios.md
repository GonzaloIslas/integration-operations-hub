# Failure scenarios

| Scenario | Detection | Current behavior | Operator action |
| --- | --- | --- | --- |
| Invalid provider credentials | Provider `401` simulation | Payment fails with non-retryable `provider_authentication_failed`. | Inspect snapshot; fix credentials/config before reattempting. |
| Provider timeout | Timeout simulation or latency over configured threshold | Payment fails as retryable `provider_timeout`. | Queue retry; inspect timeout and correlation context. |
| Provider HTTP 500 | BrokenPay/default or `http_500` | Payment fails as retryable `provider_unavailable`. | Queue retry; worker backs off and eventually dead-letters. |
| Provider HTTP 429 | `rate_limited` simulation | Payment fails as retryable `provider_rate_limited`. | Retry after provider backoff; inspect retry job schedule. |
| Malformed response | `malformed_response` | Payment fails as non-retryable `provider_malformed_response`. | Inspect raw response snapshot and adapter contract. |
| Duplicate provider request | `duplicate_request` | Payment fails as non-retryable duplicate response. | Check idempotency key and prior operation. |
| Repeated client POST | Same `Idempotency-Key` | Original payment is replayed; no duplicate provider call. | Reuse response/correlation context. |
| Retry exhaustion | Retry attempts reach configured limit | Job enters `dead_letter`; message is published to dead-letter queue. | Inspect last error and retry history; manually intervene. |
| RabbitMQ unavailable | Publish connection fails | API returns `503`; durable retry job remains queued in database. | Restore broker, then recover/re-enqueue according to runbook. |
| Database unavailable | `/ready` fails | Readiness returns `503`. | Check PostgreSQL health and API logs before restarting services. |

Inspection snapshots redact credential headers and sensitive body keys before persistence. They should be the first operational investigation surface, not a reason to expose provider secrets.
