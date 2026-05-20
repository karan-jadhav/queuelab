# Findings

These findings are based only on committed local summaries under `results/summaries/`.

## What Works

- The same 10K GH Archive dataset processed successfully through RabbitMQ, LocalStack SQS, and Postgres queue with zero failed attempts.
- Crash-after-DB-commit smoke checks produced duplicate attempts without duplicate side effects.
- Poison messages reached terminal DLQ/dead state across all three queued backends.
- DB slowdown injection is available and records slower processing in run summaries.

## Early Observations

RabbitMQ was fastest in the first 10K happy-path local run:

| backend | jobs/s |
|---|---:|
| RabbitMQ | 652.12 |
| Postgres queue | 372.77 |
| LocalStack SQS | 298.50 |

This is not a universal ranking. It is one local run on WSL2 using LocalStack for SQS.

## What Broke First

The first useful failure signal was the crash-after-DB-commit window. All backends redelivered or recovered the committed-but-unacked job, producing exactly one duplicate attempt in the unique-job smoke run.

SQS and Postgres queue recovery time is controlled by visibility timeout or lease timeout. RabbitMQ redelivery was immediate in the local smoke because closing the consumer channel released the unacked message.

## Limitations

- No AWS SQS run has been performed yet.
- Retry storm behavior is listed in config but not implemented yet.
- Current charts use summary-level metrics only.
- The 10K comparison is useful for reproducibility, not final benchmarking.
