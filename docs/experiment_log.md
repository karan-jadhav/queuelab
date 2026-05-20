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
