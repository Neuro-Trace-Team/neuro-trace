from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

import pytest

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


def test_backend_http_request_contains_expected_method_path_and_payload(
    monkeypatch, backend_client
) -> None:
    response = _Response({"id": "job-1", "status": "QUEUED"})
    urlopen = Mock(return_value=response)
    monkeypatch.setattr("service.jobs.urlopen", urlopen)

    result = backend_client.create_job("examination-1")

    assert result == {"id": "job-1", "status": "QUEUED"}
    request = urlopen.call_args.args[0]
    assert request.full_url == (
        "http://mock-backend/api/v1/examinations/examination-1/"
        "preprocessing-jobs"
    )
    assert request.method == "POST"
    assert request.headers["Authorization"] == "Bearer mock-service-token"
    assert json.loads(request.data) == {"pipeline_version": "0.1.0"}


def test_backend_http_errors_are_exposed_as_backend_api_errors(monkeypatch, backend_client) -> None:
    error = HTTPError(
        "http://mock-backend", 503, "Unavailable", {}, BytesIO(b"backend unavailable")
    )
    monkeypatch.setattr("service.jobs.urlopen", Mock(side_effect=error))

    with pytest.raises(BackendAPIError, match="backend unavailable") as raised:
        backend_client.get_job("job-1")
    assert raised.value.status_code == 503


@pytest.mark.parametrize("error", [URLError("connection refused"), TimeoutError()])
def test_backend_connection_errors_are_wrapped(monkeypatch, backend_client, error):
    monkeypatch.setattr("service.jobs.urlopen", Mock(side_effect=error))

    with pytest.raises(BackendAPIError, match="Cannot reach NeuroTrace backend") as raised:
        backend_client.get_job("job-1")
    assert raised.value.status_code is None


def test_start_job_accepts_examination_without_backend_analysis_id(monkeypatch):
    from uuid import uuid4
    from fastapi import BackgroundTasks
    import main

    examination_id, job_id = uuid4(), str(uuid4())
    backend = Mock()
    backend.create_job.return_value = {"id": job_id, "examination_id": str(examination_id)}
    manager = main.JobManager(main.settings, Mock(), backend)
    monkeypatch.setattr(main, "backend", backend)
    monkeypatch.setattr(main, "jobs", manager)
    tasks = BackgroundTasks()

    result = main.preprocess_examination(
        examination_id, tasks, main.JobRequest(examination_id=examination_id)
    )

    assert result["examination_id"] == str(examination_id)
    assert "analysis_id" not in result
    assert result["job_id"] == job_id
    assert len(tasks.tasks) == 1
    assert tasks.tasks[0].args == (job_id, str(examination_id))
    main.JobResponse(**result)


def test_request_examination_mismatch_rejected_before_backend_call(monkeypatch):
    from uuid import uuid4
    from fastapi import BackgroundTasks, HTTPException
    import main

    backend = Mock()
    monkeypatch.setattr(main, "backend", backend)
    with pytest.raises(HTTPException) as raised:
        main.preprocess_examination(
            uuid4(), BackgroundTasks(), main.JobRequest(examination_id=uuid4())
        )
    assert raised.value.status_code == 422
    backend.create_job.assert_not_called()


@pytest.mark.parametrize("backend_examination_id", [None, "invalid", "13b5b2e5-078b-447d-a6d8-6e18330d105a"])
def test_invalid_backend_examination_rejected(monkeypatch, backend_examination_id):
    from uuid import uuid4
    from fastapi import BackgroundTasks, HTTPException
    import main

    backend = Mock()
    backend.create_job.return_value = {"id": str(uuid4()), "examination_id": backend_examination_id}
    monkeypatch.setattr(main, "backend", backend)
    tasks = BackgroundTasks()
    with pytest.raises(HTTPException) as raised:
        main.preprocess_examination(uuid4(), tasks)
    assert raised.value.status_code == 502
    assert tasks.tasks == []
