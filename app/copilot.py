import json
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import OperationLog, Payment, PaymentStatus, RetryJob
from app.providers import get_provider_definition
from app.services import get_payment, get_payment_inspections, get_retry_jobs

GROUNDING_INSTRUCTIONS = """You are an integration operations copilot. Explain only what the supplied evidence establishes.
Do not invent provider behavior, credentials, request fields, incidents, or remediation steps. Clearly say when evidence is missing.
Treat sanitized snapshots as authoritative; never request or infer redacted values. Give a concise diagnosis, evidence-based next steps,
and uncertainty where relevant."""


class CopilotUnavailableError(Exception):
    pass


class CopilotClient(Protocol):
    model: str

    def explain(self, question: str, evidence: dict[str, object]) -> str: ...


class OpenAICopilotClient:
    def __init__(self, api_key: str, model: str) -> None:
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key)
        self.model = model

    def explain(self, question: str, evidence: dict[str, object]) -> str:
        from openai import OpenAIError

        try:
            response = self.client.responses.create(
                model=self.model,
                instructions=GROUNDING_INSTRUCTIONS,
                input=json.dumps({"question": question, "evidence": evidence}, default=str),
                store=False,
            )
        except OpenAIError as error:
            raise CopilotUnavailableError("Copilot request failed. Verify the OpenAI configuration and try again.") from error
        if not response.output_text:
            raise CopilotUnavailableError("The model returned no explanation.")
        return response.output_text


@dataclass(frozen=True)
class CopilotResult:
    answer: str
    sources: list[dict[str, object]]
    model: str


def get_copilot_client() -> CopilotClient:
    settings = get_settings()
    if not settings.openai_api_key:
        raise CopilotUnavailableError("Copilot is unavailable until OPENAI_API_KEY is configured.")
    return OpenAICopilotClient(settings.openai_api_key, settings.openai_model)


def explain_payment(session: Session, payment_id, question: str, client: CopilotClient) -> CopilotResult:
    payment = get_payment(session, payment_id)
    operations = list(
        session.scalars(select(OperationLog).where(OperationLog.payment_id == payment.id).order_by(OperationLog.created_at.asc()))
    )
    inspections = get_payment_inspections(session, payment.id)
    retry_jobs = get_retry_jobs(session, payment.id)
    provider = get_provider_definition(payment.provider)
    prior_failures = list(
        session.scalars(
            select(Payment)
            .where(
                Payment.provider == payment.provider,
                Payment.status == PaymentStatus.FAILED,
                Payment.id != payment.id,
            )
            .order_by(Payment.created_at.desc())
            .limit(3)
        )
    )
    evidence = {
        "payment": _payment_evidence(payment),
        "provider_mapping": {
            "name": provider.display_name if provider else payment.provider,
            "description": provider.description if provider else "No configured provider mapping.",
            "response_format": provider.response_format if provider else None,
        },
        "operation_events": [_operation_evidence(operation) for operation in operations],
        "inspections": inspections,
        "retry_jobs": [_retry_evidence(job) for job in retry_jobs],
        "prior_same_provider_failures": [_payment_evidence(failure) for failure in prior_failures],
    }
    answer = client.explain(question, evidence)
    session.add(
        OperationLog(
            payment_id=payment.id,
            event_type="copilot.explanation_requested",
            detail=json.dumps({"question": question, "model": client.model, "grounded": True}),
        )
    )
    session.commit()
    return CopilotResult(
        answer=answer,
        model=client.model,
        sources=[
            {"kind": "payment", "count": 1, "description": "Current payment lifecycle and normalized outcome."},
            {"kind": "operations", "count": len(operations), "description": "Persisted lifecycle events."},
            {"kind": "inspections", "count": len(inspections), "description": "Sanitized request and response snapshots."},
            {"kind": "retry_jobs", "count": len(retry_jobs), "description": "Durable retry and dead-letter state."},
            {"kind": "prior_failures", "count": len(prior_failures), "description": "Recent failures for the same provider."},
            {"kind": "provider_mapping", "count": 1, "description": "Configured simulator behavior and response format."},
        ],
    )


def _payment_evidence(payment: Payment) -> dict[str, object]:
    return {
        "id": str(payment.id),
        "provider": payment.provider,
        "status": payment.status,
        "correlation_id": payment.correlation_id,
        "provider_reference": payment.provider_reference,
        "failure_code": payment.failure_code,
        "failure_message": payment.failure_message,
        "retryable": payment.retryable,
    }


def _operation_evidence(operation: OperationLog) -> dict[str, object]:
    return {"event_type": operation.event_type, "detail": operation.detail, "created_at": operation.created_at}


def _retry_evidence(job: RetryJob) -> dict[str, object]:
    return {
        "status": job.status,
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
        "next_attempt_at": job.next_attempt_at,
        "last_error": job.last_error,
    }
