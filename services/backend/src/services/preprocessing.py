from typing import Protocol

from src.schemas.internal import PreprocessingExaminationResponse


class PreprocessingClient(Protocol):
    """Future boundary for submitting a preprocessing request.

    This stage deliberately defines no HTTP implementation and no caller. The
    examination upload workflow remains independent from preprocessing.
    """

    def submit(self, payload: PreprocessingExaminationResponse) -> None:
        """Submit an already prepared examination contract in a future integration."""


class PreprocessingIntegrationNotConfiguredError(RuntimeError):
    pass


class DeferredPreprocessingClient:
    """Explicit placeholder preventing accidental real preprocessing requests."""

    def submit(self, payload: PreprocessingExaminationResponse) -> None:
        del payload
        raise PreprocessingIntegrationNotConfiguredError("Preprocessing integration is not configured")
