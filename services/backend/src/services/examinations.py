import hashlib
import json
import re
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from tempfile import SpooledTemporaryFile
from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy.orm import Session

from src.config import get_settings
from src.models.medical import Examination, ExaminationStatus, Patient
from src.repositories import examinations as repository
from src.services import patients as patients_service
from src.services.storage import RustFSStorage

_ALLOWED_EEG_EXTENSIONS = frozenset({"edf", "bdf", "set", "fif", "vhdr", "eeg"})
_CHUNK_SIZE = 1024 * 1024
_EDF_HEADER_SIZE = 256
_TIMESTAMP_PATTERN = re.compile(r"^[0-9]{2}:[0-5][0-9]:[0-5][0-9]:[0-9]{3}$")
class ExaminationNotFoundError(Exception): pass
class ExaminationValidationError(Exception): pass
def _now() -> datetime: return datetime.now(UTC)
def _safe_filename(filename: str) -> str: return re.sub(r"[^A-Za-z0-9._-]", "_", Path(filename).name)[:255]

def timestamp_to_milliseconds(timestamp: str) -> int:
    """Convert the frontend's HH:MM:SS:mmm representation to milliseconds."""
    if not _TIMESTAMP_PATTERN.fullmatch(timestamp):
        raise ExaminationValidationError("timestamps must use HH:MM:SS:mmm format")
    hours, minutes, seconds, milliseconds = (int(part) for part in timestamp.split(":"))
    return (((hours * 60) + minutes) * 60 + seconds) * 1000 + milliseconds


def milliseconds_to_timestamp(milliseconds: int | float) -> str:
    """Convert an integral ML timestamp in milliseconds to HH:MM:SS:mmm."""
    if isinstance(milliseconds, bool) or not isinstance(milliseconds, (int, float)):
        raise ValueError("timestamp must be a number of milliseconds")
    if isinstance(milliseconds, float) and not milliseconds.is_integer():
        raise ValueError("timestamp must be an integral number of milliseconds")
    value = int(milliseconds)
    if value < 0 or value >= 100 * 60 * 60 * 1000:
        raise ValueError("timestamp is outside the supported HH:MM:SS:mmm range")
    hours, remainder = divmod(value, 60 * 60 * 1000)
    minutes, remainder = divmod(remainder, 60 * 1000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{millis:03d}"


def parse_timestamps(value: str) -> list[int]:
    """Validate frontend timestamps and prepare milliseconds for RustFS JSON."""
    try:
        timestamps = json.loads(value)
    except json.JSONDecodeError as error:
        raise ExaminationValidationError("timestamps must be a JSON array") from error
    if not isinstance(timestamps, list):
        raise ExaminationValidationError("timestamps must be a JSON array")
    if not all(isinstance(timestamp, str) for timestamp in timestamps):
        raise ExaminationValidationError("timestamps must use HH:MM:SS:mmm format")
    return [timestamp_to_milliseconds(timestamp) for timestamp in timestamps]


def timestamps_storage_key(storage_key: str) -> str:
    """Use a deterministic companion object next to the EEG/BDF recording."""
    return f"{storage_key.rsplit('/', 1)[0]}/timestamps.json"


def _extract_recording_datetime(file: SpooledTemporaryFile[bytes], extension: str) -> datetime | None:
    """Read the start date/time stored in the fixed EDF/BDF header.

    EDF/BDF headers do not encode a timezone. The backend stores this source
    timestamp as UTC so its value remains explicit in a TIMESTAMPTZ column.
    """
    if extension not in {"edf", "bdf"}:
        return None
    file.seek(0)
    header = file.read(_EDF_HEADER_SIZE)
    file.seek(0)
    if len(header) < _EDF_HEADER_SIZE:
        raise ExaminationValidationError("EDF/BDF file is too short to contain its header")
    try:
        date = header[168:176].decode("ascii").strip()
        time = header[176:184].decode("ascii").strip()
        return datetime.strptime(f"{date} {time}", "%d.%m.%y %H.%M.%S").replace(tzinfo=UTC)
    except (UnicodeDecodeError, ValueError) as error:
        raise ExaminationValidationError("EDF/BDF header has an invalid recording date") from error


async def upload_examination(
    session: Session,
    *,
    patient_id: UUID | None,
    generate_patient: bool,
    uploaded_by: UUID,
    file: UploadFile,
    timestamps: list[int],
) -> tuple[Examination, bool]:
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
        examination_date = _extract_recording_datetime(temporary, extension)
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
        timestamp_key = timestamps_storage_key(storage_key)
        storage = RustFSStorage()
        try:
            storage.upload(temporary, key=storage_key, content_type=file.content_type)
            storage.upload(
                BytesIO(json.dumps({"timestamps": timestamps}, ensure_ascii=False).encode("utf-8")),
                key=timestamp_key,
                content_type="application/json",
            )
        except Exception:
            session.rollback()
            storage.delete(key=timestamp_key)
            storage.delete(key=storage_key)
            raise
        try:
            examination = Examination(id=examination_id, patient_id=patient_id, uploaded_by=uploaded_by, original_filename=filename, file_format=extension, file_size_bytes=total_size, storage_bucket=settings.rustfs_bucket, storage_key=storage_key, file_checksum=checksum.hexdigest(), examination_date=examination_date)
            session.add(examination)
            session.commit(); session.refresh(examination); return examination, created_patient
        except Exception:
            session.rollback(); storage.delete(key=timestamp_key); storage.delete(key=storage_key); raise

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
