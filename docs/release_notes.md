# QueueLab v0.1 Snapshot Notes

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

Not included yet:

- Real AWS SQS runs.
- Full retry storm implementation.
- A one-command experiment orchestrator.
- Final benchmark claims.
