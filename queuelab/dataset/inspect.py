from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def inspect_dataset(path: Path) -> dict[str, Any]:
    count = 0
    first_job: dict[str, Any] | None = None
    event_types: set[str] = set()

    with path.open("r", encoding="utf-8") as input_file:
        for line in input_file:
            if not line.strip():
                continue
            row = json.loads(line)
            if first_job is None and isinstance(row, dict):
                first_job = row
            if isinstance(row, dict) and isinstance(row.get("event_type"), str):
                event_types.add(row["event_type"])
            count += 1

    metadata_path = Path(f"{path}.metadata.json")
    metadata: dict[str, Any] = {}
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    return {
        "path": str(path),
        "count": count,
        "metadata_count": metadata.get("count"),
        "sha256": metadata.get("sha256"),
        "source_files": metadata.get("source_files", []),
        "event_types": sorted(event_types),
        "first_job_id": first_job.get("job_id") if first_job else None,
    }
