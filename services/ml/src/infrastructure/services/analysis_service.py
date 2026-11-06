from dataclasses import dataclass
from uuid import UUID
from domain.entities.analysis import Analysis
from domain.repositories.ianalysis_repository import IAnalysisRepository


@dataclass(frozen=True)
class ExaminationResults:
    is_complete: bool
    received: int
    expected: int | None    # None if nothing has arrived yet
    analyses: list[Analysis]

class AnalysisService:
    def __init__(self, repo: IAnalysisRepository):
        self._repo = repo

    async def get_results(self, examination_id: UUID) -> ExaminationResults:
        analyses = await self._repo.list_for_examination(examination_id)    # ordered by event_timestamp
        expected = analyses[0].total_analyses_count if analyses else None
        complete = expected is not None and len(analyses) >= expected
        return ExaminationResults(complete, len(analyses), expected, analyses)