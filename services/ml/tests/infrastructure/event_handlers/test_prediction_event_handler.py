from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

from infrastructure.services.sklearn_predictor import SklearnPredictor
import numpy as np
import pytest

from domain.entities.analysis import Analysis, NewAnalysis
from infrastructure.event_handlers.prediction_event_handler import PredictionEventHandler


EXAM = uuid4()
FEATURES = {"feature_1": 0.5, "feature_2": 1.2}


def make_payload(**overrides):
    """Full payload as produced upstream: metadata + features."""
    payload = {
        "examination_id": str(EXAM),
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
        "total_analyses_count": 3,
        **FEATURES,
    }
    payload.update(overrides)
    return payload


def make_saved(total=3):
    return Analysis(1, EXAM, 10.5, 1.0, 0.9, total)


@pytest.fixture
def predictor():
    predictor = MagicMock()
    predictor.predict.return_value = {"prediction": [1.0], "probabilities": [[0.1, 0.9]]}
    return predictor


@pytest.fixture
def publisher():
    publisher = MagicMock()
    publisher.publish = AsyncMock()
    return publisher


@pytest.fixture
def session():
    """Fake AsyncSession usable in `async with factory() as session, session.begin():`."""
    session = MagicMock()
    session.begin.return_value.__aexit__.return_value = False  # don't swallow exceptions
    return session


@pytest.fixture
def session_factory(session):
    factory = MagicMock()
    factory.return_value.__aenter__.return_value = session
    factory.return_value.__aexit__.return_value = False
    return factory


@pytest.fixture
def repo():
    repo = MagicMock()
    repo.lock_examination = AsyncMock()
    repo.add = AsyncMock(return_value=make_saved())
    repo.count_for_examination = AsyncMock(return_value=1)
    return repo


@pytest.fixture
def repo_factory(repo):
    return MagicMock(return_value=repo)


@pytest.fixture
def handler(predictor, session_factory, publisher, repo_factory):
    return PredictionEventHandler(predictor, session_factory, publisher, repo_factory)


async def test_predictor_receives_only_feature_fields(handler, predictor):
    await handler.handle(make_payload())

    # metadata (incl. examination_id, total_analyses_count, cluster_*, ...) is stripped
    predictor.predict.assert_called_once_with(FEATURES)


async def test_repository_is_built_from_the_open_session(
    handler, repo_factory, session_factory, session
):
    await handler.handle(make_payload())

    session_factory.assert_called_once_with()
    repo_factory.assert_called_once_with(session)


async def test_stores_new_analysis_built_from_payload_and_prediction(handler, repo):
    await handler.handle(make_payload())

    repo.add.assert_awaited_once_with(
        NewAnalysis(
            examination_id=EXAM,
            event_timestamp=10.5,
            result=1.0,
            confidence=0.9,
            total_analyses_count=3,
        )
    )


async def test_locks_before_add_and_count(handler, repo):
    calls = []
    repo.lock_examination.side_effect = lambda *_: calls.append("lock")
    repo.add.side_effect = lambda *_: calls.append("add") or make_saved()
    repo.count_for_examination.side_effect = lambda *_: calls.append("count") or 1

    await handler.handle(make_payload())

    assert calls == ["lock", "add", "count"]
    repo.lock_examination.assert_awaited_once_with(EXAM)
    repo.count_for_examination.assert_awaited_once_with(EXAM)


async def test_numeric_fields_are_coerced(handler, repo):
    await handler.handle(
        make_payload(examination_id=str(EXAM), event_time_s="2.5", total_analyses_count="4")
    )

    stored = repo.add.await_args.args[0]
    assert stored.examination_id == EXAM
    assert stored.event_timestamp == 2.5
    assert stored.total_analyses_count == 4


async def test_missing_probabilities_store_none_confidence(handler, predictor, repo):
    predictor.predict.return_value = {"prediction": [2.5]}

    await handler.handle(make_payload())

    stored = repo.add.await_args.args[0]
    assert stored.result == 2.5
    assert stored.confidence is None


async def test_no_completion_event_while_results_are_missing(handler, repo, publisher):
    repo.count_for_examination.return_value = 2

    await handler.handle(make_payload())

    publisher.publish.assert_not_awaited()


@pytest.mark.parametrize("received", [3, 4])
async def test_completion_event_published_when_received_reaches_total(
    handler, repo, publisher, received
):
    repo.count_for_examination.return_value = received

    await handler.handle(make_payload())

    publisher.publish.assert_awaited_once_with(
        "examination_completed",
        {"examination_id": EXAM, "total_analyses_count": 3},
    )


async def test_completion_uses_total_of_stored_row_not_of_current_payload(
    handler, repo, publisher
):
    # duplicate delivery: stored row says total=2, the new payload claims 3
    repo.add.return_value = make_saved(total=2)
    repo.count_for_examination.return_value = 2

    await handler.handle(make_payload(total_analyses_count=3))

    publisher.publish.assert_awaited_once_with(
        "examination_completed",
        {"examination_id": EXAM, "total_analyses_count": 2},
    )


async def test_completion_event_is_published_after_transaction_commits(
    handler, session, repo, publisher
):
    events = []
    session.begin.return_value.__aexit__.side_effect = (
        lambda *a: events.append("commit") or False
    )
    publisher.publish.side_effect = lambda *a, **k: events.append("publish")
    repo.count_for_examination.return_value = 3

    await handler.handle(make_payload())

    assert events == ["commit", "publish"]



@pytest.mark.parametrize("key", ["examination_id", "event_time_s", "total_analyses_count"])
@pytest.mark.parametrize("missing", ["absent", "none"])
async def test_missing_required_field_raises_and_has_no_side_effects(
    handler, predictor, session_factory, publisher, key, missing
):
    payload = make_payload()
    if missing == "absent":
        del payload[key]
    else:
        payload[key] = None

    with pytest.raises(ValueError, match=f"missing {key}"):
        await handler.handle(payload)

    predictor.predict.assert_not_called()
    session_factory.assert_not_called()
    publisher.publish.assert_not_awaited()


@pytest.mark.parametrize("bad_id", ["not-a-uuid", "bucket/path", ""])
async def test_invalid_examination_id_raises(
    handler, predictor, session_factory, publisher, bad_id
):
    with pytest.raises(ValueError):
        await handler.handle(make_payload(examination_id=bad_id))

    predictor.predict.assert_not_called()
    session_factory.assert_not_called()
    publisher.publish.assert_not_awaited()


@pytest.mark.parametrize(
    "overrides",
    [{"event_time_s": "abc"}, {"total_analyses_count": "many"}],
)
async def test_non_numeric_fields_raise_before_prediction(
    handler, predictor, session_factory, overrides
):
    with pytest.raises(ValueError):
        await handler.handle(make_payload(**overrides))

    predictor.predict.assert_not_called()
    session_factory.assert_not_called()


async def test_predictor_failure_propagates_without_touching_db(
    handler, predictor, session_factory, publisher
):
    predictor.predict.side_effect = RuntimeError("Inference failed")

    with pytest.raises(RuntimeError, match="Inference failed"):
        await handler.handle(make_payload())

    predictor.predict.assert_called_once_with(FEATURES)
    session_factory.assert_not_called()
    publisher.publish.assert_not_awaited()


async def test_lock_failure_propagates_and_nothing_is_stored_or_published(
    handler, repo, publisher
):
    repo.lock_examination.side_effect = ConnectionError("db down")

    with pytest.raises(ConnectionError):
        await handler.handle(make_payload())

    repo.add.assert_not_awaited()
    publisher.publish.assert_not_awaited()


async def test_repository_failure_propagates_and_nothing_is_published(
    handler, repo, publisher
):
    repo.add.side_effect = ConnectionError("db down")

    with pytest.raises(ConnectionError):
        await handler.handle(make_payload())

    publisher.publish.assert_not_awaited()


async def test_exception_inside_transaction_is_not_swallowed_by_session(
    handler, session, repo
):
    # the session context manager must see the exception (-> rollback)
    repo.add.side_effect = RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await handler.handle(make_payload())

    exc_type = session.begin.return_value.__aexit__.await_args.args[0]
    assert exc_type is RuntimeError


async def test_publisher_failure_propagates(handler, repo, publisher):
    repo.count_for_examination.return_value = 3
    publisher.publish.side_effect = ConnectionError("broker down")

    with pytest.raises(ConnectionError, match="broker down"):
        await handler.handle(make_payload())


@pytest.mark.parametrize(
    "result, expected",
    [
        ({"prediction": 1}, None),
        ({"prediction": 1, "probabilities": None}, None),
        ({"prediction": 1, "probabilities": []}, None),
        ({"prediction": 1, "probabilities": [[]]}, None),
        ({"prediction": 1, "probabilities": [[0.1, 0.9]]}, 0.9),
        ({"prediction": 1, "probabilities": [[0.3, 0.3, 0.4]]}, 0.4),
    ],
)
def test_extract_confidence(result, expected):
    assert PredictionEventHandler._extract_confidence(result) == expected


def test_extract_result_casts_prediction_to_float():
    assert PredictionEventHandler._extract_result({"prediction": ["2"]}) == 2.0


def test_extract_result_requires_prediction_key():
    with pytest.raises(KeyError):
        PredictionEventHandler._extract_result({})


def test_require_returns_value_even_if_falsy():
    assert PredictionEventHandler._require({"k": 0}, "k") == 0


def test_require_rejects_none():
    with pytest.raises(ValueError, match="missing k"):
        PredictionEventHandler._require({"k": None}, "k")

@pytest.mark.asyncio
async def test_handler_works_with_real_sklearn_predictor(
    session_factory, publisher, repo, repo_factory
):
    class Model:
        def predict(self, X):
            return np.array([1])
        def predict_proba(self, X):
            return np.array([[0.1, 0.9]])

    predictor = SklearnPredictor(feature_names=["feature_1", "feature_2"])
    predictor.model = Model()
    handler = PredictionEventHandler(
        predictor, session_factory, publisher, repo_factory
    )

    await handler.handle(make_payload())

    stored = repo.add.await_args.args[0]
    assert (stored.result, stored.confidence) == (1.0, 0.9)
