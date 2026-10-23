from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from src.api.deps import get_current_user
from src.db.sessions import get_audit_db, get_medical_db
from src.models.auth import User
from src.models.medical import Analysis, AnalysisResult
from src.schemas.analyses import (
    AnalysisCreate,
    AnalysisListResponse,
    AnalysisResponse,
    AnalysisResultResponse,
    ExaminationResultListResponse,
    ExaminationResultResponse,
)
from src.services import analyses as analyses_service
from src.services import audit as audit_service
from src.services import examinations as examinations_service
from src.services import preprocessing_jobs as preprocessing_jobs_service

router = APIRouter(tags=["analyses"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


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


def _result_response(result: AnalysisResult) -> AnalysisResultResponse:
    return AnalysisResultResponse(
        id=result.id,
        analysis_id=result.analysis_id,
        pain_level=result.pain_level,
        confidence=result.confidence,
        result=result.result_json,
        explanation=result.explanation_json,
        created_at=result.created_at,
    )


@router.post(
    "/examinations/{examination_id}/results",
    response_model=AnalysisResponse,
    status_code=status.HTTP_201_CREATED,
)
def request_analysis(
    examination_id: UUID,
    payload: AnalysisCreate,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    medical_db: Annotated[Session, Depends(get_medical_db)],
    audit_db: Annotated[Session, Depends(get_audit_db)],
) -> AnalysisResponse:
    try:
        analysis = analyses_service.create_analysis(
            medical_db,
            examination_id=examination_id,
            preprocessing_job_id=payload.preprocessing_job_id,
            requested_by=current_user.id,
            model_name=payload.model_name,
            model_version=payload.model_version,
        )
    except examinations_service.ExaminationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Examination not found") from None
    except preprocessing_jobs_service.PreprocessingJobNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preprocessing job not found") from None
    except analyses_service.AnalysisValidationError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from None
    audit_service.log(
        audit_db,
        event_code="ANALYSIS_REQUESTED",
        user_id=current_user.id,
        resource_type="ANALYSIS",
        resource_id=analysis.id,
        metadata={
            "examination_id": str(examination_id),
            "preprocessing_job_id": str(payload.preprocessing_job_id),
            "model_name": analysis.model_name,
            "model_version": analysis.model_version,
        },
        ip_address=_client_ip(request),
    )
    return _analysis_response(analysis)


@router.get(
    "/examinations/{examination_id}/results", response_model=ExaminationResultListResponse
)
def list_examination_results(
    examination_id: UUID,
    medical_db: Annotated[Session, Depends(get_medical_db)],
    _: Annotated[User, Depends(get_current_user)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ExaminationResultListResponse:
    try:
        rows, total = analyses_service.list_examination_results(
            medical_db, examination_id=examination_id, page=page, page_size=page_size
        )
    except examinations_service.ExaminationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Examination not found") from None
    return ExaminationResultListResponse(
        items=[ExaminationResultResponse(analysis=_analysis_response(analysis), result=_result_response(result)) for analysis, result in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/analyses", response_model=AnalysisListResponse)
def list_analyses(
    medical_db: Annotated[Session, Depends(get_medical_db)],
    _: Annotated[User, Depends(get_current_user)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    examination_id: UUID | None = None,
    requested_by: UUID | None = None,
    analysis_status: str | None = Query(default=None, max_length=30),
) -> AnalysisListResponse:
    try:
        analyses, total = analyses_service.list_analyses(
            medical_db,
            page=page,
            page_size=page_size,
            examination_id=examination_id,
            requested_by=requested_by,
            status=analysis_status,
        )
    except examinations_service.ExaminationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Examination not found") from None
    return AnalysisListResponse(
        items=[_analysis_response(analysis) for analysis in analyses],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/analyses/{analysis_id}", response_model=AnalysisResponse)
def get_analysis(
    analysis_id: UUID,
    medical_db: Annotated[Session, Depends(get_medical_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> AnalysisResponse:
    try:
        return _analysis_response(analyses_service.get_analysis(medical_db, analysis_id))
    except analyses_service.AnalysisNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found") from None
