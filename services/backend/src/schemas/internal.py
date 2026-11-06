from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from src.schemas.analyses import AnalysisResponse, AnalysisResultResponse


class PreprocessingSourceFile(BaseModel):
    bucket: str
    storage_key: str
    original_filename: str
    file_format: str
    file_size_bytes: int
    file_checksum: str | None


class PreprocessingExaminationMetadata(BaseModel):
    examination_date: datetime | None
    sampling_frequency: int
    electrode_positions: dict[str, Any] | None
    reference: str | None
    power_line_frequency: int | None
    duration_seconds: Decimal | None


class PreprocessingChannel(BaseModel):
    channel_id: int
    code: str
    position: int


class PreprocessingEvent(BaseModel):
    id: UUID
    timestamp: Decimal
    type: str
    description: str | None
    metadata: dict[str, Any] | None


class PreprocessingExaminationResponse(BaseModel):
    examination_id: UUID
    patient_id: UUID
    source_file: PreprocessingSourceFile
    metadata: PreprocessingExaminationMetadata
    channels: list[PreprocessingChannel]
    events: list[PreprocessingEvent]


class InternalAnalysisFailureReport(BaseModel):
    error_message: str = Field(min_length=1, max_length=2000)


class InternalAnalysisCompletionResponse(BaseModel):
    analysis: AnalysisResponse
    result: AnalysisResultResponse
