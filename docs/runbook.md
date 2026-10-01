# Troubleshooting runbook

## First checks

```powershell
docker compose ps
curl http://localhost:8000/health
curl http://localhost:8000/ready
docker compose logs --tail 100 api worker rabbitmq
```

Use the React dashboard at `http://localhost:8080` to inspect provider health and retry state. Use payment details to inspect correlation IDs, lifecycle events, retries, and sanitized request/response snapshots.

## Common procedures

### API is unhealthy

Check `docker compose ps` and API logs. If `/health` works but `/ready` returns `503`, inspect PostgreSQL status and credentials. Do not delete the database volume as a first response.

### Retry stays queued

Verify RabbitMQ is healthy and the worker container is running. Review `docker compose logs worker rabbitmq`. Retry jobs are stored in PostgreSQL, so a broker outage does not erase the job state.

### Retry is dead-lettered

Open the payment retry history and inspector. Confirm attempt count and last normalized error. Review the dead-letter queue through RabbitMQ management (`http://localhost:15672`, local `guest`/`guest` only), then decide whether a fixed provider/configuration issue justifies a new retry.

### Provider failure investigation

Locate the payment by ID or correlation ID. Inspect the sanitized provider request/response snapshot, normalized failure code, provider health state, and prior retries. Never paste real credentials into the snapshot or logs.

### Start or stop the stack

```powershell
docker compose up --build
docker compose down
```

`docker compose down` stops containers but preserves named/anonymous volumes unless `-v` is added. Use volume removal only when intentionally resetting local demo data.
