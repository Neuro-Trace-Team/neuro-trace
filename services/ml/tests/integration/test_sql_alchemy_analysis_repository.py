from uuid import uuid4

from domain.entities.analysis import NewAnalysis
from infrastructure.db.models import Base
from infrastructure.db.session import create_engine, create_session_factory
from infrastructure.repositories.sql_alchemy_analysis_repository import SqlAlchemyAnalysisRepository
import pytest
import pytest_asyncio
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="session")
def pg_url():
    with PostgresContainer("postgres:17", driver="asyncpg") as pg:
        yield pg.get_connection_url()


@pytest_asyncio.fixture
async def session(pg_url):
    engine = create_engine(pg_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with create_session_factory(engine)() as s:
        yield s
    await engine.dispose()


@pytest_asyncio.fixture
async def repo(session):
    return SqlAlchemyAnalysisRepository(session)


async def test_add_assigns_identity_and_roundtrips(repo):
    exam = uuid4()

    saved = await repo.add(NewAnalysis(exam, 1.0, 0.5, None, 1))

    assert saved.analysis_id is not None
    assert (await repo.get(saved.analysis_id)) == saved


async def test_add_duplicate_is_idempotent_and_returns_original(repo):
    exam = uuid4()
    first = await repo.add(NewAnalysis(exam, 1.0, 0.5, 0.9, 1))

    second = await repo.add(NewAnalysis(exam, 1.0, 0.99, 0.1, 7))

    assert second == first
    assert await repo.count_for_examination(exam) == 1


async def test_list_for_examination_orders_by_timestamp_and_filters(repo):
    exam, other = uuid4(), uuid4()
    await repo.add(NewAnalysis(exam, 3.0, 0.3, None, 2))
    await repo.add(NewAnalysis(exam, 1.0, 0.1, None, 1))
    await repo.add(NewAnalysis(other, 2.0, 0.2, None, 1))

    result = await repo.list_for_examination(exam)

    assert [a.event_timestamp for a in result] == [1.0, 3.0]


async def test_get_missing_returns_none(repo):
    assert await repo.get(123456) is None


async def test_lock_examination_executes_on_postgres(repo):
    await repo.lock_examination(uuid4())