from datetime import datetime
from decimal import Decimal
from typing import Literal
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
    time_stamp: str = Field(pattern=r"^[0-9]{2}:[0-5][0-9]:[0-5][0-9]:[0-9]{3}$")
    is_valid: bool
    result: float | None
    confidence: float | None = Field(default=None, ge=0, le=1)
    invalid_reason: str | None = None


class ExaminationResultsResponse(BaseModel):
    examination_id: UUID
    total_analyses_count: int | None = Field(default=None, ge=0)
    analyses: list[MLAnalysisResponse]


class ExaminationResultsProcessingResponse(BaseModel):
    """ML has accepted the examination but has not produced every analysis yet."""

    examination_id: UUID
    status: Literal["PROCESSING"]
    received_analyses_count: int = Field(ge=0)
    total_analyses_count: int = Field(ge=0)
    analyses: list[MLAnalysisResponse] = Field(default_factory=list)


class ExaminationDetailResponse(ExaminationResponse):
    """Metadata plus the current availability of ML analyses."""

    analysis_status: Literal["NOT_READY", "PROCESSING", "READY"] = "NOT_READY"
    received_analyses_count: int | None = Field(default=None, ge=0)
    total_analyses_count: int | None = Field(default=None, ge=0)
    analyses: list[MLAnalysisResponse] = Field(default_factory=list)
