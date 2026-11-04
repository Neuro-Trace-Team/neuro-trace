from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

@dataclass(frozen=True)
class NewAnalysis:
    examination_id: UUID
    result: float
    confidence: float

@dataclass(frozen=True)
class Analysis:
    analysis_id: int
    examination_id: UUID
    time_stamp: datetime
    result: float
    confidence: float
    total_analyses_count: int