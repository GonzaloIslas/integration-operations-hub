# Integration Operations Hub — Canonical Project Plan

This file is the implementation checklist derived from the original project brief. Read it before proposing, planning, or implementing work. Do not infer a version's scope from a branch name or from a terse request such as “V2”; confirm it against this plan first.

## Project guardrails

- Build a realistic integration-operations product incrementally; do not turn it into an architecture exercise.
- Treat the user as a senior .NET engineer learning Python and React, not as a beginner programmer.
- Explain Python/React trade-offs in .NET terms when useful, without reteaching basic engineering concepts.
- Do not claim a technology is mastered simply because it appears in the repository.
- Do not silently alter the agreed version scope. When a request is ambiguous, identify the mapped roadmap step before implementation.

## Current state and required correction

- [x] V1 backend foundation is on `master`: FastAPI, payment/refund models, REST endpoints, PostgreSQL Docker configuration, and tests.
- [x] The prior `v2` provider-simulation work was merged into `master` and is preserved as requested.
- [ ] Do not present that provider work as true V2 or as complete V3. It is an out-of-sequence, limited implementation that needs deliberate V3 review later.
- [ ] Review V1 against the brief before calling it complete: PostgreSQL migrations, test strategy, and API shape still need deliberate decisions.

## V1 — Python backend

- [x] FastAPI backend, basic models, REST API, and automated tests.
- [x] Health endpoint and Docker Compose PostgreSQL configuration.
- [ ] Validate the initial API and data-model decisions against the product requirements; keep V1 small and useful.
- [ ] Document the V1 architecture, data model, API behavior, and testing decisions.

## V2 — React / TypeScript frontend

- [ ] Create a React + TypeScript application that consumes the real FastAPI API.
- [ ] Dashboard view.
- [ ] Payments list and payment-details views.
- [ ] Integration list and integration-details views.
- [ ] Request/response inspection UI.
- [ ] Loading, validation, and error states.
- [ ] Basic authentication only when the backend contract is ready.
- [ ] Add focused frontend tests and document the frontend structure.

## V3 — Integration simulation

- [ ] Review the limited simulator code already on `master`, then expand or replace it intentionally.
- [ ] Build fake providers: AcmePay, BancoX, WalletPro, SlowPay, and BrokenPay.
- [ ] Model realistic outcomes: success, authentication failure, timeout, HTTP 500, HTTP 429, malformed response, slow response, duplicate request, and differing response formats.
- [ ] Add an integration layer and provider-focused contract tests.

## V4 — Real integration concepts

- [ ] API authentication and API keys; OAuth where it genuinely fits.
- [ ] Webhooks, retries, idempotency, rate limiting, pagination, and data mapping/transformation.
- [ ] Error normalization, timeout handling, and correlation IDs across the actual integration boundary.

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
