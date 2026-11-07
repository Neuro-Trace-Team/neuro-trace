from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class AnalysisDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    analysis_id: int
    time_stamp: float = Field(validation_alias="event_timestamp")
    result: float
    confidence: float

class AnalysesResponse(BaseModel):
    examination_id: UUID
    total_analyses_count: int | None = None
    analyses: list[AnalysisDto]