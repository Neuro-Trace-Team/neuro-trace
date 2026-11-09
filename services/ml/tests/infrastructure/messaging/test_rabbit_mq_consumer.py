import asyncio
import json
from typing import cast
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch
import aio_pika
from sqlalchemy.exc import DataError, IntegrityError, OperationalError

import pytest

from infrastructure.event_handlers.ievent_handler import IEventHandler
from infrastructure.messaging.rabbit_mq_consumer import RabbitMQConsumer

CONSUMER_MODULE = "infrastructure.messaging.rabbit_mq_consumer"


@pytest.fixture
def mock_handler():
    # handle() is `async def` in IEventHandler, so autospec makes it an AsyncMock
    return create_autospec(IEventHandler, instance=True)


def make_consumer(handler=None) -> RabbitMQConsumer:
    return RabbitMQConsumer(
        queue_url="amqp://guest:guest@localhost/",
        queue_name="test_queue",
        handlers={"predict_event": handler} if handler else {},
    )


def make_message(body) -> MagicMock:
    """Fake incoming message. ack/nack/reject are awaitable; process() is no longer used."""
    message = MagicMock()
    message.body = (body if isinstance(body, str) else json.dumps(body)).encode()
    message.ack = AsyncMock()
    message.nack = AsyncMock()
    message.reject = AsyncMock()
    return message


def test_init(mock_handler: IEventHandler):
    handlers = {"predict_event": mock_handler}

    consumer = RabbitMQConsumer(
        queue_url="amqp://guest:guest@localhost/",
        queue_name="test_queue",
        handlers=handlers,
    )

    assert consumer.queue_url == "amqp://guest:guest@localhost/"
    assert consumer.queue_name == "test_queue"
    assert consumer.handlers == handlers
    assert consumer.connection is None


@pytest.mark.asyncio
@patch(f"{CONSUMER_MODULE}.aio_pika.connect_robust")
@patch(f"{CONSUMER_MODULE}.asyncio.Future")
async def test_start(mock_asyncio_future, mock_connect_robust, mock_handler: IEventHandler):
    mock_connection = AsyncMock()
    mock_channel = AsyncMock()
    mock_queue = AsyncMock()

    mock_connect_robust.return_value = mock_connection
    mock_connection.channel.return_value = mock_channel
    mock_channel.declare_queue.return_value = mock_queue

    mock_asyncio_future.side_effect = asyncio.CancelledError
    mock_connection.__aenter__.return_value = mock_connection

    consumer = make_consumer(mock_handler)

    with pytest.raises(asyncio.CancelledError):
        await consumer.start()

    mock_connect_robust.assert_awaited_once_with("amqp://guest:guest@localhost/")
    mock_connection.channel.assert_awaited_once()
    mock_channel.set_qos.assert_awaited_once_with(prefetch_count=1)
    mock_channel.declare_queue.assert_awaited_once_with("test_queue", durable=True)
    mock_queue.consume.assert_awaited_once_with(consumer._dispatch_message)


@pytest.mark.asyncio
async def test_dispatch_message_success(mock_handler: IEventHandler):
    payload = {"event_type": "predict_event", "features": [1.0, 2.0]}
    message = make_message(payload)

    await make_consumer(mock_handler)._dispatch_message(message)

    cast(AsyncMock, mock_handler.handle).assert_awaited_once_with(payload)
    message.ack.assert_awaited_once()
    message.nack.assert_not_awaited()
    message.reject.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatch_message_missing_handler(mock_handler: IEventHandler):
    message = make_message({"event_type": "unknown_event"})

    await make_consumer(mock_handler)._dispatch_message(message)

    cast(AsyncMock, mock_handler.handle).assert_not_awaited()
    message.reject.assert_awaited_once_with(requeue=False)   # permanent: never requeue
    message.ack.assert_not_awaited()
    message.nack.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatch_message_invalid_json_is_rejected(mock_handler: IEventHandler):
    message = make_message("{not json")

    await make_consumer(mock_handler)._dispatch_message(message)

    cast(AsyncMock, mock_handler.handle).assert_not_awaited()
    message.reject.assert_awaited_once_with(requeue=False)
    message.ack.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatch_message_permanent_handler_failure_is_rejected(mock_handler: IEventHandler):
    cast(AsyncMock, mock_handler.handle).side_effect = ValueError("missing examination_id")
    message = make_message({"event_type": "predict_event"})

    await make_consumer(mock_handler)._dispatch_message(message)

    message.reject.assert_awaited_once_with(requeue=False)
    message.nack.assert_not_awaited()
    message.ack.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [ConnectionError("db down"), asyncio.TimeoutError()])
async def test_dispatch_message_transient_failure_is_requeued(error, mock_handler: IEventHandler):
    cast(AsyncMock, mock_handler.handle).side_effect = error
    message = make_message({"event_type": "predict_event"})

    # Patch the back-off sleep so the test doesn't wait
    with patch(f"{CONSUMER_MODULE}.asyncio.sleep", new=AsyncMock()) as sleep:
        await make_consumer(mock_handler)._dispatch_message(message)

    sleep.assert_awaited_once()
    message.nack.assert_awaited_once_with(requeue=True)
    message.ack.assert_not_awaited()
    message.reject.assert_not_awaited()


@pytest.mark.asyncio
async def test_close_connection_active():
    consumer = make_consumer()
    mock_connection = AsyncMock()
    mock_connection.is_closed = False
    consumer.connection = mock_connection

    await consumer.close()

    mock_connection.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_close_connection_none_or_closed():
    consumer = make_consumer()
    consumer.connection = None

    await consumer.close()

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [IntegrityError("stmt", {}, Exception("check violated")),
     DataError("stmt", {}, Exception("bad value"))],
)
async def test_dispatch_message_db_constraint_violation_is_rejected(error, mock_handler):
    cast(AsyncMock, mock_handler.handle).side_effect = error
    message = make_message({"event_type": "predict_event"})

    with patch(f"{CONSUMER_MODULE}.asyncio.sleep", new=AsyncMock()) as sleep:
        await make_consumer(mock_handler)._dispatch_message(message)

    sleep.assert_not_awaited()
    message.reject.assert_awaited_once_with(requeue=False)
    message.nack.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [OperationalError("stmt", {}, Exception("conn lost")),
     aio_pika.exceptions.AMQPError("broker")],
)
async def test_dispatch_message_other_transient_errors_are_requeued(error, mock_handler):
    cast(AsyncMock, mock_handler.handle).side_effect = error
    message = make_message({"event_type": "predict_event"})

    with patch(f"{CONSUMER_MODULE}.asyncio.sleep", new=AsyncMock()):
        await make_consumer(mock_handler)._dispatch_message(message)

    message.nack.assert_awaited_once_with(requeue=True)
    message.reject.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatch_message_without_event_type_defaults_to_predict_event(mock_handler):
    payload = {"examination_id": "x"}
    message = make_message(payload)

    await make_consumer(mock_handler)._dispatch_message(message)

    cast(AsyncMock, mock_handler.handle).assert_awaited_once_with(payload)
    message.ack.assert_awaited_once()


@pytest.mark.asyncio
async def test_dispatch_message_non_object_json_is_rejected(mock_handler):
    message = make_message("[1, 2, 3]")   # valid JSON, but .get() fails on a list

    await make_consumer(mock_handler)._dispatch_message(message)

    message.reject.assert_awaited_once_with(requeue=False)
    cast(AsyncMock, mock_handler.handle).assert_not_awaited()
