from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.api.deps import require_roles
from src.core.roles import Role
from src.db.sessions import get_audit_db
from src.models.audit import AuditLog
from src.repositories import audit as audit_repository
from src.schemas.activity import AppActivityResponse
from src.schemas.audit import AuditLogListResponse, AuditLogResponse
from src.schemas.storage import StorageUnavailableResponse, StorageUsageResponse
from src.services.storage import ObjectStorageError, RustFSStorage

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


@router.get("/app-activity", response_model=AppActivityResponse, dependencies=[admin_only])
def get_app_activity(
    audit_db: Annotated[Session, Depends(get_audit_db)],
) -> AppActivityResponse:
    """Return the current administrator dashboard metrics for the last 24 hours."""
    period_started_at = datetime.now(UTC) - timedelta(hours=24)
    active_users, failed_logins, uploaded_examinations = audit_repository.app_activity_counts(
        audit_db, since=period_started_at
    )
    storage = RustFSStorage()
    try:
        usage = storage.usage()
        storage_response = StorageUsageResponse(
            bucket=usage.bucket,
            bucket_exists=usage.bucket_exists,
            object_count=usage.object_count,
            used_bytes=usage.used_bytes,
        )
    except ObjectStorageError:
        storage_response = StorageUnavailableResponse(bucket=storage.bucket)
    return AppActivityResponse(
        period_started_at=period_started_at,
        active_users_last_24h=active_users,
        failed_login_attempts_last_24h=failed_logins,
        examinations_uploaded_last_24h=uploaded_examinations,
        storage=storage_response,
    )


@router.get("/audit-logs", response_model=AuditLogListResponse, dependencies=[admin_only])
def list_audit_logs(
    audit_db: Annotated[Session, Depends(get_audit_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    query: str | None = Query(default=None, min_length=1, max_length=255),
    id: UUID | None = None,
    event_code: str | None = Query(default=None, min_length=1, max_length=100),
    user_id: UUID | None = None,
    type_id: int | None = Query(default=None, ge=1),
    created_at_from: datetime | None = None,
    created_at_to: datetime | None = None,
    ip_address: str | None = Query(default=None, min_length=1, max_length=45),
    request_id: UUID | None = None,
    resource_type: str | None = Query(default=None, min_length=1, max_length=50),
    resource_id: UUID | None = None,
    sort_by: Literal["id", "user_id", "type_id", "created_at", "ip_address", "request_id", "resource_type", "resource_id", "event_code"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
) -> AuditLogListResponse:
    if created_at_from is not None and created_at_to is not None and created_at_from > created_at_to:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="created_at_from must not be after created_at_to")
    rows, total = audit_repository.list_audit_logs(
        audit_db,
        page=page,
        page_size=page_size,
        query=query,
        log_id=id,
        event_code=event_code,
        user_id=user_id,
        type_id=type_id,
        created_at_from=created_at_from,
        created_at_to=created_at_to,
        ip_address=ip_address,
        request_id=request_id,
        resource_type=resource_type,
        resource_id=resource_id,
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
