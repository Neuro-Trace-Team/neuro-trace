from pathlib import Path

import pytest
import pytest_asyncio
from testcontainers.community.postgres import PostgresContainer

from infrastructure.db.session import create_engine, create_session_factory

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
    with PostgresContainer("postgres:16", driver="asyncpg") as pg:
        yield pg.get_connection_url()


@pytest_asyncio.fixture
async def engine(pg_url):
    engine = create_engine(pg_url)
    async with engine.connect() as conn:
        raw = await conn.get_raw_connection()
        await raw.driver_connection.execute("DROP TABLE IF EXISTS analyses")
        await raw.driver_connection.execute(INIT_SQL.read_text())
    yield engine
    await engine.dispose()


@pytest.fixture
def session_factory(engine):
    return create_session_factory(engine)