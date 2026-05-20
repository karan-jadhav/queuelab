from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from queuelab.workers.queued import ChaosConfig, run_postgres_queue, run_rabbitmq, run_sqs


@dataclass(frozen=True)
class ExperimentRunSpec:
    backend: str
    run_id: str
    experiment_id: str
    dataset: Path
    workers: int
    batch_size: int
    options: dict[str, Any]
    chaos: ChaosConfig


def load_experiment_config(path: Path) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError(f"experiment config must be a mapping: {path}")
    return config


def build_run_specs(path: Path, *, run_prefix: str | None = None) -> list[ExperimentRunSpec]:
    config = load_experiment_config(path)
    experiment_id = _required_str(config, "experiment_id")
    dataset_path = Path(_required_mapping(config, "dataset")["path"])
    run_config = _required_mapping(config, "run")
    workers_values = _as_list(run_config.get("workers", 1))
    batch_size_values = _as_list(run_config.get("batch_size", 10))
    chaos_values = _chaos_sweep_values(_mapping(config.get("chaos")))

    specs: list[ExperimentRunSpec] = []
    for backend, backend_options in _backend_options(config).items():
        for workers in workers_values:
            for batch_size in batch_size_values:
                for option_values in _expand_options(backend_options):
                    for chaos_options in chaos_values:
                        run_id = _run_id(
                            run_prefix=run_prefix,
                            experiment_id=experiment_id,
                            backend=backend,
                            workers=int(workers),
                            batch_size=int(batch_size),
                            options=option_values,
                            chaos_options=chaos_options,
                        )
                        specs.append(
                            ExperimentRunSpec(
                                backend=backend,
                                run_id=run_id,
                                experiment_id=experiment_id,
                                dataset=dataset_path,
                                workers=int(workers),
                                batch_size=int(batch_size),
                                options=option_values,
                                chaos=_chaos_config(chaos_options),
                            )
                        )
    return specs


def run_experiment_config(path: Path, *, run_prefix: str | None = None) -> list[str]:
    run_ids: list[str] = []
    for spec in build_run_specs(path, run_prefix=run_prefix):
        _run_spec(spec)
        run_ids.append(spec.run_id)
    return run_ids


def _run_spec(spec: ExperimentRunSpec) -> None:
    if spec.backend == "rabbitmq":
        run_rabbitmq(
            dataset=spec.dataset,
            run_id=spec.run_id,
            experiment_id=spec.experiment_id,
            workers=spec.workers,
            batch_size=spec.batch_size,
            prefetch_count=int(spec.options.get("prefetch_count", 10)),
            chaos_config=spec.chaos,
        )
        return
    if spec.backend == "sqs":
        run_sqs(
            dataset=spec.dataset,
            run_id=spec.run_id,
            experiment_id=spec.experiment_id,
            workers=spec.workers,
            batch_size=spec.batch_size,
            wait_time_seconds=int(spec.options.get("wait_seconds", 1)),
            visibility_timeout_seconds=_optional_int(
                spec.options.get("visibility_timeout_seconds")
            ),
            chaos_config=spec.chaos,
        )
        return
    if spec.backend == "postgres":
        run_postgres_queue(
            dataset=spec.dataset,
            run_id=spec.run_id,
            experiment_id=spec.experiment_id,
            workers=spec.workers,
            batch_size=spec.batch_size,
            lease_timeout_seconds=int(spec.options.get("lease_timeout_seconds", 30)),
            max_attempts=int(spec.options.get("max_attempts", 3)),
            chaos_config=spec.chaos,
        )
        return
    raise ValueError(f"unsupported experiment backend: {spec.backend}")


def _backend_options(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if "backends" in config:
        return {
            str(backend): _mapping(options)
            for backend, options in _required_mapping(config, "backends").items()
        }
    run_config = _required_mapping(config, "run")
    backend = str(run_config.get("backend", ""))
    if not backend:
        raise ValueError("config must contain backends or run.backend")
    return {backend: _mapping(config.get("backend"))}


def _expand_options(options: dict[str, Any]) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = [{}]
    for key, value in options.items():
        values = _as_list(value)
        expanded = [dict(current, **{key: item}) for current in expanded for item in values]
    return expanded


def _chaos_sweep_values(chaos: dict[str, Any]) -> list[dict[str, Any]]:
    db_delay_values = chaos.pop("db_delay_ms_values", None)
    if db_delay_values is None:
        return [chaos]
    return [dict(chaos, db_delay_ms=value) for value in _as_list(db_delay_values)]


def _chaos_config(chaos: dict[str, Any]) -> ChaosConfig:
    return ChaosConfig(
        crash_after_db_commit_attempts=int(chaos.get("crash_after_db_commit_attempts", 0)),
        max_worker_crashes=int(chaos.get("max_worker_crashes", 1)),
        fail_poison_messages=bool(chaos.get("fail_poison_messages", False)),
        db_delay_ms=int(chaos.get("db_delay_ms", 0)),
        transient_failure_rate=float(chaos.get("transient_failure_rate", 0)),
        transient_failure_max_attempts=int(chaos.get("max_attempts", 3)),
    )


def _run_id(
    *,
    run_prefix: str | None,
    experiment_id: str,
    backend: str,
    workers: int,
    batch_size: int,
    options: dict[str, Any],
    chaos_options: dict[str, Any],
) -> str:
    parts = [run_prefix or experiment_id, backend, f"w{workers}", f"b{batch_size}"]
    parts.extend(f"{_slug(key)}{_slug(value)}" for key, value in sorted(options.items()))
    parts.extend(f"{_slug(key)}{_slug(value)}" for key, value in sorted(chaos_options.items()))
    return "-".join(part for part in parts if part)


def _slug(value: object) -> str:
    return str(value).lower().replace("_", "").replace(".", "p").replace("/", "-")


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else [value]


def _mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("expected mapping")
    return dict(value)


def _required_mapping(config: dict[str, Any], key: str) -> dict[str, Any]:
    value = config.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"missing mapping: {key}")
    return value


def _required_str(config: dict[str, Any], key: str) -> str:
    value = config.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"missing string: {key}")
    return value


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)
