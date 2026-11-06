from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from infrastructure.event_handlers.prediction_event_handler import PredictionEventHandler

MODULE = "infrastructure.event_handlers.prediction_event_handler"


@pytest.fixture
def mock_predictor():
    predictor = MagicMock()
    predictor.predict.return_value = {
        "prediction": 1.0,
        "probabilities": [[0.1, 0.9]],
    }
    return predictor


@pytest.fixture
def mock_event_publisher():
    publisher = MagicMock()
    publisher.publish = AsyncMock()
    return publisher


@pytest.fixture
def mock_session_factory():
    """Fake async_sessionmaker for `async with factory() as session, session.begin():`."""
    session = MagicMock()
    session.begin.return_value.__aexit__.return_value = False   # don't swallow exceptions
    factory = MagicMock()
    factory.return_value.__aenter__.return_value = session
    factory.return_value.__aexit__.return_value = False
    return factory


def make_repo_class(received: int = 1, total: int = 3):
    """Returns (fake SqlAlchemyAnalysisRepository class, the fake instance it creates)."""
    repo = MagicMock()
    repo.lock_examination = AsyncMock()
    repo.add = AsyncMock(return_value=MagicMock(analysis_id=1, total_analyses_count=total))
    repo.count_for_examination = AsyncMock(return_value=received)
    return MagicMock(return_value=repo), repo


def make_payload(**overrides):
    payload = {
        "examination_id": str(uuid4()),
        "experiment_id": "exp_123",
        "subject_id": "sub_456",
        "recording_id": "rec_789",
        "window_id": "win_001",
        "event_id": "evt_99",
        "event_index": 1,
        "event_time_s": 10.5,
        "event_timestamp": 1600000000,
        "cluster_id": 2,
        "cluster_event_time_s": 10.0,
        "cluster_size": 5,
        "overlap_flag": False,
        "total_events": 3,
        "feature_1": 0.5,
        "feature_2": 1.2,
    }
    payload.update(overrides)
    return payload


def make_handler(predictor, session_factory, publisher):
    return PredictionEventHandler(predictor, session_factory, publisher)


@pytest.mark.asyncio
async def test_handle_success(mock_predictor, mock_session_factory, mock_event_publisher):
    repo_class, repo = make_repo_class(received=1, total=3)
    handler = make_handler(mock_predictor, mock_session_factory, mock_event_publisher)
    payload = make_payload()

    with patch(f"{MODULE}.SqlAlchemyAnalysisRepository", repo_class):
        await handler.handle(payload)

    # Only real features reach the model: metadata (incl. examination_id, total_events) is stripped
    mock_predictor.predict.assert_called_once_with({"feature_1": 0.5, "feature_2": 1.2})

    stored = repo.add.await_args.args[0]
    assert stored.examination_id == UUID(payload["examination_id"])
    assert stored.time_stamp == 10.5
    assert stored.result == 1.0
    assert stored.confidence == 0.9
    assert stored.total_analyses_count == 3
    repo.lock_examination.assert_awaited_once_with(UUID(payload["examination_id"]))
    mock_event_publisher.publish.assert_not_awaited()     # 1 of 3 received: not complete yet


@pytest.mark.asyncio
async def test_handle_stores_null_confidence_without_probabilities(
    mock_predictor, mock_session_factory, mock_event_publisher
):
    mock_predictor.predict.return_value = {"prediction": 2.5}
    repo_class, repo = make_repo_class()
    handler = make_handler(mock_predictor, mock_session_factory, mock_event_publisher)

    with patch(f"{MODULE}.SqlAlchemyAnalysisRepository", repo_class):
        await handler.handle(make_payload())

    stored = repo.add.await_args.args[0]
    assert stored.result == 2.5
    assert stored.confidence is None


@pytest.mark.asyncio
async def test_handle_publishes_completion_event_for_last_analysis(
    mock_predictor, mock_session_factory, mock_event_publisher
):
    repo_class, _ = make_repo_class(received=3, total=3)
    handler = make_handler(mock_predictor, mock_session_factory, mock_event_publisher)
    payload = make_payload()

    with patch(f"{MODULE}.SqlAlchemyAnalysisRepository", repo_class):
        await handler.handle(payload)

    mock_event_publisher.publish.assert_awaited_once_with(
        "examination_completed",
        {"examination_id": UUID(payload["examination_id"]), "total_analyses_count": 3},
    )


@pytest.mark.asyncio
async def test_completion_event_is_published_after_commit(
    mock_predictor, mock_session_factory, mock_event_publisher
):
    order = []
    session = mock_session_factory.return_value.__aenter__.return_value

    async def on_commit(*args):
        order.append("commit")
        return False

    session.begin.return_value.__aexit__ = AsyncMock(side_effect=on_commit)
    mock_event_publisher.publish = AsyncMock(side_effect=lambda *a, **k: order.append("publish"))
    repo_class, _ = make_repo_class(received=3, total=3)
    handler = make_handler(mock_predictor, mock_session_factory, mock_event_publisher)

    with patch(f"{MODULE}.SqlAlchemyAnalysisRepository", repo_class):
        await handler.handle(make_payload())

    assert order == ["commit", "publish"]


@pytest.mark.asyncio
async def test_handle_rejects_missing_examination_id(
    mock_predictor, mock_session_factory, mock_event_publisher
):
    handler = make_handler(mock_predictor, mock_session_factory, mock_event_publisher)
    payload = make_payload()
    del payload["examination_id"]

    with pytest.raises(ValueError, match="missing examination_id"):
        await handler.handle(payload)

    mock_predictor.predict.assert_not_called()
    mock_session_factory.assert_not_called()
    mock_event_publisher.publish.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_id", ["bucket/path", "invalid"])
async def test_handle_rejects_invalid_examination_id(
    bad_id, mock_predictor, mock_session_factory, mock_event_publisher
):
    handler = make_handler(mock_predictor, mock_session_factory, mock_event_publisher)

    with pytest.raises(ValueError):
        await handler.handle(make_payload(examination_id=bad_id))

    mock_predictor.predict.assert_not_called()
    mock_session_factory.assert_not_called()
    mock_event_publisher.publish.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_key", ["event_time_s", "total_events"])
async def test_handle_rejects_missing_required_fields(
    missing_key, mock_predictor, mock_session_factory, mock_event_publisher
):
    handler = make_handler(mock_predictor, mock_session_factory, mock_event_publisher)
    payload = make_payload()
    del payload[missing_key]

    with pytest.raises(ValueError, match=missing_key):
        await handler.handle(payload)

    mock_predictor.predict.assert_not_called()
    mock_session_factory.assert_not_called()


@pytest.mark.asyncio
async def test_handle_predictor_exception(mock_predictor, mock_session_factory, mock_event_publisher):
    mock_predictor.predict.side_effect = RuntimeError("Inference failed")
    handler = make_handler(mock_predictor, mock_session_factory, mock_event_publisher)

    with pytest.raises(RuntimeError, match="Inference failed"):
        await handler.handle(make_payload())

    mock_predictor.predict.assert_called_once_with({"feature_1": 0.5, "feature_2": 1.2})
    mock_session_factory.assert_not_called()          # nothing is stored if inference fails
    mock_event_publisher.publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_database_failure_propagates(
    mock_predictor, mock_session_factory, mock_event_publisher
):
    repo_class, repo = make_repo_class()
    repo.add.side_effect = ConnectionError("db down")
    handler = make_handler(mock_predictor, mock_session_factory, mock_event_publisher)

    with patch(f"{MODULE}.SqlAlchemyAnalysisRepository", repo_class):
        with pytest.raises(ConnectionError):          # must propagate so the consumer can requeue
            await handler.handle(make_payload())

    mock_event_publisher.publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_publish_failure_propagates(
    mock_predictor, mock_session_factory, mock_event_publisher
):
    mock_event_publisher.publish.side_effect = ConnectionError("broker down")
    repo_class, _ = make_repo_class(received=3, total=3)
    handler = make_handler(mock_predictor, mock_session_factory, mock_event_publisher)

    with patch(f"{MODULE}.SqlAlchemyAnalysisRepository", repo_class):
        with pytest.raises(ConnectionError):          # redelivery will retry the publish
            await handler.handle(make_payload())