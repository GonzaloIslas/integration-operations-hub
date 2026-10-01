# Requirements and assumptions

## Functional requirements implemented

- Operator authentication through local HTTP Basic credentials; integration clients can use an API key.
- Payment lifecycle persistence with correlation and idempotency keys.
- Deterministic provider outcomes and normalized provider errors.
- Partial/full refunds with balance validation.
- Provider webhooks and idempotent webhook receipts.
- Manual retry request, RabbitMQ dispatch, delayed retry, terminal dead-letter state, and retry-job history.
- Dashboard and inspector views based on persisted data.

## Non-functional requirements implemented

- Liveness, database readiness, Prometheus-style request metrics, and JSON request-completion logs.
- Docker images and Compose topology for PostgreSQL, API, RabbitMQ, worker, and frontend.
- CI for backend/frontend verification.
- Sanitization before request/response snapshots are persisted.

## Deliberate assumptions

- Provider simulators are in-process and deterministic. They represent integration contracts, not real external providers.
- Development credentials are intentionally local values configured through environment variables.
- RabbitMQ carries retry-job IDs, while PostgreSQL is the durable retry-state source of truth.
- Initial payment processing is synchronous; only retry orchestration is asynchronous.

## Non-goals at this stage

- OAuth, role-based access, secret management, real provider onboarding, and compliance controls.
- A transactional outbox, distributed rate limiter, retry alerting, or automatic dead-letter reprocessing.
- Database migration history. The project contains a limited additive compatibility step for V7 inspection columns; a versioned migration framework is still required.
