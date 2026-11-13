import json
import logging
from typing import Any

import aio_pika
from aio_pika.abc import AbstractRobustChannel, AbstractRobustConnection

logger = logging.getLogger(__name__)


class RabbitMQPublisher:
    def __init__(self, queue_url: str, queue_name: str) -> None:
        self.queue_url = queue_url
        self.queue_name = queue_name
        self._connection: AbstractRobustConnection | None = None
        self._channel: AbstractRobustChannel | None = None

    async def connect(self) -> None:
        logger.info("Attempting to create RabbitMQ publisher connection...")
        self._connection = await aio_pika.connect_robust(self.queue_url)
        self._channel = await self._connection.channel()
        await self._channel.declare_queue(self.queue_name, durable=True)
        logger.info("RabbitMQ publisher ready for queue '%s'", self.queue_name)

    async def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        if self._channel is None:
            raise RuntimeError("RabbitMQPublisher.connect() has not been called")

        body = json.dumps({"event_type": event_type, **payload}, default=str).encode()
        message = aio_pika.Message(
            body=body,
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,   # survive a broker restart
            message_id=str(payload.get("examination_id", "")) or None,  # lets receivers deduplicate
        )
        await self._channel.default_exchange.publish(
            message, routing_key=self.queue_name, timeout=5
        )
        logger.info("Published '%s' to '%s'.", event_type, self.queue_name)

    async def close(self) -> None:
        if self._connection and not self._connection.is_closed:
            await self._connection.close()

    @property
    def is_connected(self) -> bool:
        return (
            self._connection is not None and not self._connection.is_closed
            and self._channel is not None and not self._channel.is_closed
        )