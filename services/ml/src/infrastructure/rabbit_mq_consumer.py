import asyncio
import json
import logging
from typing import Dict

import aio_pika

from services.ml.src.event_handlers.ievent_handler import IEventHandler

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
        async with message.process():
            try:
                body_str = message.body.decode()
                logger.debug(f"Received raw message: {body_str}")

                payload = json.loads(body_str)

                # TODO: Determine event type (also decide how to determine)
                event_type = payload.get("event_type", "predict_event")
                logger.debug(f"Extracted event type: '{event_type}'")

                handler = self.handlers.get(event_type)
                if not handler:
                    raise KeyError(f"No handler registered for event type: {event_type}")

                logger.info(f"Dispatching event '{event_type}' to handler.")
                await handler.handle(payload)
                logger.info(f"Successfully processed event '{event_type}'.")

            except Exception as e:
                logger.exception(f"Error handling message dispatch: {e}")
                # TODO: Handle Exception

    async def close(self) -> None:
        if self.connection and not self.connection.is_closed:
            logger.info(f"Closing RabbitMQ connection for queue '{self.queue_name}'...")
            await self.connection.close()
            logger.info("RabbitMQ connection closed successfully.")
        else:
            logger.debug("Close called, but RabbitMQ connection was already closed or None.")
            # TODO: Log connection closing
        