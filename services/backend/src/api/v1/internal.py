from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.deps import require_roles
from src.core.roles import Role
from src.db.sessions import get_medical_db
from src.schemas.internal import (
    PreprocessingChannel,
    PreprocessingEvent,
    PreprocessingExaminationMetadata,
    PreprocessingExaminationResponse,
    PreprocessingSourceFile,
)
from src.services import examinations as examinations_service

router = APIRouter(prefix="/internal/preprocessing", tags=["internal preprocessing"])
admin_only = Depends(require_roles(Role.ADMIN))


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
