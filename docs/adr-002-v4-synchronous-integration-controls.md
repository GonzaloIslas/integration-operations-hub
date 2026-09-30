# ADR 002: Keep V4 controls synchronous and local

## Decision

Use local Basic/API-key authentication, an in-memory fixed-window limiter, synchronous manual retry, and synchronous webhook processing for V4.

## Why

This milestone is about the behavior of integration controls: idempotency, rate limiting, retries, timeouts, and webhook replay. Adding Redis, RabbitMQ, a secrets manager, and OAuth without an actual deployment or provider would hide those concepts behind infrastructure.

## Consequences

V4 is suitable for local learning and contract testing, not horizontal production deployment. V5/V8 must replace in-memory and synchronous mechanisms with infrastructure that fits demonstrated production requirements.
