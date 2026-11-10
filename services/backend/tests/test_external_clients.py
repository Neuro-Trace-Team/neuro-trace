from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import httpx
import pytest

from src.services import ml, preprocessing
from src.services.storage import RustFSStorage


@pytest.fixture
def examination_id():
    return uuid4()


def test_preprocessing_request_contains_storage_and_timestamps_contract(monkeypatch, examination_id) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(preprocessing, "get_settings", lambda: SimpleNamespace(preprocessing_url="http://preprocessing.test", service_timeout_seconds=1))

    def post(url: str, **kwargs):
        captured.update(url=url, **kwargs)
        return httpx.Response(202, request=httpx.Request("POST", url))

    monkeypatch.setattr(preprocessing.httpx, "post", post)
    preprocessing.PreprocessingClient().request(
        examination_id, "examinations", "examinations/patient/file.eeg", ["00:00:00:000"]
    )

    assert captured["url"] == f"http://preprocessing.test/api/v1/examinations/{examination_id}/preprocessing"
    assert captured["json"] == {"examination_id": str(examination_id), "storage_bucket": "examinations", "storage_key": "examinations/patient/file.eeg", "timestamps": ["00:00:00:000"]}


@pytest.mark.parametrize("error", [httpx.ConnectError("offline"), httpx.TimeoutException("timeout")])
def test_preprocessing_request_maps_transport_errors(monkeypatch, examination_id, error) -> None:
    monkeypatch.setattr(preprocessing, "get_settings", lambda: SimpleNamespace(preprocessing_url="http://preprocessing.test", service_timeout_seconds=1))
    monkeypatch.setattr(preprocessing.httpx, "post", lambda *args, **kwargs: (_ for _ in ()).throw(error))
    with pytest.raises(preprocessing.PreprocessingServiceError):
        preprocessing.PreprocessingClient().request(examination_id, "examinations", "key", ["00:00:00:000"])


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
    monkeypatch.setattr(ml, "get_settings", lambda: SimpleNamespace(ml_url="http://ml.test", service_timeout_seconds=1))
    captured = {}
    def get(url, **kwargs):
        captured["url"] = url
        return httpx.Response(200, json={"examination_id": str(examination_id), "total_analyses_count": 1, "analyses": [{"analysis_id": 7, "time_stamp": 12.5, "result": 6.4, "confidence": None}]}, request=httpx.Request("GET", url))
    monkeypatch.setattr(ml.httpx, "get", get)
    results = ml.MLClient().results(examination_id)
    assert results["total_analyses_count"] == 1
    assert results["analyses"][0] == {"analysis_id": 7, "time_stamp": 12.5, "result": 6.4, "confidence": None}
    assert captured["url"] == f"http://ml.test/examinations/{examination_id}/analyses"


def test_rustfs_usage_sums_all_object_listing_pages() -> None:
    storage = object.__new__(RustFSStorage)
    storage.bucket = "examinations"
    storage.client = MagicMock()
    storage.client.list_objects_v2.side_effect = [
        {"Contents": [{"Size": 10}, {"Size": 20}], "IsTruncated": True, "NextContinuationToken": "next"},
        {"Contents": [{"Size": 5}], "IsTruncated": False},
    ]

    usage = storage.usage()

    assert usage.bucket == "examinations"
    assert usage.bucket_exists is True
    assert usage.object_count == 3
    assert usage.used_bytes == 35
    assert storage.client.list_objects_v2.call_args_list[1].kwargs == {
        "Bucket": "examinations", "ContinuationToken": "next"
    }


@pytest.mark.parametrize("payload", [{}, {"examination_id": "wrong", "total_analyses_count": 0, "analyses": []}, {"examination_id": "x"}, {"examination_id": "x", "total_analyses_count": "1", "analyses": []}, {"examination_id": "x", "total_analyses_count": 1, "analyses": [{"analysis_id": 1, "result": 0.5, "confidence": 0.5}]}])
def test_ml_results_rejects_invalid_top_level_response(monkeypatch, examination_id, payload) -> None:
    monkeypatch.setattr(ml, "get_settings", lambda: SimpleNamespace(ml_url="http://ml.test", service_timeout_seconds=1))
    monkeypatch.setattr(ml.httpx, "get", lambda *args, **kwargs: httpx.Response(200, json=payload, request=httpx.Request("GET", "http://ml.test")))
    with pytest.raises(ml.MLServiceError):
        ml.MLClient().results(examination_id)