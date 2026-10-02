# V10 Integration Copilot

V10 adds an optional payment-level copilot for the operational question: “Why did this payment fail?” It is not a generic chat wrapper and it does not receive unsanitized provider data.

## Grounded evidence bundle

For a payment, the service assembles:

- Current payment lifecycle state and normalized failure fields.
- Provider mapping and expected response format.
- Persisted lifecycle events.
- Sanitized request/response inspection snapshots.
- Retry-job and dead-letter state.
- Up to three recent failed payments from the same provider.

The prompt requires the model to use only this bundle, state uncertainty when evidence is missing, and never infer redacted values. The API response identifies every evidence category and count used for the explanation.

## OpenAI integration

When `OPENAI_API_KEY` is configured, the backend uses the official Python SDK and the Responses API with `store=False`. The key is read only from environment configuration and is never written to operation logs, inspection snapshots, or the database. The current default model configuration is `gpt-6-astra`; set `OPENAI_MODEL` to change it deliberately.

When no key is configured, the copilot endpoint returns `503` and the UI shows the safe error. Automated tests inject a fake client, so the test suite never sends payment evidence to an external service.

The official [OpenAI SDK documentation](https://developers.openai.com/api/docs/libraries) describes the Python SDK and Responses API setup used by this integration.

## Deliberate limits

There is no vector database, embeddings pipeline, external provider documentation ingestion, or incident-ticket connector yet. The current prior-incident context is limited to recent failed records for the same provider. Those extensions require a real information-governance and retrieval design, so V10 establishes the grounded evidence contract before adding them.
