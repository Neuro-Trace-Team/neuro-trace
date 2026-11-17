from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import get_settings

settings = get_settings()

# The schemas live in physically separate PostgreSQL databases.  Keeping
# engines and factories separate prevents accidental cross-database queries.
auth_engine = create_engine(settings.db_auth_url, pool_pre_ping=True)
medical_engine = create_engine(settings.db_medical_url, pool_pre_ping=True)
audit_engine = create_engine(settings.db_audit_url, pool_pre_ping=True)

AuthSession = sessionmaker(bind=auth_engine, autoflush=False, expire_on_commit=False)
MedicalSession = sessionmaker(bind=medical_engine, autoflush=False, expire_on_commit=False)
AuditSession = sessionmaker(bind=audit_engine, autoflush=False, expire_on_commit=False)


def _session_dependency(factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    session = factory()
    try:
        yield session
    finally:
        session.close()


def get_auth_db() -> Generator[Session, None, None]:
    yield from _session_dependency(AuthSession)


def get_medical_db() -> Generator[Session, None, None]:
    yield from _session_dependency(MedicalSession)


def get_audit_db() -> Generator[Session, None, None]:
    yield from _session_dependency(AuditSession)
