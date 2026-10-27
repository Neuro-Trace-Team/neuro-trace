from unittest.mock import patch

import numpy as np
import pytest

from services.ml.src.models.sklearn_predictor import SklearnPredictor


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
    predictor = SklearnPredictor()
    predictor.model = DummyModelWithProba()

    features = {
        "feature1": 1.5, 
        "feature2": 2.5
    }
    result = predictor.predict(features)

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