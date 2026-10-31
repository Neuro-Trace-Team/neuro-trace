from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class PainAssessmentCreate(BaseModel):
    pain_level: Decimal = Field(ge=0)
    scale: str = Field(min_length=1, max_length=50)
    notes: str | None = None
    assessed_at: datetime | None = None

    @field_validator("scale")
    @classmethod
    def normalize_scale(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("scale must not be blank")
        return value


class PainAssessmentResponse(BaseModel):
    id: UUID
    examination_id: UUID
    assessed_by: UUID
    pain_level: Decimal
    scale: str
    notes: str | None
    assessed_at: datetime
    created_at: datetime


class PainAssessmentListResponse(BaseModel):
    items: list[PainAssessmentResponse]
    page: int
    page_size: int
    total: int
