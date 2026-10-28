from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from src.api.deps import get_current_user
from src.db.sessions import get_audit_db, get_medical_db
from src.models.auth import User
from src.models.medical import PreprocessingJob
from src.schemas.preprocessing_jobs import (
    PreprocessingJobCreate,
    PreprocessingJobListResponse,
    PreprocessingJobResponse,
)
from src.services import audit as audit_service
from src.services import examinations as examinations_service
from src.services import preprocessing_jobs as preprocessing_jobs_service

router = APIRouter(tags=["preprocessing jobs"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def preprocessing_job_response(job: PreprocessingJob) -> PreprocessingJobResponse:
    return PreprocessingJobResponse(
        id=job.id,
        examination_id=job.examination_id,
        status=job.status,
        pipeline_version=job.pipeline_version,
        parameters=job.parameters_json,
        output_bucket=job.output_bucket,
        output_storage_key=job.output_storage_key,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


@router.post(
    "/examinations/{examination_id}/preprocessing-jobs",
    response_model=PreprocessingJobResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_preprocessing_job(
    examination_id: UUID,
    payload: PreprocessingJobCreate,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    medical_db: Annotated[Session, Depends(get_medical_db)],
    audit_db: Annotated[Session, Depends(get_audit_db)],
) -> PreprocessingJobResponse:
    try:
        job = preprocessing_jobs_service.create_preprocessing_job(
            medical_db,
            examination_id=examination_id,
            pipeline_version=payload.pipeline_version,
            parameters=payload.parameters,
        )
    except examinations_service.ExaminationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Examination not found") from None
    audit_service.log(
        audit_db,
        event_code="EXAMINATION_UPDATED",
        user_id=current_user.id,
        resource_type="EXAMINATION",
        resource_id=examination_id,
        metadata={"action": "PREPROCESSING_JOB_CREATED", "job_id": str(job.id), "pipeline_version": job.pipeline_version},
        ip_address=_client_ip(request),
    )
    return preprocessing_job_response(job)


@router.get(
    "/examinations/{examination_id}/preprocessing-jobs", response_model=PreprocessingJobListResponse
)
def list_preprocessing_jobs(
    examination_id: UUID,
    medical_db: Annotated[Session, Depends(get_medical_db)],
    _: Annotated[User, Depends(get_current_user)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PreprocessingJobListResponse:
    try:
        jobs, total = preprocessing_jobs_service.list_preprocessing_jobs(
            medical_db, examination_id=examination_id, page=page, page_size=page_size
        )
    except examinations_service.ExaminationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Examination not found") from None
    return PreprocessingJobListResponse(
        items=[preprocessing_job_response(job) for job in jobs],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/preprocessing-jobs/{job_id}", response_model=PreprocessingJobResponse)
def get_preprocessing_job(
    job_id: UUID,
    medical_db: Annotated[Session, Depends(get_medical_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> PreprocessingJobResponse:
    try:
        return preprocessing_job_response(preprocessing_jobs_service.get_preprocessing_job(medical_db, job_id))
    except preprocessing_jobs_service.PreprocessingJobNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preprocessing job not found") from None
