from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class BulkExaminationRequest(BaseModel):
    examination_ids: list[UUID] = Field(min_length=1, max_length=100)

    @field_validator("examination_ids")
    @classmethod
    def reject_duplicates(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("examination_ids must be unique")
        return value


class BulkDeleteResponse(BaseModel):
    deleted_count: int
    examination_ids: list[UUID]
