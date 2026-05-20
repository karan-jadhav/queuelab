from __future__ import annotations

from typing import Any
from uuid import uuid4

from psycopg.types.json import Jsonb

from queuelab.db import connect
from queuelab.queues.base import JobPayload, QueueDepth, ReceivedJob


class PostgresQueueBackend:
    def __init__(
        self,
        *,
        run_id: str,
        worker_name: str | None = None,
        max_attempts: int = 3,
        lease_timeout_seconds: int = 30,
    ) -> None:
        self.run_id = run_id
        self.worker_name = worker_name or f"pgqueue-{uuid4().hex[:8]}"
        self.max_attempts = max_attempts
        self.lease_timeout_seconds = lease_timeout_seconds
        self.connection = connect()

    def setup(self) -> None:
        return

    def publish(self, job: JobPayload) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO pg_queue_jobs (
                  run_id,
                  job_id,
                  payload,
                  max_attempts
                )
                VALUES (%s, %s, %s, %s)
                """,
                (
                    self.run_id,
                    self._required_job_id(job),
                    Jsonb(job),
                    self.max_attempts,
                ),
            )
        self.connection.commit()

    def publish_batch(self, jobs: list[JobPayload]) -> None:
        with self.connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO pg_queue_jobs (
                  run_id,
                  job_id,
                  payload,
                  max_attempts
                )
                VALUES (%s, %s, %s, %s)
                """,
                [
                    (
                        self.run_id,
                        self._required_job_id(job),
                        Jsonb(job),
                        self.max_attempts,
                    )
                    for job in jobs
                ],
            )
        self.connection.commit()

    def receive(self, max_messages: int) -> list[ReceivedJob]:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE pg_queue_jobs
                SET status = 'queued',
                    locked_by = NULL,
                    locked_at = NULL,
                    run_at = clock_timestamp()
                WHERE run_id = %s
                  AND status = 'leased'
                  AND locked_at < clock_timestamp() - make_interval(secs => %s)
                """,
                (self.run_id, self.lease_timeout_seconds),
            )
            cursor.execute(
                """
                WITH next_jobs AS (
                  SELECT id
                  FROM pg_queue_jobs
                  WHERE run_id = %s
                    AND status = 'queued'
                    AND run_at <= clock_timestamp()
                  ORDER BY priority ASC, run_at ASC, id ASC
                  FOR UPDATE SKIP LOCKED
                  LIMIT %s
                )
                UPDATE pg_queue_jobs AS queue
                SET
                  status = 'leased',
                  locked_by = %s,
                  locked_at = clock_timestamp(),
                  attempts = queue.attempts + 1,
                  error_message = NULL
                FROM next_jobs
                WHERE queue.id = next_jobs.id
                RETURNING
                  queue.id,
                  queue.payload,
                  queue.attempts,
                  queue.locked_by,
                  queue.locked_at
                """,
                (self.run_id, max_messages, self.worker_name),
            )
            rows = cursor.fetchall()
        self.connection.commit()
        return [self._to_received_job(row) for row in rows]

    def ack(self, job: ReceivedJob) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE pg_queue_jobs
                SET status = 'finished',
                    finished_at = clock_timestamp()
                WHERE id = %s
                  AND status = 'leased'
                """,
                (job.delivery_tag,),
            )
        self.connection.commit()

    def fail(self, job: ReceivedJob, reason: str) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE pg_queue_jobs
                SET status = CASE
                      WHEN attempts >= max_attempts THEN 'dead'
                      ELSE 'queued'
                    END,
                    locked_by = NULL,
                    locked_at = NULL,
                    run_at = clock_timestamp(),
                    error_message = %s
                WHERE id = %s
                  AND status = 'leased'
                """,
                (reason, job.delivery_tag),
            )
        self.connection.commit()

    def depth(self) -> QueueDepth:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                  count(*) FILTER (WHERE status = 'queued') AS ready,
                  count(*) FILTER (WHERE status = 'leased') AS in_flight,
                  count(*) FILTER (WHERE status = 'dead') AS dead
                FROM pg_queue_jobs
                WHERE run_id = %s
                """,
                (self.run_id,),
            )
            row = cursor.fetchone()
        return QueueDepth(
            ready=int(row["ready"] or 0),
            in_flight=int(row["in_flight"] or 0),
            dead=int(row["dead"] or 0),
        )

    def close(self) -> None:
        self.connection.close()

    def _to_received_job(self, row: dict[str, Any]) -> ReceivedJob:
        return ReceivedJob(
            payload=dict(row["payload"]),
            delivery_tag=row["id"],
            attempt_no=row["attempts"],
            meta={
                "queue_row_id": row["id"],
                "locked_by": row["locked_by"],
                "locked_at": row["locked_at"].isoformat() if row["locked_at"] else None,
            },
        )

    def _required_job_id(self, job: JobPayload) -> str:
        job_id = job.get("job_id")
        if not isinstance(job_id, str) or not job_id:
            raise ValueError("job is missing required field: job_id")
        return job_id
