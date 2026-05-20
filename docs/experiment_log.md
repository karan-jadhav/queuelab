# Experiment Log

This log records completed local experiment summaries. Raw datasets and queue state are not committed.

## EXP-001 Happy Path 10K

Goal: compare the first working happy-path queue runs after RabbitMQ, SQS, and Postgres queue support exist.

Dataset:

- path: `data/jobs_10k.jsonl`
- source: `2025-01-01-0.json.gz`
- rows: 10,000
- SHA256: `3661a461fbb6ecf2b4d604a1f70063cb11e0d6a1990d85b6a8c09161844d8423`
- first job ID: `gh:45185629417`

Run environment:

- git commit at run time: `e4a9d2b`
- machine: Linux 6.6.114.1-microsoft-standard-WSL2 x86_64
- CPU count visible to runtime: 8
- Postgres image: `postgres:18`
- RabbitMQ image: `rabbitmq:4.3.0-management`
- LocalStack image: `localstack/localstack:4.9.2`

Common settings:

- workers: 4
- batch size: 10
- chaos mode: none
- RabbitMQ prefetch count: 10
- SQS wait time: 1 second

Commands:

```bash
uv run python -m queuelab dataset download \
  --start-date 2025-01-01 \
  --hours 24 \
  --limit 10000 \
  --out data/jobs_10k.jsonl

uv run python -m queuelab run \
  --backend rabbitmq \
  --dataset data/jobs_10k.jsonl \
  --run-id happy-10k-rabbitmq-001 \
  --experiment-id exp001_happy_path_10k \
  --workers 4 \
  --batch-size 10 \
  --prefetch-count 10

uv run python -m queuelab run \
  --backend sqs \
  --dataset data/jobs_10k.jsonl \
  --run-id happy-10k-sqs-001 \
  --experiment-id exp001_happy_path_10k \
  --workers 4 \
  --batch-size 10 \
  --sqs-wait-seconds 1

uv run python -m queuelab run \
  --backend postgres \
  --dataset data/jobs_10k.jsonl \
  --run-id happy-10k-postgres-001 \
  --experiment-id exp001_happy_path_10k \
  --workers 4 \
  --batch-size 10
```

Summary:

| backend | run_id | unique_processed_jobs | total_attempts | duplicate_attempts | failed_attempts | duration_seconds | jobs_per_second |
|---|---|---:|---:|---:|---:|---:|---:|
| rabbitmq | happy-10k-rabbitmq-001 | 10000 | 10000 | 0 | 0 | 15.335 | 652.12 |
| sqs | happy-10k-sqs-001 | 10000 | 10000 | 0 | 0 | 33.500 | 298.50 |
| postgres | happy-10k-postgres-001 | 10000 | 10000 | 0 | 0 | 26.826 | 372.77 |

Notes:

- This is the first happy-path local comparison, not a final benchmark.
- SQS uses LocalStack, not AWS SQS.
- No failure injection, slow database mode, retries, poison messages, or crash windows were enabled.
- Results are local-machine observations and should be rerun before making broader claims.

## EXP-002 Worker Crash Smoke

Goal: prove the first controlled crash window: a worker commits the idempotent side effect and attempt row, then exits before queue ack. RabbitMQ should redeliver the unacked message, and `processed_jobs` should block a second side effect.

Dataset:

- path: `/tmp/queuelab-smoke/jobs_sqs_dup.jsonl`
- rows: 3
- unique job IDs: 2
- duplicate job IDs already present in dataset: 1

Run environment:

- git commit at run time: `c0937eb`
- backend: RabbitMQ
- workers: 2
- batch size: 1
- prefetch count: 1
- chaos mode: crash after DB commit before ack
- controlled crashes: 1

Command:

```bash
uv run python -m queuelab run \
  --backend rabbitmq \
  --dataset /tmp/queuelab-smoke/jobs_sqs_dup.jsonl \
  --run-id smoke-rabbitmq-crash-after-commit-002 \
  --experiment-id exp002_worker_crash_smoke \
  --workers 2 \
  --batch-size 1 \
  --prefetch-count 1 \
  --chaos-crash-after-db-commit-attempts 1 \
  --chaos-max-worker-crashes 1
```

Summary:

| backend | run_id | unique_processed_jobs | total_attempts | duplicate_attempts | failed_attempts | duration_seconds | jobs_per_second |
|---|---|---:|---:|---:|---:|---:|---:|
| rabbitmq | smoke-rabbitmq-crash-after-commit-002 | 2 | 4 | 2 | 0 | 0.063 | 31.50 |

Notes:

- This is a crash-window smoke check only, not a backend comparison.
- Total attempts increased from 3 input rows to 4 because one committed but unacked message was redelivered.
- Duplicate attempts include the dataset's existing duplicate plus the crash-induced redelivery.
- The next larger version should use a unique-job dataset so crash-induced duplicates are easier to isolate.

## EXP-002 Cross-Backend Unique-Job Smoke

Goal: run the crash-after-DB-commit window across RabbitMQ, SQS, and Postgres queue using a tiny dataset with no duplicate job IDs. This isolates the duplicate caused by recovery from the crash window.

Dataset:

- path: `/tmp/queuelab-smoke/jobs_unique_10.jsonl`
- source: first 10 rows from `data/jobs_10k.jsonl`
- rows: 10
- unique job IDs: 10
- SHA256: `d8c66fbd95656185bcc86a228721656fbbea2dae354766a3860fee4f95570591`

Run environment:

- git commit at run time: `35e129a`
- workers: 2
- batch size: 1
- chaos mode: crash after DB commit before ack
- controlled crashes: 1
- RabbitMQ prefetch count: 1
- SQS visibility timeout override: 2 seconds
- Postgres queue lease timeout: 1 second

Commands:

```bash
uv run python -m queuelab run \
  --backend rabbitmq \
  --dataset /tmp/queuelab-smoke/jobs_unique_10.jsonl \
  --run-id exp002-rabbitmq-crash-unique-001 \
  --experiment-id exp002_worker_crash_unique_smoke \
  --workers 2 \
  --batch-size 1 \
  --prefetch-count 1 \
  --chaos-crash-after-db-commit-attempts 1 \
  --chaos-max-worker-crashes 1

uv run python -m queuelab run \
  --backend sqs \
  --dataset /tmp/queuelab-smoke/jobs_unique_10.jsonl \
  --run-id exp002-sqs-crash-unique-001 \
  --experiment-id exp002_worker_crash_unique_smoke \
  --workers 2 \
  --batch-size 1 \
  --sqs-wait-seconds 1 \
  --sqs-visibility-timeout-seconds 2 \
  --chaos-crash-after-db-commit-attempts 1 \
  --chaos-max-worker-crashes 1

uv run python -m queuelab run \
  --backend postgres \
  --dataset /tmp/queuelab-smoke/jobs_unique_10.jsonl \
  --run-id exp002-postgres-crash-unique-001 \
  --experiment-id exp002_worker_crash_unique_smoke \
  --workers 2 \
  --batch-size 1 \
  --pg-lease-timeout-seconds 1 \
  --chaos-crash-after-db-commit-attempts 1 \
  --chaos-max-worker-crashes 1
```

Summary:

| backend | run_id | unique_processed_jobs | total_attempts | duplicate_attempts | failed_attempts | duration_seconds | jobs_per_second |
|---|---|---:|---:|---:|---:|---:|---:|
| rabbitmq | exp002-rabbitmq-crash-unique-001 | 10 | 11 | 1 | 0 | 0.104 | 96.01 |
| sqs | exp002-sqs-crash-unique-001 | 10 | 11 | 1 | 0 | 2.391 | 4.18 |
| postgres | exp002-postgres-crash-unique-001 | 10 | 11 | 1 | 0 | 1.061 | 9.43 |

Notes:

- Each backend produced exactly one extra attempt from one controlled crash.
- `processed_jobs` stayed at 10 for all backends, so the crash did not duplicate side effects.
- SQS recovery time follows visibility timeout.
- Postgres queue recovery time follows the local lease timeout and requeue sweep in `receive`.
- This is still a small recovery smoke check; it is not a throughput comparison.
