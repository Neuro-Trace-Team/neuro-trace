from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import Mock
from urllib.error import HTTPError, URLError
from uuid import uuid4

import pytest
from pydantic import ValidationError

from service.jobs import BackendAPIError


class _Response:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_backend_examination_lookup_uses_only_examination_id(monkeypatch, backend_client) -> None:
    response = _Response({"examination_id": "examination-1"})
    urlopen = Mock(return_value=response)
    monkeypatch.setattr("service.jobs.urlopen", urlopen)

    result = backend_client.get_examination("examination-1")

    assert result == {"examination_id": "examination-1"}
    request = urlopen.call_args.args[0]
    assert request.full_url == (
        "http://mock-backend/api/v1/internal/preprocessing/examinations/examination-1"
    )
    assert request.method == "GET"
    assert request.headers["Authorization"] == "Bearer mock-service-token"
    assert request.data is None


def test_backend_http_errors_are_exposed_as_backend_api_errors(monkeypatch, backend_client) -> None:
    error = HTTPError(
        "http://mock-backend", 503, "Unavailable", {}, BytesIO(b"backend unavailable")
    )
    monkeypatch.setattr("service.jobs.urlopen", Mock(side_effect=error))

    with pytest.raises(BackendAPIError, match="backend unavailable") as raised:
        backend_client.get_examination("examination-1")
    assert raised.value.status_code == 503


@pytest.mark.parametrize("error", [URLError("connection refused"), TimeoutError()])
def test_backend_connection_errors_are_wrapped(monkeypatch, backend_client, error):
    monkeypatch.setattr("service.jobs.urlopen", Mock(side_effect=error))

    with pytest.raises(BackendAPIError, match="Cannot reach NeuroTrace backend") as raised:
        backend_client.get_examination("examination-1")
    assert raised.value.status_code is None


def test_preprocessing_request_requires_storage_coordinates():
    import main

    with pytest.raises(ValidationError) as raised:
        main.JobRequest(examination_id=uuid4())

    assert {error["loc"][-1] for error in raised.value.errors()} == {
        "storage_bucket",
        "storage_key",
    }


def test_start_preprocessing_tracks_status_by_examination(monkeypatch):
    from fastapi import BackgroundTasks
    import main

    examination_id = uuid4()
    bucket = "exam-bucket"
    source_key = f"examinations/{examination_id}/recording.bdf"
    backend = Mock()
    manager = main.JobManager(main.settings, Mock(), backend)
    monkeypatch.setattr(main, "backend", backend)
    monkeypatch.setattr(main, "jobs", manager)
    tasks = BackgroundTasks()

    result = main.preprocess_examination(
        examination_id,
        tasks,
        main.JobRequest(
            examination_id=examination_id,
            storage_bucket=bucket,
            storage_key=source_key,
        ),
    )

    assert result["examination_id"] == str(examination_id)
    assert "job_id" not in result
    assert result["status"] == "QUEUED"
    assert len(tasks.tasks) == 1
    assert tasks.tasks[0].args == (str(examination_id),)
    main.JobResponse(**result)
    backend.create_job.assert_not_called()


def test_request_examination_mismatch_rejected_before_starting(monkeypatch):
    from fastapi import BackgroundTasks, HTTPException
    import main

    backend = Mock()
    monkeypatch.setattr(main, "backend", backend)
    with pytest.raises(HTTPException) as raised:
        main.preprocess_examination(
            uuid4(),
            BackgroundTasks(),
            main.JobRequest(
                examination_id=uuid4(), storage_bucket="bucket", storage_key="source.bdf"
            ),
        )
    assert raised.value.status_code == 422
    backend.create_job.assert_not_called()


@pytest.mark.parametrize(
    ("storage_bucket", "storage_key"), [("", "source.bdf"), ("bucket", " ")]
)
def test_missing_or_blank_coordinates_are_rejected_before_job_creation(
    monkeypatch, storage_bucket, storage_key
):
    from fastapi import BackgroundTasks, HTTPException
    import main

    examination_id = uuid4()
    manager = Mock()
    monkeypatch.setattr(main, "jobs", manager)
    request = main.JobRequest(
        examination_id=examination_id,
        storage_bucket=storage_bucket,
        storage_key=storage_key,
    )

    with pytest.raises(HTTPException) as raised:
        main.preprocess_examination(examination_id, BackgroundTasks(), request)

    assert raised.value.status_code == 422
    manager.create.assert_not_called()
