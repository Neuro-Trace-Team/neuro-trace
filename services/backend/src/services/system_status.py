"""Read-only, bounded probes used by the administrator system-status endpoint."""

from collections.abc import Iterable
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from src.config import get_settings
from src.db import sessions
from src.messaging.ml_completion_consumer import completion_consumer_status
from src.schemas.system_status import (
    BackendStatus,
    ComponentStatus,
    ConnectionStatus,
    ExternalConnectionStatus,
    ExternalServiceStatus,
)
from src.services.storage import ObjectStorageError, RustFSStorage


def backend_status() -> BackendStatus:
    """Diagnose connections that are owned directly by the backend process."""
    try:
        RustFSStorage().check_available()
        rustfs = ConnectionStatus(status="up")
    except ObjectStorageError:
        rustfs = ConnectionStatus(status="down")
    except Exception:
        rustfs = ConnectionStatus(status="unknown")

    consumer = ConnectionStatus(status=completion_consumer_status())
    return BackendStatus(
        status="up",
        connections={"rustfs": rustfs, "rabbitmq_consumer": consumer},
    )


def database_statuses() -> dict[str, ComponentStatus]:
    databases: Iterable[tuple[str, Engine]] = (
        ("auth_db", sessions.auth_engine),
        ("medical_db", sessions.medical_engine),
        ("audit_db", sessions.audit_engine),
    )
    statuses: dict[str, ComponentStatus] = {}
    for name, engine in databases:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            statuses[name] = ComponentStatus(status="up")
        except SQLAlchemyError:
            statuses[name] = ComponentStatus(status="down")
    return statuses


def _connections(value: Any) -> dict[str, ExternalConnectionStatus] | None:
    if not isinstance(value, dict) or not isinstance(value.get("connections"), dict):
        return None
    connections: dict[str, ExternalConnectionStatus] = {}
    for name, item in value["connections"].items():
        if not isinstance(name, str) or not isinstance(item, dict) or not isinstance(item.get("status"), str):
            return None
        latency = item.get("latency_ms")
        if latency is not None and (not isinstance(latency, (int, float)) or isinstance(latency, bool) or latency < 0):
            return None
        error = item.get("error")
        if error is not None and not isinstance(error, str):
            return None
        connections[name] = ExternalConnectionStatus(
            status=item["status"],
            latency_ms=latency,
            error=error,
        )
    return connections


def external_service_status(url: str) -> ExternalServiceStatus:
    """Forward an existing diagnostics contract without exposing transport details."""
    try:
        response = httpx.get(url, timeout=get_settings().service_timeout_seconds)
        value = response.json()
    except (httpx.HTTPError, ValueError):
        return ExternalServiceStatus(status="down")

    connections = _connections(value)
    source_status = value.get("status") if isinstance(value, dict) else None
    if connections is None or source_status not in {"ok", "degraded"}:
        return ExternalServiceStatus(status="down")
    return ExternalServiceStatus(status=source_status, connections=connections)


def system_status() -> tuple[BackendStatus, dict[str, ComponentStatus], ExternalServiceStatus, ExternalServiceStatus]:
    settings = get_settings()
    backend = backend_status()
    databases = database_statuses()
    preprocessing = external_service_status(
        f"{settings.preprocessing_url.rstrip('/')}/health/connections"
    )
    ml = external_service_status(f"{settings.ml_url.rstrip('/')}/connections")
    return backend, databases, preprocessing, ml
