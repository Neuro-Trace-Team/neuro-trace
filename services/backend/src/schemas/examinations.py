from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
from src.models.medical import ExaminationStatus


class ExaminationResponse(BaseModel):
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


class ExaminationListResponse(BaseModel):
    items: list[ExaminationResponse]
    page: int
    page_size: int
    total: int


class ExaminationUpdate(BaseModel):
    examination_date: datetime | None = None


class ExaminationEventCreate(BaseModel):
    timestamp: Decimal = Field(ge=0)
    type: str = Field(min_length=1, max_length=50)
    description: str | None = None

    @field_validator("type")
    @classmethod
    def strip_type(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("type must not be blank")
        return value


class ExaminationEventUpdate(BaseModel):
    timestamp: Decimal | None = Field(default=None, ge=0)
    type: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = None


class ExaminationEventResponse(BaseModel):
    id: UUID
    examination_id: UUID
    timestamp: Decimal
    type: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class PreprocessingStatusResponse(BaseModel):
    examination_id: UUID
    status: str


class MLAnalysisResponse(BaseModel):
    analysis_id: int
    time_stamp: Decimal
    result: Decimal
    confidence: Decimal | None = Field(default=None, ge=0, le=1)


class ExaminationResultsResponse(BaseModel):
    examination_id: UUID
    total_analyses_count: int | None
    analyses: list[MLAnalysisResponse]
