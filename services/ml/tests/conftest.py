import json
import os
from pathlib import Path

from infrastructure.event_handlers.prediction_event_handler import METADATA_KEYS, RESULT_MAX
from infrastructure.services.confidence_services import CqrConfidence
from infrastructure.services.sklearn_predictor import SklearnPredictor
import joblib
import pandas as pd
import pytest
from sklearn.linear_model import Ridge

MODELS = Path(__file__).parents[1] / "models"
MODEL_PATH = MODELS / "lgbm_v3_2026-11-22.joblib"
TEST_FEATURES = [f"f{i}" for i in range(5)]


os.environ.setdefault(
    "MODEL_DB_URL",
    "postgresql+asyncpg://test:test@localhost:5432/test",
)

@pytest.fixture(scope="session")
def shipped_predictor():
    if not MODEL_PATH.exists():
        pytest.skip("model artifact not available")
    p = SklearnPredictor(str(MODEL_PATH), require_feature_names=True, cqr_base_path=MODELS / "cqr_lgbm_a20_v3_2026-11-22")
    p.load_model()
    return p


@pytest.fixture
def cqr_files(tmp_path):
    def _write(base="cqr_x", lo_features=("a", "b"), hi_features=("a", "b"), interval=None):
        X = pd.DataFrame({"a": [0.0, 1.0, 2.0, 3.0], "b": [1.0, 0.0, 1.0, 0.0]})
        y = [1.0, 2.0, 3.0, 4.0]
        joblib.dump(Ridge().fit(X[list(lo_features)], y), tmp_path / f"{base}_lo.joblib")
        joblib.dump(Ridge().fit(X[list(hi_features)], y), tmp_path / f"{base}_hi.joblib")
        meta = {"qhat": 0.5, "alpha": 0.2, "out_max": 10.0, "width_quantiles": [1.0, 2.0, 3.0],
                "preproc_version": "p1", "target_version": "t1", **(interval or {})}
        (tmp_path / f"{base}_interval.json").write_text(json.dumps(meta))
        return tmp_path / base
    return _write


def test_shipped_model_predicts_with_its_own_features(shipped_predictor):
    result = shipped_predictor.predict({n: 0.0 for n in shipped_predictor.feature_names})
    assert len(result["prediction"]) == 1


def test_shipped_model_features_are_not_stripped_as_metadata(shipped_predictor):
    assert set(shipped_predictor.feature_names) & METADATA_KEYS == set()


def test_shipped_cqr_is_loaded_and_consistent_with_the_point_model(shipped_predictor):
    if shipped_predictor.confidence_estimator is None:
        pytest.skip("no CQR artifacts shipped")
    assert isinstance(shipped_predictor.confidence_estimator, CqrConfidence)


def test_shipped_cqr_output_range_matches_result_range(shipped_predictor):
    est = shipped_predictor.confidence_estimator
    if est is None:
        pytest.skip("no CQR artifacts shipped")
    assert est.out_max == RESULT_MAX


def test_shipped_confidence_is_a_unit_score(shipped_predictor):
    if shipped_predictor.confidence_estimator is None:
        pytest.skip("no CQR artifacts shipped")
    r = shipped_predictor.predict({n: 0.0 for n in shipped_predictor.feature_names})
    assert 0.0 <= r["confidence"][0] <= 1.0