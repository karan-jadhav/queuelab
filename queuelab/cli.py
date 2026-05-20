from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Annotated

import typer

from queuelab import __version__
from queuelab.dataset.download_gharchive import DEFAULT_BASE_URL, download_jobs
from queuelab.dataset.inspect import inspect_dataset
from queuelab.metrics import start_metrics_server
from queuelab.reporting.summarize import (
    summarize_run,
    summary_to_json,
    summary_to_markdown,
)
from queuelab.workers.direct import run_direct
from queuelab.workers.queued import ChaosConfig, run_postgres_queue, run_rabbitmq, run_sqs


app = typer.Typer(
    help="Run QueueLab reliability experiments.",
    no_args_is_help=True,
)
dataset_app = typer.Typer(help="Download and inspect normalized job datasets.")
report_app = typer.Typer(help="Export and summarize experiment results.")

app.add_typer(dataset_app, name="dataset")
app.add_typer(report_app, name="report")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"queuelab {__version__}")
        raise typer.Exit()


@app.callback()
def root(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Show the installed QueueLab version.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
) -> None:
    _ = version


@dataset_app.command("download")
def dataset_download(
    start_date: Annotated[str, typer.Option(help="First GH Archive date to read.")],
    hours: Annotated[int, typer.Option(help="Number of hourly archives to scan.")],
    limit: Annotated[int, typer.Option(help="Maximum number of jobs to write.")],
    out: Annotated[Path, typer.Option(help="Output JSONL path.")],
    base_url: Annotated[
        str,
        typer.Option(help="Base URL or file URI containing GH Archive files."),
    ] = DEFAULT_BASE_URL,
) -> None:
    try:
        parsed_start_date = date.fromisoformat(start_date)
    except ValueError as exc:
        raise typer.BadParameter("expected YYYY-MM-DD") from exc

    result = download_jobs(
        start_date=parsed_start_date,
        hours=hours,
        limit=limit,
        out=out,
        base_url=base_url,
    )
    typer.echo(f"wrote {result.count} jobs to {result.output_path}")
    typer.echo(f"metadata: {result.metadata_path}")


@dataset_app.command("inspect")
def dataset_inspect(
    path: Annotated[Path, typer.Argument(help="Dataset JSONL path to inspect.")],
) -> None:
    summary = inspect_dataset(path)
    typer.echo(f"path: {summary['path']}")
    typer.echo(f"count: {summary['count']}")
    typer.echo(f"metadata_count: {summary['metadata_count']}")
    typer.echo(f"sha256: {summary['sha256']}")
    typer.echo(f"source_files: {', '.join(summary['source_files'])}")
    typer.echo(f"event_types: {', '.join(summary['event_types'])}")
    typer.echo(f"first_job_id: {summary['first_job_id']}")


@report_app.command("summarize")
def report_summarize(
    run_id: Annotated[str, typer.Option(help="Run identifier to summarize.")],
    output_format: Annotated[
        str,
        typer.Option("--format", help="Output format: json or markdown."),
    ] = "markdown",
) -> None:
    summary = summarize_run(run_id)
    if output_format == "json":
        typer.echo(summary_to_json(summary))
        return
    if output_format == "markdown":
        typer.echo(summary_to_markdown(summary))
        return
    raise typer.BadParameter("format must be json or markdown")


@app.command("run")
def run(
    backend: Annotated[str, typer.Option(help="Backend to run.")] = "direct",
    dataset: Annotated[Path | None, typer.Option(help="Normalized JSONL dataset.")] = None,
    run_id: Annotated[str | None, typer.Option(help="Unique run identifier.")] = None,
    experiment_id: Annotated[str, typer.Option(help="Experiment identifier.")] = "dev_direct",
    workers: Annotated[int, typer.Option(help="Number of workers to run.")] = 1,
    batch_size: Annotated[int, typer.Option(help="Queue receive batch size.")] = 10,
    prefetch_count: Annotated[int, typer.Option(help="RabbitMQ prefetch count.")] = 10,
    sqs_wait_seconds: Annotated[int, typer.Option(help="SQS long polling wait time.")] = 1,
    sqs_visibility_timeout_seconds: Annotated[
        int | None,
        typer.Option(help="SQS per-receive visibility timeout override."),
    ] = None,
    pg_max_attempts: Annotated[int, typer.Option(help="Postgres queue max attempts.")] = 3,
    pg_lease_timeout_seconds: Annotated[
        int,
        typer.Option(help="Postgres queue leased-message timeout."),
    ] = 30,
    chaos_crash_after_db_commit_attempts: Annotated[
        int,
        typer.Option(help="Crash a queued worker after this many attempts commit but before ack."),
    ] = 0,
    chaos_max_worker_crashes: Annotated[
        int,
        typer.Option(help="Maximum controlled queued worker crashes to inject."),
    ] = 1,
    chaos_fail_poison_messages: Annotated[
        bool,
        typer.Option(help="Send payloads marked with chaos=poison to dead-letter handling."),
    ] = False,
    chaos_db_delay_ms: Annotated[
        int,
        typer.Option(help="Sleep this many milliseconds before each DB side-effect write."),
    ] = 0,
    metrics_port: Annotated[
        int | None,
        typer.Option(help="Expose Prometheus metrics on this port."),
    ] = None,
) -> None:
    if dataset is None:
        raise typer.BadParameter("--dataset is required")
    if run_id is None:
        raise typer.BadParameter("--run-id is required")

    start_metrics_server(metrics_port)
    chaos_config = ChaosConfig(
        crash_after_db_commit_attempts=chaos_crash_after_db_commit_attempts,
        max_worker_crashes=chaos_max_worker_crashes,
        fail_poison_messages=chaos_fail_poison_messages,
        db_delay_ms=chaos_db_delay_ms,
    )

    if backend == "direct":
        direct_result = run_direct(
            dataset=dataset,
            run_id=run_id,
            experiment_id=experiment_id,
            db_delay_ms=chaos_db_delay_ms,
        )
        typer.echo(f"run_id: {direct_result.run_id}")
        typer.echo(f"total_attempts: {direct_result.total_attempts}")
        typer.echo(f"processed_jobs: {direct_result.processed_jobs}")
        typer.echo(f"duplicate_jobs: {direct_result.duplicate_jobs}")
        return

    if backend == "rabbitmq":
        rabbitmq_result = run_rabbitmq(
            dataset=dataset,
            run_id=run_id,
            experiment_id=experiment_id,
            batch_size=batch_size,
            prefetch_count=prefetch_count,
            workers=workers,
            chaos_config=chaos_config,
        )
        typer.echo(f"run_id: {rabbitmq_result.run_id}")
        typer.echo(f"backend: {rabbitmq_result.backend}")
        typer.echo(f"total_attempts: {rabbitmq_result.total_attempts}")
        typer.echo(f"processed_jobs: {rabbitmq_result.processed_jobs}")
        typer.echo(f"duplicate_jobs: {rabbitmq_result.duplicate_jobs}")
        typer.echo(f"failed_jobs: {rabbitmq_result.failed_jobs}")
        return

    if backend == "sqs":
        sqs_result = run_sqs(
            dataset=dataset,
            run_id=run_id,
            experiment_id=experiment_id,
            batch_size=batch_size,
            workers=workers,
            wait_time_seconds=sqs_wait_seconds,
            visibility_timeout_seconds=sqs_visibility_timeout_seconds,
            chaos_config=chaos_config,
        )
        typer.echo(f"run_id: {sqs_result.run_id}")
        typer.echo(f"backend: {sqs_result.backend}")
        typer.echo(f"total_attempts: {sqs_result.total_attempts}")
        typer.echo(f"processed_jobs: {sqs_result.processed_jobs}")
        typer.echo(f"duplicate_jobs: {sqs_result.duplicate_jobs}")
        typer.echo(f"failed_jobs: {sqs_result.failed_jobs}")
        return

    if backend == "postgres":
        postgres_result = run_postgres_queue(
            dataset=dataset,
            run_id=run_id,
            experiment_id=experiment_id,
            batch_size=batch_size,
            workers=workers,
            max_attempts=pg_max_attempts,
            lease_timeout_seconds=pg_lease_timeout_seconds,
            chaos_config=chaos_config,
        )
        typer.echo(f"run_id: {postgres_result.run_id}")
        typer.echo(f"backend: {postgres_result.backend}")
        typer.echo(f"total_attempts: {postgres_result.total_attempts}")
        typer.echo(f"processed_jobs: {postgres_result.processed_jobs}")
        typer.echo(f"duplicate_jobs: {postgres_result.duplicate_jobs}")
        typer.echo(f"failed_jobs: {postgres_result.failed_jobs}")
        return

    typer.echo(f"backend {backend!r} is not implemented yet")
    raise typer.Exit(code=1)


def main() -> None:
    app()
