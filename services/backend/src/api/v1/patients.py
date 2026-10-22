from typing import Annotated
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
) -> PatientListResponse:
    patients, total = patients_service.list_patients(medical_db, page=page, page_size=page_size, search=search)
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
