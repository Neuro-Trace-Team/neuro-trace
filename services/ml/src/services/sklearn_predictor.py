import logging
import math
import os
from typing import Any, Dict, List, Sequence

import joblib
import numpy as np
import pandas as pd

from services.ipredictor import IPredictor

class FeatureValidationError(ValueError):
    pass

logger = logging.getLogger(__name__)

class SklearnPredictor(IPredictor):
    def __init__(self, model_path: str | None = None, feature_names: Sequence[str] | None = None):
        self.model_path = model_path
        self.feature_names = list(feature_names) if feature_names else None
        self.model = None

    def load_model(self) -> None:
        """Loads a pre-trained scikit-learn model from the disk."""
        if not self.model_path:
            raise ValueError("Model path is not configured.")

        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Model file not found at {self.model_path}")

        logger.info(f"Loading scikit-learn model from {self.model_path}...")
        self.model = joblib.load(self.model_path)
        logger.info("Scikit-learn model successfully loaded into memory.")

        self._check_model()

    def predict(self, features: List[float] | Dict[str, Any] | List[List[float]]) -> Dict[str, Any]:
        if self.model is None:
            raise RuntimeError("Model has not been loaded. Call load_model() first.")

        if isinstance(features, dict):
            X = self._build_frame(features)
        else:
            X = np.array(features, dtype=float)
            if X.ndim == 1:
                X = X.reshape(1, -1)
            if self.feature_names and X.shape[1] != len(self.feature_names):
                raise FeatureValidationError(
                    f"Expected {len(self.feature_names)} features, got {X.shape[1]}"
                )

        prediction = self.model.predict(X)
        probabilities = (
            self.model.predict_proba(X).tolist()
            if hasattr(self.model, "predict_proba") else None
        )
        return {
            "prediction": prediction.tolist(),
            "probabilities": probabilities
        }
        
    def has_model(self):
        return self.model is not None

    def _check_model(self):
        """Cross-checks config against what the model was trained on."""
        trained = getattr(self.model, "feature_names_in_", None)
        if trained is not None:
            trained = list(trained)
            if self.feature_names is None:
                self.feature_names = trained
            elif trained != self.feature_names:
                raise RuntimeError(
                    "Configured FEATURE_NAMES differ from the model's feature_names_in_ "
                    f"(order or content). Model expects {len(trained)}, "
                    f"config has {len(self.feature_names)}."
                )
        n_expected = getattr(self.model, "n_features_in_", None)
        if n_expected is not None and self.feature_names is not None \
                and n_expected != len(self.feature_names):
            raise RuntimeError(
                f"Model expects {n_expected} features, config has {len(self.feature_names)}."
            )
        logger.info("Model loaded with %d expected features.", len(self.feature_names or []))

    def _build_frame(self, features: Dict[str, Any]) -> pd.DataFrame:
        names = self.feature_names
        missing = [n for n in names if n not in features]
        if missing:
            raise FeatureValidationError(f"Missing {len(missing)} features: {missing}")

        extra = set(features) - set(names)
        if extra:
            logger.debug("Ignoring unexpected keys: %s", sorted(extra))

        row = {n: features[n] for n in names}

        bad = []
        for k, v in row.items():
            try:
                f = float(v)
            except (TypeError, ValueError):
                bad.append(k)
                continue
            if math.isnan(f) or math.isinf(f):
                bad.append(k)
            row[k] = f
        if bad:
            raise FeatureValidationError(f"Non-numeric/NaN/inf values for: {bad}")

        return pd.DataFrame([row], columns=names)