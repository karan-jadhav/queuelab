# Experiment Log

This log records small reproducible checkpoints while QueueLab is built. It is not a benchmark record yet.

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
