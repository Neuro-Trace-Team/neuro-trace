from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.medical import PreprocessingJob
from src.repositories import preprocessing_jobs as preprocessing_jobs_repository
from src.services import examinations as examinations_service


class PreprocessingJobNotFoundError(Exception):
    pass


class PreprocessingJobTransitionError(Exception):
    pass


_ACTIVE_STATUSES = frozenset({"QUEUED", "RUNNING"})


def _now() -> datetime:
    return datetime.now(UTC)


def _commit(session: Session, job: PreprocessingJob) -> PreprocessingJob:
    session.commit()
    session.refresh(job)
    return job


def _get_job(session: Session, job_id: UUID) -> PreprocessingJob:
    job = preprocessing_jobs_repository.get_job(session, job_id)
    if job is None:
        raise PreprocessingJobNotFoundError
    return job


def _require_status(job: PreprocessingJob, allowed: frozenset[str]) -> None:
    if job.status not in allowed:
        raise PreprocessingJobTransitionError(
            f"Cannot transition preprocessing job from {job.status}"
        )


def create_preprocessing_job(
    session: Session,
    *,
    examination_id: UUID,
    pipeline_version: str,
    parameters: dict[str, Any] | None,
) -> PreprocessingJob:
    examination = examinations_service.get_examination(session, examination_id)
    job = PreprocessingJob(
        examination_id=examination_id,
        status="QUEUED",
        pipeline_version=pipeline_version.strip(),
        parameters_json=parameters,
    )
    examination.processing_status = "PREPROCESSING"
    examination.updated_at = _now()
    session.add(job)
    return _commit(session, job)


def get_preprocessing_job(session: Session, job_id: UUID) -> PreprocessingJob:
    return _get_job(session, job_id)


def list_preprocessing_jobs(
    session: Session, *, examination_id: UUID, page: int, page_size: int
) -> tuple[list[PreprocessingJob], int]:
    examinations_service.get_examination(session, examination_id)
    return preprocessing_jobs_repository.list_jobs(
        session, examination_id=examination_id, page=page, page_size=page_size
    )


def mark_running(session: Session, job_id: UUID) -> PreprocessingJob:
    job = _get_job(session, job_id)
    _require_status(job, frozenset({"QUEUED"}))
    examination = examinations_service.get_examination(session, job.examination_id)
    job.status = "RUNNING"
    job.started_at = _now()
    examination.processing_status = "PREPROCESSING"
    examination.updated_at = _now()
    return _commit(session, job)


def mark_completed(
    session: Session, *, job_id: UUID, output_bucket: str, output_storage_key: str
) -> PreprocessingJob:
    job = _get_job(session, job_id)
    _require_status(job, _ACTIVE_STATUSES)
    examination = examinations_service.get_examination(session, job.examination_id)
    now = _now()
    job.status = "COMPLETED"
    job.started_at = job.started_at or now
    job.completed_at = now
    job.output_bucket = output_bucket
    job.output_storage_key = output_storage_key
    job.error_message = None
    examination.processing_status = "READY"
    examination.updated_at = now
    return _commit(session, job)


def mark_failed(session: Session, *, job_id: UUID, error_message: str) -> PreprocessingJob:
    job = _get_job(session, job_id)
    _require_status(job, _ACTIVE_STATUSES)
    examination = examinations_service.get_examination(session, job.examination_id)
    now = _now()
    job.status = "FAILED"
    job.completed_at = now
    job.error_message = error_message.strip()
    examination.processing_status = "FAILED"
    examination.updated_at = now
    return _commit(session, job)


def mark_cancelled(session: Session, job_id: UUID) -> PreprocessingJob:
    job = _get_job(session, job_id)
    _require_status(job, _ACTIVE_STATUSES)
    examination = examinations_service.get_examination(session, job.examination_id)
    now = _now()
    job.status = "CANCELLED"
    job.completed_at = now
    examination.processing_status = "UPLOADED"
    examination.updated_at = now
    return _commit(session, job)
