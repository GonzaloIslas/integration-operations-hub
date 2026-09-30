# ADR 001: Keep V1 synchronous and provider-free

## Decision

V1 records integration operations and uses synchronous SQLAlchemy sessions. It creates database tables at startup only as a local-development convenience.

## Why

The first learning objective is a coherent Python API, validation, persistence, tests, and transaction boundaries. Introducing `httpx`, background workers, migrations, and retry semantics together would obscure those fundamentals.

## Consequences

The planned V2 is the React/TypeScript frontend. V3 introduces deterministic provider simulation; V4 will add real integration concepts. Alembic should replace `create_all` before shared deployment.
