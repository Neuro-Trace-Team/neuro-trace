import logging
import os
from typing import Any, Dict, List

import joblib
import numpy as np
import pandas as pd

from models.ipredictor import IPredictor


logger = logging.getLogger(__name__)

class SklearnPredictor(IPredictor):
    def __init__(self, model_path: str | None = None):
        self.model_path = model_path
        self.model = None

    def load_model(self) -> None:
        """Loads a pre-trained scikit-learn model from disk."""
        if not self.model_path:
            raise ValueError("Model path is not configured.")

        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Model file not found at {self.model_path}")

        logger.info(f"Loading scikit-learn model from {self.model_path}...")
        self.model = joblib.load(self.model_path)
        logger.info("Scikit-learn model successfully loaded into memory.")

    def predict(self, features: List[float] | Dict[str, Any] | List[List[float]]) -> Dict[str, Any]:
        if self.model is None:
            raise RuntimeError("Model has not been loaded. Call load_model() first.")

        X = None

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
        