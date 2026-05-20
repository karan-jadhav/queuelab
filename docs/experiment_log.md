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

## EXP-004 Poison Message Smoke

Goal: confirm poison messages are handled as terminal failures across RabbitMQ, SQS, and Postgres queue. A payload marked with `chaos: "poison"` should record one failed attempt, avoid writing a side effect, and move to DLQ/dead state.

Dataset:

- path: `/tmp/queuelab-smoke/jobs_poison_10.jsonl`
- source: first 10 rows from `data/jobs_10k.jsonl`, with the final row marked `chaos: "poison"`
- rows: 10
- unique job IDs: 10
- poison jobs: 1
- SHA256: `413f3f42b7a698161868109794011e50c320a947342a1a3f8f35587c9b90a279`

Run environment:

- git commit at run time: `e806b54`
- workers: 2
- batch size: 2
- chaos mode: fail poison messages
- RabbitMQ prefetch count: 2

Commands:

```bash
uv run python -m queuelab run \
  --backend rabbitmq \
  --dataset /tmp/queuelab-smoke/jobs_poison_10.jsonl \
  --run-id exp004-rabbitmq-poison-001 \
  --experiment-id exp004_poison_smoke \
  --workers 2 \
  --batch-size 2 \
  --prefetch-count 2 \
  --chaos-fail-poison-messages

uv run python -m queuelab run \
  --backend sqs \
  --dataset /tmp/queuelab-smoke/jobs_poison_10.jsonl \
  --run-id exp004-sqs-poison-001 \
  --experiment-id exp004_poison_smoke \
  --workers 2 \
  --batch-size 2 \
  --sqs-wait-seconds 1 \
  --chaos-fail-poison-messages

uv run python -m queuelab run \
  --backend postgres \
  --dataset /tmp/queuelab-smoke/jobs_poison_10.jsonl \
  --run-id exp004-postgres-poison-001 \
  --experiment-id exp004_poison_smoke \
  --workers 2 \
  --batch-size 2 \
  --chaos-fail-poison-messages
```

Summary:

| backend | run_id | unique_processed_jobs | total_attempts | duplicate_attempts | failed_attempts | dead_depth | duration_seconds | jobs_per_second |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| rabbitmq | exp004-rabbitmq-poison-001 | 9 | 10 | 0 | 1 | 1 | 0.085 | 105.54 |
| sqs | exp004-sqs-poison-001 | 9 | 10 | 0 | 1 | 1 | 0.119 | 75.87 |
| postgres | exp004-postgres-poison-001 | 9 | 10 | 0 | 1 | 1 | 0.117 | 76.74 |

Notes:

- RabbitMQ uses `basic_reject(requeue=False)` and the configured DLX.
- SQS sends the poison payload to the local DLQ and deletes it from the main queue.
- Postgres queue marks the leased row `dead`.
- This smoke check validates terminal poison handling only; it does not measure retry policy behavior.

## EXP-005 DB Slowdown Smoke

Goal: confirm the runner can inject controlled database write delay and record the slower processing path.

Dataset:

- path: `/tmp/queuelab-smoke/jobs_unique_10.jsonl`
- rows: 10
- unique job IDs: 10

Run environment:

- backend: direct
- chaos mode: 25 ms DB delay before each side-effect write

Command:

```bash
uv run python -m queuelab run \
  --backend direct \
  --dataset /tmp/queuelab-smoke/jobs_unique_10.jsonl \
  --run-id smoke-direct-db-slowdown-001 \
  --experiment-id exp005_db_slowdown_smoke \
  --chaos-db-delay-ms 25
```

Summary:

| backend | run_id | unique_processed_jobs | total_attempts | duplicate_attempts | failed_attempts | duration_seconds | jobs_per_second |
|---|---|---:|---:|---:|---:|---:|---:|
| direct | smoke-direct-db-slowdown-001 | 10 | 10 | 0 | 0 | 0.311 | 32.17 |

Notes:

- This validates delay injection and accounting only.
- Larger DB-delay sweeps should use queued backends and compare visibility/lease behavior.

## v0.2 RabbitMQ Prefetch Sweep

Dataset: `data/jobs_10k.jsonl`, 10,000 jobs.

| run_id | prefetch | processed | failed | jobs_per_second | db_write_ms_p95 | max_ready_depth |
|---|---:|---:|---:|---:|---:|---:|
| v02-rabbitmq-prefetch-1 | 1 | 10000 | 0 | 479.41 | 4.0 | 10000 |
| v02-rabbitmq-prefetch-10 | 10 | 10000 | 0 | 611.22 | 3.0 | 10000 |
| v02-rabbitmq-prefetch-50 | 50 | 10000 | 0 | 573.39 | 4.0 | 10000 |

Notes:

- Prefetch `10` was fastest in this local sweep.
- The sweep uses summary-level metrics and should be repeated before broad claims.

## v0.2 Postgres Queue Concurrency Sweep

Dataset: `data/jobs_10k.jsonl`, 10,000 jobs.

| run_id | workers | processed | failed | jobs_per_second | db_write_ms_p95 |
|---|---:|---:|---:|---:|---:|
| v02-postgres-workers-1 | 1 | 10000 | 0 | 193.31 | 1.0 |
| v02-postgres-workers-4 | 4 | 10000 | 0 | 382.06 | 4.0 |
| v02-postgres-workers-8 | 8 | 10000 | 0 | 306.24 | 9.0 |
| v02-postgres-workers-16 | 16 | 10000 | 0 | 260.95 | 24.0 |

Notes:

- Throughput peaked at 4 workers in this local run.
- Higher worker counts increased p95 DB write latency.

## v0.2 SQS Visibility Timeout With Slow DB

Dataset: `/tmp/queuelab-smoke/jobs_100.jsonl`, 100 jobs, SHA256 `240c44397b81fcb10c7d8fa9427c37e67df80f485170ef9322a1d5e805d9570f`.

| run_id | visibility_timeout_seconds | db_delay_ms | processed | duplicate_attempts | failed | jobs_per_second | db_write_ms_p95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| v02-sqs-visibility-5-db250 | 5 | 250 | 100 | 0 | 0 | 12.45 | 256.0 |
| v02-sqs-visibility-30-db250 | 30 | 250 | 100 | 0 | 0 | 12.34 | 254.1 |

Notes:

- Neither visibility timeout produced duplicates at this size and delay.
- This is a controlled local comparison against LocalStack, not AWS SQS.

## v0.2 DB Delay Sweep

Dataset: `/tmp/queuelab-smoke/jobs_100.jsonl`, 100 jobs.

| backend | db_delay_ms | processed | failed | jobs_per_second | db_write_ms_p95 |
|---|---:|---:|---:|---:|---:|
| rabbitmq | 0 | 100 | 0 | 385.48 | 2.0 |
| rabbitmq | 25 | 100 | 0 | 96.39 | 29.0 |
| rabbitmq | 100 | 100 | 0 | 29.94 | 104.0 |
| sqs | 0 | 100 | 0 | 230.29 | 4.0 |
| sqs | 25 | 100 | 0 | 77.74 | 32.0 |
| sqs | 100 | 100 | 0 | 28.43 | 104.1 |
| postgres | 0 | 100 | 0 | 370.00 | 2.0 |
| postgres | 25 | 100 | 0 | 88.75 | 31.0 |
| postgres | 100 | 100 | 0 | 29.10 | 107.0 |

Notes:

- The injected delay dominates throughput once it reaches 100 ms.
- The p95 DB write latency tracks the configured delay as expected.

## v0.2 Retry Storm Smoke

Dataset: `/tmp/queuelab-smoke/jobs_1k.jsonl`, 1,000 jobs, SHA256 `df888bc575dc541c96add108185265d129767aeb430d904bc6a68aeea296321e`.

Chaos config:

- deterministic transient failure rate: 0.05
- transient failures stop on attempt 3

| backend | run_id | processed | total_attempts | failed_attempts | attempt_amplification | jobs_per_second |
|---|---|---:|---:|---:|---:|---:|
| rabbitmq | v02-retry-rabbitmq-rate005 | 1000 | 1108 | 108 | 1.108 | 509.82 |
| sqs | v02-retry-sqs-rate005 | 1000 | 1108 | 108 | 1.108 | 117.61 |
| postgres | v02-retry-postgres-rate005 | 1000 | 1108 | 108 | 1.108 | 538.83 |

Notes:

- All backends processed all 1,000 unique jobs.
- The retry storm produced 108 failed attempts before success, matching the deterministic selected subset over two failed attempts each.
- RabbitMQ retry republishes with an internal attempt header; SQS uses visibility timeout; Postgres queue increments row attempts.
