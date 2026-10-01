# Integration Operations Hub

Integration Operations Hub is a portfolio product for operating and troubleshooting external payment integrations. It is built incrementally to demonstrate senior backend and integration thinking while developing hands-on Python, FastAPI, React, and TypeScript experience.

The canonical V1–V10 plan lives in [TODO.md](./TODO.md). Each new version starts from the current `master`; earlier working branches are preserved but never used as a base.

## V5 production engineering foundation

V5 makes the application operable as a small production-style service:

- Docker images for FastAPI and the React frontend.
- Compose orchestration for PostgreSQL, API, and frontend.
- Correlation-aware structured JSON request logs.
- Prometheus-style request metrics at `/metrics`.
- Separate liveness (`/health`) and database readiness (`/ready`) checks.
- Centralized environment-driven configuration.
- GitHub Actions CI for Python tests, frontend tests, and frontend builds.
- System workflow tests for idempotency, retry, webhooks, and metrics.

Redis, RabbitMQ, workers, distributed rate limiting, and asynchronous retries are intentionally deferred. The present synchronous workload does not justify that infrastructure; V8 will add it when retry orchestration becomes the product concern.

## V6 operational dashboard

V6 turns persisted payment and lifecycle data into an operational dashboard backed by `GET /dashboard`:

- Provider health: `healthy`, `degraded`, `down`, or `unknown`.
- Per-provider success/error rate, observed average latency, and retryable failure count.
- Overall success/error rates, retry queue depth, and observed provider latency.
- Recent requests and recent failures that link to the existing payment inspector.

These are derived from the current database and lifecycle logs, not fabricated frontend data. The dashboard deliberately reports observed historical data; V5/V6 do not yet include a separate metrics store, alerting, or distributed tracing.

## Current milestone: V7 request inspector

V7 adds a dedicated request/response inspector to the payment drill-down. Provider interactions now retain sanitized snapshots of:

- Request headers and body.
- Response status, headers, and body.
- Event timestamp and lifecycle event type.

Sensitive headers (`Authorization`, API keys, cookies) and sensitive body fields (passwords, secrets, tokens, and API keys) are redacted before a snapshot is persisted. The UI renders the stored snapshot; it never reconstructs it from a live provider request.

## Architecture

```text
Browser
   |
   v
React + TypeScript (Nginx container)
   |
   v
FastAPI API -- auth / rate limits / metrics / readiness
   |
   v
Payment service -- idempotency / retry / webhooks
   |
   v
Provider adapter -> deterministic provider simulator
   |
   v
PostgreSQL
```

Every HTTP response receives a correlation ID. Request completion is logged as JSON with method, route, response status, duration, and correlation ID. The `/metrics` endpoint exposes request counters and duration sums in Prometheus text format.

## API operations

All operations endpoints require either local HTTP Basic credentials or `X-API-Key`; `/health`, `/ready`, and `/metrics` are operational endpoints.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Process liveness |
| GET | `/ready` | Database readiness |
| GET | `/metrics` | Prometheus-style request metrics |
| GET | `/dashboard` | Operational dashboard aggregate |
| POST | `/payments` | Create an idempotent payment request |
| GET | `/payments?limit=&offset=` | List payments with offset pagination |
| GET | `/payments/{payment_id}` | Retrieve a payment and refunds |
| GET | `/payments/{payment_id}/operations` | Retrieve sanitized lifecycle context |
| GET | `/payments/{payment_id}/inspections` | Retrieve sanitized request/response snapshots |
| POST | `/payments/{payment_id}/retry` | Manually retry an eligible failed payment |
| POST | `/payments/{payment_id}/refunds` | Create a validated refund |
| POST | `/webhooks/{provider}` | Ingest an idempotent provider webhook |

See [docs/v4-integration-controls.md](./docs/v4-integration-controls.md) for authentication, idempotency, retry, and webhook behavior.

## Run the full stack

```powershell
docker compose up --build
```

Open the React console at `http://localhost:8080`; the API is available at `http://localhost:8000`. The default local operator is `operator` / `local-development-only`.

The Compose defaults are strictly local-development values. Override credentials and configuration through environment variables or a non-committed `.env` file; never use real production credentials in this repository configuration.

## Run without Docker

### Backend

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
docker compose up -d db
$env:DATABASE_URL = "postgresql+psycopg://hub:hub@localhost:5432/integration_hub"
uvicorn app.main:app --reload
```

For early learning, SQLite is supported with `DATABASE_URL=sqlite:///./integration_hub.db`. If an existing local SQLite database predates the current schema, point `DATABASE_URL` to a fresh development file; `create_all` does not alter existing tables. Proper migrations remain planned work.

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

The frontend expects the API at `http://127.0.0.1:8000` by default. Set `VITE_API_BASE_URL` to use another API location.

## Verify

```powershell
python -m compileall -q app
python -m pytest -q
cd frontend
npm run test
npm run build
```

See [docs/v5-production-engineering.md](./docs/v5-production-engineering.md) for operational boundaries and the verification strategy.
