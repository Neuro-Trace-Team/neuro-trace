import pytest
import pytest_asyncio
from testcontainers.community.postgres import PostgresContainer
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import LogMessageWaitStrategy

from infrastructure.db.session import create_engine, create_session_factory

from common import find_project_root

INIT_SQL = find_project_root() / "database" / "model" / "init.sql"


@pytest.fixture(scope="session")
def rabbit_url():
    container = (
        DockerContainer("rabbitmq:4")
        .with_exposed_ports(5672)
        .waiting_for(LogMessageWaitStrategy("Server startup complete"))
    )
    with container:
        host, port = container.get_container_host_ip(), container.get_exposed_port(5672)
        yield f"amqp://guest:guest@{host}:{port}/"


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