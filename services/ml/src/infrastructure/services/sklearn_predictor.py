import hashlib
import json
import logging
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Sequence

import joblib
import numpy as np
import pandas as pd

from domain.services.ipredictor import FeatureValidationError, IPredictor
import sklearn

logger = logging.getLogger(__name__)

class SklearnPredictor(IPredictor):
    def __init__(self, model_path: str | None = None, feature_names: Sequence[str] | None = None, require_feature_names: bool = False):
        self.model_path = model_path
        self.feature_names = list(feature_names) if feature_names else None
        self.model = None
        self._artifact_sha256: str | None = None
        self._metadata: dict[str, Any] = {}
        self.require_feature_names = require_feature_names

    def load_model(self) -> None:
        """Loads a pre-trained scikit-learn model from the disk."""
        if not self.model_path:
            raise ValueError("Model path is not configured.")

        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Model file not found at {self.model_path}")

        with open(self.model_path, "rb") as f:
            if f.read(24).startswith(b"version https://git-lfs"):
                raise RuntimeError(
                    f"{self.model_path} is a Git LFS pointer, not the model. Run `git lfs pull`."
                )

        self._artifact_sha256 = self._read_digest()

        
        logger.info("Loading scikit-learn model from %s...", self.model_path)
        self.model = joblib.load(self.model_path)
        self._check_model()
        logger.info("Scikit-learn model successfully loaded into memory.")

        logger.info("Reading model metadata...")
        
        self._metadata = self._read_metadata()

    def predict(self, features: List[float] | Dict[str, Any] | List[List[float]]) -> Dict[str, Any]:
        if self.model is None:
            raise RuntimeError("Model has not been loaded. Call load_model() first.")

        if isinstance(features, dict):
            if not self.feature_names:
                raise RuntimeError("feature_names are not configured; cannot build a frame from a dict")
            X = self._build_frame(features)
        else:
            X = np.array(features, dtype=float)
            if X.ndim == 1:
                X = X.reshape(1, -1)
            if self.feature_names and X.shape[1] != len(self.feature_names):
                raise FeatureValidationError(
                    "Expected %d features, got %d" % (len(self.feature_names), X.shape[1])
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
        
    def has_model(self) -> bool:
        return self.model is not None

    def _check_model(self):
        """Cross-checks config against what the model was trained on."""
        if not hasattr(self.model, "predict"):
            raise RuntimeError(
                f"Loaded artifact is {type(self.model).__name__}, not an estimator with predict()"
            )

        trained = getattr(self.model, "feature_names_in_", None)
        if trained is not None:
            trained = [str(n) for n in trained]
            if self.feature_names is None:
                self.feature_names = trained
            elif trained != self.feature_names:
                raise RuntimeError(
                    "Configured feature names differ from the model's feature_names_in_ "
                    "(order or content). Model expects %d, "
                    "config has %d." % (len(trained), len(self.feature_names))
                )
        n_expected = getattr(self.model, "n_features_in_", None)
        if n_expected is not None and self.feature_names is not None \
                and n_expected != len(self.feature_names):
            raise RuntimeError(
                "Model expects %d features, config has %d." % (n_expected, len(self.feature_names))
            )

        if self.require_feature_names and not self.feature_names:
            raise RuntimeError(
                "Model does not record feature_names_in_; refit it on a DataFrame."
            )
        logger.info("Model loaded with %d expected features.", len(self.feature_names or []))

    def _build_frame(self, features: Dict[str, Any]) -> pd.DataFrame:
        names = self.feature_names
        missing = [n for n in names if n not in features]
        if missing:
            raise FeatureValidationError(f"Missing {len(missing)} features: {missing}", missing=missing)

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
            raise FeatureValidationError(f"Non-numeric/NaN/inf values for: {bad}", invalid=bad)

        return pd.DataFrame([row], columns=names)

    def _read_digest(self) -> str:
        """One pass: reject a Git LFS pointer, and hash the artifact."""
        sha = hashlib.sha256()
        with open(self.model_path, "rb") as f:
            head = f.read(24)
            if head.startswith(b"version https://git-lfs"):
                raise RuntimeError(f"{self.model_path} is a Git LFS pointer, not the model. Run `git lfs pull`.")
            sha.update(head)
            for chunk in iter(lambda: f.read(1 << 20), b""):
                sha.update(chunk)
        return sha.hexdigest()

    def _read_metadata(self) -> dict[str, Any]:
        path = Path(self.model_path).with_suffix(".meta.json")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError):
            logger.warning("Ignoring unreadable model metadata at %s", path, exc_info=True)
            return {}
        return data if isinstance(data, dict) else {}

    def model_info(self) -> dict[str, Any]:
        if self.model is None:
            return {"loaded": False}
        return {
            "loaded": True,
            "estimator": type(self.model).__name__,
            "n_features": len(self.feature_names) if self.feature_names
                        else getattr(self.model, "n_features_in_", None),
            "has_probabilities": hasattr(self.model, "predict_proba"),
            "sklearn_version": sklearn.__version__,
            "artifact_sha256": self._artifact_sha256,
            "metadata": self._metadata,
        }