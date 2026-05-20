# QueueLab

QueueLab is a backend reliability lab for testing how background job systems behave after the happy path breaks.

The project will compare three queue backends over the same workload and worker logic:

- RabbitMQ
- SQS-compatible queues through LocalStack
- PostgreSQL queues using `FOR UPDATE SKIP LOCKED`

The first goal is not to crown a universal winner. The goal is to measure the failure modes that matter in production: worker crashes, duplicate delivery, poison messages, retry storms, slow database writes, queue depth growth, and dead-letter behavior.

## Current Status

This repository is being built incrementally. Early commits focus on a reproducible dataset and a direct Postgres processing path before adding queue backends.

Planned command shape:

```bash
uv run python -m queuelab dataset download ...
uv run python -m queuelab dataset inspect ...
uv run python -m queuelab run --backend direct ...
uv run python -m queuelab report summarize --run-id ...
```

## Workload

QueueLab uses public GH Archive events as job payloads. Each event is normalized into a small job record with stable identifiers, repository metadata, event timing, payload size, and a hashed actor login.

Generated datasets and raw experiment outputs are kept out of Git. The repo will keep source code, experiment configs, metadata, summaries, charts, and documentation.
