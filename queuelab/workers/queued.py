from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from time import perf_counter, sleep
from typing import Any

from queuelab.db import ExperimentRepository, ExperimentRun, connect
from queuelab.queues.base import QueueBackend, ReceivedJob
from queuelab.queues.rabbitmq import RabbitMQBackend
from queuelab.workers.direct import _count_lines, _iter_jobs


@dataclass(frozen=True)
class QueuedRunResult:
    run_id: str
    backend: str
    total_attempts: int
    processed_jobs: int
    duplicate_jobs: int
    failed_jobs: int


def run_rabbitmq(
    *,
    dataset: Path,
    run_id: str,
    experiment_id: str = "dev_rabbitmq",
    batch_size: int = 10,
    prefetch_count: int = 10,
    worker_id: str = "rabbitmq-1",
) -> QueuedRunResult:
    backend = RabbitMQBackend(prefetch_count=prefetch_count)
    return run_queued(
        backend_name="rabbitmq",
        queue=backend,
        dataset=dataset,
        run_id=run_id,
        experiment_id=experiment_id,
        batch_size=batch_size,
        worker_id=worker_id,
        queue_config={"prefetch_count": prefetch_count},
    )


def run_queued(
    *,
    backend_name: str,
    queue: QueueBackend,
    dataset: Path,
    run_id: str,
    experiment_id: str,
    batch_size: int,
    worker_id: str,
    queue_config: dict[str, Any] | None = None,
) -> QueuedRunResult:
    job_count = _count_lines(dataset)
    total_attempts = 0
    processed_jobs = 0
    duplicate_jobs = 0
    failed_jobs = 0

    try:
        queue.setup()
        queue.publish_batch(list(_iter_jobs(dataset)))

        with connect() as connection:
            repository = ExperimentRepository(connection)
            repository.create_run(
                ExperimentRun(
                    run_id=run_id,
                    experiment_id=experiment_id,
                    backend=backend_name,
                    dataset_name=dataset.name,
                    job_count_target=job_count,
                    worker_count=1,
                    batch_size=batch_size,
                    queue_config=queue_config or {},
                )
            )

            while total_attempts < job_count:
                received_jobs = queue.receive(batch_size)
                if not received_jobs:
                    sleep(0.1)
                    continue

                for received_job in received_jobs:
                    total_attempts += 1
                    try:
                        inserted, processing_ms, db_write_ms = _process_received_job(
                            repository=repository,
                            received_job=received_job,
                            run_id=run_id,
                            worker_id=worker_id,
                        )
                        if inserted:
                            processed_jobs += 1
                            status = "success"
                        else:
                            duplicate_jobs += 1
                            status = "duplicate"

                        repository.record_attempt(
                            run_id=run_id,
                            job_id=_required_job_id(received_job.payload),
                            backend=backend_name,
                            worker_id=worker_id,
                            attempt_no=received_job.attempt_no,
                            status=status,
                            processing_ms=processing_ms,
                            db_write_ms=db_write_ms,
                            message_meta=received_job.meta,
                        )
                        connection.commit()
                        queue.ack(received_job)
                    except Exception as exc:
                        failed_jobs += 1
                        repository.record_attempt(
                            run_id=run_id,
                            job_id=_best_effort_job_id(received_job),
                            backend=backend_name,
                            worker_id=worker_id,
                            attempt_no=received_job.attempt_no,
                            status="failed",
                            processing_ms=0,
                            db_write_ms=0,
                            message_meta=received_job.meta,
                            error_type=type(exc).__name__,
                            error_message=str(exc),
                        )
                        connection.commit()
                        queue.fail(received_job, reason=str(exc))

            repository.finish_run(run_id)
            connection.commit()
    finally:
        queue.close()

    return QueuedRunResult(
        run_id=run_id,
        backend=backend_name,
        total_attempts=total_attempts,
        processed_jobs=processed_jobs,
        duplicate_jobs=duplicate_jobs,
        failed_jobs=failed_jobs,
    )


def _process_received_job(
    *,
    repository: ExperimentRepository,
    received_job: ReceivedJob,
    run_id: str,
    worker_id: str,
) -> tuple[bool, int, int]:
    started = perf_counter()
    db_started = perf_counter()
    inserted = repository.insert_processed_job(
        run_id=run_id,
        job_id=_required_job_id(received_job.payload),
        worker_id=worker_id,
        result_hash=_result_hash(received_job.payload),
    )
    db_write_ms = _elapsed_ms(db_started)
    processing_ms = _elapsed_ms(started)
    return inserted, processing_ms, db_write_ms


def _required_job_id(job: dict[str, Any]) -> str:
    job_id = job.get("job_id")
    if not isinstance(job_id, str) or not job_id:
        raise ValueError("job is missing required field: job_id")
    return job_id


def _best_effort_job_id(received_job: ReceivedJob) -> str:
    try:
        return _required_job_id(received_job.payload)
    except ValueError:
        return "unknown"


def _result_hash(job: dict[str, Any]) -> str:
    payload = json.dumps(job, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _elapsed_ms(started: float) -> int:
    return int((perf_counter() - started) * 1000)
