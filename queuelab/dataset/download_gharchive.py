from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timedelta
import gzip
import json
from pathlib import Path
from urllib.request import urlopen

from queuelab.dataset.schema import JobValidationError, normalize_event


DEFAULT_BASE_URL = "https://data.gharchive.org"


def download_jobs(
    *,
    start_date: date,
    hours: int,
    limit: int,
    out: Path,
    base_url: str = DEFAULT_BASE_URL,
) -> int:
    out.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    with out.open("w", encoding="utf-8") as output:
        for archive_name, url in iter_archive_urls(start_date, hours, base_url):
            for event in stream_archive_events(url):
                if written >= limit:
                    return written
                try:
                    job = normalize_event(event, source_file=archive_name)
                except JobValidationError:
                    continue
                output.write(job.to_json())
                output.write("\n")
                written += 1
    return written


def iter_archive_urls(
    start_date: date,
    hours: int,
    base_url: str = DEFAULT_BASE_URL,
) -> Iterable[tuple[str, str]]:
    if hours < 1:
        raise ValueError("hours must be at least 1")

    start = datetime.combine(start_date, datetime.min.time())
    for offset in range(hours):
        current = start + timedelta(hours=offset)
        archive_name = f"{current:%Y-%m-%d}-{current.hour}.json.gz"
        yield archive_name, f"{base_url.rstrip('/')}/{archive_name}"


def stream_archive_events(url: str) -> Iterable[dict[str, object]]:
    with urlopen(url) as response:
        with gzip.GzipFile(fileobj=response) as gz:
            for raw_line in gz:
                if not raw_line.strip():
                    continue
                event = json.loads(raw_line)
                if isinstance(event, dict):
                    yield event
