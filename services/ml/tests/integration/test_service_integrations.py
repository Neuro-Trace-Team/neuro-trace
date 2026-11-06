import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from infrastructure.clients.backend_auth_client import BackendAuthClient
from infrastructure.clients.rest_result_publisher import RestResultPublisher
from infrastructure.messaging.rabbit_mq_consumer import RabbitMQConsumer
import respx

from core.config import Settings



def test_rabbitmq_settings_are_mapped_from_service_environment():
    settings = Settings(
        _env_file=None,
        RABBITMQ_HOST="rabbitmq",
        RABBITMQ_PORT="5672",
        RABBITMQ_USER="integration-user",
        RABBITMQ_PASSWORD="integration-password",
        RABBITMQ_QUEUE="preprocessing.combined_features",
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
        message.process.return_value = _MessageProcessContext()

        await consumer._dispatch_message(message)

        handler.handle.assert_awaited_once_with(
            {"event_type": "predict_event", "recording_id": "recording-1"}
        )

    asyncio.run(scenario())


class _MessageProcessContext:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_backend_authentication_and_result_publication_flow():
    async def scenario():
        base_url = "http://mock-backend"
        analysis_id = "de7b1a8e-c6f0-48e8-b0a9-cac4f75680a3"
        result_route = respx.post(
            f"{base_url}/api/v1/internal/analyses/{analysis_id}/result"
        ).respond(status_code=200)

        auth_client = BackendAuthClient("integration-service-token")
        publisher = RestResultPublisher(base_url, auth_client)
        payload = {
            "result": {"prediction": {"label": "mock-positive"}},
            "confidence": 0.9,
        }

        await publisher.publish_result(analysis_id, payload)

        assert result_route.call_count == 1
        request = result_route.calls.last.request
        assert request.headers["Authorization"] == "Bearer integration-service-token"
        assert json.loads(request.content) == payload

    with respx.mock:
        asyncio.run(scenario())


def test_backend_rejects_result_with_401_without_reauthentication():
    async def scenario():
        base_url = "http://mock-backend"
        analysis_id = "de7b1a8e-c6f0-48e8-b0a9-cac4f75680a3"
        result_route = respx.post(
            f"{base_url}/api/v1/internal/analyses/{analysis_id}/result"
        ).respond(status_code=401, text="Unauthorized")

        auth_client = BackendAuthClient("integration-service-token")
        publisher = RestResultPublisher(base_url, auth_client)

        try:
            await publisher.publish_result(
                analysis_id, {"result": {"prediction": [1]}}
            )
        except httpx.HTTPStatusError as error:
            assert error.response.status_code == 401
        else:
            raise AssertionError("Backend 401 response should be propagated")

        assert result_route.call_count == 1
        assert result_route.calls.last.request.headers["Authorization"] == (
            "Bearer integration-service-token"
        )

    with respx.mock:
        asyncio.run(scenario())
