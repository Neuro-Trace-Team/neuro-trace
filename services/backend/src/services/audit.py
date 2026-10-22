import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.models.audit import AuditLog, AuditLogType

logger = logging.getLogger(__name__)


def log_event(
    session: Session,
    *,
    event_code: str,
    user_id: UUID | None = None,
    resource_type: str | None = None,
    resource_id: UUID | None = None,
    metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
    """Append an audit event without allowing audit outages to break business flow."""
    try:
        event_type = session.scalar(select(AuditLogType).where(AuditLogType.code == event_code))
        if event_type is None:
            logger.error("Unknown audit event code: %s", event_code)
            return
        session.add(
            AuditLog(
                user_id=user_id,
                type_id=event_type.id,
                resource_type=resource_type,
                resource_id=resource_id,
                metadata_json=metadata,
                ip_address=ip_address,
            )
        )
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        logger.exception("Unable to persist audit event %s", event_code)
