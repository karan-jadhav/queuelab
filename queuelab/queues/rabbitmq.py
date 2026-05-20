from __future__ import annotations

import json
from typing import Any

import pika
from pika.adapters.blocking_connection import BlockingChannel
from pika.spec import Basic, BasicProperties

from queuelab.config import load_settings
from queuelab.queues.base import JobPayload, QueueDepth, ReceivedJob


EXCHANGE = "queuelab.jobs"
ROUTING_KEY = "job"
MAIN_QUEUE = "queuelab.jobs.main"
DLX = "queuelab.jobs.dlx"
DEAD_ROUTING_KEY = "dead"
DEAD_QUEUE = "queuelab.jobs.dead"


class RabbitMQBackend:
    def __init__(self, url: str | None = None, prefetch_count: int = 10) -> None:
        settings = load_settings()
        self.url = url or settings.rabbitmq_url
        self.prefetch_count = prefetch_count
        self.connection: pika.BlockingConnection | None = None
        self.channel: BlockingChannel | None = None

    def setup(self) -> None:
        channel = self._channel()
        channel.exchange_declare(exchange=EXCHANGE, exchange_type="direct", durable=True)
        channel.exchange_declare(exchange=DLX, exchange_type="direct", durable=True)
        channel.queue_declare(
            queue=MAIN_QUEUE,
            durable=True,
            arguments={
                "x-dead-letter-exchange": DLX,
                "x-dead-letter-routing-key": DEAD_ROUTING_KEY,
            },
        )
        channel.queue_declare(queue=DEAD_QUEUE, durable=True)
        channel.queue_bind(queue=MAIN_QUEUE, exchange=EXCHANGE, routing_key=ROUTING_KEY)
        channel.queue_bind(queue=DEAD_QUEUE, exchange=DLX, routing_key=DEAD_ROUTING_KEY)
        channel.basic_qos(prefetch_count=self.prefetch_count)

    def publish(self, job: JobPayload) -> None:
        self._publish(job, headers={})

    def _publish(self, job: JobPayload, headers: dict[str, object]) -> None:
        self._channel().basic_publish(
            exchange=EXCHANGE,
            routing_key=ROUTING_KEY,
            body=json.dumps(job, sort_keys=True, separators=(",", ":")).encode(),
            properties=BasicProperties(
                content_type="application/json",
                delivery_mode=2,
                headers=headers,
            ),
            mandatory=True,
        )

    def publish_batch(self, jobs: list[JobPayload]) -> None:
        for job in jobs:
            self.publish(job)

    def receive(self, max_messages: int) -> list[ReceivedJob]:
        jobs: list[ReceivedJob] = []
        channel = self._channel()
        for _ in range(max_messages):
            method, properties, body = channel.basic_get(queue=MAIN_QUEUE, auto_ack=False)
            if method is None or body is None:
                break
            jobs.append(self._to_received_job(method, properties, body))
        return jobs

    def ack(self, job: ReceivedJob) -> None:
        self._channel().basic_ack(delivery_tag=job.delivery_tag)

    def fail(self, job: ReceivedJob, reason: str) -> None:
        _ = reason
        self._publish(
            job.payload,
            headers={"x-queuelab-attempt": job.attempt_no + 1},
        )
        self._channel().basic_ack(delivery_tag=job.delivery_tag)

    def dead_letter(self, job: ReceivedJob, reason: str) -> None:
        _ = reason
        self._channel().basic_reject(delivery_tag=job.delivery_tag, requeue=False)

    def depth(self) -> QueueDepth:
        channel = self._channel()
        main = channel.queue_declare(queue=MAIN_QUEUE, durable=True, passive=True)
        dead = channel.queue_declare(queue=DEAD_QUEUE, durable=True, passive=True)
        return QueueDepth(
            ready=main.method.message_count,
            dead=dead.method.message_count,
        )

    def close(self) -> None:
        if self.channel is not None and self.channel.is_open:
            self.channel.close()
        if self.connection is not None and self.connection.is_open:
            self.connection.close()

    def _channel(self) -> BlockingChannel:
        if self.connection is None or self.connection.is_closed:
            parameters = pika.URLParameters(self.url)
            self.connection = pika.BlockingConnection(parameters)
        if self.channel is None or self.channel.is_closed:
            self.channel = self.connection.channel()
        return self.channel

    def _to_received_job(
        self,
        method: Basic.GetOk,
        properties: BasicProperties,
        body: bytes,
    ) -> ReceivedJob:
        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise ValueError("RabbitMQ payload must be a JSON object")
        headers = properties.headers or {}
        attempt_no = int(headers.get("x-queuelab-attempt", 1))
        return ReceivedJob(
            payload=payload,
            delivery_tag=method.delivery_tag,
            attempt_no=attempt_no,
            meta={
                "redelivered": method.redelivered,
                "exchange": method.exchange,
                "routing_key": method.routing_key,
                "content_type": properties.content_type,
                "attempt_no": attempt_no,
            },
        )
