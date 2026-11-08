import asyncio
import json
from dataclasses import dataclass
from uuid import uuid4

import aio_pika
import numpy as np
import pytest
import pytest_asyncio

from infrastructure.event_handlers.prediction_event_handler import PredictionEventHandler
from infrastructure.messaging.rabbit_mq_consumer import RabbitMQConsumer
from infrastructure.messaging.rabbit_mq_publisher import RabbitMQPublisher
from infrastructure.repositories.sql_alchemy_analysis_repository import (
    SqlAlchemyAnalysisRepository,
)
from infrastructure.services.features import FEATURE_NAMES
from infrastructure.services.sklearn_predictor import SklearnPredictor

pytestmark = pytest.mark.integration


class _Model:
    def predict(self, X):
        return np.array([1.0])

    def predict_proba(self, X):
        return np.array([[0.3, 0.7]])


def make_event(exam, t, total, **overrides):
    payload = {
        "event_type": "predict_event",
        "examination_id": str(exam),
        "event_time_s": float(t),
        "total_analyses_count": total,
        "event_id": f"evt-{t}",
        **{name: 0.0 for name in FEATURE_NAMES},
    }
    payload.update(overrides)
    return payload


@dataclass
class Pipeline:
    pending_name: str
    channel: aio_pika.abc.AbstractChannel
    completed_queue: aio_pika.abc.AbstractQueue
    session_factory: object

    async def send(self, body) -> None:
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        await self.channel.default_exchange.publish(
            aio_pika.Message(raw, delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
            routing_key=self.pending_name,
        )

    async def next_completion(self, timeout: float = 10):
        """basic.get doesn't block, so poll until a message shows up."""
        async def poll():
            while True:
                msg = await self.completed_queue.get(fail=False)
                if msg is not None:
                    await msg.ack()
                    return msg
                await asyncio.sleep(0.05)

        return await asyncio.wait_for(poll(), timeout)

    async def no_more_completions(self) -> bool:
        return await self.completed_queue.get(fail=False) is None

    async def rows(self, exam):
        async with self.session_factory() as s:
            return await SqlAlchemyAnalysisRepository(s).list_for_examination(exam)

    async def wait_for_rows(self, exam, n, timeout: float = 10):
        async def poll():
            while len(await self.rows(exam)) < n:
                await asyncio.sleep(0.05)

        await asyncio.wait_for(poll(), timeout)

    async def pending_backlog(self) -> int:
        q = await self.channel.declare_queue(self.pending_name, durable=True)
        return q.declaration_result.message_count


@pytest_asyncio.fixture
async def pipeline(rabbit_url, session_factory):
    suffix = uuid4().hex[:8]
    pending, completed = f"test.pending.{suffix}", f"test.completed.{suffix}"

    predictor = SklearnPredictor(feature_names=FEATURE_NAMES)
    predictor.model = _Model()

    publisher = RabbitMQPublisher(rabbit_url, completed)
    await publisher.connect()
    handler = PredictionEventHandler(
        predictor, session_factory, publisher, SqlAlchemyAnalysisRepository
    )
    consumer = RabbitMQConsumer(rabbit_url, pending, {"predict_event": handler})

    # the test plays the other services; declaring first means nothing sent
    # before the consumer is up is dropped by the default exchange
    connection = await aio_pika.connect_robust(rabbit_url)
    channel = await connection.channel()
    await channel.declare_queue(pending, durable=True)
    completed_queue = await channel.declare_queue(completed, durable=True)

    task = asyncio.create_task(consumer.start())
    try:
        yield Pipeline(pending, channel, completed_queue, session_factory)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await consumer.close()
        await publisher.close()
        await connection.close()


async def test_complete_examination_flows_from_queue_to_database_to_completion_event(pipeline):
    exam = uuid4()

    for t in (2, 0, 1):                       # out of order on purpose
        await pipeline.send(make_event(exam, t, total=3))

    msg = await pipeline.next_completion()

    assert json.loads(msg.body) == {
        "event_type": "examination_completed",
        "examination_id": str(exam),
        "total_analyses_count": 3,
    }
    assert msg.message_id == str(exam)
    assert msg.delivery_mode == aio_pika.DeliveryMode.PERSISTENT

    rows = await pipeline.rows(exam)
    assert [r.event_timestamp for r in rows] == [0.0, 1.0, 2.0]
    assert {(r.result, r.confidence, r.total_analyses_count) for r in rows} == {(1.0, 0.7, 3)}
    assert await pipeline.no_more_completions()


async def test_incomplete_examination_stores_rows_but_publishes_nothing(pipeline):
    exam = uuid4()

    await pipeline.send(make_event(exam, 0, total=3))
    await pipeline.send(make_event(exam, 1, total=3))
    await pipeline.wait_for_rows(exam, 2)

    assert await pipeline.no_more_completions()


async def test_redelivered_event_does_not_duplicate_rows_or_completion(pipeline):
    exam = uuid4()

    await pipeline.send(make_event(exam, 0, total=2))
    await pipeline.send(make_event(exam, 0, total=2))      # duplicate delivery
    await pipeline.send(make_event(exam, 1, total=2))

    await pipeline.next_completion()

    assert len(await pipeline.rows(exam)) == 2
    assert await pipeline.no_more_completions()


def _poison_cases():
    exam = uuid4()
    no_exam = make_event(exam, 0, 1)
    del no_exam["examination_id"]
    missing_feature = make_event(exam, 0, 1)
    del missing_feature[FEATURE_NAMES[0]]
    return {
        "invalid_json": b"{not json",
        "json_array": b"[1, 2, 3]",
        "unknown_event_type": make_event(exam, 0, 1, event_type="nope"),
        "missing_examination_id": no_exam,
        "missing_feature": missing_feature,
        "negative_timestamp_violates_check": make_event(exam, -1, 1),
    }


@pytest.mark.parametrize("name", list(_poison_cases()))
async def test_poison_message_is_dropped_and_the_queue_keeps_flowing(pipeline, name):
    poison = _poison_cases()[name]
    good_exam = uuid4()

    await pipeline.send(poison)
    await pipeline.send(make_event(good_exam, 0, total=1))

    await pipeline.next_completion()      # would time out if the poison blocked the queue

    assert len(await pipeline.rows(good_exam)) == 1
    assert await pipeline.pending_backlog() == 0
    assert await pipeline.no_more_completions()