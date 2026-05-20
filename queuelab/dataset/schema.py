from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any


class JobValidationError(ValueError):
    """Raised when a GH Archive event cannot be normalized into a job."""


@dataclass(frozen=True)
class Job:
    job_id: str
    event_id: str
    event_type: str
    repo_id: int
    repo_name: str
    actor_id: int
    actor_login_hash: str
    event_created_at: str
    payload_size_bytes: int
    source_file: str
    chaos: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


def normalize_event(event: dict[str, Any], source_file: str) -> Job:
    event_id = _required_str(event, "id")
    event_type = _required_str(event, "type")
    created_at = _required_str(event, "created_at")

    repo = _required_dict(event, "repo")
    repo_id = _required_int(repo, "id", parent="repo")
    repo_name = _required_str(repo, "name", parent="repo")

    actor = _required_dict(event, "actor")
    actor_id = _required_int(actor, "id", parent="actor")
    actor_login = _required_str(actor, "login", parent="actor")

    payload = event.get("payload", {})
    payload_bytes = len(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())

    return Job(
        job_id=f"gh:{event_id}",
        event_id=event_id,
        event_type=event_type,
        repo_id=repo_id,
        repo_name=repo_name,
        actor_id=actor_id,
        actor_login_hash=_hash_actor_login(actor_login),
        event_created_at=created_at,
        payload_size_bytes=payload_bytes,
        source_file=source_file,
    )


def _hash_actor_login(login: str) -> str:
    digest = hashlib.sha256(login.encode()).hexdigest()
    return f"sha256:{digest}"


def _required_dict(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise JobValidationError(f"missing or invalid object field: {key}")
    return value


def _required_str(data: dict[str, Any], key: str, parent: str | None = None) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        field = f"{parent}.{key}" if parent else key
        raise JobValidationError(f"missing or invalid string field: {field}")
    return value


def _required_int(data: dict[str, Any], key: str, parent: str | None = None) -> int:
    value = data.get(key)
    if not isinstance(value, int):
        field = f"{parent}.{key}" if parent else key
        raise JobValidationError(f"missing or invalid integer field: {field}")
    return value
