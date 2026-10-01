import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

import pika

from app.config import get_settings

logger = logging.getLogger(__name__)

EXCHANGE = "integration.operations"
RETRY_ROUTING_KEY = "retry"
DELAY_ROUTING_KEY = "retry.delay"
DEAD_LETTER_ROUTING_KEY = "retry.dead_letter"
RETRY_QUEUE = "integration.retry"
DELAY_QUEUE = "integration.retry.delay"
DEAD_LETTER_QUEUE = "integration.retry.dead_letter"


class MessagingUnavailableError(Exception):
    pass


class RetryPublisher(Protocol):
    def enqueue(self, job_id: UUID) -> None: ...

    def schedule(self, job_id: UUID, delay_seconds: int) -> None: ...

    def dead_letter(self, job_id: UUID) -> None: ...


class RabbitMQRetryPublisher:
    def __init__(self, url: str) -> None:
        self.url = url

    @classmethod
    def from_settings(cls) -> "RabbitMQRetryPublisher":
        return cls(get_settings().rabbitmq_url)

    def enqueue(self, job_id: UUID) -> None:
        self._publish(RETRY_ROUTING_KEY, job_id)

    def schedule(self, job_id: UUID, delay_seconds: int) -> None:
        self._publish(DELAY_ROUTING_KEY, job_id, expiration=str(delay_seconds * 1_000))

    def dead_letter(self, job_id: UUID) -> None:
        self._publish(DEAD_LETTER_ROUTING_KEY, job_id)

    def _publish(self, routing_key: str, job_id: UUID, expiration: str | None = None) -> None:
        try:
            connection = pika.BlockingConnection(pika.URLParameters(self.url))
            channel = connection.channel()
            declare_retry_topology(channel)
            channel.basic_publish(
                exchange=EXCHANGE,
                routing_key=routing_key,
                body=json.dumps({"job_id": str(job_id)}),
                properties=pika.BasicProperties(delivery_mode=2, content_type="application/json", expiration=expiration),
            )
            connection.close()
        except pika.exceptions.AMQPError as error:
            raise MessagingUnavailableError("RabbitMQ is unavailable.") from error


@dataclass
class RecordingRetryPublisher:
    enqueued: list[UUID] = field(default_factory=list)
    scheduled: list[tuple[UUID, int]] = field(default_factory=list)
    dead_letters: list[UUID] = field(default_factory=list)

    def enqueue(self, job_id: UUID) -> None:
        self.enqueued.append(job_id)

    def schedule(self, job_id: UUID, delay_seconds: int) -> None:
        self.scheduled.append((job_id, delay_seconds))

    def dead_letter(self, job_id: UUID) -> None:
        self.dead_letters.append(job_id)


def declare_retry_topology(channel: pika.adapters.blocking_connection.BlockingChannel) -> None:
    channel.exchange_declare(exchange=EXCHANGE, exchange_type="direct", durable=True)
    channel.queue_declare(queue=RETRY_QUEUE, durable=True)
    channel.queue_bind(queue=RETRY_QUEUE, exchange=EXCHANGE, routing_key=RETRY_ROUTING_KEY)
    channel.queue_declare(
        queue=DELAY_QUEUE,
        durable=True,
        arguments={"x-dead-letter-exchange": EXCHANGE, "x-dead-letter-routing-key": RETRY_ROUTING_KEY},
    )
    channel.queue_bind(queue=DELAY_QUEUE, exchange=EXCHANGE, routing_key=DELAY_ROUTING_KEY)
    channel.queue_declare(queue=DEAD_LETTER_QUEUE, durable=True)
    channel.queue_bind(queue=DEAD_LETTER_QUEUE, exchange=EXCHANGE, routing_key=DEAD_LETTER_ROUTING_KEY)


def get_retry_publisher() -> RetryPublisher:
    return RabbitMQRetryPublisher(get_settings().rabbitmq_url)


def consume_retry_jobs(handler: Callable[[UUID], None]) -> None:
    connection = pika.BlockingConnection(pika.URLParameters(get_settings().rabbitmq_url))
    channel = connection.channel()
    declare_retry_topology(channel)

    def on_message(channel, method, _properties, body: bytes) -> None:
        job_id = UUID(json.loads(body)["job_id"])
        try:
            handler(job_id)
            channel.basic_ack(delivery_tag=method.delivery_tag)
        except Exception:
            logger.exception("retry.worker_job_failed", extra={"job_id": str(job_id)})
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=RETRY_QUEUE, on_message_callback=on_message)
    channel.start_consuming()
