from fastapi import FastAPI

from services.ml.src.core.config import settings


app = FastAPI(title=settings.app_name)

@app.get("/info")
async def info():
    return {"app_name": settings.app_name, "model_path": settings.model_path}

@app.get("/healthz")
async def healthz():
    """Liveness probe for container orchestration."""
    return {"status": "healthy"}

@app.get("/readyz")
async def readyz():
    """Readiness probe."""
    # TODO: Add actual checks
    return {"status": "ready"}