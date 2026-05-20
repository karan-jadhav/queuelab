from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Annotated

import typer

from queuelab import __version__
from queuelab.dataset.download_gharchive import DEFAULT_BASE_URL, download_jobs
from queuelab.dataset.inspect import inspect_dataset
from queuelab.reporting.summarize import (
    summarize_run,
    summary_to_json,
    summary_to_markdown,
)
from queuelab.workers.direct import run_direct


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
) -> None:
    if backend != "direct":
        typer.echo(f"backend {backend!r} is not implemented yet")
        raise typer.Exit(code=1)
    if dataset is None:
        raise typer.BadParameter("--dataset is required for direct runs")
    if run_id is None:
        raise typer.BadParameter("--run-id is required for direct runs")

    result = run_direct(
        dataset=dataset,
        run_id=run_id,
        experiment_id=experiment_id,
    )
    typer.echo(f"run_id: {result.run_id}")
    typer.echo(f"total_attempts: {result.total_attempts}")
    typer.echo(f"processed_jobs: {result.processed_jobs}")
    typer.echo(f"duplicate_jobs: {result.duplicate_jobs}")


def main() -> None:
    app()
