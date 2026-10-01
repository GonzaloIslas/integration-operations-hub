# V7 request inspector

V7 makes provider interaction context inspectable without storing provider credentials or raw sensitive request data.

## Captured snapshots

Every provider outcome records a request/response snapshot alongside its lifecycle event. The snapshot contains:

- Request headers and body sent through the integration boundary.
- Response HTTP status, headers, and body returned by the simulator.
- Event type and timestamp.

Webhook processing also records the inbound provider payload and the resulting application response context.

## Redaction before persistence

The service redacts `Authorization`, `X-API-Key`, cookies, and related headers before serialization. Body keys containing `authorization`, `password`, `secret`, `token`, `api_key`, or `apikey` are replaced with `<redacted>` recursively before the database write.

This ordering is intentional: the database never contains the generated provider bearer token or the local webhook API key. The inspector endpoint only returns already-sanitized snapshots.

## Existing database compatibility

V7 includes an additive compatibility step for the five inspection columns when an existing local PostgreSQL or SQLite `operation_logs` table predates this milestone. It adds nullable columns only and does not remove or rewrite existing data. This is a safe bridge for the evolving local project; a full versioned migration framework remains planned work.

## API and UI

`GET /payments/{payment_id}/inspections` returns ordered request/response snapshots for an authenticated operator. The React payment detail page shows each snapshot in a two-column request/response layout next to the existing lifecycle timeline.

## Deliberate limits

V7 does not add user roles, audit retention policies, encrypted payload archives, external log search, or raw provider replay. Those need a genuine security and compliance model; this milestone establishes the safe inspection seam first.
