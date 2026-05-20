# Findings

These findings are based only on committed local summaries under `results/summaries/`.

## What Works

- The same 10K GH Archive dataset processed successfully through RabbitMQ, LocalStack SQS, and Postgres queue with zero failed attempts.
- Crash-after-DB-commit smoke checks produced duplicate attempts without duplicate side effects.
- Poison messages reached terminal DLQ/dead state across all three queued backends.
- DB slowdown injection is available and records slower processing in run summaries.
- The v0.2 runner can execute YAML experiment configs and expand simple sweeps.
- Retry storm mode creates controlled transient failures and attempt amplification.
- Queue depth samples and p50/p95 latency summaries are now exported with run summaries.

## Early Observations

RabbitMQ was fastest in the first 10K happy-path local run:

| backend | jobs/s |
|---|---:|
| RabbitMQ | 652.12 |
| Postgres queue | 372.77 |
| LocalStack SQS | 298.50 |

This is not a universal ranking. It is one local run on WSL2 using LocalStack for SQS.

In the v0.2 RabbitMQ prefetch sweep, prefetch `10` was fastest locally:

| prefetch | jobs/s |
|---:|---:|
| 1 | 479.41 |
| 10 | 611.22 |
| 50 | 573.39 |

In the v0.2 Postgres queue concurrency sweep, 4 workers was fastest locally:

| workers | jobs/s | db_write_ms_p95 |
|---:|---:|---:|
| 1 | 193.31 | 1.0 |
| 4 | 382.06 | 4.0 |
| 8 | 306.24 | 9.0 |
| 16 | 260.95 | 24.0 |

## What Broke First

The first useful failure signal was the crash-after-DB-commit window. All backends redelivered or recovered the committed-but-unacked job, producing exactly one duplicate attempt in the unique-job smoke run.

SQS and Postgres queue recovery time is controlled by visibility timeout or lease timeout. RabbitMQ redelivery was immediate in the local smoke because closing the consumer channel released the unacked message.

The retry-storm smoke selected 54 jobs deterministically at a 5% rate. Each failed twice before success, producing 108 failed attempts and an attempt amplification of 1.108 across all three backends.

## Limitations

- No AWS SQS run has been performed yet.
- Current charts still use summary-level metrics, not raw time-series traces.
- The 10K comparison is useful for reproducibility, not final benchmarking.
