"""HTTP entrypoint for the preprocessing service."""

from contextlib import asynccontextmanager

from uuid import UUID

from fastapi import BackgroundTasks, FastAPI, HTTPException, status
from pydantic import BaseModel, ConfigDict

from service.config import Settings
from service.jobs import JobManager
from service.jobs import BackendAPIError, NeuroTraceClient
from service.storage import RustFSStorage


settings = Settings.from_environment()
storage = RustFSStorage(settings)
backend = NeuroTraceClient(settings)
jobs = JobManager(settings, storage, backend)


class JobResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    job_id: UUID
    examination_id: UUID
    status: str
    pipeline_version: str


class JobRequest(BaseModel):
    examination_id: UUID


class PreprocessingRequest(JobRequest):
    storage_bucket: str
    storage_key: str


def _start_job(
    examination_id: UUID,
    background_tasks: BackgroundTasks,
    job_id: str | None = None,
):
    try:
        local_job_id = jobs.create(str(examination_id), job_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    background_tasks.add_task(jobs.run, local_job_id, str(examination_id))
    return jobs.get(local_job_id)


def _create_backend_job(examination_id: UUID, background_tasks: BackgroundTasks):
    try:
        backend_job = backend.create_job(str(examination_id))
    except BackendAPIError as exc:
        raise HTTPException(
            status_code=exc.status_code or status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    backend_job_id = backend_job.get("job_id", backend_job.get("id"))
    if not isinstance(backend_job_id, str):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Backend job response does not contain a job UUID",
        )
    try:
        backend_examination_id = UUID(backend_job.get("examination_id", ""))
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Backend job response does not contain an examination UUID",
        ) from exc
    if backend_examination_id != examination_id:
        raise HTTPException(status_code=502, detail="Backend examination_id does not match request")
    return _start_job(examination_id, background_tasks, backend_job_id)


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
    request: PreprocessingRequest,
):
    """Accept the request contract used by the backend after an upload."""
    if request.examination_id != examination_id:
        raise HTTPException(status_code=422, detail="Request examination_id does not match URL")
    if not request.storage_bucket.strip() or not request.storage_key.strip():
        raise HTTPException(status_code=422, detail="storage_bucket and storage_key must not be blank")
    return _create_backend_job(examination_id, background_tasks)


@app.post(
    "/api/v1/examinations/{examination_id}/preprocessing-jobs",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobResponse,
)
def preprocess_examination(
    examination_id: UUID,
    background_tasks: BackgroundTasks,
    request: JobRequest | None = None,
):
    """Queue preprocessing for one backend examination."""
    if request is not None and request.examination_id != examination_id:
        raise HTTPException(status_code=422, detail="Request examination_id does not match URL")
    return _create_backend_job(examination_id, background_tasks)


@app.get("/api/v1/examinations/{examination_id}/preprocessing-status")
def get_examination_preprocessing_status(examination_id: UUID) -> dict[str, str]:
    """Return the latest local job state in the format expected by the backend."""
    job = jobs.get_for_examination(str(examination_id))
    if job is None:
        raise HTTPException(status_code=404, detail="Preprocessing status not found")
    return {"examination_id": str(examination_id), "status": job["status"]}


@app.get("/api/v1/preprocessing-jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: UUID) -> dict:
    job = jobs.get(str(job_id))
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
