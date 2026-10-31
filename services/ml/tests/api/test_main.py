from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
import pytest

from api.main import app


@pytest.fixture(autouse=True)
def mock_rabbit_consumer():
    """Automatically mocks RabbitMQConsumer for all tests in this file so lifespan works smoothly."""
    with patch("api.main.RabbitMQConsumer") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.start = AsyncMock()
        mock_instance.close = AsyncMock()
        mock_cls.return_value = mock_instance
        yield mock_cls

@patch("api.main.predictor")
def test_info_endpoint(mock_predictor):
    mock_predictor.has_model.return_value = True

    with TestClient(app) as client:
        response = client.get("/info")
        assert response.status_code == 200
        data = response.json()
        assert "app_name" in data
        assert "model_path" in data

@patch("api.main.predictor")
def test_healthz_endpoint(mock_predictor):
    mock_predictor.has_model.return_value = True

    with TestClient(app) as client:
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {
            "status": "healthy"
        }

@patch("api.main.predictor")
def test_readyz_endpoint_ready(mock_predictor):
    mock_predictor.has_model.return_value = True

    with TestClient(app) as client:
        response = client.get("/readyz")
        assert response.status_code == 200
        assert response.json() == {
            "status": "ready"
        }

@patch("api.main.predictor")
def test_readyz_endpoint_not_ready(mock_predictor):
    mock_predictor.has_model.return_value = False

    with TestClient(app) as client:
        response = client.get("/readyz")
        assert response.status_code == 503
        assert response.json() == {
            "status": "not_ready",
            "reason": "model_not_loaded"
        }

@patch("api.main.predictor")
def test_lifespan_startup_and_shutdown(mock_predictor):
    mock_predictor.load_model.return_value = None
    mock_predictor.has_model.return_value = True

    with TestClient(app):
        mock_predictor.load_model.assert_called_once()
