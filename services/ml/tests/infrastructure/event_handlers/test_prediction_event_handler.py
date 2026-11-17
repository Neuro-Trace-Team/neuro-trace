import logging
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

from domain.services.ipredictor import FeatureValidationError
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
    return Analysis(
        analysis_id=1,
        examination_id=EXAM,
        event_timestamp=10.5,
        result=1.0,
        confidence=0.9,
        total_analyses_count=total,
        is_valid=True,
        invalid_reason=None
    )


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


def stored(mock_repo):
    return mock_repo.add.await_args.args[0]


class Model:
    def predict(self, X):
        return np.array([1])
    def predict_proba(self, X):
        return np.array([[0.1, 0.9]])


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
            is_valid=True,
            invalid_reason=None
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

    s = stored(repo)
    assert s.examination_id == EXAM
    assert s.event_timestamp == 2.5
    assert s.total_analyses_count == 4


async def test_missing_probabilities_store_none_confidence(handler, predictor, repo):
    predictor.predict.return_value = {"prediction": [2.5]}

    await handler.handle(make_payload())

    s = stored(repo)
    assert s.result == 2.5
    assert s.confidence is None


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
    [
        {"event_time_s": "abc"}, {"total_analyses_count": "many"}, {"event_time_s": -1.0}, 
        {"event_time_s": float("nan")}, {"event_time_s": float("inf")}, 
        {"total_analyses_count": 0},
    ],
)
async def test_non_numeric_fields_raise_before_prediction(
    handler, predictor, session_factory, overrides
):
    with pytest.raises(ValueError):
        await handler.handle(make_payload(**overrides))

    predictor.predict.assert_not_called()
    session_factory.assert_not_called()


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
    repo.add.side_effect = RuntimeError("error")

    with pytest.raises(RuntimeError, match="error"):
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


def test_require_returns_value_even_if_falsy():
    assert PredictionEventHandler._require({"k": 0}, "k") == 0


def test_require_rejects_none():
    with pytest.raises(ValueError, match="missing k"):
        PredictionEventHandler._require({"k": None}, "k")


@pytest.mark.asyncio
async def test_handler_works_with_real_sklearn_predictor(
    session_factory, publisher, repo, repo_factory
):
    predictor = SklearnPredictor(feature_names=["feature_1", "feature_2"])
    predictor.model = Model()
    handler = PredictionEventHandler(
        predictor, session_factory, publisher, repo_factory
    )

    await handler.handle(make_payload())

    s = stored(repo)
    assert (s.result, s.confidence) == (1.0, 0.9)


@pytest.mark.asyncio
async def test_feature_validation_error_is_stored_as_invalid_analysis(handler, predictor, repo):
    predictor.predict.side_effect = FeatureValidationError("bad", invalid=["feature_1"])

    await handler.handle(make_payload())

    s = stored(repo)
    assert (s.is_valid, s.result, s.confidence) == (False, None, None)
    assert s.invalid_reason == "invalid_feature_values: feature_1"


async def test_conflicting_duplicate_is_logged_and_stored_row_wins(handler, repo, publisher, caplog):
    repo.add.return_value = make_saved(total=2)
    repo.count_for_examination.return_value = 2

    with caplog.at_level(logging.WARNING):
        await handler.handle(make_payload(total_analyses_count=3))

    assert "Conflicting duplicate" in caplog.text
    publisher.publish.assert_awaited_once_with(
        "examination_completed", {"examination_id": EXAM, "total_analyses_count": 2}
    )


@pytest.mark.asyncio
async def test_invalid_analysis_still_counts_toward_completion(
    handler, predictor, repo, publisher
):
    predictor.predict.side_effect = FeatureValidationError("bad", missing=["f"])
    repo.count_for_examination.return_value = 3

    await handler.handle(make_payload())

    publisher.publish.assert_awaited_once()


@pytest.mark.asyncio
async def test_unexpected_predictor_failure_becomes_invalid_analysis(handler, predictor, repo, caplog):
    predictor.predict.side_effect = RuntimeError("model broke")

    with caplog.at_level(logging.ERROR):
        await handler.handle(make_payload())

    assert stored(repo).invalid_reason == "prediction_failed"
    assert "model broke" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("prediction, reason", [
    ({"prediction": [10.01]}, "result_out_of_range"),
    ({"prediction": [-0.01]}, "result_out_of_range"),
    ({"prediction": [float("nan")]}, "result_out_of_range"),
    ({"prediction": [float("inf")]}, "result_out_of_range"),
    ({}, "unusable_model_output"),
    ({"prediction": []}, "unusable_model_output"),
    ({"prediction": ["abc"]}, "unusable_model_output"),
])
async def test_unusable_or_out_of_range_output_is_invalid(handler, predictor, repo, prediction, reason):
    predictor.predict.return_value = prediction

    await handler.handle(make_payload())

    s = stored(repo)
    assert s.is_valid is False and s.result is None
    assert s.invalid_reason.startswith(reason)


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [0.0, 10.0])
async def test_range_boundaries_are_valid(handler, predictor, repo, value):
    predictor.predict.return_value = {"prediction": [value], "probabilities": [[0.1, 0.9]]}

    await handler.handle(make_payload())

    assert (stored(repo).is_valid, stored(repo).result) == (True, value)


@pytest.mark.asyncio
@pytest.mark.parametrize("confidence", [1.01, -0.1, float("nan")])
async def test_out_of_range_confidence_is_dropped_but_result_kept(handler, predictor, repo, confidence):
    predictor.predict.return_value = {"prediction": [1.0], "probabilities": [[confidence]]}

    await handler.handle(make_payload())

    s = stored(repo)
    assert (s.is_valid, s.result, s.confidence) == (True, 1.0, None)

	
@pytest.mark.asyncio
@pytest.mark.parametrize("mutate, expected_reason", [
    (lambda p: p.update(feature_1=None), "invalid_feature_values: feature_1"),
    (lambda p: p.update(feature_1=float("nan")), "invalid_feature_values: feature_1"),
    (lambda p: p.pop("feature_2"), "missing_features: feature_2"),
])
async def test_real_predictor_turns_null_or_missing_features_into_invalid_analysis(
    session_factory, publisher, repo, repo_factory, mutate, expected_reason
):
    predictor = SklearnPredictor(feature_names=["feature_1", "feature_2"])
    predictor.model = Model()
    handler = PredictionEventHandler(predictor, session_factory, publisher, repo_factory)
    payload = make_payload()
    mutate(payload)

    await handler.handle(payload)

    s = stored(repo)
    assert (s.is_valid, s.invalid_reason) == (False, expected_reason)