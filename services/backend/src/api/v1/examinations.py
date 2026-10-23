import json
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from src.api.deps import get_current_user
from src.db.sessions import get_audit_db, get_medical_db
from src.models.auth import User
from src.models.medical import (
    EEGChannel,
    Examination,
    ExaminationChannel,
    ExaminationEvent,
)
from src.schemas.examinations import (
    EEGChannelResponse,
    ExaminationChannelReplace,
    ExaminationChannelResponse,
    ExaminationEventCreate,
    ExaminationEventResponse,
    ExaminationListResponse,
    ExaminationResponse,
    ExaminationUpdate,
)
from src.services import audit as audit_service
from src.services import examinations as examinations_service
from src.services import patients as patients_service
from src.services.storage import ObjectStorageError

router = APIRouter(prefix="/examinations", tags=["examinations"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _examination_response(examination: Examination) -> ExaminationResponse:
    return ExaminationResponse(
        id=examination.id,
        patient_id=examination.patient_id,
        uploaded_by=examination.uploaded_by,
        original_filename=examination.original_filename,
        file_format=examination.file_format,
        file_size_bytes=examination.file_size_bytes,
        file_checksum=examination.file_checksum,
        examination_date=examination.examination_date,
        created_at=examination.created_at,
        updated_at=examination.updated_at,
        sampling_frequency=examination.sampling_frequency,
        electrode_positions=examination.electrode_positions,
        reference=examination.reference,
        power_line_frequency=examination.power_line_frequency,
        duration_seconds=examination.duration_seconds,
        processing_status=examination.processing_status,
    )


def _event_response(event: ExaminationEvent) -> ExaminationEventResponse:
    return ExaminationEventResponse(
        id=event.id,
        examination_id=event.examination_id,
        timestamp=event.timestamp,
        type=event.type,
        description=event.description,
        metadata=event.metadata_json,
        created_at=event.created_at,
        updated_at=event.updated_at,
    )


def _channel_response(row: tuple[ExaminationChannel, EEGChannel]) -> ExaminationChannelResponse:
    examination_channel, channel = row
    return ExaminationChannelResponse(
        channel_id=channel.id,
        code=channel.code,
        description=channel.description,
        position=examination_channel.position,
    )


@router.post("", response_model=ExaminationResponse, status_code=status.HTTP_201_CREATED)
async def upload_examination(
    request: Request,
    patient_id: Annotated[UUID, Form()],
    sampling_frequency: Annotated[int, Form()],
    file: Annotated[UploadFile, File()],
    current_user: Annotated[User, Depends(get_current_user)],
    medical_db: Annotated[Session, Depends(get_medical_db)],
    audit_db: Annotated[Session, Depends(get_audit_db)],
    examination_date: Annotated[datetime | None, Form()] = None,
    electrode_positions: Annotated[str | None, Form()] = None,
    reference: Annotated[str | None, Form()] = None,
    power_line_frequency: Annotated[int | None, Form()] = None,
    duration_seconds: Annotated[Decimal | None, Form()] = None,
) -> ExaminationResponse:
    positions: dict[str, Any] | None = None
    if electrode_positions is not None:
        try:
            parsed_positions = json.loads(electrode_positions)
        except json.JSONDecodeError:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="electrode_positions must be JSON") from None
        if not isinstance(parsed_positions, dict):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="electrode_positions must be a JSON object")
        positions = parsed_positions
    try:
        examination = await examinations_service.upload_examination(
            medical_db,
            patient_id=patient_id,
            uploaded_by=current_user.id,
            file=file,
            sampling_frequency=sampling_frequency,
            examination_date=examination_date,
            electrode_positions=positions,
            reference=reference,
            power_line_frequency=power_line_frequency,
            duration_seconds=duration_seconds,
        )
    except patients_service.PatientNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found") from None
    except examinations_service.ExaminationValidationError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from None
    except ObjectStorageError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from None
    audit_service.log(
        audit_db,
        event_code="EXAMINATION_UPLOADED",
        user_id=current_user.id,
        resource_type="EXAMINATION",
        resource_id=examination.id,
        metadata={"patient_id": str(patient_id), "file_format": examination.file_format, "file_size_bytes": examination.file_size_bytes},
        ip_address=_client_ip(request),
    )
    return _examination_response(examination)


@router.get("", response_model=ExaminationListResponse)
def list_examinations(
    medical_db: Annotated[Session, Depends(get_medical_db)],
    _: Annotated[User, Depends(get_current_user)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    patient_id: UUID | None = None,
    uploaded_by: UUID | None = None,
    processing_status: str | None = Query(default=None, max_length=30),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> ExaminationListResponse:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="date_from must not be after date_to")
    examinations, total = examinations_service.list_examinations(
        medical_db,
        page=page,
        page_size=page_size,
        patient_id=patient_id,
        uploaded_by=uploaded_by,
        processing_status=processing_status,
        date_from=date_from,
        date_to=date_to,
    )
    return ExaminationListResponse(
        items=[_examination_response(examination) for examination in examinations],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/eeg-channels", response_model=list[EEGChannelResponse])
def list_eeg_channels(
    medical_db: Annotated[Session, Depends(get_medical_db)], _: Annotated[User, Depends(get_current_user)]
) -> list[EEGChannelResponse]:
    return [EEGChannelResponse(id=channel.id, code=channel.code, description=channel.description) for channel in examinations_service.list_eeg_channels(medical_db)]


@router.get("/{examination_id}", response_model=ExaminationResponse)
def get_examination(
    examination_id: UUID,
    medical_db: Annotated[Session, Depends(get_medical_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> ExaminationResponse:
    try:
        return _examination_response(examinations_service.get_examination(medical_db, examination_id))
    except examinations_service.ExaminationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Examination not found") from None


@router.patch("/{examination_id}", response_model=ExaminationResponse)
def update_examination(
    examination_id: UUID,
    payload: ExaminationUpdate,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    medical_db: Annotated[Session, Depends(get_medical_db)],
    audit_db: Annotated[Session, Depends(get_audit_db)],
) -> ExaminationResponse:
    try:
        examination = examinations_service.update_examination(
            medical_db, examination_id=examination_id, updates=payload.model_dump(exclude_unset=True)
        )
    except examinations_service.ExaminationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Examination not found") from None
    audit_service.log(
        audit_db,
        event_code="EXAMINATION_UPDATED",
        user_id=current_user.id,
        resource_type="EXAMINATION",
        resource_id=examination.id,
        metadata={"fields": sorted(payload.model_fields_set)},
        ip_address=_client_ip(request),
    )
    return _examination_response(examination)


@router.delete("/{examination_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_examination(
    examination_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    medical_db: Annotated[Session, Depends(get_medical_db)],
    audit_db: Annotated[Session, Depends(get_audit_db)],
) -> None:
    try:
        examinations_service.soft_delete_examination(medical_db, examination_id)
    except examinations_service.ExaminationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Examination not found") from None
    audit_service.log(
        audit_db,
        event_code="EXAMINATION_DELETED",
        user_id=current_user.id,
        resource_type="EXAMINATION",
        resource_id=examination_id,
        ip_address=_client_ip(request),
    )


@router.get("/{examination_id}/channels", response_model=list[ExaminationChannelResponse])
def list_examination_channels(
    examination_id: UUID,
    medical_db: Annotated[Session, Depends(get_medical_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> list[ExaminationChannelResponse]:
    try:
        return [_channel_response(row) for row in examinations_service.list_channels(medical_db, examination_id)]
    except examinations_service.ExaminationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Examination not found") from None


@router.put("/{examination_id}/channels", response_model=list[ExaminationChannelResponse])
def replace_examination_channels(
    examination_id: UUID,
    payload: ExaminationChannelReplace,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    medical_db: Annotated[Session, Depends(get_medical_db)],
    audit_db: Annotated[Session, Depends(get_audit_db)],
) -> list[ExaminationChannelResponse]:
    try:
        rows = examinations_service.replace_channels(
            medical_db, examination_id=examination_id, channels=[channel.model_dump() for channel in payload.channels]
        )
    except examinations_service.ExaminationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Examination not found") from None
    except examinations_service.ExaminationValidationError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from None
    audit_service.log(
        audit_db,
        event_code="EXAMINATION_UPDATED",
        user_id=current_user.id,
        resource_type="EXAMINATION",
        resource_id=examination_id,
        metadata={"action": "CHANNELS_REPLACED", "channel_count": len(rows)},
        ip_address=_client_ip(request),
    )
    return [_channel_response(row) for row in rows]


@router.get("/{examination_id}/events", response_model=list[ExaminationEventResponse])
def list_examination_events(
    examination_id: UUID,
    medical_db: Annotated[Session, Depends(get_medical_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> list[ExaminationEventResponse]:
    try:
        return [_event_response(event) for event in examinations_service.list_events(medical_db, examination_id)]
    except examinations_service.ExaminationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Examination not found") from None


@router.post("/{examination_id}/events", response_model=ExaminationEventResponse, status_code=status.HTTP_201_CREATED)
def create_examination_event(
    examination_id: UUID,
    payload: ExaminationEventCreate,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    medical_db: Annotated[Session, Depends(get_medical_db)],
    audit_db: Annotated[Session, Depends(get_audit_db)],
) -> ExaminationEventResponse:
    try:
        event = examinations_service.create_event(
            medical_db, examination_id=examination_id, event=payload.model_dump()
        )
    except examinations_service.ExaminationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Examination not found") from None
    audit_service.log(
        audit_db,
        event_code="EXAMINATION_UPDATED",
        user_id=current_user.id,
        resource_type="EXAMINATION",
        resource_id=examination_id,
        metadata={"action": "EVENT_CREATED", "event_type": event.type},
        ip_address=_client_ip(request),
    )
    return _event_response(event)
