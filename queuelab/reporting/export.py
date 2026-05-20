from __future__ import annotations

from pathlib import Path

from queuelab.reporting.summarize import summarize_run, summary_to_json


def export_summaries(run_ids: list[str], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for run_id in run_ids:
        summary = summarize_run(run_id)
        path = out_dir / f"{run_id}.json"
        path.write_text(summary_to_json(summary) + "\n", encoding="utf-8")
        written.append(path)
    return written
