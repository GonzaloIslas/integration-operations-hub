# Project TODO

This list reflects the remaining product work described in the V1 design and its planned milestones. Items marked complete are covered by the repository's automated tests; unmarked items are not implemented yet.

## V1 completion

- [x] Create and retrieve payments, including correlation-ID propagation.
- [x] Validate payment and refund request payloads.
- [x] Enforce the refundable-balance rule and record payment/refund lifecycle events.
- [x] Provide a liveness endpoint.
- [ ] Add a supported payment-status transition (for example, provider confirmation from `pending` to `succeeded`). Refunds currently require a payment to be `succeeded`, but the public API has no transition that can set that state.
- [ ] Define and enforce all payment/refund state transitions, including how a fully refunded payment becomes `refunded`.
- [ ] Make operation logs a complete, immutable request-inspection audit trail (request context, normalized response/error, actor, and timestamps).
- [ ] Add database migrations and constraints/indexes appropriate for PostgreSQL; table creation at application startup is not a migration strategy.
- [ ] Add structured logging coverage, error handling for database failures, and a readiness check that verifies database connectivity.
- [ ] Add CI to install the project and run the pytest suite on a supported Python version.

## Later milestones

- [ ] Provider simulators/adapters and normalized provider errors.
- [ ] Authentication and authorization for operator actions.
- [ ] React operations UI for payment lookup, inspection, and refunds.
- [ ] Webhook ingestion, idempotency handling, retries, queues, and asynchronous processing.
- [ ] Metrics, tracing, dashboards, alerts, deployment configuration, and operational runbooks.

## Test backlog

- [ ] PostgreSQL integration tests, including migrations and decimal precision behavior.
- [ ] Concurrent-refund tests to prove the refundable balance cannot be overspent under parallel requests.
- [ ] API tests for the future status-transition and audit-inspection endpoints.
- [ ] Provider adapter contract tests and end-to-end workflow tests once integrations exist.
