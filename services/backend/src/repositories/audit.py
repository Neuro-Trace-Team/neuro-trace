from datetime import datetime
from uuid import UUID

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from src.models.audit import AuditLog, AuditLogType


def app_activity_counts(session: Session, *, since: datetime) -> tuple[int, int, int]:
    """Return login and examination activity recorded since ``since``."""
    event_codes = ("LOGIN", "FAILED_LOGIN_ATTEMPT", "EXAMINATION_UPLOADED")
    event_counts = dict(
        session.execute(
            select(AuditLogType.code, func.count(AuditLog.id))
            .join(AuditLog, AuditLog.type_id == AuditLogType.id)
            .where(AuditLog.created_at >= since, AuditLogType.code.in_(event_codes))
            .group_by(AuditLogType.code)
        ).all()
    )
    active_users = session.scalar(
        select(func.count(func.distinct(AuditLog.user_id)))
        .join(AuditLogType, AuditLog.type_id == AuditLogType.id)
        .where(
            AuditLog.created_at >= since,
            AuditLogType.code == "LOGIN",
            AuditLog.user_id.is_not(None),
        )
    ) or 0
    return (
        active_users,
        event_counts.get("FAILED_LOGIN_ATTEMPT", 0),
        event_counts.get("EXAMINATION_UPLOADED", 0),
    )


def list_audit_logs(
    session: Session,
    *,
    page: int,
    page_size: int,
    query: str | None = None,
    log_id: UUID | None = None,
    event_code: str | None = None,
    user_id: UUID | None = None,
    type_id: int | None = None,
    created_at_from: datetime | None = None,
    created_at_to: datetime | None = None,
    ip_address: str | None = None,
    request_id: UUID | None = None,
    resource_type: str | None = None,
    resource_id: UUID | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> tuple[list[tuple[AuditLog, str]], int]:
    filters = []
    if query is not None:
        pattern = f"%{query}%"
        filters.append(or_(
            cast(AuditLog.id, String).ilike(pattern),
            cast(AuditLog.user_id, String).ilike(pattern),
            cast(AuditLog.ip_address, String).ilike(pattern),
        ))
    if log_id is not None:
        filters.append(AuditLog.id == log_id)
    if event_code is not None:
        filters.append(AuditLogType.code == event_code)
    if user_id is not None:
        filters.append(AuditLog.user_id == user_id)
    if type_id is not None:
        filters.append(AuditLog.type_id == type_id)
    if created_at_from is not None:
        filters.append(AuditLog.created_at >= created_at_from)
    if created_at_to is not None:
        filters.append(AuditLog.created_at <= created_at_to)
    if ip_address is not None:
        filters.append(AuditLog.ip_address == ip_address)
    if request_id is not None:
        filters.append(AuditLog.request_id == request_id)
    if resource_type is not None:
        filters.append(AuditLog.resource_type == resource_type)
    if resource_id is not None:
        filters.append(AuditLog.resource_id == resource_id)

    total = session.scalar(
        select(func.count()).select_from(AuditLog).join(AuditLogType).where(*filters)
    ) or 0
    sort_columns = {
        "id": AuditLog.id,
        "user_id": AuditLog.user_id,
        "type_id": AuditLog.type_id,
        "created_at": AuditLog.created_at,
        "ip_address": AuditLog.ip_address,
        "request_id": AuditLog.request_id,
        "resource_type": AuditLog.resource_type,
        "resource_id": AuditLog.resource_id,
        "event_code": AuditLogType.code,
    }
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
