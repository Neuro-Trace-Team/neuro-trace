from datetime import datetime

from pydantic import BaseModel, Field

from src.schemas.storage import StorageUnavailableResponse, StorageUsageResponse


class AppActivityResponse(BaseModel):
    """Operational metrics collected during the last 24 hours."""

    period_started_at: datetime
    active_users_last_24h: int = Field(ge=0)
    failed_login_attempts_last_24h: int = Field(ge=0)
    examinations_uploaded_last_24h: int = Field(ge=0)
    storage: StorageUsageResponse | StorageUnavailableResponse
