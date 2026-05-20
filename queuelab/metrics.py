from __future__ import annotations

from prometheus_client import Counter, Histogram, start_http_server


JOBS_PUBLISHED = Counter(
    "queuelab_jobs_published_total",
    "Jobs published to a queue backend.",
    ["run_id", "backend"],
)
JOBS_RECEIVED = Counter(
    "queuelab_jobs_received_total",
    "Jobs received by workers.",
    ["run_id", "backend"],
)
JOBS_PROCESSED = Counter(
    "queuelab_jobs_processed_total",
    "Jobs processed successfully.",
    ["run_id", "backend"],
)
JOBS_ACKED = Counter(
    "queuelab_jobs_acked_total",
    "Jobs acknowledged or marked complete after processing.",
    ["run_id", "backend"],
)
JOBS_FAILED = Counter(
    "queuelab_jobs_failed_total",
    "Job attempts that failed.",
    ["run_id", "backend", "error_type"],
)
JOBS_DUPLICATE = Counter(
    "queuelab_jobs_duplicate_total",
    "Duplicate job attempts blocked by idempotency.",
    ["run_id", "backend"],
)

JOB_PROCESSING_SECONDS = Histogram(
    "queuelab_job_processing_seconds",
    "Time spent processing one job attempt.",
    ["run_id", "backend"],
)
DB_WRITE_SECONDS = Histogram(
    "queuelab_db_write_seconds",
    "Time spent writing job processing state to Postgres.",
    ["run_id", "backend"],
)
QUEUE_ACK_SECONDS = Histogram(
    "queuelab_queue_ack_seconds",
    "Time spent acknowledging or completing a queue message.",
    ["run_id", "backend"],
)


def start_metrics_server(port: int | None) -> None:
    if port is not None:
        start_http_server(port)
