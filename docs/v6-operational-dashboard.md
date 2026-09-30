# V6 operational dashboard

V6 adds an operational view backed by persisted application data rather than frontend mock calculations.

## Dashboard contract

`GET /dashboard` returns:

- Overall payment totals, success/error rate, refunded count, retryable failure count, and average observed provider latency.
- One health record for every configured provider, including providers without activity.
- Recent payments and recent failed payments for drill-down into the existing inspector.

Provider health is intentionally transparent and simple:

| Condition | Health |
| --- | --- |
| No payments observed | `unknown` |
| 0% error rate | `healthy` |
| Error rate below 25% | `degraded` |
| Error rate 25% or higher | `down` |

Success counts include `succeeded` and `refunded` final payment states. Retry queue depth is the number of failed payments marked retryable. Latency is calculated from the persisted provider outcome records; simulated timeouts therefore contribute their configured observed latency.

## UI behavior

The React dashboard loads the aggregate alongside payment and integration data after authentication. It shows headline rate/latency/retry cards, provider health, recent requests, and recent failures. Selecting a payment continues to use the existing details and sanitized operation-inspection view.

## Deliberate limits

This is an in-application operational dashboard, not a replacement for an external observability platform. It has no retention policy, real-time streaming, alerting, SLO evaluation, distributed tracing, or time-window trend storage. Those capabilities require a demonstrated production need and belong to later work.
