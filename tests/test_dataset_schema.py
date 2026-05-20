import json

import pytest

from queuelab.dataset.schema import JobValidationError, normalize_event


def test_normalize_event_builds_public_job_shape() -> None:
    event = {
        "id": "1234567890",
        "type": "PushEvent",
        "actor": {"id": 456, "login": "octocat"},
        "repo": {"id": 123, "name": "owner/repo"},
        "payload": {"size": 2, "ref": "refs/heads/main"},
        "public": True,
        "created_at": "2025-01-01T00:00:01Z",
    }

    job = normalize_event(event, source_file="2025-01-01-0.json.gz")

    assert job.job_id == "gh:1234567890"
    assert job.event_id == "1234567890"
    assert job.event_type == "PushEvent"
    assert job.repo_id == 123
    assert job.repo_name == "owner/repo"
    assert job.actor_id == 456
    assert job.actor_login_hash.startswith("sha256:")
    assert "octocat" not in job.to_json()
    assert job.event_created_at == "2025-01-01T00:00:01Z"
    assert job.payload_size_bytes == len(
        json.dumps(event["payload"], sort_keys=True, separators=(",", ":")).encode()
    )
    assert job.source_file == "2025-01-01-0.json.gz"
    assert job.chaos is None


def test_normalize_event_rejects_missing_required_fields() -> None:
    event = {
        "id": "1234567890",
        "type": "PushEvent",
        "actor": {"id": 456, "login": "octocat"},
        "payload": {},
        "created_at": "2025-01-01T00:00:01Z",
    }

    with pytest.raises(JobValidationError, match="repo"):
        normalize_event(event, source_file="2025-01-01-0.json.gz")
