from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
import gzip
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

from queuelab.dataset.schema import JobValidationError, normalize_event


DEFAULT_BASE_URL = "https://data.gharchive.org"
USER_AGENT = "QueueLab/0.1 (+https://github.com/)"


@dataclass(frozen=True)
class DownloadResult:
    output_path: Path
    metadata_path: Path
    count: int
    sha256: str
    source_files: list[str]


def download_jobs(
    *,
    start_date: date,
    hours: int,
    limit: int,
    out: Path,
    base_url: str = DEFAULT_BASE_URL,
) -> DownloadResult:
    out.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    source_files: list[str] = []
    with out.open("w", encoding="utf-8") as output:
        for archive_name, url in iter_archive_urls(start_date, hours, base_url):
            source_files.append(archive_name)
            for event in stream_archive_events(url):
                if written >= limit:
                    return _write_metadata(
                        out=out,
                        count=written,
                        source_files=source_files,
                    )
                try:
                    job = normalize_event(event, source_file=archive_name)
                except JobValidationError:
                    continue
                output.write(job.to_json())
                output.write("\n")
                written += 1
    return _write_metadata(out=out, count=written, source_files=source_files)


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
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request) as response:
        with gzip.GzipFile(fileobj=response) as gz:
            for raw_line in gz:
                if not raw_line.strip():
                    continue
                event = json.loads(raw_line)
                if isinstance(event, dict):
                    yield event


def _write_metadata(out: Path, count: int, source_files: list[str]) -> DownloadResult:
    digest = _sha256_file(out)
    metadata_path = Path(f"{out}.metadata.json")
    result = DownloadResult(
        output_path=out,
        metadata_path=metadata_path,
        count=count,
        sha256=digest,
        source_files=source_files,
    )
    metadata = {
        **asdict(result),
        "output_path": str(result.output_path),
        "metadata_path": str(result.metadata_path),
        "created_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as input_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
