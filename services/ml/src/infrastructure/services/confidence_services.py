from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any, Self, Sequence

from domain.services.iconfidence_estimator import Confidence, IConfidenceEstimator
import joblib
import numpy as np

logger = logging.getLogger(__name__)

VERSION_KEYS = ("preproc_version", "target_version")


class ProbabilityConfidence:
    """For classifiers: probability of the predicted class."""
    def estimate(self, X, prediction, probabilities):
        if probabilities is None:
            raise ValueError("Model produced no probabilities")
        return Confidence(np.max(probabilities, axis=1).tolist(), "max_probability")

    def info(self) -> dict[str, Any]:
        return {"kind": "max_probability"}


def _load_joblib(path: Path):
    with open(path, "rb") as f:
        if f.read(24).startswith(b"version https://git-lfs"):
            raise RuntimeError(f"{path} is a Git LFS pointer, not the model. Run `git lfs pull`.")
    return joblib.load(path)


class CqrConfidence:
    """Conformalized quantile regression: confidence from the width of the prediction interval."""
    def __init__(self, lo, hi, *, qhat: float, alpha: float, out_max: float, width_quantiles: Sequence[float] | None = None):
        self.lo = lo
        self.hi = hi
        self.qhat = qhat
        self.alpha = alpha
        self.out_max = out_max

        wq = np.asarray(width_quantiles if width_quantiles is not None else [], float)
        self.width_quantiles = wq if wq.size else None
        self.kind = "interval_width_percentile" if self.width_quantiles is not None else "interval_width_scale"

    @classmethod
    def load(cls, base_path: str | Path, *, feature_names: Sequence[str] | None, point_meta: dict[str, Any]) -> Self:
        """base_path is the shared prefix, without _lo/_hi/_interval."""
        base = Path(str(base_path))
        part = lambda suffix: base.parent / f"{base.name}_{suffix}"

        lo = _load_joblib(part("lo.joblib"))
        hi = _load_joblib(part("hi.joblib"))

        meta_path = part("interval.json")
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            qhat, alpha, out_max = (float(meta[k]) for k in ("qhat", "alpha", "out_max"))
            wq = meta.get("width_quantiles") or None
            wq_array = None if wq is None else np.asarray(wq, float)
        except (KeyError, TypeError, ValueError) as e:
            raise RuntimeError(f"{meta_path.name} is unreadable or lacks numeric qhat/alpha/out_max") from e
        
        if not (math.isfinite(qhat) and qhat >= 0):
            raise RuntimeError(f"{meta_path.name}: qhat must be a finite number >= 0")
        if not 0 < alpha < 1:
            raise RuntimeError(f"{meta_path.name}: alpha must be between 0 and 1")
        if not (math.isfinite(out_max) and out_max > 0):
            raise RuntimeError(f"{meta_path.name}: out_max must be a finite number > 0")
        if wq_array is not None and (
            wq_array.ndim != 1 or not np.all(np.isfinite(wq_array)) or np.any(np.diff(wq_array) < 0)
        ):
            raise RuntimeError(f"{meta_path.name}: width_quantiles must be a sorted list of numbers")

        names = [getattr(m, "feature_names_in_", None) for m in (lo, hi)]
        if any(n is None for n in names):
            raise RuntimeError("CQR models do not record feature_names_in; refit them on a DataFrame")
        lo_names, hi_names = ([str(n) for n in ns] for ns in names)
        expected = list(feature_names) if feature_names else lo_names
        if not lo_names == hi_names == expected:
            raise RuntimeError("point model and CQR models were trained on different feature lists"
                " - retrain them together")

        for key in VERSION_KEYS:
            if (key in point_meta 
                and key in meta 
                and point_meta[key] != meta[key]
            ):
                raise RuntimeError(f"{key} differs between point model ({point_meta[key]}) "
                                   f"and CQR ({meta[key]}) - retrain them together")
                
        return cls(lo, hi, qhat=qhat, alpha=alpha, out_max=out_max, width_quantiles=wq)

    def estimate(self, X, prediction, probabilities=None) -> Confidence:
        a = self.lo.predict(X)
        b = self.hi.predict(X)
        low = np.clip(np.minimum(a, b) - self.qhat, 0.0, self.out_max)
        high = np.clip(np.maximum(a, b) + self.qhat, 0.0, self.out_max)

        return Confidence(self._score(high - low).tolist(), self.kind, {"lower": low.tolist(), "upper": high.tolist()})

    def _score(self, width: np.ndarray) -> np.ndarray:
        """Percentile kind: 1 = narrower than nearly all validation intervals. A relative score."""
        if self.width_quantiles is None:
            return np.clip(1.0 - width / self.out_max, 0.0, 1.0)
        n = len(self.width_quantiles)
        left = np.searchsorted(self.width_quantiles, width, "left")
        right = np.searchsorted(self.width_quantiles, width, "right")
        return np.clip(1.0 - (left + right) / (2 * n), 0.0, 1.0)

    def info(self) -> dict[str, Any]:
        return {
            "kind": self.kind, 
            "method": "cqr", 
            "alpha": self.alpha,
            "nominal_coverage": round(1 - self.alpha, 4), 
            "qhat": self.qhat, 
            "out_max": self.out_max,
            "calibration_widths": 0 if self.width_quantiles is None else len(self.width_quantiles),
        }


def build_confidence_estimator(model, *, feature_names, cqr_base_path, point_meta) -> IConfidenceEstimator | None:
    """An explicitly configured CQR wins, then a classifier's probabilities, otherwise no confidence."""
    if cqr_base_path:
        return CqrConfidence.load(cqr_base_path, feature_names=feature_names, point_meta=point_meta)
    if hasattr(model, "predict_proba"):
        return ProbabilityConfidence()
    return None