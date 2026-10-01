# Integration Operations Hub

Integration Operations Hub is a full-stack portfolio project for operating payment-provider integrations. It models the work after an API call leaves the application boundary: normalized outcomes, provider health, retry state, request inspection, and operational recovery.

It demonstrates project experience with Python, FastAPI, SQLAlchemy, PostgreSQL, RabbitMQ, React, TypeScript, Docker, CI, testing, and integration-oriented system design. It does not claim real provider credentials, a production deployment, or professional experience with every project technology.

## What it does

- Creates, retrieves, refunds, paginates, and inspects payments.
- Simulates five providers with divergent formats, failures, latency, and retry behavior.
- Applies Basic/API-key authentication, correlation IDs, idempotency, rate limits, timeouts, and webhook receipts.
- Queues retryable failures through RabbitMQ with exponential backoff and dead-letter state.
- Provides a React operations console for provider health, rates, latency, retries, recent failures, and sanitized request/response inspection.
- Runs as a Docker Compose stack with PostgreSQL, RabbitMQ, API, worker, and frontend.

## Architecture

```text
React + TypeScript (Nginx)
        |
        v
FastAPI API
  |-- authentication, idempotency, rate limiting, logging, metrics
  |-- payment/refund/webhook services
  |-- provider adapter and deterministic simulators
  |
  +--> PostgreSQL
  +--> RabbitMQ retry -> delay -> dead-letter queues
         |
         v
       Retry worker
```

## Run locally

```powershell
docker compose up --build
```

- Console: `http://localhost:8080`
- API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- RabbitMQ management: `http://localhost:15672`

Local operator login: `operator` / `local-development-only`.

To stop the stack:

```powershell
docker compose down
```

## Verify

```powershell
python -m compileall -q app
python -m pytest -q
cd frontend
npm run test
npm run build
```

## Documentation

Start with the [documentation map](./docs/README.md):

- [Product overview](./docs/product-overview.md)
- [Architecture](./docs/architecture.md)
- [API reference](./docs/api-reference.md)
- [Data model](./docs/data-model.md)
- [Integration mapping](./docs/integration-mapping.md)
- [Failure scenarios](./docs/failure-scenarios.md)
- [Deployment](./docs/deployment.md)
- [Troubleshooting runbook](./docs/runbook.md)
- [Testing strategy](./docs/testing-strategy.md)

The canonical evolution plan is [TODO.md](./TODO.md). New project work starts from `master`, and every completed milestone ends in verification, commit, push, and pull request.
