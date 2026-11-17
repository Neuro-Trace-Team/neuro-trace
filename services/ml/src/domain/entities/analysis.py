from dataclasses import dataclass
from uuid import UUID

def _check_validity(is_valid, result, confidence, invalid_reason) -> None:
    if is_valid:
        if result is None or invalid_reason is not None:
            raise ValueError("a valid analysis needs a result and no invalid_reason")
    elif result is not None or confidence is not None or not invalid_reason:
        raise ValueError("an invalid analysis has no result or confidence and needs an invalid_reason")

@dataclass(frozen=True)
class NewAnalysis:
    examination_id: UUID
    event_timestamp: float
    result: float | None
    confidence: float | None
    total_analyses_count: int
    is_valid: bool = True
    invalid_reason: str | None = None

    def __post_init__(self) -> None:
        _check_validity(self.is_valid, self.result, self.confidence, self.invalid_reason)

@dataclass(frozen=True)
class Analysis:
    analysis_id: int
    examination_id: UUID
    event_timestamp: float
    result: float | None
    confidence: float | None
    total_analyses_count: int
    is_valid: bool = True
    invalid_reason: str | None = None

    def __post_init__(self) -> None:
        _check_validity(self.is_valid, self.result, self.confidence, self.invalid_reason)