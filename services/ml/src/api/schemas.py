from uuid import UUID
from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class AnalysisDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    analysis_id: int
    time_stamp: float = Field(validation_alias=AliasChoices("event_timestamp", "time_stamp"))
    result: float
    confidence: float | None = None

class AnalysesResponse(BaseModel):
    examination_id: UUID
    total_analyses_count: int | None = None
    analyses: list[AnalysisDto]