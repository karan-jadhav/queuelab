from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


JobPayload = dict[str, Any]


@dataclass(frozen=True)
class ReceivedJob:
    payload: JobPayload
    delivery_tag: Any
    attempt_no: int = 1
    meta: dict[str, Any] | None = None


@dataclass(frozen=True)
class QueueDepth:
    ready: int
    in_flight: int = 0
    dead: int = 0


class QueueBackend(Protocol):
    def setup(self) -> None:
        """Create or verify backend resources."""

    def publish(self, job: JobPayload) -> None:
        """Publish one job."""

    def publish_batch(self, jobs: list[JobPayload]) -> None:
        """Publish a batch of jobs."""

    def receive(self, max_messages: int) -> list[ReceivedJob]:
        """Receive up to max_messages jobs without acknowledging them."""

    def ack(self, job: ReceivedJob) -> None:
        """Mark a received job as complete."""

    def fail(self, job: ReceivedJob, reason: str) -> None:
        """Mark a received job as failed."""

    def dead_letter(self, job: ReceivedJob, reason: str) -> None:
        """Move a received job to a terminal dead-letter state."""

    def depth(self) -> QueueDepth:
        """Return queue depth information."""

    def close(self) -> None:
        """Close backend resources."""
