from uuid import UUID
from domain.entities.analysis import Analysis, NewAnalysis
from infrastructure.db.models import AnalysisRow
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert


def _to_domain(r: AnalysisRow) -> Analysis:
    return Analysis(r.analysis_id, r.examination_id, r.time_stamp,
                    r.result, r.confidence, r.total_analyses_count)

class SqlAlchemyAnalysisRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, analysis: NewAnalysis) -> Analysis:
        count = (await self._session.execute(
            select(func.count()).where(AnalysisRow.examination_id == analysis.examination_id)
        )).scalar_one()

        stmt = (
            insert(AnalysisRow)
            .values(
                examination_id=analysis.examination_id,
                time_stamp=analysis.time_stamp,
                result=analysis.result,
                confidence=analysis.confidence,
                total_analyses_count=count + 1,
            )
            .on_conflict_do_nothing(index_elements=["examination_id", "time_stamp"])
            .returning(AnalysisRow)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()

        if row is None:
            # Idempotency: Duplicate (e.g. redelivered message): return the analysis that already exists
            row = (await self._session.execute(
                select(AnalysisRow).where(
                    AnalysisRow.examination_id == analysis.examination_id,
                    AnalysisRow.time_stamp == analysis.time_stamp,
                )
            )).scalar_one()

        return _to_domain(row)

    async def get(self, analysis_id: int) -> Analysis | None:
        row = await self._session.get(AnalysisRow, analysis_id)
        return _to_domain(row) if row else None

    async def list_for_examination(self, examination_id: UUID) -> list[Analysis]:
        rows = await self._session.scalars(
            select(AnalysisRow)
            .where(AnalysisRow.examination_id == examination_id)
            .order_by(AnalysisRow.time_stamp)
        )
        return [_to_domain(r) for r in rows]