from typing import Literal

from pydantic import BaseModel, Field


class StorageUsageResponse(BaseModel):
    """Live usage of the RustFS bucket owned by the backend."""

    status: Literal["available"] = "available"
    bucket: str
    bucket_exists: bool
    object_count: int = Field(ge=0)
    used_bytes: int = Field(ge=0)


class StorageUnavailableResponse(BaseModel):
    """Storage state embedded in a dashboard response when RustFS is down."""

    status: Literal["unavailable"] = "unavailable"
    bucket: str
