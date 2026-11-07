from unittest.mock import AsyncMock, MagicMock, Mock
from uuid import uuid4

import pytest

from infrastructure.event_handlers.prediction_event_handler import PredictionEventHandler


def make_session_factory():
    """Fake async_sessionmaker: `async with factory() as session, session.begin():`."""
    session = MagicMock()
    session.begin.return_value.__aexit__.return_value = False   # don't swallow exceptions
    factory = MagicMock()
    factory.return_value.__aenter__.return_value = session
    factory.return_value.__aexit__.return_value = False
    return factory


def make_repo_factory(received: int, total: int):
    """Returns (repository_factory, repo); the factory is injected into the handler."""
    repo = MagicMock()
    repo.lock_examination = AsyncMock()
    repo.add = AsyncMock(return_value=MagicMock(analysis_id=1, total_analyses_count=total))
    repo.count_for_examination = AsyncMock(return_value=received)
    return MagicMock(return_value=repo), repo


def make_publisher():
    publisher = Mock()
    publisher.publish = AsyncMock()
    return publisher


@pytest.mark.asyncio
async def test_analysis_uuid_is_stored_as_examination_id():
    examination_id = uuid4()
    predictor = Mock()
    predictor.predict.return_value = {"prediction": [1], "probabilities": [[0.2, 0.8]]}
    publisher = make_publisher()
    session_factory = make_session_factory()
    repo_factory, repo = make_repo_factory(received=1, total=3)
    handler = PredictionEventHandler(predictor, session_factory, publisher, repo_factory)

    await handler.handle({
        "examination_id": str(examination_id),
        "event_time_s": 12.5,
        "total_events": 3,
        "alpha_power": 0.42,
    })

    # metadata keys (including total_events) must not leak into the model features
    predictor.predict.assert_called_once_with({"alpha_power": 0.42})

    # the repository is built from the session opened by the session factory
    session = session_factory.return_value.__aenter__.return_value
    repo_factory.assert_called_once_with(session)

    stored = repo.add.await_args.args[0]
    assert stored.examination_id == examination_id
    assert stored.event_timestamp == 12.5
    assert stored.result == 1.0
    assert stored.confidence == 0.8
    assert stored.total_analyses_count == 3
    publisher.publish.assert_not_awaited()      # 1 of 3 received: not complete yet


@pytest.mark.asyncio
@pytest.mark.parametrize("examination_id", [None, "bucket/path", "invalid"])
async def test_invalid_analysis_uuid_is_not_predicted_or_stored(examination_id):
    predictor = Mock()
    publisher = make_publisher()
    session_factory = make_session_factory()
    repo_factory, _ = make_repo_factory(received=1, total=1)
    handler = PredictionEventHandler(predictor, session_factory, publisher, repo_factory)

    with pytest.raises(ValueError):
        await handler.handle({
            "examination_id": examination_id,
            "event_time_s": 1.0,
            "total_events": 1,
            "alpha_power": 0.42,
        })

    predictor.predict.assert_not_called()
    session_factory.assert_not_called()
    repo_factory.assert_not_called()
    publisher.publish.assert_not_awaited()