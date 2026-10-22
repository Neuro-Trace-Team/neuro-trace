from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class PatientResponse(BaseModel):
    id: UUID
    created_at: datetime
    updated_at: datetime


class PatientListResponse(BaseModel):
    items: list[PatientResponse]
    page: int
    page_size: int
    total: int


class PatientStatisticsResponse(BaseModel):
    total_patients: int
    patients_with_examinations: int
    active_examinations: int


class PatientExaminationResponse(BaseModel):
    id: UUID
    patient_id: UUID
    examination_date: datetime | None
    created_at: datetime
    updated_at: datetime
    file_format: str
    file_size_bytes: int
    sampling_frequency: int
    duration_seconds: Decimal | None
    processing_status: str


class PatientExaminationListResponse(BaseModel):
    items: list[PatientExaminationResponse]
    page: int
    page_size: int
    total: int
