# Testing strategy

## Backend tests

- Domain/service tests cover payment/refund transitions, provider normalization, retry jobs, and schema compatibility.
- API tests cover authentication, idempotency, pagination, webhooks, dashboard data, inspection redaction, and retry-job endpoints.
- Messaging tests validate queue topology declaration and publisher lifecycle calls without requiring a broker.
- System workflow tests cover idempotent creation, queued retry requests, webhook reconciliation, operation history, and metrics.

## Frontend tests

The React suite validates dashboard rendering, API-error handling, and authentication flow. Type checking and Vite production builds validate the complete frontend contract.

## Environment verification

- `python -m compileall -q app`
- `python -m pytest -q`
- `npm run test`
- `npm run build`
- `npm audit --omit=dev --audit-level=moderate`
- `docker compose config --quiet`
- Compose runtime checks for PostgreSQL, API, RabbitMQ, worker, and frontend health.

## Current scope limits

Tests are deterministic and local. They do not exercise real provider endpoints, cloud infrastructure, multi-worker contention, fault injection against an external broker, or browser end-to-end automation. Those belong to future production/integration validation when the project has a real deployment target.
