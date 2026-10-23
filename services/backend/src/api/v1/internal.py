from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, require_roles
from src.core.roles import Role
from src.db.sessions import get_audit_db, get_medical_db
from src.models.auth import User
from src.models.medical import Analysis, AnalysisResult, PreprocessingJob
from src.schemas.analyses import (
    AnalysisResultCreate,
    AnalysisResultResponse,
    AnalysisResponse,
    AnalysisStatusUpdate,
)
from src.schemas.internal import (
    InternalAnalysisCompletionResponse,
    InternalAnalysisFailureReport,
    PreprocessingChannel,
    PreprocessingEvent,
    PreprocessingExaminationMetadata,
    PreprocessingExaminationResponse,
    PreprocessingSourceFile,
)
from src.schemas.preprocessing_jobs import (
    PreprocessingJobResponse,
    PreprocessingJobResult,
    PreprocessingJobStatusUpdate,
)
from src.services import audit as audit_service
from src.services import analyses as analyses_service
from src.services import examinations as examinations_service
from src.services import preprocessing_jobs as preprocessing_jobs_service

router = APIRouter(prefix="/internal/preprocessing", tags=["internal preprocessing"])
analysis_router = APIRouter(prefix="/internal/analyses", tags=["internal analyses"])
admin_only = Depends(require_roles(Role.ADMIN))


def _preprocessing_job_response(job: PreprocessingJob) -> PreprocessingJobResponse:
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


def _analysis_response(analysis: Analysis) -> AnalysisResponse:
    return AnalysisResponse(
        id=analysis.id,
        examination_id=analysis.examination_id,
        preprocessing_job_id=analysis.preprocessing_job_id,
        requested_by=analysis.requested_by,
        status=analysis.status,
        model_name=analysis.model_name,
        model_version=analysis.model_version,
        created_at=analysis.created_at,
        started_at=analysis.started_at,
        completed_at=analysis.completed_at,
        error_message=analysis.error_message,
    )


def _analysis_result_response(result: AnalysisResult) -> AnalysisResultResponse:
    return AnalysisResultResponse(
        id=result.id,
        analysis_id=result.analysis_id,
        pain_level=result.pain_level,
        confidence=result.confidence,
        result=result.result_json,
        explanation=result.explanation_json,
        created_at=result.created_at,
    )


@router.get(
    "/examinations/{examination_id}",
    response_model=PreprocessingExaminationResponse,
    dependencies=[admin_only],
)
def get_preprocessing_examination(
    examination_id: UUID,
    medical_db: Annotated[Session, Depends(get_medical_db)],
) -> PreprocessingExaminationResponse:
    """Expose source-object coordinates and clinical-neutral metadata internally.

    The endpoint sends neither EEG bytes nor RustFS credentials. A future
    preprocessing service downloads the source object from RustFS itself.
    """
    try:
        examination = examinations_service.get_examination(medical_db, examination_id)
    except examinations_service.ExaminationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Examination not found") from None

    channels = examinations_service.list_channels(medical_db, examination_id)
    events = examinations_service.list_events(medical_db, examination_id)
    return PreprocessingExaminationResponse(
        examination_id=examination.id,
        patient_id=examination.patient_id,
        source_file=PreprocessingSourceFile(
            bucket=examination.storage_bucket,
            storage_key=examination.storage_key,
            original_filename=examination.original_filename,
            file_format=examination.file_format,
            file_size_bytes=examination.file_size_bytes,
            file_checksum=examination.file_checksum,
        ),
        metadata=PreprocessingExaminationMetadata(
            examination_date=examination.examination_date,
            sampling_frequency=examination.sampling_frequency,
            electrode_positions=examination.electrode_positions,
            reference=examination.reference,
            power_line_frequency=examination.power_line_frequency,
            duration_seconds=examination.duration_seconds,
        ),
        channels=[
            PreprocessingChannel(channel_id=channel.id, code=channel.code, position=assignment.position)
            for assignment, channel in channels
        ],
        events=[
            PreprocessingEvent(
                id=event.id,
                timestamp=event.timestamp,
                type=event.type,
                description=event.description,
                metadata=event.metadata_json,
            )
            for event in events
        ],
    )


@router.patch(
    "/jobs/{job_id}/status",
    response_model=PreprocessingJobResponse,
    dependencies=[admin_only],
)
def update_preprocessing_job_status(
    job_id: UUID,
    payload: PreprocessingJobStatusUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    medical_db: Annotated[Session, Depends(get_medical_db)],
    audit_db: Annotated[Session, Depends(get_audit_db)],
) -> PreprocessingJobResponse:
    try:
        if payload.status == "RUNNING":
            job = preprocessing_jobs_service.mark_running(medical_db, job_id)
        else:
            job = preprocessing_jobs_service.mark_cancelled(medical_db, job_id)
    except preprocessing_jobs_service.PreprocessingJobNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preprocessing job not found") from None
    except preprocessing_jobs_service.PreprocessingJobTransitionError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from None
    audit_service.log(
        audit_db,
        event_code="EXAMINATION_UPDATED",
        user_id=current_user.id,
        resource_type="EXAMINATION",
        resource_id=job.examination_id,
        metadata={"action": "PREPROCESSING_JOB_STATUS_UPDATED", "job_id": str(job.id), "status": job.status},
    )
    return _preprocessing_job_response(job)


@router.post(
    "/jobs/{job_id}/result",
    response_model=PreprocessingJobResponse,
    dependencies=[admin_only],
)
def save_preprocessing_job_result(
    job_id: UUID,
    payload: PreprocessingJobResult,
    current_user: Annotated[User, Depends(get_current_user)],
    medical_db: Annotated[Session, Depends(get_medical_db)],
    audit_db: Annotated[Session, Depends(get_audit_db)],
) -> PreprocessingJobResponse:
    try:
        if payload.status == "COMPLETED":
            job = preprocessing_jobs_service.mark_completed(
                medical_db,
                job_id=job_id,
                output_bucket=payload.output_bucket,
                output_storage_key=payload.output_storage_key,
            )
        else:
            job = preprocessing_jobs_service.mark_failed(
                medical_db, job_id=job_id, error_message=payload.error_message
            )
    except preprocessing_jobs_service.PreprocessingJobNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preprocessing job not found") from None
    except preprocessing_jobs_service.PreprocessingJobTransitionError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from None
    audit_service.log(
        audit_db,
        event_code="EXAMINATION_UPDATED",
        user_id=current_user.id,
        resource_type="EXAMINATION",
        resource_id=job.examination_id,
        metadata={"action": "PREPROCESSING_JOB_RESULT_SAVED", "job_id": str(job.id), "status": job.status},
    )
    return _preprocessing_job_response(job)


@analysis_router.patch(
    "/{analysis_id}/status",
    response_model=AnalysisResponse,
    dependencies=[admin_only],
)
def update_analysis_status(
    analysis_id: UUID,
    payload: AnalysisStatusUpdate,
    medical_db: Annotated[Session, Depends(get_medical_db)],
) -> AnalysisResponse:
    try:
        if payload.status == "RUNNING":
            analysis = analyses_service.mark_running(medical_db, analysis_id)
        else:
            analysis = analyses_service.mark_cancelled(medical_db, analysis_id)
    except analyses_service.AnalysisNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found") from None
    except analyses_service.AnalysisTransitionError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from None
    return _analysis_response(analysis)


@analysis_router.post(
    "/{analysis_id}/result",
    response_model=InternalAnalysisCompletionResponse,
    dependencies=[admin_only],
)
def save_analysis_result(
    analysis_id: UUID,
    payload: AnalysisResultCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    medical_db: Annotated[Session, Depends(get_medical_db)],
    audit_db: Annotated[Session, Depends(get_audit_db)],
) -> InternalAnalysisCompletionResponse:
    try:
        analysis, result = analyses_service.mark_completed(
            medical_db,
            analysis_id=analysis_id,
            pain_level=payload.pain_level,
            confidence=payload.confidence,
            result=payload.result,
            explanation=payload.explanation,
        )
    except analyses_service.AnalysisNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found") from None
    except analyses_service.AnalysisTransitionError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from None
    audit_service.log(
        audit_db,
        event_code="ANALYSIS_COMPLETED",
        user_id=current_user.id,
        resource_type="ANALYSIS",
        resource_id=analysis.id,
        metadata={"examination_id": str(analysis.examination_id), "model_name": analysis.model_name, "model_version": analysis.model_version},
    )
    return InternalAnalysisCompletionResponse(
        analysis=_analysis_response(analysis), result=_analysis_result_response(result)
    )


@analysis_router.post(
    "/{analysis_id}/error",
    response_model=AnalysisResponse,
    dependencies=[admin_only],
)
def save_analysis_error(
    analysis_id: UUID,
    payload: InternalAnalysisFailureReport,
    current_user: Annotated[User, Depends(get_current_user)],
    medical_db: Annotated[Session, Depends(get_medical_db)],
    audit_db: Annotated[Session, Depends(get_audit_db)],
) -> AnalysisResponse:
    try:
        analysis = analyses_service.mark_failed(
            medical_db, analysis_id=analysis_id, error_message=payload.error_message
        )
    except analyses_service.AnalysisNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found") from None
    except analyses_service.AnalysisTransitionError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from None
    audit_service.log(
        audit_db,
        event_code="ANALYSIS_FAILED",
        user_id=current_user.id,
        resource_type="ANALYSIS",
        resource_id=analysis.id,
        metadata={"examination_id": str(analysis.examination_id), "model_name": analysis.model_name, "model_version": analysis.model_version},
    )
    return _analysis_response(analysis)
