from domain.entities.analysis import Analysis, NewAnalysis
from domain.repositories.analysis_repository import AnalysisRepository

# Temporary class before an actual implementation
class AnalysisService:
    def __init__(self, repo: AnalysisRepository):
        self._repo = repo

    async def record(self, new: NewAnalysis) -> Analysis:
        return await self._repo.add(new)