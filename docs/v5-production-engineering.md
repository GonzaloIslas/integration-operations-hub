# V5 production engineering

V5 adds enough operational structure to run, observe, and verify the application as a composed service without claiming production readiness that the project has not earned yet.

## Containers and Compose

- The root `Dockerfile` builds a non-root FastAPI runtime image.
- `frontend/Dockerfile` builds Vite assets with Node 22 and serves them from Nginx.
- `docker-compose.yml` starts PostgreSQL, the API, and the frontend. PostgreSQL health gates API startup; API liveness gates frontend startup.

`docker compose up --build` exposes the frontend on port 8080 and API on port 8000. Compose credentials are local-development defaults only.

## Observability

The HTTP middleware generates or propagates `X-Correlation-ID`, returns it to callers, emits a JSON request-completion log, and records request count/duration metrics. Logs intentionally avoid request bodies, authorization headers, and API keys.

`/health` answers whether the process is alive. `/ready` verifies a `SELECT 1` database connection. `/metrics` exposes Prometheus-style request counters and duration sums.

## CI and verification

`.github/workflows/ci.yml` runs backend compilation/tests and frontend install/test/build on pull requests and `master` pushes. The system workflow test validates the integrated API path for idempotency, retry, webhook reconciliation, operation history, and metrics.

Docker was not run from this development environment because no Docker CLI is available here; `docker compose config --quiet` should be run locally or in CI as the next environment-level validation step.

## Deliberate limits

The V5 rate limiter is in-memory and per process. There is no distributed metrics backend, tracing collector, secret manager, queue, or worker yet. Those are not omissions hidden by the documentation: they are deferred until a real multi-process or asynchronous need exists in later milestones.
