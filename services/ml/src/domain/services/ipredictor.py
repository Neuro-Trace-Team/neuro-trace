from typing import Any, Dict, List, Protocol, Union


class FeatureValidationError(ValueError):
    def __init__(self, message: str, *, missing=(), invalid=()):
        super().__init__(message)
        self.missing, self.invalid = list(missing), list(invalid)
        

class IPredictor(Protocol):
    def load_model(self) -> None:
        """Loads the model artifact into memory."""
        ...

    def predict(self, features: Union[List[float], Dict[str, Any]]) -> Dict[str, Any]:
        """Performs inference and returns prediction results."""
        ...

    def has_model(self) -> bool:
        """Checks whether the model has been loaded."""
        ...

    def model_info(self) -> dict[str, Any]:
        """Returns dictionary of the model metadata."""
        ...