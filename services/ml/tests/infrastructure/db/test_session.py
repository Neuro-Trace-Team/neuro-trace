from infrastructure.db.session import create_engine, create_session_factory
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession


DB_URL = "postgresql+asyncpg://user:pass@localhost:5432/test"


def test_create_engine_returns_async_engine_with_expected_pool_config():
    engine = create_engine(DB_URL)

    assert isinstance(engine, AsyncEngine)
    assert engine.pool.size() == 5
    assert engine.pool._pre_ping is True  # private attr; see note below


def test_create_session_factory_binds_engine_and_keeps_objects_after_commit():
    engine = create_engine(DB_URL)

    factory = create_session_factory(engine)
    session = factory()

    assert isinstance(session, AsyncSession)
    assert session.bind is engine
    assert factory.kw["expire_on_commit"] is False