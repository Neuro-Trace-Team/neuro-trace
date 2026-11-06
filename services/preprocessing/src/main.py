"""HTTP entrypoint for the preprocessing service."""

from contextlib import asynccontextmanager

from uuid import UUID

from fastapi import BackgroundTasks, FastAPI, HTTPException, status
from pydantic import BaseModel, ConfigDict

from service.config import Settings
from service.jobs import JobManager
from service.jobs import NeuroTraceClient
from service.storage import RustFSStorage


settings = Settings.from_environment()
storage = RustFSStorage(settings)
backend = NeuroTraceClient(settings)
jobs = JobManager(settings, storage, backend)


class JobResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    examination_id: UUID
    status: str
    pipeline_version: str


class JobRequest(BaseModel):
    examination_id: UUID
    storage_bucket: str
    storage_key: str


def _start_job(
    examination_id: UUID,
    background_tasks: BackgroundTasks,
    storage_bucket: str,
    storage_key: str,
):
    try:
        local_examination_id = jobs.create(
            str(examination_id), storage_bucket=storage_bucket, storage_key=storage_key
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    background_tasks.add_task(jobs.run, local_examination_id)
    return jobs.get(local_examination_id)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.work_root.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="EEG preprocessing service", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/api/v1/examinations/{examination_id}/preprocessing",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobResponse,
)
def request_preprocessing(
    examination_id: UUID,
    background_tasks: BackgroundTasks,
    request: JobRequest,
):
    """Accept the request contract used by the backend after an upload."""
    if request.examination_id != examination_id:
        raise HTTPException(status_code=422, detail="Request examination_id does not match URL")
    if not request.storage_bucket.strip() or not request.storage_key.strip():
        raise HTTPException(status_code=422, detail="storage_bucket and storage_key must not be blank")
    if not request.storage_bucket.strip() or not request.storage_key.strip():
        raise HTTPException(status_code=422, detail="storage_bucket and storage_key must not be blank")
    return _start_job(examination_id, background_tasks, request.storage_bucket, request.storage_key)


@app.post(
    "/api/v1/examinations/{examination_id}/preprocessing-jobs",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobResponse,
)
def preprocess_examination(
    examination_id: UUID,
    background_tasks: BackgroundTasks,
    request: JobRequest,
):
    """Queue preprocessing for one backend examination."""
    if request.examination_id != examination_id:
        raise HTTPException(status_code=422, detail="Request examination_id does not match URL")
    if not request.storage_bucket.strip() or not request.storage_key.strip():
        raise HTTPException(status_code=422, detail="storage_bucket and storage_key must not be blank")
    return _start_job(examination_id, background_tasks, request.storage_bucket, request.storage_key)


@app.get("/api/v1/examinations/{examination_id}/preprocessing-status")
def get_examination_preprocessing_status(examination_id: UUID) -> dict[str, str]:
    """Return the latest local job state in the format expected by the backend."""
    job = jobs.get_for_examination(str(examination_id))
    if job is None:
        raise HTTPException(status_code=404, detail="Preprocessing status not found")
    return {"examination_id": str(examination_id), "status": job["status"]}
