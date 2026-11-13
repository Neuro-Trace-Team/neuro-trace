from uuid import uuid4
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from src.schemas.examinations import ExaminationResultsProcessingResponse, ExaminationResultsResponse
from src.api.deps import get_current_user
from src.api.v1 import examinations as examination_api
from src.db.sessions import get_medical_db
from src.main import app
from src.models.medical import ExaminationStatus
from src.services import ml


def test_ml_results_contract_preserves_timestamp_count_and_null_confidence() -> None:
    examination_id = uuid4()

    response = ExaminationResultsResponse.model_validate({
        "examination_id": str(examination_id),
        "total_analyses_count": 2,
        "analyses": [
            {"analysis_id": 7, "time_stamp": "00:00:12:500", "is_valid": True, "result": 6.4, "confidence": None, "invalid_reason": None},
        ],
    })

    assert response.model_dump(mode="json") == {
        "examination_id": str(examination_id),
        "total_analyses_count": 2,
        "analyses": [
            {"analysis_id": 7, "time_stamp": "00:00:12:500", "is_valid": True, "result": 6.4, "confidence": None, "invalid_reason": None},
        ],
    }


def test_ml_processing_contract_exposes_progress_without_fake_analyses() -> None:
    examination_id = uuid4()

    response = ExaminationResultsProcessingResponse.model_validate({
        "examination_id": str(examination_id),
        "status": "PROCESSING",
        "received_analyses_count": 0,
        "total_analyses_count": 3,
    })

    assert response.model_dump(mode="json") == {
        "examination_id": str(examination_id),
        "status": "PROCESSING",
        "received_analyses_count": 0,
        "total_analyses_count": 3,
        "analyses": [],
    }


@pytest.mark.parametrize("suffix", ["", "/results"])
@pytest.mark.parametrize("all_invalid", [False, True])
def test_results_endpoints_preserve_invalid_analyses(monkeypatch, suffix, all_invalid) -> None:
    examination_id = uuid4()
    now = datetime.now(timezone.utc)
    examination = SimpleNamespace(
        id=examination_id, patient_id=uuid4(), uploaded_by=uuid4(),
        original_filename="test.edf", file_format="edf", file_size_bytes=123,
        file_checksum=None, status=ExaminationStatus.READY,
        examination_date=now, created_at=now, updated_at=now,
    )
    analyses = [
        {"analysis_id": 7, "time_stamp": 12500, "is_valid": False,
         "result": None, "confidence": None, "invalid_reason": "PAF_UNAVAILABLE"},
        {"analysis_id": 8, "time_stamp": 25000, "is_valid": not all_invalid,
         "result": None if all_invalid else 6.4},
    ]
    monkeypatch.setattr(examination_api.service, "get_examination", lambda *_: examination)
    monkeypatch.setattr(ml, "get_settings", lambda: SimpleNamespace(ml_url="http://ml.test", service_timeout_seconds=1))
    monkeypatch.setattr(ml.httpx, "get", lambda url, **kwargs: httpx.Response(
        200, json={"examination_id": str(examination_id), "total_analyses_count": 2, "analyses": analyses},
        request=httpx.Request("GET", url),
    ))
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: SimpleNamespace(role="ADMIN"))
    monkeypatch.setitem(app.dependency_overrides, get_medical_db, lambda: None)

    response = TestClient(app).get(f"/api/v1/examinations/{examination_id}{suffix}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_analyses_count"] == 2
    assert body["analyses"] == [
        {**analyses[0], "time_stamp": "00:00:12:500"},
        {**analyses[1], "time_stamp": "00:00:25:000", "confidence": None, "invalid_reason": None},
    ]
    if not suffix:
        assert body["status"] == "READY"
        assert body["analysis_status"] == "READY"
