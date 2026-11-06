from datetime import datetime
from decimal import Decimal
import re
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
from src.models.medical import ExaminationStatus

_TIMESTAMP_RE = re.compile(r"^(?P<hours>\d+):(?P<minutes>[0-5]\d):(?P<seconds>[0-5]\d):(?P<microseconds>\d{1,6})$")


def parse_timestamp(value: object) -> Decimal:
    """Accept seconds or frontend HH:MM:SS:microseconds timestamps."""
    if not isinstance(value, str):
        return Decimal(str(value))
    match = _TIMESTAMP_RE.fullmatch(value.strip())
    if match is None:
        raise ValueError("timestamp must be seconds or HH:MM:SS:microseconds")
    groups = match.groupdict()
    microseconds = groups["microseconds"].ljust(6, "0")
    return Decimal(int(groups["hours"]) * 3600 + int(groups["minutes"]) * 60 + int(groups["seconds"])) + Decimal(int(microseconds)) / Decimal(1_000_000)


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

    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_frontend_timestamp(cls, value: object) -> Decimal:
        return parse_timestamp(value)

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

    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_frontend_timestamp(cls, value: object) -> Decimal | None:
        return None if value is None else parse_timestamp(value)


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
    result: Decimal
    confidence: Decimal = Field(ge=0, le=1)


class ExaminationResultsResponse(BaseModel):
    examination_id: UUID
    analyses: list[MLAnalysisResponse]


class ExaminationDetailResponse(ExaminationResponse):
    """Metadata plus per-analysis ML results when the examination is READY."""
    analyses: list[MLAnalysisResponse] = Field(default_factory=list)
