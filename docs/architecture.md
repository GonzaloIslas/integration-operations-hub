# Architecture

```text
Browser
  |
  v
React + TypeScript frontend (Nginx)
  |
  v
FastAPI API
  |-- authentication, idempotency, rate limits, logs, metrics
  |-- payment/refund/webhook services
  |-- provider adapter and deterministic simulators
  |
  +--> PostgreSQL
  |      payments, refunds, operation logs, webhook receipts, retry jobs
  |
  +--> RabbitMQ
         retry queue -> worker -> delay queue or dead-letter queue
```

## Synchronous path

The API validates a payment request, establishes a correlation ID and idempotency key, invokes a provider adapter, stores normalized outcome data, and returns the persisted payment. The adapter owns provider-format parsing; the service owns lifecycle state and transaction boundaries.

## Asynchronous retry path

`POST /payments/{payment_id}/retry` creates a retry-job row first, then publishes its ID to RabbitMQ. The worker reloads the job and payment from PostgreSQL, invokes the retry path, and marks the job completed, scheduled, or dead-lettered. Delayed jobs use RabbitMQ TTL/dead-letter routing to return to the retry queue.

## Operational path

HTTP middleware propagates or generates a correlation ID, emits a JSON completion log, and records request metrics. The dashboard derives provider health, rates, latency, recent failures, and retry state from persisted payments and operation logs. The inspector reads pre-sanitized snapshots from operation logs.

## Scaling boundaries

The database is currently the source of truth. The in-memory API rate limiter and direct publish-after-commit retry dispatch are intentionally local-development limitations. A production-scale deployment would need a transactional outbox, distributed rate-limit storage, worker concurrency policy, secret management, and a migration framework.
