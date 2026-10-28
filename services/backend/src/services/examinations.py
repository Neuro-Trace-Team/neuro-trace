import hashlib
import re
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import SpooledTemporaryFile
from typing import Any
from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy.orm import Session

from src.config import get_settings
from src.models.medical import (
    EEGChannel,
    Examination,
    ExaminationChannel,
    ExaminationEvent,
)
from src.repositories import examinations as examinations_repository
from src.services import patients as patients_service
from src.services.storage import RustFSStorage

_ALLOWED_EEG_EXTENSIONS = frozenset({"edf", "bdf", "set", "fif", "vhdr", "eeg"})
_CHUNK_SIZE = 1024 * 1024


class ExaminationNotFoundError(Exception):
    pass


class ExaminationValidationError(Exception):
    pass


class ExaminationEventNotFoundError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def _safe_filename(filename: str) -> str:
    name = Path(filename).name
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)[:255]


async def upload_examination(
    session: Session,
    *,
    patient_id: UUID,
    uploaded_by: UUID,
    file: UploadFile,
    sampling_frequency: int,
    examination_date: datetime | None,
    electrode_positions: dict[str, Any] | None,
    reference: str | None,
    power_line_frequency: int | None,
    duration_seconds: Decimal | None,
) -> Examination:
    patients_service.get_patient(session, patient_id)
    if sampling_frequency <= 0:
        raise ExaminationValidationError("sampling_frequency must be positive")
    if power_line_frequency is not None and power_line_frequency not in (50, 60):
        raise ExaminationValidationError("power_line_frequency must be 50 or 60")
    if duration_seconds is not None and duration_seconds <= 0:
        raise ExaminationValidationError("duration_seconds must be positive")
    if not file.filename:
        raise ExaminationValidationError("A file name is required")

    filename = _safe_filename(file.filename)
    extension = Path(filename).suffix.lower().lstrip(".")
    if not filename or extension not in _ALLOWED_EEG_EXTENSIONS:
        allowed = ", ".join(sorted(_ALLOWED_EEG_EXTENSIONS))
        raise ExaminationValidationError(f"Unsupported EEG format. Allowed formats: {allowed}")

    settings = get_settings()
    checksum = hashlib.sha256()
    total_size = 0
    with SpooledTemporaryFile(max_size=min(settings.max_upload_size_bytes, 10 * 1024 * 1024), mode="w+b") as temporary:
        try:
            while chunk := await file.read(_CHUNK_SIZE):
                total_size += len(chunk)
                if total_size > settings.max_upload_size_bytes:
                    raise ExaminationValidationError("The uploaded file exceeds the configured size limit")
                checksum.update(chunk)
                temporary.write(chunk)
            if total_size == 0:
                raise ExaminationValidationError("The uploaded file is empty")

            examination_id = uuid4()
            storage_key = f"examinations/{patient_id}/{examination_id}/{filename}"
            temporary.seek(0)
            storage = RustFSStorage()
            storage.upload(temporary, key=storage_key, content_type=file.content_type)
            try:
                examination = Examination(
                    id=examination_id,
                    patient_id=patient_id,
                    uploaded_by=uploaded_by,
                    original_filename=filename,
                    file_format=extension.upper(),
                    file_size_bytes=total_size,
                    storage_bucket=storage.bucket,
                    storage_key=storage_key,
                    file_checksum=checksum.hexdigest(),
                    examination_date=examination_date,
                    sampling_frequency=sampling_frequency,
                    electrode_positions=electrode_positions,
                    reference=reference.strip() if reference else None,
                    power_line_frequency=power_line_frequency,
                    duration_seconds=duration_seconds,
                    processing_status="UPLOADED",
                )
                session.add(examination)
                session.commit()
                session.refresh(examination)
                return examination
            except Exception:
                session.rollback()
                storage.delete(key=storage_key)
                raise
        finally:
            await file.close()


def get_examination(session: Session, examination_id: UUID) -> Examination:
    examination = examinations_repository.get_examination(session, examination_id)
    if examination is None:
        raise ExaminationNotFoundError
    return examination


def list_examinations(
    session: Session,
    *,
    page: int,
    page_size: int,
    patient_id: UUID | None,
    uploaded_by: UUID | None,
    processing_status: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    channel: str | None = None,
    pain_level: Decimal | None = None,
    pain_level_min: Decimal | None = None,
    pain_level_max: Decimal | None = None,
    pain_source: str = "doctor",
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> tuple[list[Examination], int]:
    return examinations_repository.list_examinations(
        session,
        page=page,
        page_size=page_size,
        patient_id=patient_id,
        uploaded_by=uploaded_by,
        processing_status=processing_status,
        date_from=date_from,
        date_to=date_to,
        channel=channel,
        pain_level=pain_level,
        pain_level_min=pain_level_min,
        pain_level_max=pain_level_max,
        pain_source=pain_source,
        sort_by=sort_by,
        sort_order=sort_order,
    )


def update_examination(session: Session, *, examination_id: UUID, updates: dict[str, Any]) -> Examination:
    examination = get_examination(session, examination_id)
    for field, value in updates.items():
        setattr(examination, field, value.strip() if field == "reference" and value else value)
    examination.updated_at = _now()
    session.commit()
    session.refresh(examination)
    return examination


def soft_delete_examination(session: Session, examination_id: UUID) -> Examination:
    examination = get_examination(session, examination_id)
    now = _now()
    examination.deleted_at = now
    examination.updated_at = now
    session.commit()
    session.refresh(examination)
    return examination


def soft_delete_examinations(session: Session, examination_ids: list[UUID]) -> list[Examination]:
    examinations = [get_examination(session, examination_id) for examination_id in examination_ids]
    now = _now()
    for examination in examinations:
        examination.deleted_at = now
        examination.updated_at = now
    session.commit()
    for examination in examinations:
        session.refresh(examination)
    return examinations


def list_eeg_channels(session: Session) -> list[EEGChannel]:
    return examinations_repository.list_eeg_channels(session)


def replace_channels(
    session: Session, *, examination_id: UUID, channels: list[dict[str, int]]
) -> list[tuple[ExaminationChannel, EEGChannel]]:
    get_examination(session, examination_id)
    channel_ids = [channel["channel_id"] for channel in channels]
    positions = [channel["position"] for channel in channels]
    if len(channel_ids) != len(set(channel_ids)) or len(positions) != len(set(positions)):
        raise ExaminationValidationError("Channel IDs and positions must be unique")
    catalog = examinations_repository.get_eeg_channels_by_ids(session, set(channel_ids))
    if len(catalog) != len(channel_ids):
        raise ExaminationValidationError("One or more EEG channel IDs are unknown")
    session.query(ExaminationChannel).filter(ExaminationChannel.examination_id == examination_id).delete()
    session.add_all(
        ExaminationChannel(examination_id=examination_id, channel_id=channel["channel_id"], position=channel["position"])
        for channel in channels
    )
    session.commit()
    return examinations_repository.list_examination_channels(session, examination_id)


def list_channels(session: Session, examination_id: UUID) -> list[tuple[ExaminationChannel, EEGChannel]]:
    get_examination(session, examination_id)
    return examinations_repository.list_examination_channels(session, examination_id)


def create_event(session: Session, *, examination_id: UUID, event: dict[str, Any]) -> ExaminationEvent:
    get_examination(session, examination_id)
    record = ExaminationEvent(
        examination_id=examination_id,
        timestamp=event["timestamp"],
        type=event["type"].strip(),
        description=event.get("description"),
        metadata_json=event.get("metadata"),
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def list_events(session: Session, examination_id: UUID) -> list[ExaminationEvent]:
    get_examination(session, examination_id)
    return examinations_repository.list_events(session, examination_id)


def update_event(
    session: Session, *, examination_id: UUID, event_id: UUID, updates: dict[str, Any]
) -> ExaminationEvent:
    get_examination(session, examination_id)
    event = examinations_repository.get_event(session, examination_id=examination_id, event_id=event_id)
    if event is None:
        raise ExaminationEventNotFoundError
    for field, value in updates.items():
        if field == "metadata":
            event.metadata_json = value
        else:
            setattr(event, field, value.strip() if field == "type" and value else value)
    event.updated_at = _now()
    session.commit()
    session.refresh(event)
    return event


def delete_event(session: Session, *, examination_id: UUID, event_id: UUID) -> None:
    get_examination(session, examination_id)
    event = examinations_repository.get_event(session, examination_id=examination_id, event_id=event_id)
    if event is None:
        raise ExaminationEventNotFoundError
    session.delete(event)
    session.commit()
