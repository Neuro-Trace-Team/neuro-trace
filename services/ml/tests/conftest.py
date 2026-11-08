import os

os.environ.setdefault(
    "MODEL_DB_URL",
    "postgresql+asyncpg://test:test@localhost:5432/test",
)