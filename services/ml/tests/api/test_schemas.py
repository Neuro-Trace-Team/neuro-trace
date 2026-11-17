from uuid import uuid4

from api.schemas import AnalysesResponse, AnalysisDto
from domain.entities.analysis import Analysis
import pytest


def test_dto_is_built_from_domain_entity_using_event_timestamp():
    dto = AnalysisDto.from_domain(Analysis(1, uuid4(), 12.5, 0.7, 0.9, 3))

    assert dto.model_dump() == {
        "analysis_id": 1, "time_stamp": 12500, "result": 0.7, "confidence": 0.9, "is_valid": True, "invalid_reason": None
    }


def test_dto_allows_missing_confidence():
    dto = AnalysisDto.from_domain(Analysis(1, uuid4(), 1.0, 0.7, None, 3))
    assert dto.confidence is None


def test_response_total_count_defaults_to_none():
    assert AnalysesResponse(examination_id=uuid4(), analyses=[]).total_analyses_count is None


@pytest.mark.parametrize("raw, expected", [(7.126, 7.13), (7.124, 7.12), (0.0, 0.0),
                                           (10.0, 10.0), (9.999, 10.0), (0.004, 0.0)])
def test_dto_rounds_result_to_two_decimals(raw, expected):
    assert AnalysisDto.from_domain(Analysis(1, uuid4(), 1.0, raw, None, 1)).result == expected


def test_dto_for_invalid_analysis_has_null_result_and_reason():
    dto = AnalysisDto.from_domain(Analysis(1, uuid4(), 1.0, None, None, 1, False, "prediction_failed"))
    assert (dto.is_valid, dto.result, dto.invalid_reason) == (False, None, "prediction_failed")
