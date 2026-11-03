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
    sort_by: str = "created_at",
    sort_order: str = "desc",
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
    sort_columns = {"created_at": AuditLog.created_at, "event_code": AuditLogType.code}
    order_column = sort_columns[sort_by]
    ordering = order_column.asc() if sort_order == "asc" else order_column.desc()
    rows = list(
        session.execute(
            select(AuditLog, AuditLogType.code)
            .join(AuditLogType)
            .where(*filters)
            .order_by(ordering, AuditLog.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return rows, total


def get_audit_log(session: Session, log_id: UUID) -> tuple[AuditLog, str] | None:
    return session.execute(
        select(AuditLog, AuditLogType.code).join(AuditLogType).where(AuditLog.id == log_id)
    ).one_or_none()
