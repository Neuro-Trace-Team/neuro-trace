from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from domain.entities.analysis import Analysis, NewAnalysis
from infrastructure.db.models import AnalysisRow
from infrastructure.repositories.sql_alchemy_analysis_repository import SqlAlchemyAnalysisRepository, _to_domain
import pytest


def make_row(analysis_id=1, exam_id=None, ts=1.0, result=0.5, conf=0.9, count=1):
    return AnalysisRow(
        analysis_id=analysis_id,
        examination_id=exam_id or uuid4(),
        event_timestamp=ts,
        result=result,
        confidence=conf,
        total_analyses_count=count,
    )


@pytest.fixture
def session():
    s = MagicMock()
    s.execute = AsyncMock(return_value=MagicMock())
    s.scalars = AsyncMock()
    s.get = AsyncMock()
    return s


@pytest.fixture
def repo(session):
    return SqlAlchemyAnalysisRepository(session)


def test_to_domain_maps_all_fields():
    row = make_row(analysis_id=7, ts=12.5, result=0.1, conf=None, count=3)

    result = _to_domain(row)

    assert result == Analysis(7, row.examination_id, 12.5, 0.1, None, 3)


@pytest.mark.asyncio
async def test_add_returns_inserted_row_without_fallback_query(repo, session):
    row = make_row()
    session.execute.return_value.scalar_one_or_none.return_value = row
    new = NewAnalysis(row.examination_id, 1.0, 0.5, 0.9, 1)

    result = await repo.add(new)

    assert result.analysis_id == row.analysis_id
    assert session.execute.await_count == 1


@pytest.mark.asyncio
async def test_add_on_conflict_falls_back_to_select_of_existing_row(repo, session):
    existing = make_row(analysis_id=42)
    insert_result = MagicMock()
    insert_result.scalar_one_or_none.return_value = None
    select_result = MagicMock()
    select_result.scalar_one.return_value = existing
    session.execute.side_effect = [insert_result, select_result]
    new = NewAnalysis(existing.examination_id, 1.0, 0.5, 0.9, 1)

    result = await repo.add(new)

    assert result.analysis_id == 42
    assert session.execute.await_count == 2


@pytest.mark.asyncio
async def test_get_returns_none_when_missing(repo, session):
    session.get.return_value = None

    assert await repo.get(999) is None
    session.get.assert_awaited_once_with(AnalysisRow, 999)


@pytest.mark.asyncio
async def test_get_maps_row_to_domain(repo, session):
    session.get.return_value = make_row(analysis_id=5)

    result = await repo.get(5)

    assert isinstance(result, Analysis)
    assert result.analysis_id == 5


@pytest.mark.asyncio
async def test_list_for_examination_maps_rows(repo, session):
    exam = uuid4()
    session.scalars.return_value = [make_row(1, exam), make_row(2, exam)]

    result = await repo.list_for_examination(exam)

    assert [a.analysis_id for a in result] == [1, 2]


@pytest.mark.asyncio
async def test_count_for_examination_returns_scalar(repo, session):
    session.execute.return_value.scalar_one.return_value = 4

    assert await repo.count_for_examination(uuid4()) == 4


@pytest.mark.asyncio
async def test_lock_examination_executes_advisory_lock_with_stringified_id(repo, session):
    exam = uuid4()

    await repo.lock_examination(exam)

    stmt, params = session.execute.await_args.args
    assert "pg_advisory_xact_lock" in str(stmt)
    assert params == {"k": str(exam)}