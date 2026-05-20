# Build Log

This log records small reproducible checkpoints while QueueLab is built. It is not an experiment record or benchmark log.

## Dataset Smoke Check

Goal: confirm the project can turn GH Archive `.json.gz` event files into normalized JSONL jobs with metadata.

Command shape:

```bash
uv run python -m queuelab dataset download \
  --start-date 2025-01-01 \
  --hours 24 \
  --limit 1000 \
  --out data/jobs_1k.jsonl
```

Inspection command:

```bash
uv run python -m queuelab dataset inspect data/jobs_1k.jsonl
```

Current notes:

- The downloader streams hourly archives and stops at the requested limit.
- Actor login is hashed in the normalized job output.
- Metadata is written next to the JSONL file as `<dataset>.metadata.json`.
- Generated datasets stay out of Git under `data/`.
- Queue backends and processing runs are not implemented yet.

## Direct Backend Smoke Check

Goal: confirm the project can process a normalized dataset directly into Postgres before adding queue backends.

Local proof command used a one-job dataset generated under `/tmp`:

```bash
uv run python -m queuelab run \
  --backend direct \
  --dataset /tmp/queuelab-out/jobs_1.jsonl \
  --run-id dev-direct-2
```

Summary command:

```bash
uv run python -m queuelab report summarize --run-id dev-direct-2
```

Observed smoke-check summary:

| metric | value |
|---|---:|
| run_id | dev-direct-2 |
| backend | direct |
| dataset | jobs_1.jsonl |
| unique_processed_jobs | 1 |
| total_attempts | 1 |
| duplicate_attempts | 0 |
| failed_attempts | 0 |
| duration_seconds | 0.004 |
| jobs_per_second | 240.85 |

Current notes:

- This is a wiring check only, not an experiment result or benchmark.
- The direct backend writes `experiment_runs`, `job_attempts`, and `processed_jobs`.
- Queue ack/delete behavior is intentionally not present yet.

## Direct Backend Duplicate Smoke Check

Goal: confirm direct processing records every attempt while the idempotency table only accepts the first copy of a duplicated job.

Temporary dataset:

- path: `/tmp/queuelab-smoke/jobs_dup.jsonl`
- rows: 3
- unique job IDs: 2
- duplicate job IDs: 1
- metadata SHA256: `444d0f73102071b3b2623017c970de49f42f4c7357f3c27fc37038bc5a2afb45`

Run command:

```bash
uv run python -m queuelab run \
  --backend direct \
  --dataset /tmp/queuelab-smoke/jobs_dup.jsonl \
  --run-id smoke-direct-duplicates-001
```

Runner output:

```text
run_id: smoke-direct-duplicates-001
total_attempts: 3
processed_jobs: 2
duplicate_jobs: 1
```

Summary command:

```bash
uv run python -m queuelab report summarize --run-id smoke-direct-duplicates-001
```

Observed smoke-check summary:

| metric | value |
|---|---:|
| run_id | smoke-direct-duplicates-001 |
| backend | direct |
| dataset | jobs_dup.jsonl |
| unique_processed_jobs | 2 |
| total_attempts | 3 |
| duplicate_attempts | 1 |
| failed_attempts | 0 |
| duration_seconds | 0.007 |
| jobs_per_second | 269.94 |

Current notes:

- This is a correctness smoke check only.
- It verifies the intended split between attempts and idempotent side effects.
- A summary aggregation bug was found here and fixed before this entry was recorded.

## RabbitMQ Duplicate Smoke Check

Goal: confirm the RabbitMQ backend can publish normalized jobs, consume them with manual ack, and preserve the same idempotency behavior as the direct backend.

Temporary dataset:

- path: `/tmp/queuelab-smoke/jobs_dup.jsonl`
- rows: 3
- unique job IDs: 2
- duplicate job IDs: 1

Run command:

```bash
uv run python -m queuelab run \
  --backend rabbitmq \
  --dataset /tmp/queuelab-smoke/jobs_dup.jsonl \
  --run-id smoke-rabbitmq-duplicates-001 \
  --batch-size 2 \
  --prefetch-count 2
```

Runner output:

```text
run_id: smoke-rabbitmq-duplicates-001
backend: rabbitmq
total_attempts: 3
processed_jobs: 2
duplicate_jobs: 1
failed_jobs: 0
```

Summary command:

```bash
uv run python -m queuelab report summarize --run-id smoke-rabbitmq-duplicates-001
```

Observed smoke-check summary:

| metric | value |
|---|---:|
| run_id | smoke-rabbitmq-duplicates-001 |
| backend | rabbitmq |
| dataset | jobs_dup.jsonl |
| unique_processed_jobs | 2 |
| total_attempts | 3 |
| duplicate_attempts | 1 |
| failed_attempts | 0 |
| duration_seconds | 0.019 |
| jobs_per_second | 106.13 |

Current notes:

- This is a broker wiring check only, not an experiment result.
- RabbitMQ publish uses persistent messages.
- RabbitMQ consume uses manual ack after the database commit.

## RabbitMQ Worker Pool Smoke Check

Goal: confirm queued processing can run more than one RabbitMQ worker while preserving the same idempotency behavior.

Temporary dataset:

- path: `/tmp/queuelab-smoke/jobs_pool_dup.jsonl`
- rows: 3
- unique job IDs: 2
- duplicate job IDs: 1

Run command:

```bash
uv run python -m queuelab run \
  --backend rabbitmq \
  --dataset /tmp/queuelab-smoke/jobs_pool_dup.jsonl \
  --run-id smoke-rabbitmq-workers-001 \
  --workers 2 \
  --batch-size 2 \
  --prefetch-count 2
```

Runner output:

```text
run_id: smoke-rabbitmq-workers-001
backend: rabbitmq
total_attempts: 3
processed_jobs: 2
duplicate_jobs: 1
failed_jobs: 0
```

Summary command:

```bash
uv run python -m queuelab report summarize --run-id smoke-rabbitmq-workers-001
```

Observed smoke-check summary:

| metric | value |
|---|---:|
| run_id | smoke-rabbitmq-workers-001 |
| backend | rabbitmq |
| dataset | jobs_pool_dup.jsonl |
| unique_processed_jobs | 2 |
| total_attempts | 3 |
| duplicate_attempts | 1 |
| failed_attempts | 0 |
| duration_seconds | 0.062 |
| jobs_per_second | 32.33 |

Current notes:

- This is a worker-pool wiring check only, not an experiment result.
- Each worker owns its own RabbitMQ and Postgres connections.
- The run row is committed before workers start so attempt rows can reference it safely.

## Metrics Smoke Check

Goal: confirm the Prometheus metrics instrumentation can initialize during a normal run without changing processing behavior.

Temporary dataset:

- path: `/tmp/queuelab-smoke/jobs_metrics.jsonl`
- rows: 1

Run command:

```bash
uv run python -m queuelab run \
  --backend direct \
  --dataset /tmp/queuelab-smoke/jobs_metrics.jsonl \
  --run-id smoke-direct-metrics-001 \
  --metrics-port 8001
```

Runner output:

```text
run_id: smoke-direct-metrics-001
total_attempts: 1
processed_jobs: 1
duplicate_jobs: 0
```

Summary command:

```bash
uv run python -m queuelab report summarize --run-id smoke-direct-metrics-001
```

Observed smoke-check summary:

| metric | value |
|---|---:|
| run_id | smoke-direct-metrics-001 |
| backend | direct |
| dataset | jobs_metrics.jsonl |
| unique_processed_jobs | 1 |
| total_attempts | 1 |
| duplicate_attempts | 0 |
| failed_attempts | 0 |
| duration_seconds | 0.005 |
| jobs_per_second | 183.28 |

Current notes:

- This is a metrics wiring check only, not an experiment result.
- The metrics HTTP endpoint is most useful during longer-running jobs because short smoke runs exit quickly.
- Prometheus and Grafana services are not wired yet.
