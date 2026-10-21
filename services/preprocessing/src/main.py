"""HTTP entrypoint for the preprocessing service."""

from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException, status

from service.config import Settings
from service.jobs import JobManager
from service.storage import RustFSStorage


settings = Settings.from_environment()
storage = RustFSStorage(settings)
jobs = JobManager(settings, storage)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.work_root.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="EEG preprocessing service", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/api/v1/internal/preprocessing/studies/{study_id}",
    status_code=status.HTTP_202_ACCEPTED,
)
def preprocess_study(study_id: str, background_tasks: BackgroundTasks) -> dict[str, str]:
    """Queue preprocessing for one study downloaded from RustFS."""
    try:
        job_id = jobs.create(study_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    background_tasks.add_task(jobs.run, job_id, study_id)
    return {"job_id": job_id, "study_id": study_id, "status": "queued"}


@app.get("/api/v1/internal/preprocessing/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
