from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from src.services import ml, preprocessing


@pytest.fixture
def examination_id():
    return uuid4()


def test_preprocessing_request_contains_only_storage_contract(monkeypatch, examination_id) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(preprocessing, "get_settings", lambda: SimpleNamespace(preprocessing_url="http://preprocessing.test", service_timeout_seconds=1))

    def post(url: str, **kwargs):
        captured.update(url=url, **kwargs)
        return httpx.Response(202, request=httpx.Request("POST", url))

    monkeypatch.setattr(preprocessing.httpx, "post", post)
    preprocessing.PreprocessingClient().request(examination_id, "examinations", "examinations/patient/file.eeg")

    assert captured["url"] == f"http://preprocessing.test/api/v1/examinations/{examination_id}/preprocessing"
    assert captured["json"] == {"examination_id": str(examination_id), "storage_bucket": "examinations", "storage_key": "examinations/patient/file.eeg"}


@pytest.mark.parametrize("error", [httpx.ConnectError("offline"), httpx.TimeoutException("timeout")])
def test_preprocessing_request_maps_transport_errors(monkeypatch, examination_id, error) -> None:
    monkeypatch.setattr(preprocessing, "get_settings", lambda: SimpleNamespace(preprocessing_url="http://preprocessing.test", service_timeout_seconds=1))
    monkeypatch.setattr(preprocessing.httpx, "post", lambda *args, **kwargs: (_ for _ in ()).throw(error))
    with pytest.raises(preprocessing.PreprocessingServiceError):
        preprocessing.PreprocessingClient().request(examination_id, "examinations", "key")


def test_preprocessing_status_validates_identity(monkeypatch, examination_id) -> None:
    monkeypatch.setattr(preprocessing, "get_settings", lambda: SimpleNamespace(preprocessing_url="http://preprocessing.test", service_timeout_seconds=1))
    response = httpx.Response(200, json={"examination_id": str(examination_id), "status": "RUNNING"}, request=httpx.Request("GET", "http://preprocessing.test"))
    monkeypatch.setattr(preprocessing.httpx, "get", lambda *args, **kwargs: response)
    assert preprocessing.PreprocessingClient().status(examination_id) == {"examination_id": str(examination_id), "status": "RUNNING"}


@pytest.mark.parametrize("payload", [{}, {"examination_id": "wrong", "status": "RUNNING"}, {"examination_id": "not-a-uuid"}])
def test_preprocessing_status_rejects_invalid_response(monkeypatch, examination_id, payload) -> None:
    monkeypatch.setattr(preprocessing, "get_settings", lambda: SimpleNamespace(preprocessing_url="http://preprocessing.test", service_timeout_seconds=1))
    monkeypatch.setattr(preprocessing.httpx, "get", lambda *args, **kwargs: httpx.Response(200, json=payload, request=httpx.Request("GET", "http://preprocessing.test")))
    with pytest.raises(preprocessing.PreprocessingServiceError):
        preprocessing.PreprocessingClient().status(examination_id)


def test_ml_results_validates_contract(monkeypatch, examination_id) -> None:
    analysis_id = uuid4()
    monkeypatch.setattr(ml, "get_settings", lambda: SimpleNamespace(ml_url="http://ml.test", service_timeout_seconds=1))
    monkeypatch.setattr(ml.httpx, "get", lambda *args, **kwargs: httpx.Response(200, json={"examination_id": str(examination_id), "analyses": [{"analysis_id": str(analysis_id), "result": 6.4, "confidence": 0.91}]}, request=httpx.Request("GET", "http://ml.test")))
    assert ml.MLClient().results(examination_id)["analyses"][0]["analysis_id"] == str(analysis_id)


@pytest.mark.parametrize("payload", [{}, {"examination_id": "wrong", "analyses": []}, {"examination_id": "x"}])
def test_ml_results_rejects_invalid_top_level_response(monkeypatch, examination_id, payload) -> None:
    monkeypatch.setattr(ml, "get_settings", lambda: SimpleNamespace(ml_url="http://ml.test", service_timeout_seconds=1))
    monkeypatch.setattr(ml.httpx, "get", lambda *args, **kwargs: httpx.Response(200, json=payload, request=httpx.Request("GET", "http://ml.test")))
    with pytest.raises(ml.MLServiceError):
        ml.MLClient().results(examination_id)
