from __future__ import annotations

import json
from typing import Any

from queuelab.db import connect


def summarize_run(run_id: str) -> dict[str, Any]:
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                  r.run_id,
                  r.experiment_id,
                  r.backend,
                  r.dataset_name,
                  r.dataset_sha256,
                  r.job_count_target,
                  r.worker_count,
                  r.batch_size,
                  r.started_at,
                  r.finished_at,
                  EXTRACT(EPOCH FROM (r.finished_at - r.started_at)) AS duration_seconds,
                  count(a.id) AS total_attempts,
                  count(DISTINCT a.job_id) AS unique_attempted_jobs,
                  count(*) FILTER (WHERE a.status = 'success') AS successful_attempts,
                  count(*) FILTER (WHERE a.status = 'duplicate') AS duplicate_attempts,
                  count(*) FILTER (WHERE a.status = 'failed') AS failed_attempts,
                  count(DISTINCT p.job_id) AS unique_processed_jobs
                FROM experiment_runs r
                LEFT JOIN job_attempts a ON a.run_id = r.run_id
                LEFT JOIN processed_jobs p ON p.run_id = r.run_id
                WHERE r.run_id = %s
                GROUP BY r.run_id
                """,
                (run_id,),
            )
            row = cursor.fetchone()

    if row is None:
        raise ValueError(f"run not found: {run_id}")

    duration = float(row["duration_seconds"] or 0)
    unique_processed = int(row["unique_processed_jobs"] or 0)
    throughput = unique_processed / duration if duration > 0 else 0

    return {
        "run_id": row["run_id"],
        "experiment_id": row["experiment_id"],
        "backend": row["backend"],
        "dataset_name": row["dataset_name"],
        "dataset_sha256": row["dataset_sha256"],
        "job_count_target": row["job_count_target"],
        "worker_count": row["worker_count"],
        "batch_size": row["batch_size"],
        "started_at": _stringify(row["started_at"]),
        "finished_at": _stringify(row["finished_at"]),
        "duration_seconds": duration,
        "total_attempts": int(row["total_attempts"] or 0),
        "unique_attempted_jobs": int(row["unique_attempted_jobs"] or 0),
        "unique_processed_jobs": unique_processed,
        "successful_attempts": int(row["successful_attempts"] or 0),
        "duplicate_attempts": int(row["duplicate_attempts"] or 0),
        "failed_attempts": int(row["failed_attempts"] or 0),
        "jobs_per_second": throughput,
    }


def summary_to_json(summary: dict[str, Any]) -> str:
    return json.dumps(summary, indent=2, sort_keys=True)


def summary_to_markdown(summary: dict[str, Any]) -> str:
    rows = [
        ("run_id", summary["run_id"]),
        ("backend", summary["backend"]),
        ("dataset", summary["dataset_name"]),
        ("unique_processed_jobs", summary["unique_processed_jobs"]),
        ("total_attempts", summary["total_attempts"]),
        ("duplicate_attempts", summary["duplicate_attempts"]),
        ("failed_attempts", summary["failed_attempts"]),
        ("duration_seconds", f"{summary['duration_seconds']:.3f}"),
        ("jobs_per_second", f"{summary['jobs_per_second']:.2f}"),
    ]
    lines = ["| metric | value |", "|---|---:|"]
    lines.extend(f"| {metric} | {value} |" for metric, value in rows)
    return "\n".join(lines)


def _stringify(value: Any) -> str | None:
    return value.isoformat() if value is not None else None
