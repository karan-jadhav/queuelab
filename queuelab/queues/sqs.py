from __future__ import annotations

import json
from typing import Any

import boto3

from queuelab.config import load_settings
from queuelab.queues.base import JobPayload, QueueDepth, ReceivedJob


MAIN_QUEUE = "queuelab-main"
DLQ_QUEUE = "queuelab-dlq"


class SQSBackend:
    def __init__(
        self,
        *,
        endpoint_url: str | None = None,
        region_name: str | None = None,
        wait_time_seconds: int = 1,
        visibility_timeout_seconds: int | None = None,
    ) -> None:
        settings = load_settings()
        self.endpoint_url = endpoint_url or settings.sqs_endpoint_url
        self.region_name = region_name or settings.aws_region
        self.wait_time_seconds = wait_time_seconds
        self.visibility_timeout_seconds = visibility_timeout_seconds
        self.client = boto3.client(
            "sqs",
            endpoint_url=self.endpoint_url,
            region_name=self.region_name,
            aws_access_key_id="test",
            aws_secret_access_key="test",
        )
        self.main_queue_url: str | None = None
        self.dead_queue_url: str | None = None

    def setup(self) -> None:
        self.dead_queue_url = self._queue_url(DLQ_QUEUE)
        self.main_queue_url = self._queue_url(MAIN_QUEUE)

    def publish(self, job: JobPayload) -> None:
        self.client.send_message(
            QueueUrl=self._main_queue_url(),
            MessageBody=json.dumps(job, sort_keys=True, separators=(",", ":")),
        )

    def publish_batch(self, jobs: list[JobPayload]) -> None:
        for start in range(0, len(jobs), 10):
            entries = [
                {
                    "Id": str(index),
                    "MessageBody": json.dumps(job, sort_keys=True, separators=(",", ":")),
                }
                for index, job in enumerate(jobs[start : start + 10])
            ]
            if entries:
                self.client.send_message_batch(
                    QueueUrl=self._main_queue_url(),
                    Entries=entries,
                )

    def receive(self, max_messages: int) -> list[ReceivedJob]:
        request: dict[str, Any] = {
            "QueueUrl": self._main_queue_url(),
            "MaxNumberOfMessages": min(max_messages, 10),
            "WaitTimeSeconds": self.wait_time_seconds,
            "AttributeNames": ["ApproximateReceiveCount", "SentTimestamp"],
        }
        if self.visibility_timeout_seconds is not None:
            request["VisibilityTimeout"] = self.visibility_timeout_seconds
        response = self.client.receive_message(**request)
        messages = response.get("Messages", [])
        return [self._to_received_job(message) for message in messages]

    def ack(self, job: ReceivedJob) -> None:
        self.client.delete_message(
            QueueUrl=self._main_queue_url(),
            ReceiptHandle=job.delivery_tag,
        )

    def fail(self, job: ReceivedJob, reason: str) -> None:
        _ = job
        _ = reason
        # SQS retry is controlled by visibility timeout and redrive policy.

    def depth(self) -> QueueDepth:
        main = self.client.get_queue_attributes(
            QueueUrl=self._main_queue_url(),
            AttributeNames=[
                "ApproximateNumberOfMessages",
                "ApproximateNumberOfMessagesNotVisible",
            ],
        )
        dead = self.client.get_queue_attributes(
            QueueUrl=self._dead_queue_url(),
            AttributeNames=["ApproximateNumberOfMessages"],
        )
        main_attrs = main["Attributes"]
        dead_attrs = dead["Attributes"]
        return QueueDepth(
            ready=int(main_attrs.get("ApproximateNumberOfMessages", "0")),
            in_flight=int(main_attrs.get("ApproximateNumberOfMessagesNotVisible", "0")),
            dead=int(dead_attrs.get("ApproximateNumberOfMessages", "0")),
        )

    def close(self) -> None:
        return

    def _queue_url(self, queue_name: str) -> str:
        return self.client.get_queue_url(QueueName=queue_name)["QueueUrl"]

    def _main_queue_url(self) -> str:
        if self.main_queue_url is None:
            self.setup()
        assert self.main_queue_url is not None
        return self.main_queue_url

    def _dead_queue_url(self) -> str:
        if self.dead_queue_url is None:
            self.setup()
        assert self.dead_queue_url is not None
        return self.dead_queue_url

    def _to_received_job(self, message: dict[str, Any]) -> ReceivedJob:
        payload = json.loads(message["Body"])
        if not isinstance(payload, dict):
            raise ValueError("SQS payload must be a JSON object")

        attributes = message.get("Attributes", {})
        receive_count = int(attributes.get("ApproximateReceiveCount", "1"))
        return ReceivedJob(
            payload=payload,
            delivery_tag=message["ReceiptHandle"],
            attempt_no=receive_count,
            meta={
                "message_id": message.get("MessageId"),
                "receive_count": receive_count,
                "sent_timestamp": attributes.get("SentTimestamp"),
            },
        )
