# ADR 001: Keep V1 synchronous and provider-free

## Decision

V1 records integration operations but does not call a provider. It uses synchronous SQLAlchemy sessions and creates database tables at startup only as a local-development convenience.

## Why

The first learning objective is a coherent Python API, validation, persistence, tests, and transaction boundaries. Introducing `httpx`, background workers, migrations, and retry semantics together would obscure those fundamentals.

## Consequences

`pending` is currently a truthful state: no provider outcome has been obtained. V2 will introduce provider adapters and a transition to `succeeded`/`failed`; Alembic should replace `create_all` before shared deployment.
