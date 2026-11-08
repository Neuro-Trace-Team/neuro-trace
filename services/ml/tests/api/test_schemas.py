from uuid import uuid4

from api.schemas import AnalysesResponse, AnalysisDto
from domain.entities.analysis import Analysis


def test_dto_is_built_from_domain_entity_using_event_timestamp():
    dto = AnalysisDto.model_validate(Analysis(1, uuid4(), 12.5, 0.7, 0.9, 3))

    assert dto.model_dump() == {
        "analysis_id": 1, "time_stamp": 12.5, "result": 0.7, "confidence": 0.9,
    }


def test_dto_allows_missing_confidence():
    dto = AnalysisDto.model_validate(Analysis(1, uuid4(), 1.0, 0.7, None, 3))
    assert dto.confidence is None


def test_response_total_count_defaults_to_none():
    assert AnalysesResponse(examination_id=uuid4(), analyses=[]).total_analyses_count is None
