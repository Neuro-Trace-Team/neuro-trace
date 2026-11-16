"""Consume completion events emitted by the ML service."""

from __future__ import annotations

import asyncio
import json
import logging
from uuid import UUID

import aio_pika
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from src.services.examinations import mark_examination_ready

logger = logging.getLogger(__name__)
_EVENT_TYPE = "examination_completed"
_active_consumer: "MLCompletionConsumer | None" = None


def set_active_completion_consumer(consumer: "MLCompletionConsumer | None") -> None:
    """Expose the lifespan-owned consumer for read-only diagnostics."""
    global _active_consumer
    _active_consumer = consumer


def completion_consumer_status() -> str:
    """Return the state of the actual completion-event consumer, not a broker probe."""
    if _active_consumer is None:
        return "unknown"
    return "up" if _active_consumer.is_listening else "down"


class MLCompletionConsumer:
    def __init__(self, *, queue_url: str, queue_name: str, session_factory: sessionmaker[Session]) -> None:
        self.queue_url = queue_url
        self.queue_name = queue_name
        self.session_factory = session_factory
        self.connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._is_listening = False

    @property
    def is_listening(self) -> bool:
        """Whether the registered consumer currently has an active AMQP transport."""
        if not self._is_listening or self.connection is None or self.connection.is_closed:
            return False
        connected = getattr(self.connection, "connected", None)
        return bool(connected is not None and connected.is_set())

    async def start(self) -> None:
        self._is_listening = False
        logger.info("Connecting backend ML completion consumer to queue '%s'", self.queue_name)
        self.connection = await aio_pika.connect_robust(self.queue_url)
        channel = await self.connection.channel()
        await channel.set_qos(prefetch_count=1)
        queue = await channel.declare_queue(self.queue_name, durable=True)
        await queue.consume(self._dispatch_message)
        self._is_listening = True
        logger.info("Backend ML completion consumer is listening on '%s'", self.queue_name)
        try:
            await asyncio.Future()
        finally:
            self._is_listening = False

    async def run(self) -> None:
        """Reconnect after broker outages without taking down the HTTP API."""
        while True:
            try:
                await self.start()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("ML completion consumer disconnected; retrying in 5 seconds")
                await self.close()
                await asyncio.sleep(5)

    async def _dispatch_message(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        try:
            payload = json.loads(message.body.decode("utf-8"))
            if payload.get("event_type") != _EVENT_TYPE:
                raise ValueError(f"Unsupported ML event type: {payload.get('event_type')!r}")
            examination_id = UUID(str(payload["examination_id"]))
            with self.session_factory() as session:
                updated = mark_examination_ready(session, examination_id)
            if updated:
                logger.info("Marked examination %s as READY after ML completion", examination_id)
            else:
                logger.warning("Ignoring completion event for missing or deleted examination %s", examination_id)
            await message.ack()
        except (KeyError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
            logger.exception("Rejecting invalid ML completion event")
            await message.reject(requeue=False)
        except (SQLAlchemyError, OSError, asyncio.TimeoutError, aio_pika.exceptions.AMQPError):
            logger.exception("Temporary completion-event failure; requeueing")
            await message.nack(requeue=True)
        except Exception:
            logger.exception("Unexpected completion-event failure; requeueing")
            await message.nack(requeue=True)

    async def close(self) -> None:
        self._is_listening = False
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
        self.connection = None
