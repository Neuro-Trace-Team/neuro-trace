from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field
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


class ExaminationStatusesResponse(BaseModel):
    statuses: list[ExaminationStatus]


class ExaminationUpdate(BaseModel):
    examination_date: datetime | None = None


class PreprocessingStatusResponse(BaseModel):
    examination_id: UUID
    status: str


class MLAnalysisResponse(BaseModel):
    analysis_id: int
    result: Decimal
    confidence: Decimal = Field(ge=0, le=1)


class ExaminationResultsResponse(BaseModel):
    examination_id: UUID
    analyses: list[MLAnalysisResponse]


class ExaminationDetailResponse(ExaminationResponse):
    """Metadata plus per-analysis ML results when the examination is READY."""
    analyses: list[MLAnalysisResponse] = Field(default_factory=list)
