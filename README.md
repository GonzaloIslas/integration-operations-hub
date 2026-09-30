# Integration Operations Hub

Integration Operations Hub is a portfolio product for operating and troubleshooting external payment integrations. It is built incrementally to demonstrate senior backend and integration thinking while developing hands-on Python, FastAPI, React, and TypeScript experience.

The canonical V1–V10 plan lives in [TODO.md](./TODO.md). Each new version starts from the current `master`; earlier working branches are preserved but never used as a base.

## Current milestone: V3 integration simulation

V2's React/TypeScript console is now part of `master`; V3 extends its backend contract with a deliberate integration-simulation boundary. Five deterministic provider simulators emit incompatible raw responses, then adapters normalize the outcomes before the payment service persists them.

| Provider | Default behavior | Success format |
| --- | --- | --- |
| AcmePay | Successful approval | JSON |
| BancoX | Successful approval | Pipe-delimited text |
| WalletPro | Authentication failure | JSON error |
| SlowPay | Slow successful response | JSON |
| BrokenPay | HTTP 500 failure | JSON error |

The simulation supports normal success, authentication failure, timeout, HTTP 500, HTTP 429, malformed response, slow response, duplicate request, and unsupported-provider behavior. It is deterministic and in-process for fast tests; V4 will introduce actual integration concerns without pretending this is a production provider client.

## Architecture

```text
React + TypeScript (Vite)
        |
        v
FastAPI application
        |
        v
Payment service -> provider adapter -> deterministic provider simulator
        |
        v
SQLAlchemy -> PostgreSQL
```

The simulator emits raw HTTP-like status, body, and latency data. The adapter owns provider-format parsing and converts protocol failures into a common `NormalizedProviderError`. The payment service remains provider-agnostic and records normalized failure context in the operation log.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Liveness check |
| POST | `/payments` | Record a payment request and run its selected simulation |
| GET | `/payments` | List payment records for the operations console |
| GET | `/payments/{payment_id}` | Retrieve a payment and refunds |
| GET | `/payments/{payment_id}/operations` | Retrieve sanitized lifecycle context |
| POST | `/payments/{payment_id}/refunds` | Create a validated refund |
| GET | `/integrations` | List integrations exposed by the backend |
| GET | `/integrations/{integration_name}` | Retrieve integration details |

For V3 testing, `POST /payments` accepts an optional `simulation_case` alongside `amount`, `currency`, and `provider`:

```json
{
  "amount": "150.00",
  "currency": "ARS",
  "provider": "BrokenPay",
  "simulation_case": "rate_limited"
}
```

`simulation_case` is test control, not a real payment-provider request field. See [docs/v3-provider-simulation.md](./docs/v3-provider-simulation.md) for the full contract.

## Repository structure

```text
app/        FastAPI application, adapter layer, and provider simulators
frontend/   React + TypeScript operations console
tests/      API, service, and provider-contract tests
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

For early learning, SQLite is supported with `DATABASE_URL=sqlite:///./integration_hub.db`. If an existing local SQLite database predates the current schema, point `DATABASE_URL` to a fresh development file; `create_all` does not alter existing tables. Proper database migrations remain planned work.

### Frontend

In a separate terminal, with the API running:

```powershell
cd frontend
npm install
npm run dev
```

The frontend expects the API at `http://127.0.0.1:8000` by default. Set `VITE_API_BASE_URL` to use another API location. The backend allows Vite's default origin through `FRONTEND_ORIGIN`, which defaults to `http://127.0.0.1:5173`.

The default local operator is `operator`; set `OPERATOR_USERNAME` and `OPERATOR_PASSWORD` before starting FastAPI to use different development credentials. Do not use a real production password: this is a deliberately local Basic-auth milestone, not the production authentication design planned for V4.

## Verify

```powershell
python -m pytest -q
cd frontend
npm run test
npm run build
```

See [docs/v2-frontend.md](./docs/v2-frontend.md) for the UI scope and [docs/v3-provider-simulation.md](./docs/v3-provider-simulation.md) for the provider contract.
