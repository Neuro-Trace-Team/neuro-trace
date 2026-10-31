from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class AnalysisCreate(BaseModel):
    preprocessing_job_id: UUID
    model_name: str = Field(min_length=1, max_length=100)
    model_version: str = Field(min_length=1, max_length=100)

    @field_validator("model_name", "model_version")
    @classmethod
    def reject_blank_values(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value must not be blank")
        return value


class AnalysisResponse(BaseModel):
    id: UUID
    examination_id: UUID
    preprocessing_job_id: UUID
    requested_by: UUID
    status: str
    model_name: str
    model_version: str
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None


class AnalysisListResponse(BaseModel):
    items: list[AnalysisResponse]
    page: int
    page_size: int
    total: int


class AnalysisStatusUpdate(BaseModel):
    status: Literal["RUNNING", "CANCELLED"]


class AnalysisResultCreate(BaseModel):
    pain_level: Decimal | None = None
    confidence: Decimal | None = Field(default=None, ge=0, le=1)
    result: dict[str, Any] | None = None
    explanation: dict[str, Any] | None = None


class AnalysisResultResponse(BaseModel):
    id: UUID
    analysis_id: UUID
    pain_level: Decimal | None
    confidence: Decimal | None
    result: dict[str, Any] | None
    explanation: dict[str, Any] | None
    created_at: datetime


class ExaminationResultResponse(BaseModel):
    analysis: AnalysisResponse
    result: AnalysisResultResponse


class ExaminationResultListResponse(BaseModel):
    items: list[ExaminationResultResponse]
    page: int
    page_size: int
    total: int
