from decimal import Decimal
from uuid import UUID
from domain.entities.analysis import Analysis
from pydantic import BaseModel


RESULT_DECIMALS = 2

class AnalysisDto(BaseModel):
    analysis_id: int
    time_stamp: int
    is_valid: bool
    result: float | None
    confidence: float | None = None
    invalid_reason: str | None = None

    @classmethod
    def from_domain(cls, a: Analysis) -> "AnalysisDto":
        return cls(
            analysis_id=a.analysis_id,
            time_stamp=round(a.event_timestamp * 1000),
            is_valid=a.is_valid,
            result=None if a.result is None else round(a.result, RESULT_DECIMALS),
            confidence=a.confidence,
            invalid_reason=a.invalid_reason
        )

class AnalysesResponse(BaseModel):
    examination_id: UUID
    total_analyses_count: int | None = None
    analyses: list[AnalysisDto]