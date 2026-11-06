from pathlib import Path
from uuid import uuid4

from domain.entities.analysis import NewAnalysis
from infrastructure.db.models import Base
from infrastructure.db.session import create_engine, create_session_factory
from infrastructure.repositories.sql_alchemy_analysis_repository import SqlAlchemyAnalysisRepository

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError
from testcontainers.community.postgres import PostgresContainer

def find_project_root(marker="database"):
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / marker).exists():
            return parent
        # Stop if we hit the system root
        if parent == parent.parent:
            break
    raise FileNotFoundError(f"Could not find project root containing '{marker}'")

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