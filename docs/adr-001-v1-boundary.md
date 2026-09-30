# ADR 001: Keep V1 synchronous and provider-free

## Decision

V1 records integration operations and uses synchronous SQLAlchemy sessions. It creates database tables at startup only as a local-development convenience.

## Why

The first learning objective is a coherent Python API, validation, persistence, tests, and transaction boundaries. Introducing `httpx`, background workers, migrations, and retry semantics together would obscure those fundamentals.

## Consequences

The original planned V2 is the React/TypeScript frontend; provider adapters belong to V3 and real integration concerns to V4. A limited provider simulator was merged into `master` ahead of that plan and is deliberately preserved, but it does not change the roadmap or constitute completed V3 work. Alembic should replace `create_all` before shared deployment.
