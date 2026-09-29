# Integration Operations Hub

An operations-focused sandbox for payment integrations. It records payment attempts and refunds in a way that will later support provider health, request inspection, normalized failures, and retries.

## V1 design

**Product definition.** A backend API for an operator to create, look up, and refund payments while preserving the operational context needed to investigate an integration outcome.

**Scope.** One FastAPI service, PostgreSQL persistence, payment/refund lifecycle validation, correlation IDs, structured application logs, health checks, and automated tests. V1 intentionally excludes provider calls, auth, queues, retries, webhooks, and React. We model the seams for those features without pretending to implement them.

**Architecture.** `HTTP API -> application service -> SQLAlchemy repository/model -> PostgreSQL`. FastAPI owns HTTP concerns; the service owns state transitions. A future provider adapter will be invoked by the service, and an immutable operation-log table will become the request inspector's source.

**Technology choices.** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, PostgreSQL/psycopg, pytest, and Docker Compose. SQLAlchemy is deliberately used synchronously in V1: it makes the transaction boundary clear before async I/O becomes necessary for provider clients.

**Repository structure.**

```
app/             FastAPI application and domain implementation
tests/           HTTP-level automated tests
docs/            architecture decisions and operating notes
docker-compose.yml  local PostgreSQL
```

**Database model.** `payments` holds amount, currency, provider name, status, correlation ID, provider reference, and timestamps. `refunds` belongs to a payment, carries an amount and status, and makes partial-refund validation explicit. `operation_logs` is the future request/response audit trail; V1 writes a small lifecycle event only.

**Initial API.**

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Liveness check |
| POST | `/payments` | Record a payment request |
| GET | `/payments/{payment_id}` | Retrieve payment and refunds |
| POST | `/payments/{payment_id}/refunds` | Create a validated refund |

**Milestones.** (1) this V1 domain/API/tests; (2) provider simulators and normalized errors; (3) React operations UI; (4) async retries and messaging; (5) observability, deployment, and operational dashboard.

**Minimum Python before starting.** Type hints and `dataclass`/Pydantic-style models; modules and imports; exceptions; context managers (`with`); virtual environments and packages; and `async def` only at the FastAPI boundary for now. The closest .NET analogy: Pydantic request models are DTOs with runtime validation, and FastAPI dependency injection is lightweight parameter-based DI.

**React/TypeScript later.** Type aliases/interfaces, components and props, `useState`/`useEffect`, controlled forms, fetching/loading/error states, routing, and table composition. Treat components as focused views: state and API access should not diffuse across the UI.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
docker compose up -d db
$env:DATABASE_URL = "postgresql+psycopg://hub:hub@localhost:5432/integration_hub"
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs`. Run tests with `pytest`.

For early learning, SQLite is supported by setting `DATABASE_URL=sqlite:///./integration_hub.db`; production-like local work should use the compose PostgreSQL service.
