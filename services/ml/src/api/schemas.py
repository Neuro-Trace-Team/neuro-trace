from uuid import UUID
from domain.entities.analysis import Analysis
from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class AnalysisDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    analysis_id: int
    time_stamp: int
    result: float
    confidence: float | None = None

    @classmethod
    def from_domain(cls, a: Analysis) -> "AnalysisDto":
        return cls(
            analysis_id=a.analysis_id,
            time_stamp=round(a.event_timestamp * 1000),
            result=a.result,
            confidence=a.confidence,
        )

class AnalysesResponse(BaseModel):
    examination_id: UUID
    total_analyses_count: int | None = None
    analyses: list[AnalysisDto]