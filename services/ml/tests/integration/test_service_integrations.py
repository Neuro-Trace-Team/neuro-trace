import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from infrastructure.messaging.rabbit_mq_consumer import RabbitMQConsumer

from core.config import Settings



def test_rabbitmq_settings_are_mapped_from_service_environment():
    settings = Settings(
        _env_file=None,
        MODEL_DB_URL="postgresql+asyncpg://test:test@db:5432/test",
        RABBITMQ_HOST="rabbitmq",
        RABBITMQ_PORT="5672",
        RABBITMQ_USER="integration-user",
        RABBITMQ_PASSWORD="integration-password",
        PENDING_ANALYSIS_QUEUE_NAME="preprocessing.combined_features",
        COMPLETED_ANALYSIS_QUEUE_NAME="ml.ready_examinations",
    )

    assert settings.queue_url == (
        "amqp://integration-user:integration-password@rabbitmq:5672/"
    )
    assert settings.pending_analysis_queue_name == "preprocessing.combined_features"


class _FakeQueue:
    def __init__(self):
        self.consumer_callback = None

    async def consume(self, callback):
        self.consumer_callback = callback


class _FakeChannel:
    def __init__(self, queue):
        self.queue = queue
        self.prefetch_count = None
        self.declared_queue = None
        self.durable = None

    async def set_qos(self, prefetch_count):
        self.prefetch_count = prefetch_count

    async def declare_queue(self, name, durable):
        self.declared_queue = name
        self.durable = durable
        return self.queue


class _FakeConnection:
    def __init__(self, channel):
        self.channel_instance = channel
        self.is_closed = False
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def channel(self):
        return self.channel_instance

    async def close(self):
        self.closed = True
        self.is_closed = True


def test_rabbitmq_consumer_connects_to_configured_host_and_queue():
    async def scenario():
        queue = _FakeQueue()
        channel = _FakeChannel(queue)
        connection = _FakeConnection(channel)
        queue_url = "amqp://integration-user:integration-password@rabbitmq:5672/"
        queue_name = "preprocessing.combined_features"

        with patch(
            "infrastructure.messaging.rabbit_mq_consumer.aio_pika.connect_robust",
            new=AsyncMock(return_value=connection),
        ) as connect_robust:
            consumer = RabbitMQConsumer(queue_url, queue_name, handlers={})
            task = asyncio.create_task(consumer.start())

            for _ in range(20):
                if queue.consumer_callback is not None:
                    break
                await asyncio.sleep(0)

            assert queue.consumer_callback is not None
            connect_robust.assert_awaited_once_with(queue_url)
            assert channel.prefetch_count == 1
            assert channel.declared_queue == queue_name
            assert channel.durable is True

            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    asyncio.run(scenario())


def test_rabbitmq_consumer_dispatches_mock_message_to_registered_handler():
    async def scenario():
        handler = MagicMock()
        handler.handle = AsyncMock()
        consumer = RabbitMQConsumer(
            queue_url="amqp://mock",
            queue_name="mock_queue",
            handlers={"predict_event": handler},
        )

        message = MagicMock()
        message.body = json.dumps(
            {"event_type": "predict_event", "recording_id": "recording-1"}
        ).encode()
        message.ack = AsyncMock()
        message.nack = AsyncMock()
        message.reject = AsyncMock()

        await consumer._dispatch_message(message)

        handler.handle.assert_awaited_once_with(
            {"event_type": "predict_event", "recording_id": "recording-1"}
        )
        message.ack.assert_awaited_once()
        message.nack.assert_not_awaited()
        message.reject.assert_not_awaited()

    asyncio.run(scenario())
