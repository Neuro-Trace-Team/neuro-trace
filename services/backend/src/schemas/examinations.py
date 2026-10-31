from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ExaminationResponse(BaseModel):
    id: UUID
    patient_id: UUID
    uploaded_by: UUID
    original_filename: str
    file_format: str
    file_size_bytes: int
    file_checksum: str | None
    examination_date: datetime | None
    created_at: datetime
    updated_at: datetime
    sampling_frequency: int
    electrode_positions: dict[str, Any] | None
    reference: str | None
    power_line_frequency: int | None
    duration_seconds: Decimal | None
    processing_status: str


class ExaminationListResponse(BaseModel):
    items: list[ExaminationResponse]
    page: int
    page_size: int
    total: int


class ExaminationUpdate(BaseModel):
    examination_date: datetime | None = None
    electrode_positions: dict[str, Any] | None = None
    reference: str | None = Field(default=None, max_length=50)
    power_line_frequency: int | None = None
    duration_seconds: Decimal | None = Field(default=None, gt=0)

    @field_validator("power_line_frequency")
    @classmethod
    def validate_power_line_frequency(cls, value: int | None) -> int | None:
        if value is not None and value not in (50, 60):
            raise ValueError("power_line_frequency must be 50 or 60")
        return value


class ExaminationEventCreate(BaseModel):
    timestamp: Decimal = Field(ge=0)
    type: str = Field(min_length=1, max_length=50)
    description: str | None = None
    metadata: dict[str, Any] | None = None


class ExaminationEventUpdate(BaseModel):
    timestamp: Decimal | None = Field(default=None, ge=0)
    type: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = None
    metadata: dict[str, Any] | None = None


class ExaminationEventResponse(BaseModel):
    id: UUID
    examination_id: UUID
    timestamp: Decimal
    type: str
    description: str | None
    metadata: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class ExaminationChannelInput(BaseModel):
    channel_id: int = Field(gt=0)
    position: int = Field(ge=0)


class ExaminationChannelReplace(BaseModel):
    channels: list[ExaminationChannelInput]


class ExaminationChannelResponse(BaseModel):
    channel_id: int
    code: str
    description: str | None
    position: int


class EEGChannelResponse(BaseModel):
    id: int
    code: str
    description: str | None
