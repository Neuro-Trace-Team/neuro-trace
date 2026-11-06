from uuid import UUID
from pydantic import BaseModel, ConfigDict


class AnalysisDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    analysis_id: int
    time_stamp: float
    result: float
    confidence: float

class AnalysesResponse(BaseModel):
    examination_id: UUID
    total_analyses_count: int | None
    analyses: list[AnalysisDto]