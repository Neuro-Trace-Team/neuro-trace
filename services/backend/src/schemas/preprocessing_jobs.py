from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class PreprocessingJobCreate(BaseModel):
    pipeline_version: str = Field(min_length=1, max_length=100)
    parameters: dict[str, Any] | None = None


class PreprocessingJobResponse(BaseModel):
    id: UUID
    examination_id: UUID
    status: str
    pipeline_version: str
    parameters: dict[str, Any] | None
    output_bucket: str | None
    output_storage_key: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class PreprocessingJobListResponse(BaseModel):
    items: list[PreprocessingJobResponse]
    page: int
    page_size: int
    total: int


class PreprocessingJobStatusUpdate(BaseModel):
    status: Literal["RUNNING", "CANCELLED"]


class PreprocessingJobResult(BaseModel):
    status: Literal["COMPLETED", "FAILED"]
    output_bucket: str | None = Field(default=None, max_length=100)
    output_storage_key: str | None = Field(default=None, max_length=1024)
    error_message: str | None = Field(default=None, min_length=1, max_length=2000)

    @model_validator(mode="after")
    def validate_result(self) -> "PreprocessingJobResult":
        has_output = bool(self.output_bucket) or bool(self.output_storage_key)
        if self.status == "COMPLETED":
            if self.output_bucket is None or self.output_storage_key is None:
                raise ValueError("Completed preprocessing requires output_bucket and output_storage_key")
            if self.error_message is not None:
                raise ValueError("Completed preprocessing cannot contain error_message")
        elif has_output:
            raise ValueError("Failed preprocessing cannot contain output storage coordinates")
        elif self.error_message is None:
            raise ValueError("Failed preprocessing requires error_message")
        return self
