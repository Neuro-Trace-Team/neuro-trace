import asyncio
import json
import logging

from typing import Dict
from sqlalchemy.exc import DBAPIError, DataError, DBAPIError, IntegrityError

import aio_pika

from infrastructure.event_handlers.ievent_handler import IEventHandler

logger = logging.getLogger(__name__)


class RabbitMQConsumer:
    def __init__(
            self,
            queue_url : str,
            queue_name : str,
            handlers: Dict[str, IEventHandler]  # {"predict_event": prediction_handler_instance}
        ):
        self.queue_url = queue_url
        self.queue_name = queue_name
        self.handlers = handlers
        self.connection = None
        logger.debug(
            f"Initialized RabbitMQConsumer for queue '{self.queue_name}'"
        )

    async def start(self) -> None:
        logger.info(
            f"Connecting to RabbitMQ at {self.queue_url} for queue"
            f" '{self.queue_name}'..."
        )
        self.connection = await aio_pika.connect_robust(self.queue_url)

        async with self.connection:
            channel = await self.connection.channel()
            await channel.set_qos(prefetch_count=1)

            queue = await channel.declare_queue(self.queue_name, durable=True)
            logger.info(
                f"Successfully connected and listening on queue: {self.queue_name}"
            )

            await queue.consume(self._dispatch_message)
            await asyncio.Future()

    async def _dispatch_message(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        """Dispatches incoming messages to the appropriate registered handler."""
        try:
            payload = json.loads(message.body.decode())
            event_type = payload.get("event_type", "predict_event")
            handler = self.handlers.get(event_type)
            if not handler:
                raise KeyError(f"No handler registered for event type: {event_type}")
            await handler.handle(payload)
            await message.ack()
        except (IntegrityError, DataError):
            logger.exception("Data rejected by the database, rejecting")
            await message.reject(requeue=False)
        except (DBAPIError, OSError, asyncio.TimeoutError, aio_pika.exceptions.AMQPError):
            # Transient: put it back, but pause so a long outage doesn't spin hot
            logger.exception("Transient failure, requeueing")
            await asyncio.sleep(5)               # safe: prefetch=1, nothing else is waiting
            await message.nack(requeue=True)
        except Exception:
            # Permanent (bad JSON, missing fields, unknown event, bad features)
            logger.exception("Permanent failure, rejecting")
            await message.reject(requeue=False)  # dropped, or dead-lettered if you configure a DLX

    async def close(self) -> None:
        if self.connection and not self.connection.is_closed:
            logger.info(f"Closing RabbitMQ connection for queue '{self.queue_name}'...")
            await self.connection.close()
            logger.info("RabbitMQ connection closed successfully.")
        else:
            logger.debug("Close called, but RabbitMQ connection was already closed or None.")

    @property
    def is_connected(self) -> bool:
        return self.connection is not None and not self.connection.is_closed