from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np


@dataclass(frozen=True)
class Confidence:
    values: list[float]
    kind: str
    interval: dict[str, list[float]] | None = None


class IConfidenceEstimator(Protocol):
    def estimate(self, X: Any, prediction: np.ndarray, probabilities: np.ndarray | None) -> Confidence:
        ...
    def info(self) -> dict[str, Any]:
        ...