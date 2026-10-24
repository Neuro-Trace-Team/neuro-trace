from fastapi import FastAPI

app = FastAPI(title="ML Microservice API", version="0.0.1")

@app.get("/healthz")
async def healthz():
    """Liveness probe for container orchestration."""
    return {"status": "healthy"}

@app.get("/readyz")
async def readyz():
    """Readiness probe."""
    # TODO: Add actual checks
    return {"status": "ready"}