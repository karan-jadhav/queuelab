# Reproducibility

This checklist describes the local path used for QueueLab v0.2.1 results.

## Requirements

- Python 3.13
- `uv`
- Docker Compose
- Linux or WSL2 tested locally

## Services

Start the local queue and result-store services:

```bash
docker compose up -d postgres rabbitmq localstack
docker compose exec -T postgres psql -U queuelab -d queuelab -f /docker-entrypoint-initdb.d/init.sql
```

Stop services when finished:

```bash
docker compose stop postgres rabbitmq localstack
```

## Dataset

Create the 10K GH Archive dataset:

```bash
uv run python -m queuelab dataset download \
  --start-date 2025-01-01 \
  --hours 24 \
  --limit 10000 \
  --out data/jobs_10k.jsonl
```

Inspect it:

```bash
uv run python -m queuelab dataset inspect data/jobs_10k.jsonl
```

Expected v0.2 dataset hash:

```text
3661a461fbb6ecf2b4d604a1f70063cb11e0d6a1990d85b6a8c09161844d8423
```

## Final Runs

Plan before running:

```bash
uv run python -m queuelab experiment plan experiments/configs/exp_001_happy_path_10k.yaml --run-prefix final-exp001
uv run python -m queuelab experiment plan experiments/configs/exp_004_poison_messages.yaml --run-prefix final-exp004
uv run python -m queuelab experiment plan experiments/configs/exp_009_retry_storm.yaml --run-prefix final-exp009
```

Run the configured experiments:

```bash
uv run python -m queuelab experiment run experiments/configs/exp_001_happy_path_10k.yaml --run-prefix final-exp001
uv run python -m queuelab experiment run experiments/configs/exp_007_rabbitmq_prefetch.yaml --run-prefix final-exp007
uv run python -m queuelab experiment run experiments/configs/exp_008_postgres_concurrency.yaml --run-prefix final-exp008
uv run python -m queuelab experiment run experiments/configs/exp_006_sqs_visibility_timeout.yaml --run-prefix final-exp006
uv run python -m queuelab experiment run experiments/configs/exp_005_db_slowdown.yaml --run-prefix final-exp005
uv run python -m queuelab experiment run experiments/configs/exp_009_retry_storm.yaml --run-prefix final-exp009
uv run python -m queuelab experiment run experiments/configs/exp_004_poison_messages.yaml --run-prefix final-exp004
```

Poison datasets are generated automatically when a config contains `dataset.poison_count`. Generated files are ignored under `.queuelab/generated/experiments/`.

## Export Summaries

Export summaries after each run set:

```bash
uv run python -m queuelab report export \
  --out-dir results/summaries \
  --run-id <run-id>
```

Generate charts:

```bash
uv run python -m queuelab report charts \
  --summary-dir results/summaries \
  --out-dir docs/charts
```

## Committed Artifacts

Committed:

- `experiments/configs/*.yaml`
- `results/summaries/*.json`
- `docs/charts/*.svg`
- `docs/experiment_log.md`

Ignored:

- `data/`
- `.queuelab/`
- local virtualenvs and caches

## Caveats

- SQS results use LocalStack, not AWS SQS.
- Charts use summary-level metrics.
- Run timing depends on local hardware and Docker performance.
