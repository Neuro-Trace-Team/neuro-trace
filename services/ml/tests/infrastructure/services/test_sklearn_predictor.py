from pathlib import Path
from unittest.mock import patch

from infrastructure.event_handlers.prediction_event_handler import METADATA_KEYS
from infrastructure.services.features import FEATURE_NAMES
import numpy as np
import pytest

from infrastructure.services.sklearn_predictor import FeatureValidationError, SklearnPredictor


class DummyModelWithProba:
    def predict(self, X):
        return np.array([1])

    def predict_proba(self, X):
        return np.array([[0.2, 0.8]])

class DummyModelNoProba:
    def predict(self, X):
        return np.array([0])

def test_init():
    predictor = SklearnPredictor(model_path="dummy_path.pkl")
    assert predictor.model_path == "dummy_path.pkl"
    assert predictor.model is None
    assert predictor.has_model() is False

def test_load_model_no_path():
    predictor_none = SklearnPredictor(model_path=None)
    with pytest.raises(ValueError, match="Model path is not configured."):
        predictor_none.load_model()

def test_load_model_empty_path():
    predictor_empty = SklearnPredictor(model_path="")
    with pytest.raises(ValueError, match="Model path is not configured."):
        predictor_empty.load_model()

@patch("os.path.exists", return_value=False)
def test_load_model_file_not_found(mock_exists):
    predictor = SklearnPredictor(model_path="non_existent.pkl")
    with pytest.raises(FileNotFoundError, match="Model file not found at"):
        predictor.load_model()

@patch("os.path.exists", return_value=True)
@patch("joblib.load")
def test_load_model_success(mock_joblib_load, mock_exists):
    dummy_model = DummyModelWithProba()
    mock_joblib_load.return_value = dummy_model

    predictor = SklearnPredictor(model_path="model.pkl")
    predictor.load_model()

    mock_joblib_load.assert_called_once_with("model.pkl")
    assert predictor.model == dummy_model
    assert predictor.has_model() is True

def test_predict_without_loading():
    predictor = SklearnPredictor(model_path="model.pkl")
    with pytest.raises(RuntimeError, match="Model has not been loaded. Call load_model\\(\\) first."):
        predictor.predict([1.0, 2.0])

def test_predict_with_dict_features():
    predictor = SklearnPredictor(feature_names=["feature1", "feature2"])
    predictor.model = DummyModelWithProba()

    result = predictor.predict({"feature1": 1.5, "feature2": 2.5})

    assert result == {"prediction": [1], "probabilities": [[0.2, 0.8]]}
    assert result == {
        "prediction": [1],
        "probabilities": [[0.2, 0.8]]
    }

def test_predict_with_list_1d_features():
    predictor = SklearnPredictor()
    predictor.model = DummyModelWithProba()

    features = [1.0, 2.0, 3.0]
    result = predictor.predict(features)

    assert result == {
        "prediction": [1],
        "probabilities": [[0.2, 0.8]]
    }

def test_predict_with_list_2d_features():
    predictor = SklearnPredictor()
    predictor.model = DummyModelWithProba()

    features = [[1.0, 2.0], [3.0, 4.0]]
    result = predictor.predict(features)

    assert result == {
        "prediction": [1],
        "probabilities": [[0.2, 0.8]]
    }

def test_predict_without_predict_proba():
    predictor = SklearnPredictor()
    predictor.model = DummyModelNoProba()

    features = [1.0, 2.0]
    result = predictor.predict(features)

    assert result == {
        "prediction": [0],
        "probabilities": None
    }

class RecordingModel:
    """Captures the DataFrame it receives."""
    def predict(self, X):
        self.X = X
        return np.array([1])


@pytest.fixture
def predictor():
    p = SklearnPredictor(feature_names=["a", "b", "c"])
    p.model = RecordingModel()
    return p


def test_columns_follow_configured_order(predictor):
    predictor.predict({"c": 3, "a": 1, "b": 2})
    assert list(predictor.model.X.columns) == ["a", "b", "c"]
    assert predictor.model.X.iloc[0].tolist() == [1, 2, 3]


def test_extra_keys_are_ignored(predictor):
    predictor.predict({"a": 1, "b": 2, "c": 3, "event_id": "x"})
    assert list(predictor.model.X.columns) == ["a", "b", "c"]


def test_missing_feature_raises(predictor):
    with pytest.raises(FeatureValidationError, match="Missing 1 features: \\['c'\\]"):
        predictor.predict({"a": 1, "b": 2})


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), "abc", None])
def test_invalid_values_raise(predictor, bad):
    with pytest.raises(FeatureValidationError):
        predictor.predict({"a": 1, "b": 2, "c": bad})


def load_with(model, **kwargs):
    p = SklearnPredictor(model_path="m.pkl", **kwargs)
    with patch("os.path.exists", return_value=True), patch("joblib.load", return_value=model):
        p.load_model()
    return p


class NamedModel(DummyModelWithProba):
    def __init__(self, names=None, n=None):
        if names is not None:
            self.feature_names_in_ = np.array(names, dtype=object)
        if n is not None:
            self.n_features_in_ = n

def test_load_adopts_feature_names_from_model_when_not_configured():
    p = load_with(NamedModel(names=["a", "b"]))
    assert p.feature_names == ["a", "b"]


def test_load_accepts_matching_configured_names():
    p = load_with(NamedModel(names=["a", "b"], n=2), feature_names=["a", "b"])
    assert p.feature_names == ["a", "b"]


@pytest.mark.parametrize("configured", [["b", "a"], ["a", "c"], ["a"]])
def test_load_rejects_names_that_differ_in_order_or_content(configured):
    with pytest.raises(RuntimeError, match="differ from the model"):
        load_with(NamedModel(names=["a", "b"]), feature_names=configured)


def test_load_rejects_feature_count_mismatch_without_names():
    with pytest.raises(RuntimeError, match="Model expects 3 features, config has 2"):
        load_with(NamedModel(n=3), feature_names=["a", "b"])


def test_load_without_any_feature_metadata_is_allowed():
    p = load_with(DummyModelWithProba())
    assert p.has_model() and p.feature_names is None


def test_dict_without_configured_feature_names_raises_validation_error():
    p = SklearnPredictor()
    p.model = DummyModelWithProba()
    with pytest.raises(FeatureValidationError, match="not configured"):
        p.predict({"a": 1})


def test_list_with_wrong_length_raises():
    p = SklearnPredictor(feature_names=["a", "b", "c"])
    p.model = DummyModelWithProba()
    with pytest.raises(FeatureValidationError, match="Expected 3 features, got 2"):
        p.predict([1.0, 2.0])


def test_1d_list_is_reshaped_to_single_row():
    p = SklearnPredictor()
    p.model = RecordingModel()
    p.predict([1.0, 2.0, 3.0])
    assert p.model.X.shape == (1, 3)


def test_numeric_strings_and_bools_are_coerced_to_float():
    p = SklearnPredictor(feature_names=["a", "b"])
    p.model = RecordingModel()
    p.predict({"a": "1.5", "b": True})
    assert p.model.X.iloc[0].tolist() == [1.5, 1.0]


def test_predict_returns_json_friendly_lists():
    p = SklearnPredictor()
    p.model = DummyModelWithProba()
    result = p.predict([1.0, 2.0])
    assert isinstance(result["prediction"], list)
    assert isinstance(result["probabilities"], list)

MODEL_PATH = Path(__file__).parents[3] / "models" / "model.joblib"


@pytest.mark.skipif(not MODEL_PATH.exists(), reason="model artifact not available")
def test_shipped_model_matches_configured_feature_names():
    p = SklearnPredictor(str(MODEL_PATH), FEATURE_NAMES)
    p.load_model()

    result = p.predict({name: 0.0 for name in FEATURE_NAMES})

    assert len(result["prediction"]) == 1
    assert hasattr(p.model, "feature_names_in_"), "artifact doesn't record its feature order"

def test_load_rejects_artifact_without_predict():
    with pytest.raises(RuntimeError, match="not an estimator"):
        load_with({"model": object()})


def test_feature_names_are_unique():
    assert len(FEATURE_NAMES) == len(set(FEATURE_NAMES))


def test_no_feature_is_stripped_as_metadata():
    assert set(FEATURE_NAMES) & METADATA_KEYS == set()