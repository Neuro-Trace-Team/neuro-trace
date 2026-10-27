import asyncio
import json
from typing import Dict
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

import pytest

from services.ml.src.event_handlers.ievent_handler import IEventHandler
from services.ml.src.infrastructure.rabbit_mq_consumer import RabbitMQConsumer


@pytest.fixture
def mock_handler():
    handler = MagicMock()
    handler.handle = AsyncMock()
    return create_autospec(IEventHandler, instance=True)

def test_init(mock_handler: IEventHandler):
    handlers = {
        "predict_event": mock_handler
    }

    consumer = RabbitMQConsumer(
        queue_url="amqp://guest:guest@localhost/",
        queue_name="test_queue",
        handlers=handlers
    )

    assert consumer.queue_url == "amqp://guest:guest@localhost/"
    assert consumer.queue_name == "test_queue"
    assert consumer.handlers == handlers
    assert consumer.connection is None

@pytest.mark.asyncio
@patch("services.ml.src.infrastructure.rabbit_mq_consumer.aio_pika.connect_robust")
@patch("services.ml.src.infrastructure.rabbit_mq_consumer.asyncio.Future")
async def test_start(mock_asyncio_future, mock_connect_robust, mock_handler: IEventHandler):
    mock_connection = AsyncMock()
    mock_channel = AsyncMock()
    mock_queue = AsyncMock()

    mock_connect_robust.return_value = mock_connection
    mock_connection.channel.return_value = mock_channel
    mock_channel.declare_queue.return_value = mock_queue

    mock_asyncio_future.side_effect = asyncio.CancelledError
    mock_connection.__aenter__.return_value = mock_connection

    consumer = RabbitMQConsumer(
        queue_url="amqp://guest:guest@localhost/",
        queue_name="test_queue",
        handlers={"predict_event": mock_handler}
    )

    with pytest.raises(asyncio.CancelledError):
        await consumer.start()

    mock_connect_robust.assert_awaited_once_with("amqp://guest:guest@localhost/")
    mock_connection.channel.assert_awaited_once()
    mock_channel.set_qos.assert_awaited_once_with(prefetch_count=1)
    mock_channel.declare_queue.assert_awaited_once_with("test_queue", durable=True)
    mock_queue.consume.assert_awaited_once_with(consumer._dispatch_message)

@pytest.mark.asyncio
async def test_dispatch_message_success(mock_handler: IEventHandler):
    consumer = RabbitMQConsumer(
        queue_url="amqp://guest:guest@localhost/",
        queue_name="test_queue",
        handlers={"predict_event": mock_handler}
    )

    mock_message = MagicMock()
    payload = {"event_type": "predict_event", "features": [1.0, 2.0]}
    mock_message.body = json.dumps(payload).encode()

    cm = AsyncMock()
    cm.__aenter__.return_value = None
    cm.__aexit__.return_value = None
    mock_message.process.return_value = cm

    await consumer._dispatch_message(mock_message)

    # TODO: make this warning go away...
    mock_handler.handle.assert_awaited_once_with(payload)

@pytest.mark.asyncio
async def test_dispatch_message_missing_handler(mock_handler):
    consumer = RabbitMQConsumer(
        queue_url="amqp://guest:guest@localhost/",
        queue_name="test_queue",
        handlers={"predict_event": mock_handler}
    )

    mock_message = MagicMock()
    payload = {"event_type": "unknown_event"}
    mock_message.body = json.dumps(payload).encode()

    cm = AsyncMock()
    cm.__aenter__.return_value = None
    cm.__aexit__.return_value = None
    mock_message.process.return_value = cm

    await consumer._dispatch_message(mock_message)

    mock_handler.handle.assert_not_awaited()

@pytest.mark.asyncio
async def test_close_connection_active():
    consumer = RabbitMQConsumer(
        queue_url="amqp://guest:guest@localhost/",
        queue_name="test_queue",
        handlers={}
    )
    mock_connection = AsyncMock()
    mock_connection.is_closed = False
    consumer.connection = mock_connection

    await consumer.close()

    mock_connection.close.assert_awaited_once()

@pytest.mark.asyncio
async def test_close_connection_none_or_closed():
    consumer = RabbitMQConsumer(
        queue_url="amqp://guest:guest@localhost/",
        queue_name="test_queue",
        handlers={}
    )
    consumer.connection = None

    await consumer.close()