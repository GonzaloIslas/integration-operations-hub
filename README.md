# Integration Operations Hub

Integration Operations Hub is a full-stack portfolio project for operating payment-provider integrations. It models the work after an API call leaves the application boundary: normalized outcomes, provider health, retry state, request inspection, and operational recovery.

It demonstrates project experience with Python, FastAPI, SQLAlchemy, PostgreSQL, RabbitMQ, React, TypeScript, Docker, CI, testing, and integration-oriented system design. It does not claim real provider credentials, a production deployment, or professional experience with every project technology.

## What it does

- Creates, retrieves, refunds, paginates, and inspects payments.
- Simulates five providers with divergent formats, failures, latency, and retry behavior.
- Applies Basic/API-key authentication, correlation IDs, idempotency, rate limits, timeouts, and webhook receipts.
- Queues retryable failures through RabbitMQ with exponential backoff and dead-letter state.
- Provides a React operations console for provider health, rates, latency, retries, recent failures, and sanitized request/response inspection.
- Offers an optional grounded Integration Copilot that explains a payment from sanitized evidence only when an OpenAI API key is configured.
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

## Integration Copilot

The Copilot uses the OpenAI Responses API only when `OPENAI_API_KEY` is explicitly configured. It receives a sanitized evidence bundle containing the current payment, lifecycle logs, inspection snapshots, retry history, provider mapping, and recent same-provider failures. It is instructed to state uncertainty and not invent facts outside that evidence. See [V10 Copilot documentation](./docs/v10-integration-copilot.md).

## Run locally

```powershell
docker compose up --build
```

- Console: `http://localhost:8080`
- API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- RabbitMQ management: `http://localhost:15672`

Local operator login: `operator` / `local-development-only`.

To enable the Copilot locally, set `OPENAI_API_KEY` in your shell or a non-committed `.env` file before `docker compose up --build`. The key is never stored in the database, snapshots, or repository configuration.

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
- [Integration Copilot](./docs/v10-integration-copilot.md)

The canonical evolution plan is [TODO.md](./TODO.md). New project work starts from `master`, and every completed milestone ends in verification, commit, push, and pull request.

## Coverage

The current measured Python branch-aware coverage baseline is 86%. CI enforces a minimum 85% coverage, runs the full backend suite, and uploads `coverage.xml` as a workflow artifact. The intentional gap to 100% is documented by unexercised external process boundaries such as real RabbitMQ consumption and real OpenAI SDK calls; those are tested through deterministic seams instead of live services.
