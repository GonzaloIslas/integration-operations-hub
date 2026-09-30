# Integration Operations Hub

Integration Operations Hub is a portfolio product for operating and troubleshooting external payment integrations. It is built incrementally to demonstrate senior backend and integration thinking while developing hands-on Python, FastAPI, React, and TypeScript experience.

The canonical V1–V10 plan lives in [TODO.md](./TODO.md). Each new version starts from the current `master`; earlier working branches are preserved but never used as a base.

## Current milestone: V4 integration controls

V4 adds a practical, synchronous integration-control layer on top of V3 provider simulations:

- Local operator Basic authentication and integration API-key authentication.
- Fixed-window per-principal rate limiting.
- Idempotent payment creation with replay/conflict handling.
- Offset pagination for operations queries.
- Configurable provider timeout enforcement.
- Manual retry for retryable failures.
- Authenticated, idempotent webhook ingestion.
- Correlation and normalized protocol context in lifecycle logs.

OAuth is intentionally deferred: there is no real authorization server or third-party OAuth flow to integrate yet. Adding a fake one would not demonstrate an integration concern honestly. Distributed rate limiting, automatic retries, and queue-backed webhook processing remain later production work.

## Architecture

```text
React + TypeScript (Vite)
        |
        v
FastAPI API -- Basic auth / API key -- rate limit
        |
        v
Payment service -- idempotency / retry / webhook processing
        |
        v
Provider adapter -> deterministic provider simulator
        |
        v
SQLAlchemy -> PostgreSQL
```

The provider adapter normalizes raw status, body, and latency results. The payment service records correlation-aware, operator-safe protocol context and applies idempotency/retry/webhook rules before persisting a lifecycle change.

## API

All operations endpoints require either local HTTP Basic credentials or `X-API-Key`. The health endpoint remains public.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Liveness check |
| POST | `/payments` | Create an idempotent payment request |
| GET | `/payments?limit=&offset=` | List payments with offset pagination |
| GET | `/payments/{payment_id}` | Retrieve a payment and refunds |
| GET | `/payments/{payment_id}/operations` | Retrieve sanitized lifecycle context |
| POST | `/payments/{payment_id}/retry` | Manually retry an eligible failed payment |
| POST | `/payments/{payment_id}/refunds` | Create a validated refund |
| POST | `/webhooks/{provider}` | Ingest an idempotent provider webhook |
| GET | `/integrations` | List integration definitions |
| GET | `/integrations/{integration_name}` | Retrieve integration details |

### Integration headers

| Header | Purpose |
| --- | --- |
| `X-API-Key` | Authenticates a service/provider client. |
| `Idempotency-Key` | Makes repeated `POST /payments` calls replay safely. |
| `X-Correlation-ID` | Propagates an operator-supplied trace identifier. |

`POST /payments` returns `Idempotency-Key`, `Idempotency-Replayed`, and `X-Correlation-ID`. Paginated payment lists return `X-Total-Count` and, when more data exists, `X-Next-Offset`.

For V3/V4 exploration, `POST /payments` accepts an optional `simulation_case` test control. See [docs/v3-provider-simulation.md](./docs/v3-provider-simulation.md).

## Local configuration

These development-only defaults can be overridden by environment variables:

| Setting | Default |
| --- | --- |
| `OPERATOR_USERNAME` | `operator` |
| `OPERATOR_PASSWORD` | `local-development-only` |
| `INTEGRATION_API_KEY` | `local-integration-api-key` |
| `API_RATE_LIMIT` | `100` requests |
| `API_RATE_WINDOW_SECONDS` | `60` seconds |
| `PROVIDER_TIMEOUT_MS` | `2000` milliseconds |

Do not use real production credentials in this configuration. V4 uses local development configuration to demonstrate the control boundaries; a production identity and secrets-management design belongs to later work.

## Repository structure

```text
app/        FastAPI API, integration controls, adapter layer, and simulators
frontend/   React + TypeScript operations console
tests/      API, service, security, and provider-contract tests
docs/       Architecture decisions and milestone documentation
```

## Run locally

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

In a separate terminal, with the API running:

```powershell
cd frontend
npm install
npm run dev
```

The frontend expects the API at `http://127.0.0.1:8000` by default. Set `VITE_API_BASE_URL` to use another API location.

## Verify

```powershell
python -m pytest -q
cd frontend
npm run test
npm run build
```

See [docs/v2-frontend.md](./docs/v2-frontend.md), [docs/v3-provider-simulation.md](./docs/v3-provider-simulation.md), and [docs/v4-integration-controls.md](./docs/v4-integration-controls.md) for milestone details.
