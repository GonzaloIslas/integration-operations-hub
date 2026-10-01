import logging
from uuid import UUID

from app.config import get_settings
from app.database import SessionLocal
from app.messaging import RabbitMQRetryPublisher, consume_retry_jobs
from app.models import RetryJobStatus
from app.services import RetryJobNotFoundError, process_retry_job

logger = logging.getLogger(__name__)


def handle_retry_job(job_id: UUID) -> None:
    with SessionLocal() as session:
        try:
            job = process_retry_job(session, job_id)
        except RetryJobNotFoundError:
            logger.warning("retry.worker_job_missing", extra={"job_id": str(job_id)})
            return
    publisher = RabbitMQRetryPublisher.from_settings()
    if job.status == RetryJobStatus.RETRY_SCHEDULED:
        delay_seconds = get_settings().retry_initial_backoff_seconds * (2 ** (job.attempts - 1))
        publisher.schedule(job.id, delay_seconds)
    elif job.status == RetryJobStatus.DEAD_LETTER:
        publisher.dead_letter(job.id)


if __name__ == "__main__":
    consume_retry_jobs(handle_retry_job)
