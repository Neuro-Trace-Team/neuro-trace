from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from src.api.deps import get_current_user
from src.db.sessions import get_audit_db, get_medical_db
from src.models.auth import User
from src.models.medical import PainAssessment
from src.schemas.pain_assessments import (
    PainAssessmentCreate,
    PainAssessmentListResponse,
    PainAssessmentResponse,
)
from src.services import audit as audit_service
from src.services import examinations as examinations_service
from src.services import pain_assessments as pain_assessments_service

router = APIRouter(tags=["pain assessments"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _assessment_response(assessment: PainAssessment) -> PainAssessmentResponse:
    return PainAssessmentResponse(
        id=assessment.id,
        examination_id=assessment.examination_id,
        assessed_by=assessment.assessed_by,
        pain_level=assessment.pain_level,
        scale=assessment.scale,
        notes=assessment.notes,
        assessed_at=assessment.assessed_at,
        created_at=assessment.created_at,
    )


@router.post(
    "/examinations/{examination_id}/pain-assessments",
    response_model=PainAssessmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_pain_assessment(
    examination_id: UUID,
    payload: PainAssessmentCreate,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    medical_db: Annotated[Session, Depends(get_medical_db)],
    audit_db: Annotated[Session, Depends(get_audit_db)],
) -> PainAssessmentResponse:
    try:
        assessment = pain_assessments_service.create_assessment(
            medical_db,
            examination_id=examination_id,
            assessed_by=current_user.id,
            pain_level=payload.pain_level,
            scale=payload.scale,
            notes=payload.notes,
            assessed_at=payload.assessed_at,
        )
    except examinations_service.ExaminationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Examination not found") from None
    audit_service.log(
        audit_db,
        event_code="EXAMINATION_UPDATED",
        user_id=current_user.id,
        resource_type="EXAMINATION",
        resource_id=examination_id,
        metadata={"action": "PAIN_ASSESSMENT_CREATED", "assessment_id": str(assessment.id), "scale": assessment.scale},
        ip_address=_client_ip(request),
    )
    return _assessment_response(assessment)


@router.get(
    "/examinations/{examination_id}/pain-assessments", response_model=PainAssessmentListResponse
)
def list_pain_assessments(
    examination_id: UUID,
    medical_db: Annotated[Session, Depends(get_medical_db)],
    _: Annotated[User, Depends(get_current_user)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PainAssessmentListResponse:
    try:
        assessments, total = pain_assessments_service.list_assessments(
            medical_db, examination_id=examination_id, page=page, page_size=page_size
        )
    except examinations_service.ExaminationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Examination not found") from None
    return PainAssessmentListResponse(
        items=[_assessment_response(assessment) for assessment in assessments],
        page=page,
        page_size=page_size,
        total=total,
    )
