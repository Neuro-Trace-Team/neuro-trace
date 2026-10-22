from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.audit import AuditLog, AuditLogType


def list_audit_logs(
    session: Session,
    *,
    page: int,
    page_size: int,
    event_code: str | None = None,
    user_id: UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> tuple[list[tuple[AuditLog, str]], int]:
    filters = []
    if event_code is not None:
        filters.append(AuditLogType.code == event_code)
    if user_id is not None:
        filters.append(AuditLog.user_id == user_id)
    if date_from is not None:
        filters.append(AuditLog.created_at >= date_from)
    if date_to is not None:
        filters.append(AuditLog.created_at <= date_to)

    total = session.scalar(
        select(func.count()).select_from(AuditLog).join(AuditLogType).where(*filters)
    ) or 0
    rows = list(
        session.execute(
            select(AuditLog, AuditLogType.code)
            .join(AuditLogType)
            .where(*filters)
            .order_by(AuditLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return rows, total


def get_audit_log(session: Session, log_id: UUID) -> tuple[AuditLog, str] | None:
    return session.execute(
        select(AuditLog, AuditLogType.code).join(AuditLogType).where(AuditLog.id == log_id)
    ).one_or_none()
