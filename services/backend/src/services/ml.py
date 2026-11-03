from typing import Protocol
from uuid import UUID


class MLClient(Protocol):
    """Contract for the future analysis/ML integration."""

    def request_analysis(self, analysis_id: UUID) -> None: ...


class MLIntegrationNotConfiguredError(RuntimeError):
    pass


class DeferredMLClient:
    """Intentional non-network placeholder until ML integration is enabled."""

    def request_analysis(self, analysis_id: UUID) -> None:
        raise MLIntegrationNotConfiguredError(
            "ML integration is not configured; analysis jobs are persisted only"
        )
