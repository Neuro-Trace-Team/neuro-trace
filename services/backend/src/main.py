import logging
from collections.abc import Iterable

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from src.api.v1.admin import router as admin_router
from src.api.v1.auth import router as auth_router
from src.api.v1.examinations import router as examinations_router
from src.api.v1.internal import router as internal_router
from src.api.v1.patients import router as patients_router
from src.api.v1.users import router as users_router
from src.db import sessions

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="NeuroTrace Backend", version="0.1.0")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(patients_router, prefix="/api/v1")
app.include_router(examinations_router, prefix="/api/v1")
app.include_router(internal_router, prefix="/api/v1")


@app.get("/health/live", tags=["health"])
def live() -> dict[str, str]:
    """Liveness deliberately has no dependency checks."""
    return {"status": "ok"}


def _check_databases() -> dict[str, str]:
    dependencies: dict[str, str] = {}
    databases: Iterable[tuple[str, Engine]] = (
        ("auth_db", sessions.auth_engine),
        ("medical_db", sessions.medical_engine),
        ("audit_db", sessions.audit_engine),
    )
    for name, engine in databases:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            dependencies[name] = "ok"
        except SQLAlchemyError:
            logger.warning("Readiness check failed for %s", name, exc_info=True)
            dependencies[name] = "unavailable"
    return dependencies


@app.get("/health/ready", tags=["health"], response_model=None)
def ready() -> JSONResponse | dict[str, object]:
    dependencies = _check_databases()
    if all(result == "ok" for result in dependencies.values()):
        return {"status": "ready", "dependencies": dependencies}
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "not_ready", "dependencies": dependencies},
    )
