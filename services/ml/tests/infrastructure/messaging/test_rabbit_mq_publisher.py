import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import aio_pika
import pytest

from infrastructure.messaging.rabbit_mq_publisher import RabbitMQPublisher

PUBLISHER_MODULE = "infrastructure.messaging.rabbit_mq_publisher"


@pytest.fixture
def channel():
    ch = MagicMock()
    ch.declare_queue = AsyncMock()
    ch.default_exchange.publish = AsyncMock()
    return ch


@pytest.fixture
def connection(channel):
    c = MagicMock()
    c.channel = AsyncMock(return_value=channel)
    c.close = AsyncMock()
    c.is_closed = False
    return c


@pytest.fixture
def publisher(connection, channel):
    p = RabbitMQPublisher("amqp://guest:guest@localhost/", "events_queue")
    p._connection, p._channel = connection, channel
    return p


def sent_message(channel) -> aio_pika.Message:
    return channel.default_exchange.publish.await_args.args[0]


def test_init_is_not_connected():
    p = RabbitMQPublisher("amqp://x", "q")
    assert (p.queue_url, p.queue_name) == ("amqp://x", "q")
    assert p._connection is None and p._channel is None


@pytest.mark.asyncio
async def test_connect_opens_channel_and_declares_durable_queue(connection, channel):
    p = RabbitMQPublisher("amqp://x", "events_queue")

    with patch(f"{PUBLISHER_MODULE}.aio_pika.connect_robust",
               new=AsyncMock(return_value=connection)) as connect:
        await p.connect()

    connect.assert_awaited_once_with("amqp://x")
    channel.declare_queue.assert_awaited_once_with("events_queue", durable=True)
    assert p._channel is channel


@pytest.mark.asyncio
async def test_publish_before_connect_raises():
    p = RabbitMQPublisher("amqp://x", "q")

    with pytest.raises(RuntimeError, match="connect"):
        await p.publish("examination_completed", {})


@pytest.mark.asyncio
async def test_publish_sends_json_body_with_event_type_and_serialized_uuid(publisher, channel):
    exam = uuid4()

    await publisher.publish(
        "examination_completed", {"examination_id": exam, "total_analyses_count": 3}
    )

    assert json.loads(sent_message(channel).body) == {
        "event_type": "examination_completed",
        "examination_id": str(exam),
        "total_analyses_count": 3,
    }


@pytest.mark.asyncio
async def test_publish_message_is_persistent_json_with_examination_id_as_message_id(
    publisher, channel
):
    exam = uuid4()

    await publisher.publish("examination_completed", {"examination_id": exam})

    msg = sent_message(channel)
    assert msg.delivery_mode == aio_pika.DeliveryMode.PERSISTENT
    assert msg.content_type == "application/json"
    assert msg.message_id == str(exam)


@pytest.mark.asyncio
async def test_publish_without_examination_id_leaves_message_id_unset(publisher, channel):
    await publisher.publish("something", {"x": 1})

    assert sent_message(channel).message_id is None


@pytest.mark.asyncio
async def test_publish_routes_to_configured_queue_with_timeout(publisher, channel):
    await publisher.publish("e", {})

    kwargs = channel.default_exchange.publish.await_args.kwargs
    assert kwargs["routing_key"] == "events_queue"
    assert kwargs["timeout"] == 5


@pytest.mark.asyncio
async def test_publish_propagates_broker_errors(publisher, channel):
    channel.default_exchange.publish.side_effect = aio_pika.exceptions.AMQPError("down")

    with pytest.raises(aio_pika.exceptions.AMQPError):
        await publisher.publish("e", {})


@pytest.mark.asyncio
async def test_close_closes_open_connection(publisher, connection):
    await publisher.close()

    connection.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_close_is_noop_when_not_connected_or_already_closed(publisher, connection):
    connection.is_closed = True
    await publisher.close()
    connection.close.assert_not_awaited()

    await RabbitMQPublisher("amqp://x", "q").close()


def test_publisher_is_connected_only_while_connection_and_channel_are_open(publisher, connection, channel):
    channel.is_closed = False
    assert publisher.is_connected is True

    channel.is_closed = True
    assert publisher.is_connected is False

    channel.is_closed = False
    connection.is_closed = True
    assert publisher.is_connected is False


def test_publisher_is_not_connected_before_connect():
    assert RabbitMQPublisher("amqp://x", "q").is_connected is False