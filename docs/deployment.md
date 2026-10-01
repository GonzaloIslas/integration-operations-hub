# Deployment

## Local Compose topology

`docker compose up --build` starts:

| Service | Local port | Responsibility |
| --- | --- | --- |
| `frontend` | 8080 | React build served by Nginx. |
| `api` | 8000 | FastAPI API, health, readiness, and metrics. |
| `db` | 5432 | PostgreSQL persistence. |
| `rabbitmq` | 5672 / 15672 | AMQP broker and local management UI. |
| `worker` | none | RabbitMQ retry consumer. |

The API waits for PostgreSQL and RabbitMQ health checks. The frontend waits for API liveness. Worker waits for PostgreSQL and RabbitMQ.

## Configuration

Use environment variables or a non-committed `.env` file. Important values include database URL, API credentials, RabbitMQ URL, provider timeout, rate limit, retry max attempts, and initial retry backoff. The Compose file contains local-only defaults and must not be copied as a production secrets pattern.

## Production readiness gaps

Before a real deployment, add versioned migrations, managed secret storage, TLS/ingress configuration, production image scanning, backup/recovery, a transactional outbox, distributed rate limits, queue monitoring, alerting, and deployment-specific configuration policy.
