from typing import Protocol
from uuid import UUID

from domain.entities.analysis import Analysis, NewAnalysis


class IAnalysisRepository(Protocol):
    async def add(self, analysis: NewAnalysis) -> Analysis: ...
    async def get(self, analysis_id: int) -> Analysis | None: ...
    async def list_for_examination(self, examination_id: UUID) -> list[Analysis]: ...