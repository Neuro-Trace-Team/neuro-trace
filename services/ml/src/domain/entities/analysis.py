from dataclasses import dataclass
from uuid import UUID

@dataclass(frozen=True)
class NewAnalysis:
    examination_id: UUID
    time_stamp: float
    result: float
    confidence: float | None
    total_analyses_count: int

@dataclass(frozen=True)
class Analysis:
    analysis_id: int
    examination_id: UUID
    time_stamp: float
    result: float
    confidence: float | None
    total_analyses_count: int