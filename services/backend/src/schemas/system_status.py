from typing import Literal

from pydantic import BaseModel, Field


class ConnectionStatus(BaseModel):
    status: Literal["up", "down", "unknown"]


class ComponentStatus(ConnectionStatus):
    pass


class BackendStatus(ComponentStatus):
    connections: dict[str, ConnectionStatus] = Field(default_factory=dict)


class ExternalConnectionStatus(BaseModel):
    """A sanitized connection result reported by preprocessing or ML."""

    status: str
    latency_ms: float | None = Field(default=None, ge=0)
    error: str | None = None


class ExternalServiceStatus(BaseModel):
    status: Literal["ok", "degraded", "down"]
    connections: dict[str, ExternalConnectionStatus] = Field(default_factory=dict)


class SystemStatusResponse(BaseModel):
    """Administrator-facing aggregate of the deployed service topology."""

    status: Literal["ok", "degraded"]
    backend: BackendStatus
    databases: dict[str, ComponentStatus]
    preprocessing: ExternalServiceStatus
    ml: ExternalServiceStatus
