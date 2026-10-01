from uuid import uuid4

from app.messaging import (
    DEAD_LETTER_QUEUE,
    DELAY_QUEUE,
    EXCHANGE,
    RETRY_QUEUE,
    RecordingRetryPublisher,
    declare_retry_topology,
)


class RecordingChannel:
    def __init__(self) -> None:
        self.exchanges = []
        self.queues = []
        self.bindings = []

    def exchange_declare(self, **kwargs) -> None:
        self.exchanges.append(kwargs)

    def queue_declare(self, **kwargs) -> None:
        self.queues.append(kwargs)

    def queue_bind(self, **kwargs) -> None:
        self.bindings.append(kwargs)


def test_retry_topology_declares_durable_retry_delay_and_dead_letter_queues():
    channel = RecordingChannel()

    declare_retry_topology(channel)

    assert channel.exchanges == [{"exchange": EXCHANGE, "exchange_type": "direct", "durable": True}]
    assert {queue["queue"] for queue in channel.queues} == {RETRY_QUEUE, DELAY_QUEUE, DEAD_LETTER_QUEUE}


def test_recording_publisher_captures_retry_lifecycle_messages():
    publisher = RecordingRetryPublisher()
    job_id = uuid4()

    publisher.enqueue(job_id)
    publisher.schedule(job_id, 10)
    publisher.dead_letter(job_id)

    assert publisher.enqueued == [job_id]
    assert publisher.scheduled == [(job_id, 10)]
    assert publisher.dead_letters == [job_id]
