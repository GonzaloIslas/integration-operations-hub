# V8 asynchronous retries

V8 moves retry orchestration out of the request path while preserving the database as the durable record of retry state.

## Flow

```text
Operator retry request
        |
        v
FastAPI creates retry_jobs row
        |
        v
RabbitMQ retry queue carries job ID
        |
        v
Worker loads job and payment from PostgreSQL
        |
        +-- success -> completed
        +-- retryable failure -> delay queue -> retry queue
        +-- max attempts -> dead-letter queue + dead_letter state
```

## Durable state and idempotency

The queue payload contains only a retry-job UUID. Attempts, next scheduled time, last error, and terminal state live in PostgreSQL. An active queued, processing, or delayed job is reused when an operator requests another retry for the same payment.

## Backoff and dead letters

The worker calculates exponential delay from `RETRY_INITIAL_BACKOFF_SECONDS`: 5 seconds, then 10 seconds, then terminal dead-lettering after `RETRY_MAX_ATTEMPTS` (default 3). RabbitMQ TTL on the delay queue sends scheduled jobs back to the main retry queue. Dead-lettered jobs are published to the durable `integration.retry.dead_letter` queue and remain visible in the payment retry history.

## Limits

There is no transactional outbox yet: if RabbitMQ is unavailable after a retry job commits, the API returns `503` while the durable queued job remains available for operator recovery. V8 does not implement distributed worker coordination, alerting, or automatic dead-letter reprocessing; those require production requirements and operator policies beyond this milestone.
