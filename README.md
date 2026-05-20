# QueueLab

QueueLab is a backend reliability lab for comparing queue-backed worker behavior when the happy path breaks.

It runs the same normalized GH Archive workload through:

- RabbitMQ
- SQS-compatible queues through LocalStack
- PostgreSQL queues using `FOR UPDATE SKIP LOCKED`

The goal is not to claim a universal winner. The goal is to make failure behavior visible: duplicate delivery, worker crashes, poison messages, slow database writes, queue recovery, and dead-letter handling.

## Current Status

QueueLab now has a reproducible local path for:

- downloading and inspecting a GH Archive dataset
- processing jobs directly into Postgres
- processing jobs through RabbitMQ, LocalStack SQS, and Postgres queue
- recording attempts and idempotent side effects
- summarizing runs
- exporting summary JSON
- generating simple SVG charts
- running controlled crash, poison, and DB slowdown smoke checks
- running YAML experiment configs and sweeps
- injecting transient failures for retry-storm experiments
- exporting latency percentiles and queue-depth summaries

## Quick Start

Install dependencies with `uv`, then start local services:

```bash
docker compose up -d postgres rabbitmq localstack
```

Create a 10K dataset:

```bash
uv run python -m queuelab dataset download \
  --start-date 2025-01-01 \
  --hours 24 \
  --limit 10000 \
  --out data/jobs_10k.jsonl
```

Run one backend:

```bash
uv run python -m queuelab run \
  --backend rabbitmq \
  --dataset data/jobs_10k.jsonl \
  --run-id local-rabbitmq-10k \
  --workers 4 \
  --batch-size 10 \
  --prefetch-count 10
```

Summarize it:

```bash
uv run python -m queuelab report summarize --run-id local-rabbitmq-10k
```

## Stable Commands

```bash
uv run python -m queuelab dataset download ...
uv run python -m queuelab dataset inspect ...
uv run python -m queuelab run --backend direct ...
uv run python -m queuelab run --backend rabbitmq ...
uv run python -m queuelab run --backend sqs ...
uv run python -m queuelab run --backend postgres ...
uv run python -m queuelab report summarize --run-id ...
uv run python -m queuelab report export --run-id ... --out-dir results/summaries
uv run python -m queuelab report charts --summary-dir results/summaries --out-dir docs/charts
uv run python -m queuelab experiment plan experiments/configs/exp_007_rabbitmq_prefetch.yaml
uv run python -m queuelab experiment run experiments/configs/exp_007_rabbitmq_prefetch.yaml
```

## First Local Results

The first committed 10K happy-path comparison used dataset SHA256 `3661a461fbb6ecf2b4d604a1f70063cb11e0d6a1990d85b6a8c09161844d8423`.

| backend | processed jobs | failed attempts | jobs/s |
|---|---:|---:|---:|
| RabbitMQ | 10000 | 0 | 652.12 |
| LocalStack SQS | 10000 | 0 | 298.50 |
| Postgres queue | 10000 | 0 | 372.77 |

These are local WSL2 observations, not final benchmark claims.

## Failure Smokes

Crash-after-DB-commit with 10 unique jobs:

| backend | attempts | processed | duplicates | failures |
|---|---:|---:|---:|---:|
| RabbitMQ | 11 | 10 | 1 | 0 |
| SQS | 11 | 10 | 1 | 0 |
| Postgres queue | 11 | 10 | 1 | 0 |

Poison message handling with 9 normal jobs and 1 poison job:

| backend | attempts | processed | failed | dead depth |
|---|---:|---:|---:|---:|
| RabbitMQ | 10 | 9 | 1 | 1 |
| SQS | 10 | 9 | 1 | 1 |
| Postgres queue | 10 | 9 | 1 | 1 |

## v0.2 Sweeps

RabbitMQ prefetch sweep on 10K jobs:

| prefetch | jobs/s |
|---:|---:|
| 1 | 479.41 |
| 10 | 611.22 |
| 50 | 573.39 |

Postgres queue concurrency sweep on 10K jobs:

| workers | jobs/s |
|---:|---:|
| 1 | 193.31 |
| 4 | 382.06 |
| 8 | 306.24 |
| 16 | 260.95 |

Retry storm smoke on 1K jobs:

| backend | attempts | failed attempts | amplification |
|---|---:|---:|---:|
| RabbitMQ | 1108 | 108 | 1.108 |
| SQS | 1108 | 108 | 1.108 |
| Postgres queue | 1108 | 108 | 1.108 |

## Docs

- [Architecture](docs/architecture.md)
- [Experiment Log](docs/experiment_log.md)
- [Findings](docs/findings.md)
- [Build Log](docs/build_log.md)
- [Release Notes](docs/release_notes.md)
- [Charts](docs/charts)

## Limitations

- SQS runs use LocalStack, not AWS SQS.
- Charts currently use summary-level metrics, not full time-series traces.
- Raw datasets stay out of Git; committed artifacts are summaries, configs, charts, and docs.
