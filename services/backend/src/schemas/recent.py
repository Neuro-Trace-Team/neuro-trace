from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from src.models.medical import ExaminationStatus


class RecentPatientResponse(BaseModel):
    id: UUID
    patient_id: UUID
    created_at: datetime
    updated_at: datetime
    last_visited_at: datetime
    first_examination_date: datetime | None
    last_examination_date: datetime | None
    examination_count: int


class RecentExaminationResponse(BaseModel):
    id: UUID
    patient_id: UUID
    uploaded_by: UUID
    original_filename: str
    file_format: str
    file_size_bytes: int
    file_checksum: str | None
    status: ExaminationStatus
    examination_date: datetime | None
    created_at: datetime
    updated_at: datetime
    last_visited_at: datetime
