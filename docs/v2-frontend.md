# V2 React frontend

V2 adds a React and TypeScript operations console on top of the FastAPI API. It is intentionally a focused client application, not a dashboard framework or a duplicate integration engine.

## Scope

- Dashboard with live payment-status counts and recent payments.
- Payment list and payment-details view.
- Integration catalog and integration-details view.
- Sanitized operation inspector showing the backend-recorded payment request and provider-result context.
- Loading and API-error states.
- Local HTTP Basic authentication against the FastAPI API.
- A focused component test for the API-backed dashboard.

The login form stores a Base64-encoded Basic-auth value only in browser session storage and sends it to the FastAPI API. This is a local development boundary, not a production identity system: it has no user lifecycle, hashing, roles, token rotation, or secure cross-device session. V4 must replace it with a deliberate authentication design.

## API contract used by the UI

| UI concern | Endpoint |
| --- | --- |
| Dashboard and payments | `GET /payments` |
| Payment detail | `GET /payments/{payment_id}` |
| Operation inspector | `GET /payments/{payment_id}/operations` |
| Integration catalog | `GET /integrations` |
| Integration detail | `GET /integrations/{integration_name}` |

The operation inspector is not the complete V7 request inspector. It deliberately displays only the sanitized lifecycle context the backend currently records. V7 will define durable request/response capture, redaction, and access controls.

## Frontend structure

```
frontend/
  src/api.ts       typed HTTP boundary
  src/types.ts     API contract types
  src/App.tsx      dashboard and focused operator views
  src/styles.css   application styling
  src/App.test.tsx component test
```

The state remains local to `App` because this is a small three-view console. Introducing a global store now would obscure the data flow without solving a demonstrated problem.

## Local operator credentials

FastAPI protects operations endpoints with HTTP Basic authentication. Defaults are intended only for local learning:

- Username: `operator`
- Password: `local-development-only`

Override them with `OPERATOR_USERNAME` and `OPERATOR_PASSWORD` in the environment before starting the backend. Do not use a real or production password in this configuration.

## Run locally

Start the API first. Its `FRONTEND_ORIGIN` setting defaults to `http://127.0.0.1:5173` for Vite development.

For a clean SQLite development database, set `DATABASE_URL=sqlite:///./integration_hub_v2.db` before starting the API. This avoids reusing a local database created before the provider fields were added; proper migrations are planned work.

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Run `npm run test` for frontend tests and `npm run build` to type-check and produce a production build.
