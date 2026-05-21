# QueueLab Snapshot Notes

## v0.2.1

Patch release:

- Experiment configs with `dataset.poison_count` now generate ignored derived poison datasets automatically.
- Poison experiments no longer require manual JSONL editing.

## v0.2

This snapshot adds the first experiment-runner and sweep layer on top of the v0.1 reliability lab.

Added:

- YAML experiment runner with `experiment plan` and `experiment run`.
- Deterministic transient-failure injection for retry-storm experiments.
- Retryable RabbitMQ failures using an internal attempt header.
- Queue depth sampling into Postgres.
- p50/p95 processing and DB write latency in summaries.
- RabbitMQ prefetch sweep summaries and charts.
- SQS visibility timeout comparison under slow DB writes.
- Postgres queue concurrency sweep summaries and charts.
- DB-delay sweep summaries and charts.
- Retry-storm smoke summaries and charts.

Still deferred:

- Real AWS SQS runs.
- Full raw time-series charting.

## v0.1

This snapshot contains a reproducible local reliability lab for queue-backed workers.

Included:

- GH Archive dataset downloader and inspector.
- Direct Postgres baseline.
- RabbitMQ backend with manual ack and DLQ.
- LocalStack SQS backend with delete-after-commit and DLQ handling.
- Postgres `FOR UPDATE SKIP LOCKED` queue backend.
- Idempotent side-effect table.
- Prometheus metrics endpoint.
- Prometheus and Grafana local services.
- Controlled crash-after-DB-commit mode.
- Poison message handling.
- DB slowdown mode.
- Experiment configs, summaries, charts, architecture notes, and findings.

Not included in v0.1:

- Real AWS SQS runs.
- A one-command experiment orchestrator.
- Final benchmark claims.
