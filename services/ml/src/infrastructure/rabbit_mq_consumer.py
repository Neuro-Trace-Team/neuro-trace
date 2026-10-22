import asyncio
import json
from typing import Dict

import aio_pika

from services.ml.src.event_handlers.ievent_handler import IEventHandler


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

    async def start(self) -> None:
        # TODO: Add logging
        self.connection = await aio_pika.connect_robust(self.queue_url)

        async with self.connection:
            channel = await self.connection.channel()
            await channel.set_qos(prefetch_count=1)

            queue = await channel.declare_queue(self.queue_name, durable=True)
            # TODO: Log start of listening

            await queue.consume(self._dispatch_message)
            await asyncio.Future()

    async def _dispatch_message(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        """Dispatches incoming messages to the appropriate registered handler."""
        async with message.process():
            try:
                payload = json.loads(message.body.decode())

                # TODO: Determine event type (also decide how to determine)
                event_type = payload.get("event_type", "predict_event")

                handler = self.handlers.get(event_type)
                if not handler:
                    raise KeyError(f"No handler registered for event type: {event_type}")

                await handler.handle(payload)

            except Exception as e:
                print(f"Error handling message dispatch: {e}")
                # TODO: Handle Exception

    async def close(self) -> None:
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
            # TODO: Log connection closing
        