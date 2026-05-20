from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def generate_charts(summary_dir: Path, out_dir: Path) -> list[Path]:
    summaries = _load_summaries(summary_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    written = [
        _write_bar_chart(
            summaries=summaries,
            out=out_dir / "happy_path_throughput.svg",
            title="EXP-001 Happy Path Throughput",
            experiment_id="exp001_happy_path_10k",
            metric="jobs_per_second",
            ylabel="jobs/s",
        ),
        _write_bar_chart(
            summaries=summaries,
            out=out_dir / "failure_attempts.svg",
            title="Failure Smoke Attempts",
            experiment_id_prefix="exp00",
            metric="total_attempts",
            ylabel="attempts",
            include_failed=True,
        ),
        _write_bar_chart(
            summaries=summaries,
            out=out_dir / "rabbitmq_prefetch_throughput.svg",
            title="EXP-007 RabbitMQ Prefetch Throughput",
            experiment_id="exp007_rabbitmq_prefetch",
            metric="jobs_per_second",
            ylabel="jobs/s",
        ),
        _write_bar_chart(
            summaries=summaries,
            out=out_dir / "postgres_concurrency_throughput.svg",
            title="EXP-008 Postgres Queue Concurrency",
            experiment_id="exp008_postgres_concurrency",
            metric="jobs_per_second",
            ylabel="jobs/s",
        ),
        _write_bar_chart(
            summaries=summaries,
            out=out_dir / "sqs_visibility_slowdb.svg",
            title="EXP-006 SQS Visibility With Slow DB",
            experiment_id="exp006_sqs_visibility_timeout",
            metric="jobs_per_second",
            ylabel="jobs/s",
        ),
        _write_bar_chart(
            summaries=summaries,
            out=out_dir / "db_delay_latency_p95.svg",
            title="EXP-005 DB Delay p95 Write Latency",
            experiment_id="exp005_db_slowdown",
            metric="db_write_ms_p95",
            ylabel="ms",
        ),
        _write_bar_chart(
            summaries=_with_retry_amplification(summaries),
            out=out_dir / "retry_attempt_amplification.svg",
            title="EXP-009 Retry Attempt Amplification",
            experiment_id="exp009_retry_storm",
            metric="attempt_amplification",
            ylabel="attempts/job",
            include_failed=True,
        ),
        _write_bar_chart(
            summaries=summaries,
            out=out_dir / "queue_ready_depth.svg",
            title="Max Ready Queue Depth",
            experiment_id_prefix="exp00",
            metric="max_ready_depth",
            ylabel="messages",
            include_failed=True,
        ),
    ]
    return written


def _load_summaries(summary_dir: Path) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for path in sorted(summary_dir.glob("*.json")):
        summaries.append(json.loads(path.read_text(encoding="utf-8")))
    return summaries


def _with_retry_amplification(summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for summary in summaries:
        processed = float(summary.get("unique_processed_jobs") or 0)
        row = dict(summary)
        row["attempt_amplification"] = (
            float(summary.get("total_attempts") or 0) / processed if processed > 0 else 0
        )
        rows.append(row)
    return rows


def _write_bar_chart(
    *,
    summaries: list[dict[str, Any]],
    out: Path,
    title: str,
    metric: str,
    ylabel: str,
    experiment_id: str | None = None,
    experiment_id_prefix: str | None = None,
    include_failed: bool = False,
) -> Path:
    rows = [
        summary
        for summary in summaries
        if (experiment_id is None or summary["experiment_id"] == experiment_id)
        and (
            experiment_id_prefix is None
            or str(summary["experiment_id"]).startswith(experiment_id_prefix)
        )
        and (include_failed or int(summary.get("failed_attempts", 0)) == 0)
    ]
    rows.sort(key=lambda row: (row["experiment_id"], row["backend"], row["run_id"]))

    width = max(720, 140 + len(rows) * 86)
    height = 420
    margin_left = 72
    margin_bottom = 112
    plot_width = width - margin_left - 32
    plot_height = height - 92 - margin_bottom
    max_value = max((float(row.get(metric, 0)) for row in rows), default=1)
    bar_width = min(56, plot_width / max(len(rows), 1) * 0.7)
    step = plot_width / max(len(rows), 1)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{margin_left}" y="36" font-family="sans-serif" font-size="22" font-weight="700">{_escape(title)}</text>',
        f'<text x="{margin_left}" y="64" font-family="sans-serif" font-size="12" fill="#555">{_escape(ylabel)}</text>',
        f'<line x1="{margin_left}" y1="{height - margin_bottom}" x2="{width - 32}" y2="{height - margin_bottom}" stroke="#222"/>',
        f'<line x1="{margin_left}" y1="82" x2="{margin_left}" y2="{height - margin_bottom}" stroke="#222"/>',
    ]
    for index, row in enumerate(rows):
        value = float(row.get(metric, 0))
        bar_height = 0 if max_value == 0 else value / max_value * plot_height
        x = margin_left + index * step + (step - bar_width) / 2
        y = height - margin_bottom - bar_height
        label = f"{row['backend']}\\n{row['run_id'].replace('-', ' ')}"
        parts.extend(
            [
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{bar_height:.1f}" fill="#2f6f73"/>',
                f'<text x="{x + bar_width / 2:.1f}" y="{y - 8:.1f}" text-anchor="middle" font-family="sans-serif" font-size="11">{value:.2f}</text>',
                f'<text x="{x + bar_width / 2:.1f}" y="{height - margin_bottom + 18}" text-anchor="middle" font-family="sans-serif" font-size="10">{_escape(row["backend"])}</text>',
                f'<text x="{x + bar_width / 2:.1f}" y="{height - margin_bottom + 34}" text-anchor="middle" font-family="sans-serif" font-size="9" fill="#555">{_escape(_short_run_id(row["run_id"]))}</text>',
            ]
        )
        _ = label
    parts.append("</svg>")
    out.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return out


def _short_run_id(run_id: str) -> str:
    return (
        run_id.replace("happy-10k-", "")
        .replace("exp002-", "e2 ")
        .replace("exp004-", "e4 ")
        .replace("v02-", "")
        .replace("rabbitmq-", "rmq ")
        .replace("postgres-", "pg ")
    )


def _escape(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
