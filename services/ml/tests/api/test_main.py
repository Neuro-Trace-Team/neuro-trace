import asyncio
import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.main import _log_consumer_exit, app, connections, healthz, info, lifespan, readyz
from core.config import settings
from infrastructure.repositories.sql_alchemy_analysis_repository import (
    SqlAlchemyAnalysisRepository,
)

from tests.conftest import TEST_FEATURES




def make_engine(execute_side_effect=None):
    """Fake AsyncEngine: `async with engine.connect() as conn: await conn.execute(...)`."""
    conn = MagicMock()
    conn.execute = AsyncMock(side_effect=execute_side_effect)

    engine = MagicMock()
    engine.connect.return_value.__aenter__.return_value = conn
    engine.connect.return_value.__aexit__.return_value = False
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

        assert app.state.publisher is mock_publisher
        assert app.state.consumer is mock_consumer

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
    async def make_error():
        raise OSError("broker down")

    task = asyncio.create_task(make_error())
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


async def test_info_describes_model_without_leaking_the_filesystem_path(client):
    with patch("api.main.predictor") as p:
        p.model_info.return_value = {"loaded": True, "estimator": "X"}
        r = await client.get("/info")
    assert r.json() == {"app_name": settings.app_name, "model": {"loaded": True, "estimator": "X"}}
    assert settings.model_path not in r.text


@pytest.fixture
def wired_app(monkeypatch):
    engine, conn = make_engine()
    wiring = SimpleNamespace(
        engine=engine,
        conn=conn,
        consumer=MagicMock(is_connected=True),
        publisher=MagicMock(is_connected=True),
        task=MagicMock(**{"done.return_value": False}),
    )
    for name, value in {
        "engine": engine, "consumer": wiring.consumer,
        "publisher": wiring.publisher, "consumer_task": wiring.task,
    }.items():
        monkeypatch.setattr(app.state, name, value, raising=False)
    return wiring


async def test_connections_all_up(client, wired_app):
    r = await client.get("/connections")

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert {k: v["status"] for k, v in body["connections"].items()} == {
        "database": "up", "rabbitmq_consumer": "up", "rabbitmq_publisher": "up",
    }
    assert isinstance(body["connections"]["database"]["latency_ms"], int)


@pytest.mark.parametrize("break_it, down", [
    (lambda w: setattr(w.consumer, "is_connected", False), "rabbitmq_consumer"),
    (lambda w: w.task.done.configure_mock(return_value=True), "rabbitmq_consumer"),
    (lambda w: setattr(w.publisher, "is_connected", False), "rabbitmq_publisher"),
    (lambda w: setattr(w.conn, "execute", AsyncMock(side_effect=ConnectionError("db down"))), "database"),
])
async def test_connections_reports_only_the_broken_one_as_down(client, wired_app, break_it, down):
    break_it(wired_app)

    r = await client.get("/connections")

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "degraded"
    assert {k for k, v in body["connections"].items() if v["status"] == "down"} == {down}


async def test_connections_does_not_leak_error_details(client, wired_app):
    wired_app.conn.execute = AsyncMock(side_effect=ConnectionError("password=hunter2 host=10.0.0.5"))

    r = await client.get("/connections")

    assert "hunter2" not in r.text and "10.0.0.5" not in r.text
    assert settings.queue_url not in r.text


async def test_connections_database_timeout_is_reported_down(client, wired_app, monkeypatch):
    monkeypatch.setattr("api.main.READINESS_DB_TIMEOUT_S", 0.01)

    async def hang(*args, **kwargs):
        await asyncio.sleep(10)

    wired_app.conn.execute = hang

    r = await client.get("/connections")

    assert r.json()["connections"]["database"] == {"status": "down"}


@pytest.mark.asyncio
async def test_connections_before_startup_reports_everything_down_instead_of_failing():
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))   # lifespan never ran

    body = await connections(request)

    assert body["status"] == "degraded"
    assert all(c["status"] == "down" for c in body["connections"].values())