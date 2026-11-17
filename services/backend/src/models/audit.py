from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import AuditBase


class AuditLogType(AuditBase):
    __tablename__ = "audit_log_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class AuditLog(AuditBase):
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    type_id: Mapped[int] = mapped_column(ForeignKey("audit_log_types.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    ip_address: Mapped[str | None] = mapped_column(INET)
    request_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    resource_type: Mapped[str | None] = mapped_column(String(50))
    resource_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
