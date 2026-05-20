from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from time import perf_counter, sleep
from threading import Lock, Thread
from typing import Any

from queuelab import metrics
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


@dataclass
class _RunCounters:
    total_attempts: int = 0
    reserved_attempts: int = 0
    processed_jobs: int = 0
    duplicate_jobs: int = 0
    failed_jobs: int = 0


def run_rabbitmq(
    *,
    dataset: Path,
    run_id: str,
    experiment_id: str = "dev_rabbitmq",
    batch_size: int = 10,
    prefetch_count: int = 10,
    workers: int = 1,
) -> QueuedRunResult:
    return run_queued(
        backend_name="rabbitmq",
        queue_factory=lambda: RabbitMQBackend(prefetch_count=prefetch_count),
        dataset=dataset,
        run_id=run_id,
        experiment_id=experiment_id,
        batch_size=batch_size,
        workers=workers,
        queue_config={"prefetch_count": prefetch_count},
    )


def run_queued(
    *,
    backend_name: str,
    queue_factory: Any,
    dataset: Path,
    run_id: str,
    experiment_id: str,
    batch_size: int,
    workers: int,
    queue_config: dict[str, Any] | None = None,
) -> QueuedRunResult:
    if workers < 1:
        raise ValueError("workers must be at least 1")

    job_count = _count_lines(dataset)
    counters = _RunCounters()
    lock = Lock()

    queue = queue_factory()
    try:
        queue.setup()
        jobs = list(_iter_jobs(dataset))
        queue.publish_batch(jobs)
        metrics.JOBS_PUBLISHED.labels(run_id=run_id, backend=backend_name).inc(len(jobs))
    finally:
        queue.close()

    with connect() as connection:
        repository = ExperimentRepository(connection)
        repository.create_run(
            ExperimentRun(
                run_id=run_id,
                experiment_id=experiment_id,
                backend=backend_name,
                dataset_name=dataset.name,
                job_count_target=job_count,
                worker_count=workers,
                batch_size=batch_size,
                queue_config=queue_config or {},
            )
        )
        connection.commit()

    threads = [
        Thread(
            target=_run_worker,
            kwargs={
                "backend_name": backend_name,
                "queue_factory": queue_factory,
                "run_id": run_id,
                "worker_id": f"{backend_name}-{worker_index + 1}",
                "batch_size": batch_size,
                "job_count": job_count,
                "counters": counters,
                "lock": lock,
            },
        )
        for worker_index in range(workers)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    with connect() as connection:
        repository = ExperimentRepository(connection)
        repository.finish_run(run_id)
        connection.commit()

    return QueuedRunResult(
        run_id=run_id,
        backend=backend_name,
        total_attempts=counters.total_attempts,
        processed_jobs=counters.processed_jobs,
        duplicate_jobs=counters.duplicate_jobs,
        failed_jobs=counters.failed_jobs,
    )


def _run_worker(
    *,
    backend_name: str,
    queue_factory: Any,
    run_id: str,
    worker_id: str,
    batch_size: int,
    job_count: int,
    counters: _RunCounters,
    lock: Lock,
) -> None:
    queue = queue_factory()
    try:
        queue.setup()
        with connect() as connection:
            repository = ExperimentRepository(connection)
            while True:
                with lock:
                    remaining = job_count - counters.total_attempts - counters.reserved_attempts
                    if remaining <= 0:
                        return
                    receive_limit = min(batch_size, remaining)
                    counters.reserved_attempts += receive_limit

                received_jobs = queue.receive(receive_limit)
                if not received_jobs:
                    with lock:
                        counters.reserved_attempts -= receive_limit
                    sleep(0.1)
                    continue

                if len(received_jobs) < receive_limit:
                    with lock:
                        counters.reserved_attempts -= receive_limit - len(received_jobs)

                for received_job in received_jobs:
                    metrics.JOBS_RECEIVED.labels(run_id=run_id, backend=backend_name).inc()
                    with lock:
                        counters.total_attempts += 1
                        counters.reserved_attempts -= 1

                    try:
                        inserted, processing_ms, db_write_ms = _process_received_job(
                            repository=repository,
                            received_job=received_job,
                            run_id=run_id,
                            worker_id=worker_id,
                        )
                        if inserted:
                            status = "success"
                            with lock:
                                counters.processed_jobs += 1
                            metrics.JOBS_PROCESSED.labels(
                                run_id=run_id,
                                backend=backend_name,
                            ).inc()
                        else:
                            status = "duplicate"
                            with lock:
                                counters.duplicate_jobs += 1
                            metrics.JOBS_DUPLICATE.labels(
                                run_id=run_id,
                                backend=backend_name,
                            ).inc()

                        metrics.DB_WRITE_SECONDS.labels(
                            run_id=run_id,
                            backend=backend_name,
                        ).observe(db_write_ms / 1000)
                        metrics.JOB_PROCESSING_SECONDS.labels(
                            run_id=run_id,
                            backend=backend_name,
                        ).observe(processing_ms / 1000)

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
                        ack_started = perf_counter()
                        queue.ack(received_job)
                        metrics.QUEUE_ACK_SECONDS.labels(
                            run_id=run_id,
                            backend=backend_name,
                        ).observe(_elapsed_seconds(ack_started))
                        metrics.JOBS_ACKED.labels(
                            run_id=run_id,
                            backend=backend_name,
                        ).inc()
                    except Exception as exc:
                        with lock:
                            counters.failed_jobs += 1
                        metrics.JOBS_FAILED.labels(
                            run_id=run_id,
                            backend=backend_name,
                            error_type=type(exc).__name__,
                        ).inc()
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
    finally:
        queue.close()


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


def _elapsed_seconds(started: float) -> float:
    return perf_counter() - started
