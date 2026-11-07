# tests/integration/test_concurrent_handlers.py
import asyncio
from uuid import uuid4

import pytest

from infrastructure.event_handlers.prediction_event_handler import PredictionEventHandler
from infrastructure.repositories.sql_alchemy_analysis_repository import (
    SqlAlchemyAnalysisRepository,
)

pytestmark = pytest.mark.integration


class StubPredictor:
    def predict(self, features):
        return {"prediction": [1.0], "probabilities": [[0.3, 0.7]]}


class RecordingPublisher:
    def __init__(self):
        self.events = []

    async def publish(self, event_type, payload):
        self.events.append((event_type, payload))


class DelayedAddRepository(SqlAlchemyAnalysisRepository):
    """Real lock; the pause forces writers to overlap between insert and count."""
    async def add(self, analysis):
        saved = await super().add(analysis)
        await asyncio.sleep(0.2)
        return saved


class UnlockedRepository(DelayedAddRepository):
    async def lock_examination(self, examination_id):
        pass


def make_payload(exam, i, total):
    return {
        "examination_id": str(exam),
        "event_time_s": float(i),
        "total_events": total,
        "feature_1": 0.1,
    }


async def run_all(repo_factory, session_factory, exam, total):
    publisher = RecordingPublisher()
    handler = PredictionEventHandler(StubPredictor(), session_factory, publisher, repo_factory)
    await asyncio.gather(*(handler.handle(make_payload(exam, i, total)) for i in range(total)))
    return publisher


async def stored_count(session_factory, exam):
    async with session_factory() as s:
        return await SqlAlchemyAnalysisRepository(s).count_for_examination(exam)


@pytest.mark.parametrize("total", [2, 6])
async def test_concurrent_writers_publish_completion_exactly_once(session_factory, total):
    exam = uuid4()

    publisher = await run_all(DelayedAddRepository, session_factory, exam, total)

    assert await stored_count(session_factory, exam) == total
    assert [name for name, _ in publisher.events] == ["examination_completed"]


async def test_without_the_lock_the_completion_event_is_lost(session_factory):
    """Control: shows the race is real, so the test above proves something."""
    exam = uuid4()

    publisher = await run_all(UnlockedRepository, session_factory, exam, total=2)

    assert await stored_count(session_factory, exam) == 2
    assert publisher.events == []        # each writer counted only its own uncommitted row


async def test_redelivered_message_is_stored_once(session_factory):
    exam = uuid4()
    handler = PredictionEventHandler(
        StubPredictor(), session_factory, RecordingPublisher(), SqlAlchemyAnalysisRepository
    )

    await asyncio.gather(*(handler.handle(make_payload(exam, 0, total=3)) for _ in range(3)))

    assert await stored_count(session_factory, exam) == 1