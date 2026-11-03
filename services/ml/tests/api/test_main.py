import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.main import app, healthz, info, lifespan, readyz


@pytest.mark.asyncio
@patch("api.main.predictor")
async def test_info_endpoint(mock_predictor):
    response = await info()

    assert response["app_name"]
    assert "model_path" in response
    mock_predictor.assert_not_called()


@pytest.mark.asyncio
async def test_healthz_endpoint():
    assert await healthz() == {"status": "healthy"}


@pytest.mark.asyncio
@patch("api.main.predictor")
async def test_readyz_endpoint_ready(mock_predictor):
    mock_predictor.has_model.return_value = True

    assert await readyz() == {"status": "ready"}


@pytest.mark.asyncio
@patch("api.main.predictor")
async def test_readyz_endpoint_not_ready(mock_predictor):
    mock_predictor.has_model.return_value = False

    response = await readyz()

    assert response.status_code == 503
    assert json.loads(response.body) == {
        "status": "not_ready",
        "reason": "model_not_loaded",
    }


@pytest.mark.asyncio
@patch("api.main.predictor")
@patch("api.main.RabbitMQConsumer")
async def test_lifespan_startup_and_shutdown(mock_consumer_class, mock_predictor):
    mock_consumer = MagicMock()
    mock_consumer.start = AsyncMock()
    mock_consumer.close = AsyncMock()
    mock_consumer_class.return_value = mock_consumer
    mock_predictor.load_model.return_value = None

    async with lifespan(app):
        mock_predictor.load_model.assert_called_once()
        mock_consumer_class.assert_called_once()

    mock_consumer.close.assert_awaited_once()
