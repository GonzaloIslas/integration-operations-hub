# Integration Operations Hub — Canonical Project Plan

Read this roadmap before planning or implementing a version. Map work to the project brief rather than inferring scope from a branch name or an abbreviated request.

## Guardrails

- Build a realistic integration-operations product incrementally; do not turn it into an architecture exercise.
- Treat the user as a senior .NET engineer learning Python, React, and TypeScript.
- Explain meaningful trade-offs in .NET terms when useful, without reteaching basic engineering concepts.
- Do not claim a technology is mastered simply because it appears in the repository.
- New work begins by pulling `master` and creating a fresh branch from it. Preserve earlier working branches, but do not use them as a base.
- End completed implementation work with verification, commit, push, and a pull request unless the user explicitly opts out.

## Current state

- [x] V1 Python backend is merged into `master`: FastAPI, payment/refund models, REST endpoints, PostgreSQL Docker configuration, and automated tests.
- [x] V2 React/TypeScript frontend is merged into `master`.
- [x] V3 replaces the earlier limited simulator with the planned five-provider integration simulation and contract tests.
- [x] V4 integration controls are implemented on `v4` and await review/merge.
- [ ] PostgreSQL migrations, shared-database safety, and the V1 API/data-model review remain deliberate follow-up work.

## V1 — Python backend

- [x] FastAPI backend, basic models, REST API, and automated tests.
- [x] Health endpoint and Docker Compose PostgreSQL configuration.
- [ ] Document the settled V1 architecture, data model, API behavior, and testing decisions.

## V2 — React / TypeScript frontend

- [x] React + TypeScript application consuming the real FastAPI API.
- [x] Dashboard, payments, integrations, sanitized operation inspection, loading/error states, and local authentication boundary.
- [x] Focused frontend tests and V2 documentation.

## V3 — Integration simulation

- [x] Five fake providers: AcmePay, BancoX, WalletPro, SlowPay, and BrokenPay.
- [x] Simulate success, authentication failure, timeout, HTTP 500, HTTP 429, malformed response, slow response, duplicate request, and differing response formats.
- [x] Provider boundary with deterministic contract tests and normalized outcomes.

## V4 — Real integration concepts

- [x] Local operator authentication and integration API keys. OAuth is deferred until a real authorization-server integration exists.
- [x] Authenticated webhook ingestion, manual retries, idempotency, fixed-window rate limiting, and offset pagination.
- [x] Error normalization, configurable timeout enforcement, data-format mapping, and correlation-aware lifecycle logs.
- [ ] Merge the reviewed `v4` work into `master` before beginning V5.

## V5 — Production engineering

- [ ] Docker/Docker Compose, structured logging, metrics, configuration, and health checks.
- [ ] CI/CD, Redis/RabbitMQ/background workers only where they solve a demonstrated need.
- [ ] Integration and system tests; production-style deployment and troubleshooting configuration.

## V6 — Operational dashboard

- [ ] Provider health, success/error rate, request latency, recent requests/failures, payment status, and retry status.

## V7 — Request inspector

- [ ] Show sanitized request headers/body and response status/body for an integration operation.
- [ ] Preserve enough context to troubleshoot failures without exposing secrets.

## V8 — Retry and asynchronous processing

- [ ] Introduce RabbitMQ, workers, retry policies, backoff, idempotency, and dead-letter behavior only after the synchronous integration flow is solid.

## V9 — Documentation and runbook

- [ ] Product overview, requirements, assumptions, architecture, API, data model, integration mapping, failure scenarios, deployment, troubleshooting, testing strategy, and ADRs.
- [ ] Make the README demonstrate relevant senior backend, integration, and full-stack project experience honestly.

## V10 — AI / Integration Copilot

- [ ] Only after the operational core works, add a grounded assistant for investigating real integration failures.
- [ ] Use retrieved requests, responses, logs, provider documentation, and prior incidents; do not build a generic chat wrapper.

## Optional .NET interoperability

- [ ] Consider a small .NET service only after the Python product is solid and only when it demonstrates a meaningful interoperability concern.
