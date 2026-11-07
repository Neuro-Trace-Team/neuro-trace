import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from infrastructure.messaging.rabbit_mq_consumer import RabbitMQConsumer

from core.config import Settings
import pytest


class _FakeQueue:
    def __init__(self):
        self.consumer_callback = None
        self.consuming = asyncio.Event()

    async def consume(self, callback):
        self.consumer_callback = callback
        self.consuming.set()


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


@pytest.mark.asyncio
async def test_start_declares_durable_queue_and_consumes_until_cancelled():
    queue = _FakeQueue()
    channel = _FakeChannel(queue)
    connection = _FakeConnection(channel)
    url, name = "amqp://u:p@rabbitmq:5672/", "preprocessing.combined_features"

    with patch(
        "infrastructure.messaging.rabbit_mq_consumer.aio_pika.connect_robust",
        new=AsyncMock(return_value=connection),
    ) as connect_robust:
        consumer = RabbitMQConsumer(url, name, handlers={})
        task = asyncio.create_task(consumer.start())
        try:
            await asyncio.wait_for(queue.consuming.wait(), timeout=1)

            connect_robust.assert_awaited_once_with(url)
            assert channel.prefetch_count == 1
            assert (channel.declared_queue, channel.durable) == (name, True)
            assert queue.consumer_callback == consumer._dispatch_message
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task