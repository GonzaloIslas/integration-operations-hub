# Integration Operations Hub

Integration Operations Hub is a portfolio product for operating and troubleshooting external payment integrations. It is being built incrementally to demonstrate senior backend and integration thinking while developing hands-on Python, FastAPI, React, and TypeScript experience.

The canonical V1–V10 plan is in [TODO.md](./TODO.md). Read it before planning a new version: the project deliberately separates frontend work, provider simulation, real integration concerns, and production engineering.

## Current milestone: V2 React frontend

V2 adds a React/TypeScript operations console that consumes the live FastAPI API. It supports:

- A dashboard with payment-status counts and recent payments.
- Payment list, detail, failure context, and sanitized operation inspection.
- Integration list and detail views.
- Loading and API-error states.
- Focused backend and frontend tests.

The console uses local HTTP Basic authentication against the FastAPI API. It is intentionally a minimal learning boundary, configured through environment variables, not a production identity system.

> A limited provider simulator is already present on `master` from earlier out-of-sequence work. It is preserved, but it is not treated as V2 or complete V3 functionality; see [TODO.md](./TODO.md).

## Architecture

```text
React + TypeScript (Vite)
        |
        | HTTP / JSON
        v
FastAPI application
        |
        v
SQLAlchemy -> PostgreSQL
```

The V2 frontend is intentionally a small client with local component state and a typed API boundary. V3 will deliberately expand the provider layer; V4 will add real integration concepts such as idempotency, retries, and authentication.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Liveness check |
| POST | `/payments` | Record a payment request |
| GET | `/payments` | List payment records for the operations console |
| GET | `/payments/{payment_id}` | Retrieve a payment and refunds |
| GET | `/payments/{payment_id}/operations` | Retrieve sanitized lifecycle context |
| POST | `/payments/{payment_id}/refunds` | Create a validated refund |
| GET | `/integrations` | List integrations exposed by the backend |
| GET | `/integrations/{integration_name}` | Retrieve integration details |

The operation endpoint is a deliberately narrow UI-enabling contract, not the complete audit/request inspector planned for V7. It never exposes authorization secrets.

## Repository structure

```text
app/        FastAPI application and domain implementation
frontend/   React + TypeScript operations console
tests/      Backend automated tests
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

For early learning, SQLite is supported with `DATABASE_URL=sqlite:///./integration_hub.db`. PostgreSQL is the intended local integration target.

If an existing local SQLite database predates the provider fields currently on `master`, point `DATABASE_URL` to a new development file (for example, `sqlite:///./integration_hub_v2.db`). `create_all` does not alter existing tables; proper database migrations remain planned work.

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

See [docs/v2-frontend.md](./docs/v2-frontend.md) for the UI scope, API contract, and intentional boundaries.
