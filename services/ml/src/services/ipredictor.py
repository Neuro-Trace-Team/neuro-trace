from typing import Any, Dict, List, Protocol, Union


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