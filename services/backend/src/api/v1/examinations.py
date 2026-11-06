from datetime import datetime
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
from src.services.ml import MLClient, MLServiceError
from src.services.preprocessing import PreprocessingClient, PreprocessingServiceError
from src.services.storage import ObjectStorageError

router = APIRouter(prefix="/examinations", tags=["examinations"])
def ip(r: Request): return r.client.host if r.client else None
def exam(v: Examination): return ExaminationResponse.model_validate(v, from_attributes=True)
def event(v: ExaminationEvent): return ExaminationEventResponse.model_validate(v, from_attributes=True)

@router.post("", response_model=ExaminationResponse, status_code=201)
async def upload(request: Request, patient_id: Annotated[UUID, Form()], file: Annotated[UploadFile, File()], user: Annotated[User, Depends(get_current_user)], medical: Annotated[Session, Depends(get_medical_db)], audit: Annotated[Session, Depends(get_audit_db)], examination_date: Annotated[datetime | None, Form()] = None):
    try: value = await service.upload_examination(medical, patient_id=patient_id, uploaded_by=user.id, file=file, examination_date=examination_date)
    except patients_service.PatientNotFoundError: raise HTTPException(404, "Patient not found") from None
    except service.ExaminationValidationError as error: raise HTTPException(422, str(error)) from None
    except ObjectStorageError as error: raise HTTPException(503, str(error)) from None
    audit_service.log(audit, event_code="EXAMINATION_UPLOADED", user_id=user.id, resource_type="EXAMINATION", resource_id=value.id, metadata={"patient_id": str(patient_id), "file_format": value.file_format, "file_size_bytes": value.file_size_bytes}, ip_address=ip(request))
    metadata = {"examination_id": str(value.id), "storage_bucket": value.storage_bucket, "storage_key": value.storage_key}
    try: PreprocessingClient().request(value.id, value.storage_bucket, value.storage_key)
    except PreprocessingServiceError as error:
        audit_service.log(audit, event_code="PREPROCESSING_FAILED", user_id=user.id, resource_type="EXAMINATION", resource_id=value.id, metadata=metadata | {"reason": str(error)}, ip_address=ip(request)); raise HTTPException(502, "Examination was saved, but preprocessing could not be requested") from error
    audit_service.log(audit, event_code="PREPROCESSING_REQUESTED", user_id=user.id, resource_type="EXAMINATION", resource_id=value.id, metadata=metadata, ip_address=ip(request)); return exam(value)

@router.get("", response_model=ExaminationListResponse)
def list_all(medical: Annotated[Session, Depends(get_medical_db)], _: Annotated[User, Depends(get_current_user)], page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), patient_id: UUID | None = None, uploaded_by: UUID | None = None, date_from: datetime | None = None, date_to: datetime | None = None, sort_by: Literal["created_at", "examination_date"] = "created_at", sort_order: Literal["asc", "desc"] = "desc"):
    if date_from and date_to and date_from > date_to: raise HTTPException(400, "date_from must not be after date_to")
    rows, total = service.list_examinations(medical, page=page, page_size=page_size, patient_id=patient_id, uploaded_by=uploaded_by, date_from=date_from, date_to=date_to, sort_by=sort_by, sort_order=sort_order); return ExaminationListResponse(items=[exam(v) for v in rows], page=page, page_size=page_size, total=total)

@router.get("/{examination_id}", response_model=ExaminationResponse)
def get_one(examination_id: UUID, medical: Annotated[Session, Depends(get_medical_db)], _: Annotated[User, Depends(get_current_user)]):
    try: return exam(service.get_examination(medical, examination_id))
    except service.ExaminationNotFoundError: raise HTTPException(404, "Examination not found") from None

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
