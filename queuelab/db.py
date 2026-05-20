from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from queuelab.config import load_settings


@dataclass(frozen=True)
class ExperimentRun:
    run_id: str
    experiment_id: str
    backend: str
    git_commit: str | None = None
    dataset_name: str | None = None
    dataset_sha256: str | None = None
    job_count_target: int | None = None
    worker_count: int | None = None
    batch_size: int | None = None
    queue_config: dict[str, Any] = field(default_factory=dict)
    chaos_config: dict[str, Any] = field(default_factory=dict)
    hardware: dict[str, Any] = field(default_factory=dict)
    notes: str | None = None


def connect() -> psycopg.Connection:
    settings = load_settings()
    return psycopg.connect(settings.database_url, row_factory=dict_row)


class ExperimentRepository:
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def create_run(self, run: ExperimentRun) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO experiment_runs (
                  run_id,
                  experiment_id,
                  backend,
                  git_commit,
                  dataset_name,
                  dataset_sha256,
                  job_count_target,
                  worker_count,
                  batch_size,
                  queue_config,
                  chaos_config,
                  hardware,
                  notes
                )
                VALUES (
                  %(run_id)s,
                  %(experiment_id)s,
                  %(backend)s,
                  %(git_commit)s,
                  %(dataset_name)s,
                  %(dataset_sha256)s,
                  %(job_count_target)s,
                  %(worker_count)s,
                  %(batch_size)s,
                  %(queue_config)s,
                  %(chaos_config)s,
                  %(hardware)s,
                  %(notes)s
                )
                ON CONFLICT (run_id) DO NOTHING
                """,
                {
                    "run_id": run.run_id,
                    "experiment_id": run.experiment_id,
                    "backend": run.backend,
                    "git_commit": run.git_commit,
                    "dataset_name": run.dataset_name,
                    "dataset_sha256": run.dataset_sha256,
                    "job_count_target": run.job_count_target,
                    "worker_count": run.worker_count,
                    "batch_size": run.batch_size,
                    "queue_config": Jsonb(run.queue_config),
                    "chaos_config": Jsonb(run.chaos_config),
                    "hardware": Jsonb(run.hardware),
                    "notes": run.notes,
                },
            )

    def insert_processed_job(
        self,
        *,
        run_id: str,
        job_id: str,
        worker_id: str,
        result_hash: str | None,
    ) -> bool:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO processed_jobs (run_id, job_id, worker_id, result_hash)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (run_id, job_id) DO NOTHING
                RETURNING job_id
                """,
                (run_id, job_id, worker_id, result_hash),
            )
            return cursor.fetchone() is not None

    def record_attempt(
        self,
        *,
        run_id: str,
        job_id: str,
        backend: str,
        worker_id: str,
        attempt_no: int,
        status: str,
        processing_ms: int,
        db_write_ms: int,
        message_meta: dict[str, Any] | None = None,
        error_type: str | None = None,
        error_message: str | None = None,
    ) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO job_attempts (
                  run_id,
                  job_id,
                  backend,
                  worker_id,
                  attempt_no,
                  started_at,
                  finished_at,
                  acked_at,
                  status,
                  error_type,
                  error_message,
                  processing_ms,
                  db_write_ms,
                  message_meta
                )
                VALUES (
                  %s,
                  %s,
                  %s,
                  %s,
                  %s,
                  now(),
                  now(),
                  now(),
                  %s,
                  %s,
                  %s,
                  %s,
                  %s,
                  %s
                )
                """,
                (
                    run_id,
                    job_id,
                    backend,
                    worker_id,
                    attempt_no,
                    status,
                    error_type,
                    error_message,
                    processing_ms,
                    db_write_ms,
                    Jsonb(message_meta or {}),
                ),
            )

    def finish_run(self, run_id: str) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE experiment_runs
                SET finished_at = now()
                WHERE run_id = %s
                """,
                (run_id,),
            )
