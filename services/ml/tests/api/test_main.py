import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.main import app, healthz, info, lifespan, readyz
from core.config import settings


def make_engine(execute_side_effect=None):
    """Fake AsyncEngine: `async with engine.connect() as conn: await conn.execute(...)`."""
    conn = MagicMock()
    conn.execute = AsyncMock(side_effect=execute_side_effect)

    engine = MagicMock()
    engine.connect.return_value.__aenter__.return_value = conn
    engine.connect.return_value.__aexit__.return_value = False  # don't swallow exceptions
    return engine, conn


def make_request(engine):
    request = MagicMock()
    request.app.state.engine = engine
    return request


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
    engine, conn = make_engine()

    assert await readyz(make_request(engine)) == {"status": "ready"}
    conn.execute.assert_awaited_once()


@pytest.mark.asyncio
@patch("api.main.predictor")
async def test_readyz_endpoint_not_ready_model_not_loaded(mock_predictor):
    mock_predictor.has_model.return_value = False
    engine, _ = make_engine()

    response = await readyz(make_request(engine))

    assert response.status_code == 503
    assert json.loads(response.body) == {
        "status": "not_ready",
        "reason": "model_not_loaded",
    }
    engine.connect.assert_not_called()  # no point hitting the DB if the model is missing


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [ConnectionError("db down"), asyncio.TimeoutError()])
@patch("api.main.predictor")
async def test_readyz_endpoint_not_ready_database_unavailable(mock_predictor, error):
    mock_predictor.has_model.return_value = True
    engine, _ = make_engine(execute_side_effect=error)

    response = await readyz(make_request(engine))

    assert response.status_code == 503
    assert json.loads(response.body) == {
        "status": "not_ready",
        "reason": "database_unavailable",
    }


@pytest.mark.asyncio
@patch("api.main.PredictionEventHandler")
@patch("api.main.RabbitMQPublisher")
@patch("api.main.RabbitMQConsumer")
@patch("api.main.create_session_factory")
@patch("api.main.create_engine")
@patch("api.main.predictor")
async def test_lifespan_startup_and_shutdown(
    mock_predictor,
    mock_create_engine,
    mock_create_session_factory,
    mock_consumer_class,
    mock_publisher_class,
    mock_handler_class,
):
    mock_predictor.load_model.return_value = None

    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()
    mock_create_engine.return_value = mock_engine
    mock_session_factory = MagicMock()
    mock_create_session_factory.return_value = mock_session_factory

    mock_consumer = MagicMock()
    mock_consumer.start = AsyncMock()
    mock_consumer.close = AsyncMock()
    mock_consumer_class.return_value = mock_consumer

    mock_publisher = MagicMock()
    mock_publisher.connect = AsyncMock()
    mock_publisher.close = AsyncMock()
    mock_publisher_class.return_value = mock_publisher

    async with lifespan(app):
        mock_predictor.load_model.assert_called_once()
        mock_create_engine.assert_called_once_with(settings.database_url)
        mock_create_session_factory.assert_called_once_with(mock_engine)
        mock_publisher.connect.assert_awaited_once()
        mock_handler_class.assert_called_once_with(
            predictor=mock_predictor,
            session_factory=mock_session_factory,
            event_publisher=mock_publisher,
        )
        mock_consumer_class.assert_called_once()
        assert app.state.engine is mock_engine
        assert app.state.session_factory is mock_session_factory

    mock_consumer.close.assert_awaited_once()
    mock_publisher.close.assert_awaited_once()
    mock_engine.dispose.assert_awaited_once()