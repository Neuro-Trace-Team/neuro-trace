from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: UUID
    event_code: str
    user_id: UUID | None
    resource_type: str | None
    resource_id: UUID | None
    metadata: dict[str, Any] | None
    ip_address: str | None
    request_id: UUID | None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    page: int
    page_size: int
    total: int
