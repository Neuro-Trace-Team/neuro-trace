import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

DATABASE_URL = os.environ["DATABASE_URL"]  # postgresql+asyncpg://user:pass@db:5432/ml

engine = create_async_engine(DATABASE_URL, pool_size=5, pool_pre_ping=True)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)