import logging
from typing import Any, Dict, List

import numpy as np
import pandas as pd
from services.ipredictor import IPredictor

logger = logging.getLogger(__name__)

class MockPredictor(IPredictor):
    def __init__(self, model_path: str | None = None):
        self.model_path = model_path
        self.model = None

    def load_model(self) -> None:
        logger.info(f"Mocking scikit-learn model loading...")
        class DummyModel:
            def predict(self, X):
                return np.ones(len(X))

            def predict_proba(self, X):
                return np.array([[0.1, 0.9] for _ in range(len(X))])

        self.model = DummyModel()
        logger.info("Mock Scikit-learn model successfully loaded into memory.")

    def predict(self, features: List[float] | Dict[str, Any] | List[List[float]]) -> Dict[str, Any]:
        if self.model is None:
            raise RuntimeError("Model has not been loaded. Call load_model() first.")

        if isinstance(features, dict):
            X = pd.DataFrame([features])
        else:
            X = np.array(features)
            if X.ndim == 1:
                X = X.reshape(1, -1)

        prediction = self.model.predict(X)
        
        probabilities = None
        if hasattr(self.model, "predict_proba"):
            probabilities = self.model.predict_proba(X).tolist()

        return {
            "prediction": prediction.tolist(),
            "probabilities": probabilities
        }

    def has_model(self):
        return self.model is not None