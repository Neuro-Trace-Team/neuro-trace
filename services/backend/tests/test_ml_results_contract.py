from uuid import uuid4

from src.schemas.examinations import ExaminationResultsProcessingResponse, ExaminationResultsResponse


def test_ml_results_contract_preserves_timestamp_count_and_null_confidence() -> None:
    examination_id = uuid4()

    response = ExaminationResultsResponse.model_validate({
        "examination_id": str(examination_id),
        "total_analyses_count": 2,
        "analyses": [
            {"analysis_id": 7, "time_stamp": 12.5, "result": 6.4, "confidence": None},
        ],
    })

    assert response.model_dump(mode="json") == {
        "examination_id": str(examination_id),
        "total_analyses_count": 2,
        "analyses": [
            {"analysis_id": 7, "time_stamp": 12.5, "result": 6.4, "confidence": None},
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
