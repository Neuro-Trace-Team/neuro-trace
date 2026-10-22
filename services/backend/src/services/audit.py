import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.audit import AuditLog, AuditLogType

logger = logging.getLogger(__name__)

_REDACTED = "[REDACTED]"
_OMITTED = "[OMITTED]"

# Metadata must remain useful for investigating an event, but it is never a
# place for credentials, tokens, source EEG data, or direct patient details.
_SECRET_KEY_PARTS = frozenset(
    {"password", "passwd", "secret", "token", "jwt", "authorization", "credential"}
)
_EEG_KEY_PARTS = frozenset({"eeg", "signal", "waveform", "recording", "raw_data", "file_content"})
_PATIENT_IDENTIFIER_KEY_PARTS = frozenset(
    {"pesel", "patient_name", "first_name", "last_name", "address", "phone", "birth_date", "email"}
)


def _safe_metadata(value: Any, *, key: str | None = None) -> Any:
    """Return JSON-safe diagnostic metadata without sensitive content."""
    normalized_key = (key or "").lower().replace("-", "_")
    if any(part in normalized_key for part in _SECRET_KEY_PARTS):
        return _REDACTED
    if any(part in normalized_key for part in _EEG_KEY_PARTS):
        return _OMITTED
    if any(part in normalized_key for part in _PATIENT_IDENTIFIER_KEY_PARTS):
        return _OMITTED
    if isinstance(value, dict):
        return {str(item_key): _safe_metadata(item_value, key=str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_metadata(item, key=key) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def log(
    session: Session,
    *,
    event_code: str,
    user_id: UUID | None = None,
    resource_type: str | None = None,
    resource_id: UUID | None = None,
    metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
    """Best-effort central audit writer; an audit failure never breaks the caller."""
    try:
        # Resolve the database type on every write.  The database, rather than
        # application code, remains the source of truth for permitted events.
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
                metadata_json=_safe_metadata(metadata) if metadata is not None else None,
                ip_address=ip_address,
            )
        )
        session.commit()
    except Exception:
        try:
            session.rollback()
        except Exception:
            logger.exception("Unable to roll back audit write for event %s", event_code)
        logger.exception("Unable to persist audit event %s", event_code)


# Compatibility alias for code written before the audit service was centralized.
log_event = log
