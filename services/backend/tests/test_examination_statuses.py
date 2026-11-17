from src.models.medical import ExaminationStatus
from src.schemas.examinations import ExaminationStatusesResponse


def test_examination_statuses_are_backend_owned_enums() -> None:
    response = ExaminationStatusesResponse(statuses=list(ExaminationStatus))

    assert response.model_dump(mode="json") == {
        "statuses": ["PREPROCESSING", "READY"],
    }
