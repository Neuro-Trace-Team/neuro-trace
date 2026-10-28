from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.api.deps import require_roles
from src.core.roles import Role
from src.db.sessions import get_audit_db
from src.models.audit import AuditLog
from src.repositories import audit as audit_repository
from src.schemas.audit import AuditLogListResponse, AuditLogResponse

router = APIRouter(prefix="/admin", tags=["administration"])
admin_only = Depends(require_roles(Role.ADMIN))


def _to_response(log: AuditLog, event_code: str) -> AuditLogResponse:
    return AuditLogResponse(
        id=log.id,
        event_code=event_code,
        user_id=log.user_id,
        resource_type=log.resource_type,
        resource_id=log.resource_id,
        metadata=log.metadata_json,
        ip_address=str(log.ip_address) if log.ip_address else None,
        request_id=log.request_id,
        created_at=log.created_at,
    )


@router.get("/audit-logs", response_model=AuditLogListResponse, dependencies=[admin_only])
def list_audit_logs(
    audit_db: Annotated[Session, Depends(get_audit_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    event_code: str | None = Query(default=None, min_length=1, max_length=100),
    user_id: UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort_by: Literal["created_at", "event_code"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
) -> AuditLogListResponse:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="date_from must not be after date_to")
    rows, total = audit_repository.list_audit_logs(
        audit_db,
        page=page,
        page_size=page_size,
        event_code=event_code,
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return AuditLogListResponse(
        items=[_to_response(log, code) for log, code in rows], page=page, page_size=page_size, total=total
    )


@router.get("/audit-logs/{log_id}", response_model=AuditLogResponse, dependencies=[admin_only])
def get_audit_log(log_id: UUID, audit_db: Annotated[Session, Depends(get_audit_db)]) -> AuditLogResponse:
    row = audit_repository.get_audit_log(audit_db, log_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit log not found")
    return _to_response(*row)
