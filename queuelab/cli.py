from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Annotated

import typer

from queuelab import __version__
from queuelab.dataset.download_gharchive import DEFAULT_BASE_URL, download_jobs


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

    count = download_jobs(
        start_date=parsed_start_date,
        hours=hours,
        limit=limit,
        out=out,
        base_url=base_url,
    )
    typer.echo(f"wrote {count} jobs to {out}")


@app.command("run")
def run(
    backend: Annotated[str, typer.Option(help="Backend to run.")] = "direct",
) -> None:
    typer.echo(f"backend {backend!r} is not implemented yet")


def main() -> None:
    app()
