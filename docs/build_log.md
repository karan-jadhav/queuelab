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

## Observability Infra Smoke Check

Goal: confirm Prometheus and Grafana start with the QueueLab scrape config, datasource provisioning, and starter dashboard.

Config checks:

```bash
docker compose config
uv run python -m json.tool infra/grafana/dashboards/queuelab.json
```

Image tags verified by pull:

```bash
docker compose pull prometheus grafana
```

Started services:

```bash
docker compose up -d prometheus grafana
docker compose ps prometheus grafana
```

Observed service status:

```text
queuelab-prometheus-1   prom/prometheus:v3.9.1   Up   0.0.0.0:9090->9090/tcp
queuelab-grafana-1      grafana/grafana:12.4.0   Up   0.0.0.0:3000->3000/tcp
```

Current notes:

- This is an infra wiring check only, not an experiment result.
- Prometheus scrapes `host.docker.internal:8001`, matching `--metrics-port 8001`.
- Grafana provisions the Prometheus datasource and `QueueLab Reliability Dashboard`.

## LocalStack SQS Infra Smoke Check

Goal: confirm the local SQS emulator can start and create the main queue plus DLQ.

Image choice:

- Tried `localstack/localstack:2026.04.0`; it requires `LOCALSTACK_AUTH_TOKEN` and exits without credentials.
- Pinned `localstack/localstack:4.9.2` so the public repo remains runnable without a LocalStack account.

Config checks:

```bash
docker compose config
bash -n infra/localstack/init-sqs.sh
```

Service check:

```bash
docker compose up -d --force-recreate localstack
docker compose logs --tail=80 localstack
docker compose exec -T localstack awslocal sqs list-queues --region us-east-1
```

Observed queues:

```text
http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/queuelab-dlq
http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/queuelab-main
```

Current notes:

- This is SQS infra verification only, not a worker run.
- The main queue uses a DLQ redrive policy with `maxReceiveCount` defaulting to 3.
- The default visibility timeout is 30 seconds.

## SQS Duplicate Smoke Check

Goal: confirm the SQS backend can publish normalized jobs to LocalStack, receive them with worker threads, delete processed messages, and preserve idempotency behavior.

Temporary dataset:

- path: `/tmp/queuelab-smoke/jobs_sqs_dup.jsonl`
- rows: 3
- unique job IDs: 2
- duplicate job IDs: 1

Run command:

```bash
uv run python -m queuelab run \
  --backend sqs \
  --dataset /tmp/queuelab-smoke/jobs_sqs_dup.jsonl \
  --run-id smoke-sqs-duplicates-001 \
  --workers 2 \
  --batch-size 2 \
  --sqs-wait-seconds 1
```

Runner output:

```text
run_id: smoke-sqs-duplicates-001
backend: sqs
total_attempts: 3
processed_jobs: 2
duplicate_jobs: 1
failed_jobs: 0
```

Summary command:

```bash
uv run python -m queuelab report summarize --run-id smoke-sqs-duplicates-001
```

Observed smoke-check summary:

| metric | value |
|---|---:|
| run_id | smoke-sqs-duplicates-001 |
| backend | sqs |
| dataset | jobs_sqs_dup.jsonl |
| unique_processed_jobs | 2 |
| total_attempts | 3 |
| duplicate_attempts | 1 |
| failed_attempts | 0 |
| duration_seconds | 0.083 |
| jobs_per_second | 24.11 |

Current notes:

- This is a LocalStack SQS wiring check only, not an experiment result.
- SQS ack is `DeleteMessage` after the database commit.
- SQS fail currently relies on visibility timeout and redrive policy by not deleting the message.

## Postgres Queue Duplicate Smoke Check

Goal: confirm the Postgres queue backend can enqueue normalized jobs, lease them with `FOR UPDATE SKIP LOCKED`, complete them after the database commit, and preserve idempotency behavior.

Temporary dataset:

- path: `/tmp/queuelab-smoke/jobs_sqs_dup.jsonl`
- rows: 3
- unique job IDs: 2
- duplicate job IDs: 1

Run command:

```bash
uv run python -m queuelab run \
  --backend postgres \
  --dataset /tmp/queuelab-smoke/jobs_sqs_dup.jsonl \
  --run-id smoke-pgqueue-duplicates-001 \
  --workers 2 \
  --batch-size 2
```

Runner output:

```text
run_id: smoke-pgqueue-duplicates-001
backend: postgres
total_attempts: 3
processed_jobs: 2
duplicate_jobs: 1
failed_jobs: 0
```

Summary command:

```bash
uv run python -m queuelab report summarize --run-id smoke-pgqueue-duplicates-001
```

Observed smoke-check summary:

| metric | value |
|---|---:|
| run_id | smoke-pgqueue-duplicates-001 |
| backend | postgres |
| dataset | jobs_sqs_dup.jsonl |
| unique_processed_jobs | 2 |
| total_attempts | 3 |
| duplicate_attempts | 1 |
| failed_attempts | 0 |
| duration_seconds | 0.059 |
| jobs_per_second | 33.76 |

Current notes:

- This is a Postgres queue wiring check only, not an experiment result.
- Workers lease rows with `FOR UPDATE SKIP LOCKED`.
- Queue rows are allowed to duplicate job IDs; `processed_jobs` remains the idempotency boundary.

## All Backend Parity Smoke Check

Goal: confirm direct processing, RabbitMQ, SQS, and the Postgres queue all preserve the same basic attempt and idempotency behavior before running larger comparisons.

Temporary dataset:

- path: `/tmp/queuelab-smoke/jobs_sqs_dup.jsonl`
- rows: 3
- unique job IDs: 2
- duplicate job IDs: 1

Run commands:

```bash
uv run python -m queuelab run \
  --backend direct \
  --dataset /tmp/queuelab-smoke/jobs_sqs_dup.jsonl \
  --run-id smoke-parity-direct-001

uv run python -m queuelab run \
  --backend rabbitmq \
  --dataset /tmp/queuelab-smoke/jobs_sqs_dup.jsonl \
  --run-id smoke-parity-rabbitmq-001 \
  --workers 2 \
  --batch-size 2 \
  --prefetch-count 2

uv run python -m queuelab run \
  --backend sqs \
  --dataset /tmp/queuelab-smoke/jobs_sqs_dup.jsonl \
  --run-id smoke-parity-sqs-001 \
  --workers 2 \
  --batch-size 2 \
  --sqs-wait-seconds 1

uv run python -m queuelab run \
  --backend postgres \
  --dataset /tmp/queuelab-smoke/jobs_sqs_dup.jsonl \
  --run-id smoke-parity-postgres-001 \
  --workers 2 \
  --batch-size 2
```

Observed smoke-check summaries:

| backend | run_id | unique_processed_jobs | total_attempts | duplicate_attempts | failed_attempts | duration_seconds | jobs_per_second |
|---|---|---:|---:|---:|---:|---:|---:|
| direct | smoke-parity-direct-001 | 2 | 3 | 1 | 0 | 0.008 | 241.63 |
| rabbitmq | smoke-parity-rabbitmq-001 | 2 | 3 | 1 | 0 | 0.060 | 33.37 |
| sqs | smoke-parity-sqs-001 | 2 | 3 | 1 | 0 | 0.068 | 29.35 |
| postgres | smoke-parity-postgres-001 | 2 | 3 | 1 | 0 | 0.058 | 34.23 |

Current notes:

- This is a parity smoke check only, not a benchmark.
- All backends recorded one attempt per input row.
- All backends wrote only two idempotent side effects for the two unique job IDs.
