import os
from pathlib import Path

from infrastructure.event_handlers.prediction_event_handler import METADATA_KEYS
from infrastructure.services.sklearn_predictor import SklearnPredictor
import pytest

MODEL_PATH = Path(__file__).parents[1] / "models" / "model.joblib"
TEST_FEATURES = [f"f{i}" for i in range(5)]


os.environ.setdefault(
    "MODEL_DB_URL",
    "postgresql+asyncpg://test:test@localhost:5432/test",
)

@pytest.fixture(scope="session")
def shipped_predictor():
    if not MODEL_PATH.exists():
        pytest.skip("model artifact not available")
    p = SklearnPredictor(str(MODEL_PATH), require_feature_names=True)
    p.load_model()
    return p


def test_shipped_model_predicts_with_its_own_features(shipped_predictor):
    result = shipped_predictor.predict({n: 0.0 for n in shipped_predictor.feature_names})
    assert len(result["prediction"]) == 1

def test_shipped_model_features_are_not_stripped_as_metadata(shipped_predictor):
    assert set(shipped_predictor.feature_names) & METADATA_KEYS == set()