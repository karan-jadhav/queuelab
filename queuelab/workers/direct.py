from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from time import perf_counter
from typing import Any

from queuelab.db import ExperimentRepository, ExperimentRun, connect


@dataclass(frozen=True)
class DirectRunResult:
    run_id: str
    total_attempts: int
    processed_jobs: int
    duplicate_jobs: int


def run_direct(
    *,
    dataset: Path,
    run_id: str,
    experiment_id: str = "dev_direct",
    worker_id: str = "direct-1",
) -> DirectRunResult:
    with connect() as connection:
        repository = ExperimentRepository(connection)
        repository.create_run(
            ExperimentRun(
                run_id=run_id,
                experiment_id=experiment_id,
                backend="direct",
                dataset_name=dataset.name,
                job_count_target=_count_lines(dataset),
                worker_count=1,
                batch_size=1,
            )
        )

        total_attempts = 0
        processed_jobs = 0
        duplicate_jobs = 0

        for job in _iter_jobs(dataset):
            total_attempts += 1
            job_id = _required_job_id(job)

            started = perf_counter()
            db_started = perf_counter()
            inserted = repository.insert_processed_job(
                run_id=run_id,
                job_id=job_id,
                worker_id=worker_id,
                result_hash=_result_hash(job),
            )
            db_write_ms = _elapsed_ms(db_started)
            processing_ms = _elapsed_ms(started)

            if inserted:
                processed_jobs += 1
                status = "success"
            else:
                duplicate_jobs += 1
                status = "duplicate"

            repository.record_attempt(
                run_id=run_id,
                job_id=job_id,
                backend="direct",
                worker_id=worker_id,
                attempt_no=1,
                status=status,
                processing_ms=processing_ms,
                db_write_ms=db_write_ms,
            )

        repository.finish_run(run_id)
        connection.commit()

    return DirectRunResult(
        run_id=run_id,
        total_attempts=total_attempts,
        processed_jobs=processed_jobs,
        duplicate_jobs=duplicate_jobs,
    )


def _iter_jobs(dataset: Path) -> Any:
    with dataset.open("r", encoding="utf-8") as input_file:
        for line in input_file:
            if line.strip():
                yield json.loads(line)


def _count_lines(dataset: Path) -> int:
    with dataset.open("r", encoding="utf-8") as input_file:
        return sum(1 for line in input_file if line.strip())


def _required_job_id(job: dict[str, Any]) -> str:
    job_id = job.get("job_id")
    if not isinstance(job_id, str) or not job_id:
        raise ValueError("job is missing required field: job_id")
    return job_id


def _result_hash(job: dict[str, Any]) -> str:
    payload = json.dumps(job, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _elapsed_ms(started: float) -> int:
    return int((perf_counter() - started) * 1000)
