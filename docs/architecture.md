# Architecture

QueueLab runs the same normalized job payloads through different queue backends and records the observable behavior in Postgres.

## Core Flow

1. Download GH Archive events into normalized JSONL jobs.
2. Publish the jobs into one backend: RabbitMQ, SQS through LocalStack, or a Postgres `SKIP LOCKED` queue.
3. Workers receive jobs, write side effects through `processed_jobs`, record every attempt in `job_attempts`, commit the database transaction, then ack/delete/complete the queue message.
4. Reports summarize the committed run rows and attempt rows.

The direct backend skips the queue and exists as a correctness baseline.

## Result Store

`experiment_runs` stores one row per run with dataset, worker, queue, and chaos configuration.

`job_attempts` stores every observed attempt, including duplicates and failures.

`processed_jobs` stores idempotent side effects. Its primary key is `(run_id, job_id)`, so duplicate deliveries can create more attempts without creating duplicate side effects.

## Queue Semantics

RabbitMQ uses persistent messages, manual ack, and a DLX-backed dead queue.

SQS uses LocalStack for local runs. Successful jobs are deleted after the database commit. Poison jobs are copied to the DLQ and removed from the main queue. Transient retry behavior is planned separately.

Postgres queue uses `FOR UPDATE SKIP LOCKED` to lease rows. Finished rows are marked `finished`; poison rows are marked `dead`; stale leased rows can be requeued after a lease timeout.

## Failure Windows

The most important window is after the DB commit and before queue acknowledgement. If the worker exits there, the side effect is already committed, but the queue may redeliver the message. QueueLab expects duplicate attempts in this case and relies on `processed_jobs` to prevent duplicate side effects.

## Current Limitations

These results are local-machine observations. LocalStack is not AWS SQS. The current runner is intentionally simple and does not yet include a full experiment orchestrator, retry-storm implementation, percentile latency reports, or production-grade process supervision.
