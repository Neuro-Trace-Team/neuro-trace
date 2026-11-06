import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from tempfile import SpooledTemporaryFile
from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy.orm import Session

from src.config import get_settings
from src.models.medical import Examination, ExaminationEvent, ExaminationStatus, Patient
from src.repositories import examinations as repository
from src.services import patients as patients_service
from src.services.storage import RustFSStorage

_ALLOWED_EEG_EXTENSIONS = frozenset({"edf", "bdf", "set", "fif", "vhdr", "eeg"})
_CHUNK_SIZE = 1024 * 1024
class ExaminationNotFoundError(Exception): pass
class ExaminationValidationError(Exception): pass
class ExaminationEventNotFoundError(Exception): pass
def _now() -> datetime: return datetime.now(UTC)
def _safe_filename(filename: str) -> str: return re.sub(r"[^A-Za-z0-9._-]", "_", Path(filename).name)[:255]

async def upload_examination(session: Session, *, patient_id: UUID | None, generate_patient: bool, uploaded_by: UUID, file: UploadFile, examination_date: datetime | None, events: list[dict]) -> tuple[Examination, bool]:
    if not file.filename: raise ExaminationValidationError("A file name is required")
    filename = _safe_filename(file.filename)
    extension = Path(filename).suffix.lower().lstrip(".")
    if not filename or extension not in _ALLOWED_EEG_EXTENSIONS: raise ExaminationValidationError("Unsupported EEG format")
    settings, checksum, total_size = get_settings(), hashlib.sha256(), 0
    with SpooledTemporaryFile(max_size=min(settings.max_upload_size_bytes, 10 * 1024 * 1024), mode="w+b") as temporary:
        while chunk := await file.read(_CHUNK_SIZE):
            total_size += len(chunk)
            if total_size > settings.max_upload_size_bytes: raise ExaminationValidationError("The uploaded file exceeds the configured size limit")
            checksum.update(chunk); temporary.write(chunk)
        if not total_size: raise ExaminationValidationError("The uploaded file is empty")
        created_patient = False
        if patient_id is None:
            if not generate_patient:
                raise ExaminationValidationError("patient_id or generate_patient=true is required")
            patient = Patient()
            session.add(patient)
            session.flush()
            patient_id = patient.id
            created_patient = True
        else:
            if generate_patient:
                raise ExaminationValidationError("patient_id and generate_patient cannot be used together")
            patients_service.get_patient(session, patient_id)
        examination_id = uuid4(); storage_key = f"examinations/{patient_id}/{examination_id}/{filename}"; temporary.seek(0)
        storage = RustFSStorage()
        try:
            storage.upload(temporary, key=storage_key, content_type=file.content_type)
        except Exception:
            session.rollback()
            raise
        try:
            examination = Examination(id=examination_id, patient_id=patient_id, uploaded_by=uploaded_by, original_filename=filename, file_format=extension, file_size_bytes=total_size, storage_bucket=settings.rustfs_bucket, storage_key=storage_key, file_checksum=checksum.hexdigest(), examination_date=examination_date)
            session.add(examination)
            session.add_all(ExaminationEvent(examination_id=examination_id, **event) for event in events)
            session.commit(); session.refresh(examination); return examination, created_patient
        except Exception:
            session.rollback(); storage.delete(key=storage_key); raise

def get_examination(session: Session, examination_id: UUID) -> Examination:
    record = repository.get_examination(session, examination_id)
    if record is None: raise ExaminationNotFoundError
    return record
def mark_examination_ready(session: Session, examination_id: UUID) -> bool:
    record = repository.get_examination(session, examination_id)
    if record is None:
        return False
    if record.status is ExaminationStatus.READY:
        return True
    record.status = ExaminationStatus.READY
    record.updated_at = _now()
    session.commit()
    return True
def list_examinations(session: Session, **kwargs): return repository.list_examinations(session, **kwargs)
def update_examination(session: Session, *, examination_id: UUID, updates: dict) -> Examination:
    record = get_examination(session, examination_id)
    for field, value in updates.items(): setattr(record, field, value)
    record.updated_at = _now(); session.commit(); session.refresh(record); return record
def soft_delete_examination(session: Session, examination_id: UUID) -> Examination:
    record = get_examination(session, examination_id); record.deleted_at = record.updated_at = _now(); session.commit(); session.refresh(record); return record
def soft_delete_examinations(session: Session, examination_ids: list[UUID]) -> list[Examination]:
    records = [get_examination(session, value) for value in examination_ids]
    now = _now()
    for record in records: record.deleted_at = record.updated_at = now
    session.commit(); return records
def list_events(session: Session, examination_id: UUID): get_examination(session, examination_id); return repository.list_events(session, examination_id)
def create_event(session: Session, *, examination_id: UUID, event: dict) -> ExaminationEvent:
    get_examination(session, examination_id); record = ExaminationEvent(examination_id=examination_id, **event); session.add(record); session.commit(); session.refresh(record); return record
def update_event(session: Session, *, examination_id: UUID, event_id: UUID, updates: dict) -> ExaminationEvent:
    get_examination(session, examination_id); record = repository.get_event(session, examination_id, event_id)
    if record is None: raise ExaminationEventNotFoundError
    for field, value in updates.items(): setattr(record, field, value)
    record.updated_at = _now(); session.commit(); session.refresh(record); return record
def delete_event(session: Session, *, examination_id: UUID, event_id: UUID) -> None:
    get_examination(session, examination_id); record = repository.get_event(session, examination_id, event_id)
    if record is None: raise ExaminationEventNotFoundError
    session.delete(record); session.commit()
