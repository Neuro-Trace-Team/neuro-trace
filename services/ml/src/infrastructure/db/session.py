import os
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine, async_sessionmaker

def create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url, pool_size=5, pool_pre_ping=True)

def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)