from __future__ import annotations

import json
from unittest.mock import Mock

from service.jobs import BackendAPIError, NeuroTraceClient


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
    error = Mock()
    error.code = 503
    error.read.return_value = b"backend unavailable"
    monkeypatch.setattr("service.jobs.urlopen", Mock(side_effect=BackendAPIError("mock error", 503)))

    try:
        backend_client.get_job("job-1")
    except BackendAPIError as raised:
        assert raised.status_code == 503
    else:
        raise AssertionError("BackendAPIError was not raised")
