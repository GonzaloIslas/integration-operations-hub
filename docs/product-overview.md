# Product overview

Integration Operations Hub is an operator-facing system for monitoring and troubleshooting payment-provider integrations. It is deliberately shaped around the operational questions that arise after a request leaves an application boundary:

- Did the provider receive the request?
- Which correlation and idempotency keys identify it?
- Was the outcome successful, retryable, permanently failed, or replayed?
- What sanitized request and response context can an operator inspect?
- Is a provider healthy, degraded, or producing retry/dead-letter work?

## Intended users

- Integration and backend engineers investigating provider behavior.
- Support or operations users following a payment lifecycle.
- Interview reviewers evaluating API design, integration boundaries, Python/FastAPI, React/TypeScript, testing, Docker, and asynchronous processing.

## Product capabilities today

- Create, retrieve, refund, paginate, and inspect payment records.
- Run deterministic provider simulators with incompatible response formats and controlled failure modes.
- Apply API key/Basic authentication, idempotency, rate limiting, correlation IDs, webhook ingestion, and timeout normalization.
- Queue retryable failures through RabbitMQ; worker retries use exponential backoff and dead-letter handling.
- Display provider health, rates, latency, retry state, recent activity, and sanitized request/response snapshots in a React operations console.

## Portfolio framing

The repository demonstrates project experience building a Python/FastAPI and React/TypeScript system. It complements, rather than replaces, professional experience in backend and integration engineering. It does not claim a production deployment, real provider credentials, compliance certification, or managed production observability.
