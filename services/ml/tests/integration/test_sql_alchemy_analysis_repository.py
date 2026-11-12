from uuid import uuid4

from domain.entities.analysis import NewAnalysis
from infrastructure.db.models import AnalysisRow, Base
from infrastructure.db.session import create_engine, create_session_factory
from infrastructure.repositories.sql_alchemy_analysis_repository import SqlAlchemyAnalysisRepository

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from testcontainers.community.postgres import PostgresContainer

from common import find_project_root

pytestmark = pytest.mark.integration


INIT_SQL = find_project_root() / "database" / "model" / "init.sql"


@pytest.fixture(scope="session")
def pg_url():
    with PostgresContainer("postgres:17", driver="asyncpg") as pg:
        yield pg.get_connection_url()


@pytest_asyncio.fixture
async def session(pg_url):
    engine = create_engine(pg_url)
    async with engine.connect() as conn:
        raw = await conn.get_raw_connection()
        await raw.driver_connection.execute("DROP TABLE IF EXISTS analyses")
        await raw.driver_connection.execute(INIT_SQL.read_text())
    async with create_session_factory(engine)() as s:
        yield s
    await engine.dispose()


@pytest_asyncio.fixture
async def repo(session):
    return SqlAlchemyAnalysisRepository(session)


async def test_add_assigns_identity_and_roundtrips(repo):
    saved = await repo.add(NewAnalysis(uuid4(), 1.0, 0.5, 0.9, 1))

    assert saved.analysis_id is not None
    assert await repo.get(saved.analysis_id) == saved


async def test_add_duplicate_is_idempotent_and_returns_original(repo):
    exam = uuid4()
    first = await repo.add(NewAnalysis(exam, 1.0, 0.5, 0.9, 1))

    second = await repo.add(NewAnalysis(exam, 1.0, 0.99, 0.1, 7))

    assert second == first
    assert await repo.count_for_examination(exam) == 1


async def test_list_for_examination_orders_by_timestamp_and_filters(repo):
    exam, other = uuid4(), uuid4()
    await repo.add(NewAnalysis(exam, 3.0, 0.3, 0.5, 2))
    await repo.add(NewAnalysis(exam, 1.0, 0.1, 0.5, 1))
    await repo.add(NewAnalysis(other, 2.0, 0.2, 0.5, 1))

    result = await repo.list_for_examination(exam)

    assert [a.event_timestamp for a in result] == [1.0, 3.0]


async def test_get_missing_returns_none(repo):
    assert await repo.get(123456) is None


async def test_lock_examination_executes_on_postgres(repo):
    await repo.lock_examination(uuid4())


@pytest.mark.parametrize(
    "ts, confidence, count",
    [(-1.0, 0.5, 1), (1.0, 1.5, 1), (1.0, -0.1, 1), (1.0, 0.5, 0)],
)
async def test_add_rejects_values_violating_check_constraints(repo, ts, confidence, count):
    with pytest.raises(IntegrityError):
        await repo.add(NewAnalysis(uuid4(), ts, 0.5, confidence, count))


async def test_add_accepts_missing_confidence(repo):
    saved = await repo.add(NewAnalysis(uuid4(), 1.0, 0.5, None, 1))

    assert saved.confidence is None
    assert await repo.get(saved.analysis_id) == saved


async def test_invalid_analysis_roundtrips_with_null_result(repo):
    saved = await repo.add(NewAnalysis(uuid4(), 1.0, None, None, 1, is_valid=False, invalid_reason="x"))
    assert (saved.result, saved.is_valid) == (None, False)
    assert await repo.get(saved.analysis_id) == saved


@pytest.mark.parametrize("result", [0.0, 10.0])
async def test_result_range_boundaries_are_accepted(repo, result):
    assert (await repo.add(NewAnalysis(uuid4(), 1.0, result, None, 1))).result == result


@pytest.mark.parametrize("result", [-0.1, 10.1])
async def test_database_rejects_result_outside_range(repo, result):
    with pytest.raises(IntegrityError):
        await repo.add(NewAnalysis(uuid4(), 1.0, result, None, 1))


async def test_database_rejects_inconsistent_validity_rows(session_factory):
    """Backstop that doesn't depend on the Python entity."""
    sql = text("INSERT INTO analyses (examination_id, event_timestamp, result, confidence, "
               "total_analyses_count, is_valid, invalid_reason) "
               "VALUES (:e, 1, 1, NULL, 1, false, 'x')")      # invalid, yet has a result
    async with session_factory() as s:
        with pytest.raises(IntegrityError):
            await s.execute(sql, {"e": uuid4()})


async def test_orm_model_matches_database_schema(engine):
    """You've had column drift twice (time_stamp, confidence nullability); this catches it."""
    async with engine.connect() as conn:
        rows = (await conn.execute(text(
            "SELECT column_name, is_nullable FROM information_schema.columns WHERE table_name = 'analyses'"
        ))).all()
    assert {n: nullable == "YES" for n, nullable in rows} == \
           {c.name: c.nullable for c in AnalysisRow.__table__.columns}