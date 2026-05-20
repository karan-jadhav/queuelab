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
