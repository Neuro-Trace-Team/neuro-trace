from datetime import datetime
import json
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.orm import Session
from src.api.deps import get_current_user
from src.db.sessions import get_audit_db, get_medical_db
from src.models.auth import User
from src.models.medical import Examination, ExaminationEvent, ExaminationStatus
from src.schemas.examinations import *
from src.services import audit as audit_service
from src.services import examinations as service
from src.services import patients as patients_service
from src.services import recent as recent_service
from src.core.roles import Role
from src.services.ml import MLClient, MLServiceError
from src.services.preprocessing import PreprocessingClient, PreprocessingServiceError
from src.services.storage import ObjectStorageError

router = APIRouter(prefix="/examinations", tags=["examinations"])
def ip(r: Request): return r.client.host if r.client else None
def exam(v: Examination): return ExaminationResponse.model_validate(v, from_attributes=True)
def detail(v: Examination, analyses: list[dict] | None = None):
    return ExaminationDetailResponse.model_validate(exam(v).model_dump() | {"analyses": analyses or []})
def event(v: ExaminationEvent): return ExaminationEventResponse.model_validate(v, from_attributes=True)

def parse_upload_events(raw_events: str | None) -> list[dict]:
    if raw_events is None:
        return []
    try:
        payload = json.loads(raw_events)
    except json.JSONDecodeError as error:
        raise ValueError("events must be a JSON array") from error
    if not isinstance(payload, list):
        raise ValueError("events must be a JSON array")
    return [ExaminationEventCreate.model_validate(event).model_dump() for event in payload]


@router.post("", response_model=ExaminationResponse, status_code=201)
async def upload(request: Request, file: Annotated[UploadFile, File()], user: Annotated[User, Depends(get_current_user)], medical: Annotated[Session, Depends(get_medical_db)], audit: Annotated[Session, Depends(get_audit_db)], patient_id: Annotated[UUID | None, Form()] = None, generate_patient: Annotated[bool, Form()] = False, events: Annotated[str | None, Form()] = None, examination_date: Annotated[datetime | None, Form()] = None):
    try:
        uploaded_events = parse_upload_events(events)
        value, created_patient = await service.upload_examination(medical, patient_id=patient_id, generate_patient=generate_patient, uploaded_by=user.id, file=file, examination_date=examination_date, events=uploaded_events)
    except ValueError as error: raise HTTPException(422, str(error)) from None
    except patients_service.PatientNotFoundError: raise HTTPException(404, "Patient not found") from None
    except service.ExaminationValidationError as error: raise HTTPException(422, str(error)) from None
    except ObjectStorageError as error: raise HTTPException(503, str(error)) from None
    if created_patient:
        audit_service.log(audit, event_code="PATIENT_CREATED", user_id=user.id, resource_type="PATIENT", resource_id=value.patient_id, ip_address=ip(request))
    audit_service.log(audit, event_code="EXAMINATION_UPLOADED", user_id=user.id, resource_type="EXAMINATION", resource_id=value.id, metadata={"patient_id": str(patient_id), "file_format": value.file_format, "file_size_bytes": value.file_size_bytes}, ip_address=ip(request))
    metadata = {"examination_id": str(value.id), "storage_bucket": value.storage_bucket, "storage_key": value.storage_key}
    try: PreprocessingClient().request(value.id, value.storage_bucket, value.storage_key)
    except PreprocessingServiceError as error:
        audit_service.log(audit, event_code="PREPROCESSING_FAILED", user_id=user.id, resource_type="EXAMINATION", resource_id=value.id, metadata=metadata | {"reason": str(error)}, ip_address=ip(request)); raise HTTPException(502, "Examination was saved, but preprocessing could not be requested") from error
    audit_service.log(audit, event_code="PREPROCESSING_REQUESTED", user_id=user.id, resource_type="EXAMINATION", resource_id=value.id, metadata=metadata, ip_address=ip(request)); return exam(value)

@router.get("", response_model=ExaminationListResponse)
def list_all(
    medical: Annotated[Session, Depends(get_medical_db)],
    _: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    query: str | None = Query(default=None, min_length=1, max_length=255),
    id: UUID | None = None,
    patient_id: UUID | None = None,
    uploaded_by: UUID | None = None,
    status: ExaminationStatus | None = None,
    examination_date_from: datetime | None = None,
    examination_date_to: datetime | None = None,
    sort_by: Literal["id", "patient_id", "uploaded_by", "status", "examination_date", "created_at", "updated_at"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
):
    if examination_date_from and examination_date_to and examination_date_from > examination_date_to:
        raise HTTPException(400, "examination_date_from must not be after examination_date_to")
    rows, total = service.list_examinations(
        medical, page=page, page_size=page_size, query=query, examination_id=id,
        patient_id=patient_id, uploaded_by=uploaded_by, status=status,
        examination_date_from=examination_date_from, examination_date_to=examination_date_to,
        sort_by=sort_by, sort_order=sort_order,
    )
    return ExaminationListResponse(items=[exam(v) for v in rows], page=page, page_size=page_size, total=total)


@router.get("/statuses", response_model=ExaminationStatusesResponse)
def list_statuses(_: Annotated[User, Depends(get_current_user)]) -> ExaminationStatusesResponse:
    """Expose backend-owned examination lifecycle values for frontend selectors."""
    return ExaminationStatusesResponse(statuses=list(ExaminationStatus))

@router.get("/{examination_id}", response_model=ExaminationDetailResponse)
def get_one(examination_id: UUID, medical: Annotated[Session, Depends(get_medical_db)], current_user: Annotated[User, Depends(get_current_user)]):
    try:
        examination = service.get_examination(medical, examination_id)
        if current_user.role == Role.DOCTOR:
            recent_service.record_examination_visit(medical, doctor_id=current_user.id, examination_id=examination.id)
        analyses = MLClient().results(examination_id)["analyses"] if examination.status is ExaminationStatus.READY else []
        return detail(examination, analyses)
    except service.ExaminationNotFoundError: raise HTTPException(404, "Examination not found") from None
    except MLServiceError as error: raise HTTPException(502, str(error)) from error

@router.patch("/{examination_id}", response_model=ExaminationResponse)
def update(examination_id: UUID, payload: ExaminationUpdate, medical: Annotated[Session, Depends(get_medical_db)], _: Annotated[User, Depends(get_current_user)]):
    try: return exam(service.update_examination(medical, examination_id=examination_id, updates=payload.model_dump(exclude_unset=True)))
    except service.ExaminationNotFoundError: raise HTTPException(404, "Examination not found") from None

@router.delete("/{examination_id}", status_code=204)
def delete(examination_id: UUID, medical: Annotated[Session, Depends(get_medical_db)], _: Annotated[User, Depends(get_current_user)]):
    try: service.soft_delete_examination(medical, examination_id)
    except service.ExaminationNotFoundError: raise HTTPException(404, "Examination not found") from None

@router.get("/{examination_id}/preprocessing-status", response_model=PreprocessingStatusResponse)
def preprocessing_status(examination_id: UUID, medical: Annotated[Session, Depends(get_medical_db)], _: Annotated[User, Depends(get_current_user)]):
    try: service.get_examination(medical, examination_id); return PreprocessingStatusResponse.model_validate(PreprocessingClient().status(examination_id))
    except service.ExaminationNotFoundError: raise HTTPException(404, "Examination not found") from None
    except PreprocessingServiceError as error: raise HTTPException(502, str(error)) from error

@router.get("/{examination_id}/results", response_model=ExaminationResultsResponse)
def results(examination_id: UUID, medical: Annotated[Session, Depends(get_medical_db)], _: Annotated[User, Depends(get_current_user)]):
    try:
        examination = service.get_examination(medical, examination_id)
        if examination.status is not ExaminationStatus.READY:
            raise HTTPException(status.HTTP_409_CONFLICT, "ML analyses are not ready")
        return ExaminationResultsResponse.model_validate(MLClient().results(examination_id))
    except service.ExaminationNotFoundError: raise HTTPException(404, "Examination not found") from None
    except MLServiceError as error: raise HTTPException(502, str(error)) from error

@router.get("/{examination_id}/events", response_model=list[ExaminationEventResponse])
def events(examination_id: UUID, medical: Annotated[Session, Depends(get_medical_db)], _: Annotated[User, Depends(get_current_user)]):
    try: return [event(v) for v in service.list_events(medical, examination_id)]
    except service.ExaminationNotFoundError: raise HTTPException(404, "Examination not found") from None

@router.post("/{examination_id}/events", response_model=ExaminationEventResponse, status_code=201)
def create_event(examination_id: UUID, payload: ExaminationEventCreate, medical: Annotated[Session, Depends(get_medical_db)], _: Annotated[User, Depends(get_current_user)]):
    try: return event(service.create_event(medical, examination_id=examination_id, event=payload.model_dump()))
    except service.ExaminationNotFoundError: raise HTTPException(404, "Examination not found") from None

@router.patch("/{examination_id}/events/{event_id}", response_model=ExaminationEventResponse)
def patch_event(examination_id: UUID, event_id: UUID, payload: ExaminationEventUpdate, medical: Annotated[Session, Depends(get_medical_db)], _: Annotated[User, Depends(get_current_user)]):
    try: return event(service.update_event(medical, examination_id=examination_id, event_id=event_id, updates=payload.model_dump(exclude_unset=True)))
    except service.ExaminationNotFoundError: raise HTTPException(404, "Examination not found") from None
    except service.ExaminationEventNotFoundError: raise HTTPException(404, "Examination event not found") from None

@router.delete("/{examination_id}/events/{event_id}", status_code=204)
def remove_event(examination_id: UUID, event_id: UUID, medical: Annotated[Session, Depends(get_medical_db)], _: Annotated[User, Depends(get_current_user)]):
    try: service.delete_event(medical, examination_id=examination_id, event_id=event_id)
    except service.ExaminationNotFoundError: raise HTTPException(404, "Examination not found") from None
    except service.ExaminationEventNotFoundError: raise HTTPException(404, "Examination event not found") from None
