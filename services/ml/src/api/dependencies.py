from typing import AsyncIterator
from fastapi import Request
from infrastructure.repositories.sql_alchemy_analysis_repository import SqlAlchemyAnalysisRepository
from infrastructure.services.analysis_service import AnalysisService


async def get_analysis_service(request: Request) -> AsyncIterator[AnalysisService]:
    async with request.app.state.session_factory() as session:
        yield AnalysisService(SqlAlchemyAnalysisRepository(session))