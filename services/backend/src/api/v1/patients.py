from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from src.api.deps import get_current_user
from src.db.sessions import get_audit_db, get_medical_db
from src.models.auth import User
from src.models.medical import Examination, Patient
from src.schemas.patients import (
    PatientExaminationListResponse,
    PatientExaminationResponse,
    PatientExaminationStatisticsResponse,
    PatientListResponse,
    PatientResponse,
    PatientStatisticsResponse,
)
from src.services import audit as audit_service
from src.services import patients as patients_service

router = APIRouter(prefix="/patients", tags=["patients"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _patient_response(patient: Patient) -> PatientResponse:
    return PatientResponse(id=patient.id, created_at=patient.created_at, updated_at=patient.updated_at)


def _examination_response(examination: Examination) -> PatientExaminationResponse:
    return PatientExaminationResponse(
        id=examination.id,
        patient_id=examination.patient_id,
        examination_date=examination.examination_date,
        created_at=examination.created_at,
        updated_at=examination.updated_at,
        file_format=examination.file_format,
        file_size_bytes=examination.file_size_bytes,
        sampling_frequency=examination.sampling_frequency,
        duration_seconds=examination.duration_seconds,
        processing_status=examination.processing_status,
    )


@router.post("", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
def create_patient(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    medical_db: Annotated[Session, Depends(get_medical_db)],
    audit_db: Annotated[Session, Depends(get_audit_db)],
) -> PatientResponse:
    patient = patients_service.create_patient(medical_db)
    audit_service.log(
        audit_db,
        event_code="PATIENT_CREATED",
        user_id=current_user.id,
        resource_type="PATIENT",
        resource_id=patient.id,
        ip_address=_client_ip(request),
    )
    return _patient_response(patient)


@router.get("", response_model=PatientListResponse)
def list_patients(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    medical_db: Annotated[Session, Depends(get_medical_db)],
    audit_db: Annotated[Session, Depends(get_audit_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, min_length=1, max_length=36),
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    sort_by: Literal["created_at", "updated_at"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
) -> PatientListResponse:
    if created_from is not None and created_to is not None and created_from > created_to:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="created_from must not be after created_to")
    patients, total = patients_service.list_patients(
        medical_db, page=page, page_size=page_size, search=search, created_from=created_from,
        created_to=created_to, sort_by=sort_by, sort_order=sort_order,
    )
    audit_service.log(
        audit_db,
        event_code="PATIENT_ACCESSED",
        user_id=current_user.id,
        resource_type="PATIENT",
        metadata={"action": "LIST", "result_count": len(patients)},
        ip_address=_client_ip(request),
    )
    return PatientListResponse(items=[_patient_response(patient) for patient in patients], page=page, page_size=page_size, total=total)


@router.get("/stats", response_model=PatientStatisticsResponse)
def get_patient_statistics(
    medical_db: Annotated[Session, Depends(get_medical_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> PatientStatisticsResponse:
    total_patients, patients_with_examinations, active_examinations = patients_service.patient_statistics(medical_db)
    return PatientStatisticsResponse(
        total_patients=total_patients,
        patients_with_examinations=patients_with_examinations,
        active_examinations=active_examinations,
    )


@router.get("/{patient_id}", response_model=PatientResponse)
def get_patient(
    patient_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    medical_db: Annotated[Session, Depends(get_medical_db)],
    audit_db: Annotated[Session, Depends(get_audit_db)],
) -> PatientResponse:
    try:
        patient = patients_service.get_patient(medical_db, patient_id)
    except patients_service.PatientNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found") from None
    audit_service.log(
        audit_db,
        event_code="PATIENT_ACCESSED",
        user_id=current_user.id,
        resource_type="PATIENT",
        resource_id=patient.id,
        metadata={"action": "DETAIL"},
        ip_address=_client_ip(request),
    )
    return _patient_response(patient)


@router.get("/{patient_id}/stats", response_model=PatientExaminationStatisticsResponse)
def get_patient_examination_statistics(
    patient_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    medical_db: Annotated[Session, Depends(get_medical_db)],
    audit_db: Annotated[Session, Depends(get_audit_db)],
) -> PatientExaminationStatisticsResponse:
    try:
        examination_count, first_examination_at, last_examination_at = patients_service.patient_examination_statistics(
            medical_db, patient_id
        )
    except patients_service.PatientNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found") from None
    audit_service.log(
        audit_db, event_code="PATIENT_ACCESSED", user_id=current_user.id, resource_type="PATIENT",
        resource_id=patient_id, metadata={"action": "STATISTICS"}, ip_address=_client_ip(request),
    )
    return PatientExaminationStatisticsResponse(
        patient_id=patient_id, examination_count=examination_count,
        first_examination_at=first_examination_at, last_examination_at=last_examination_at,
    )


@router.get("/{patient_id}/examinations", response_model=PatientExaminationListResponse)
def list_patient_examinations(
    patient_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    medical_db: Annotated[Session, Depends(get_medical_db)],
    audit_db: Annotated[Session, Depends(get_audit_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PatientExaminationListResponse:
    try:
        examinations, total = patients_service.list_patient_examinations(
            medical_db, patient_id=patient_id, page=page, page_size=page_size
        )
    except patients_service.PatientNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found") from None
    audit_service.log(
        audit_db,
        event_code="PATIENT_ACCESSED",
        user_id=current_user.id,
        resource_type="PATIENT",
        resource_id=patient_id,
        metadata={"action": "EXAMINATION_LIST", "result_count": len(examinations)},
        ip_address=_client_ip(request),
    )
    return PatientExaminationListResponse(
        items=[_examination_response(examination) for examination in examinations],
        page=page,
        page_size=page_size,
        total=total,
    )
