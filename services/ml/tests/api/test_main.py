import asyncio
import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

from infrastructure.services.features import FEATURE_NAMES
import pytest

from api.main import _log_consumer_exit, app, healthz, info, lifespan, readyz
from core.config import settings
from infrastructure.repositories.sql_alchemy_analysis_repository import (
    SqlAlchemyAnalysisRepository,
)


def make_engine(execute_side_effect=None):
    """Fake AsyncEngine: `async with engine.connect() as conn: await conn.execute(...)`."""
    conn = MagicMock()
    conn.execute = AsyncMock(side_effect=execute_side_effect)

    engine = MagicMock()
    engine.connect.return_value.__aenter__.return_value = conn
    engine.connect.return_value.__aexit__.return_value = False  # don't swallow exceptions
    return engine, conn


def make_request(engine, consumer_running=True):
    request = MagicMock()
    request.app.state.engine = engine
    request.app.state.consumer_task.done.return_value = not consumer_running
    return request


@pytest.mark.asyncio
async def test_info_endpoint():
    response = await info()

    assert response["app_name"]


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
    engine.connect.assert_not_called()


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

        mock_publisher_class.assert_called_once_with(
            settings.queue_url, settings.completed_queue_name
        )
        mock_publisher.connect.assert_awaited_once()

        mock_handler_class.assert_called_once_with(
            predictor=mock_predictor,
            session_factory=mock_session_factory,
            event_publisher=mock_publisher,
            repository_factory=SqlAlchemyAnalysisRepository,
        )

        mock_consumer_class.assert_called_once_with(
            queue_url=settings.queue_url,
            queue_name=settings.pending_analysis_queue_name,
            handlers={"predict_event": mock_handler_class.return_value},
        )

        await asyncio.sleep(0)
        mock_consumer.start.assert_awaited_once()

        assert app.state.engine is mock_engine
        assert app.state.session_factory is mock_session_factory

    mock_consumer.close.assert_awaited_once()
    mock_publisher.close.assert_awaited_once()
    mock_engine.dispose.assert_awaited_once()


@pytest.mark.asyncio
@patch("api.main.RabbitMQPublisher")
@patch("api.main.create_engine")
@patch("api.main.predictor")
async def test_lifespan_aborts_startup_when_model_fails_to_load(
    mock_predictor, mock_create_engine, mock_publisher_class
):
    mock_predictor.load_model.side_effect = RuntimeError("bad model")

    with pytest.raises(RuntimeError, match="bad model"):
        async with lifespan(app):
            pytest.fail("the app must not start without a model")

    mock_create_engine.assert_not_called()
    mock_publisher_class.assert_not_called()


@pytest.mark.asyncio
@patch("api.main.PredictionEventHandler")
@patch("api.main.RabbitMQPublisher")
@patch("api.main.RabbitMQConsumer")
@patch("api.main.create_session_factory")
@patch("api.main.create_engine")
@patch("api.main.predictor")
async def test_lifespan_cancels_running_consumer_on_shutdown(
    mock_predictor,
    mock_create_engine,
    mock_create_session_factory,
    mock_consumer_class,
    mock_publisher_class,
    mock_handler_class,
):
    """A real consumer never returns on its own: shutdown must cancel it, then clean up."""
    cancelled = asyncio.Event()

    async def run_forever():
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    mock_create_engine.return_value.dispose = AsyncMock()
    mock_consumer = MagicMock()
    mock_consumer.start = run_forever
    mock_consumer.close = AsyncMock()
    mock_consumer_class.return_value = mock_consumer
    mock_publisher = MagicMock()
    mock_publisher.connect = AsyncMock()
    mock_publisher.close = AsyncMock()
    mock_publisher_class.return_value = mock_publisher

    async with lifespan(app):
        await asyncio.sleep(0)

    assert cancelled.is_set()
    mock_consumer.close.assert_awaited_once()
    mock_publisher.close.assert_awaited_once()
    mock_create_engine.return_value.dispose.assert_awaited_once()


def test_module_predictor_is_configured_with_feature_names():
    from api.main import predictor
    assert predictor.feature_names == FEATURE_NAMES          # bug 1


@pytest.mark.asyncio
@patch("api.main.predictor")
async def test_readyz_not_ready_when_consumer_task_is_dead(mock_predictor):
    mock_predictor.has_model.return_value = True
    engine, _ = make_engine()

    response = await readyz(make_request(engine, consumer_running=False))

    assert response.status_code == 503
    assert json.loads(response.body)["reason"] == "consumer_not_running"


@pytest.mark.asyncio
@patch("api.main.predictor")
async def test_readyz_times_out_on_hanging_database(mock_predictor, monkeypatch):
    mock_predictor.has_model.return_value = True
    monkeypatch.setattr("api.main.READINESS_DB_TIMEOUT_S", 0.01)
    engine, conn = make_engine()

    async def hang(*args, **kwargs):
        await asyncio.sleep(10)

    conn.execute = hang

    response = await readyz(make_request(engine))

    assert response.status_code == 503
    assert json.loads(response.body)["reason"] == "database_unavailable"


@pytest.mark.asyncio
async def test_consumer_crash_is_logged(caplog):
    async def boom():
        raise OSError("broker down")

    task = asyncio.create_task(boom())
    await asyncio.sleep(0)

    with caplog.at_level(logging.CRITICAL):
        _log_consumer_exit(task)

    assert "stopped unexpectedly" in caplog.text


@pytest.mark.asyncio
@patch("api.main.PredictionEventHandler")
@patch("api.main.RabbitMQConsumer")
@patch("api.main.RabbitMQPublisher")
@patch("api.main.create_session_factory")
@patch("api.main.create_engine")
@patch("api.main.predictor")
async def test_lifespan_disposes_engine_when_publisher_connect_fails(
    mock_predictor, mock_create_engine, mock_create_session_factory,
    mock_publisher_class, mock_consumer_class, mock_handler_class,
):
    mock_create_engine.return_value.dispose = AsyncMock()
    publisher = MagicMock()
    publisher.connect = AsyncMock(side_effect=OSError("broker down"))
    publisher.close = AsyncMock()
    mock_publisher_class.return_value = publisher

    with pytest.raises(OSError):
        async with lifespan(app):
            pytest.fail("must not start without a broker")

    mock_consumer_class.assert_not_called()
    publisher.close.assert_awaited_once()
    mock_create_engine.return_value.dispose.assert_awaited_once()