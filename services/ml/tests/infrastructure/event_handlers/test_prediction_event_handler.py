from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from infrastructure.event_handlers.prediction_event_handler import PredictionEventHandler


@pytest.fixture
def mock_predictor():
    predictor = MagicMock()
    predictor.predict.return_value = {
        "prediction": [1],
        "probabilities": [[0.1, 0.9]],
    }
    return predictor


@pytest.fixture
def mock_result_publisher():
    publisher = MagicMock()
    publisher.publish_result = AsyncMock()
    return publisher


@pytest.mark.asyncio
async def test_handle_success(mock_predictor, mock_result_publisher):
    analysis_id = str(uuid4())
    handler = PredictionEventHandler(mock_predictor, mock_result_publisher)
    payload = {
        "analysis_id": analysis_id,
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
        "feature_1": 0.5,
        "feature_2": 1.2,
    }

    await handler.handle(payload)

    mock_predictor.predict.assert_called_once_with({
        "feature_1": 0.5,
        "feature_2": 1.2,
    })
    mock_result_publisher.publish_result.assert_awaited_once_with(
        analysis_id,
        {
            "result": mock_predictor.predict.return_value,
            "confidence": 0.9,
        },
    )


@pytest.mark.asyncio
async def test_handle_rejects_missing_analysis_id(mock_predictor, mock_result_publisher):
    handler = PredictionEventHandler(mock_predictor, mock_result_publisher)

    with pytest.raises(ValueError, match="missing analysis_id"):
        await handler.handle({"feature_1": 0.5})

    mock_predictor.predict.assert_not_called()
    mock_result_publisher.publish_result.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_rejects_invalid_analysis_id(mock_predictor, mock_result_publisher):
    handler = PredictionEventHandler(mock_predictor, mock_result_publisher)

    with pytest.raises(ValueError):
        await handler.handle({"analysis_id": "bucket/path", "feature_1": 0.5})

    mock_predictor.predict.assert_not_called()
    mock_result_publisher.publish_result.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_predictor_exception(mock_predictor, mock_result_publisher):
    mock_predictor.predict.side_effect = RuntimeError("Inference failed")
    handler = PredictionEventHandler(mock_predictor, mock_result_publisher)

    with pytest.raises(RuntimeError, match="Inference failed"):
        await handler.handle({"analysis_id": str(uuid4()), "feature_1": 0.5})

    mock_predictor.predict.assert_called_once_with({"feature_1": 0.5})
    mock_result_publisher.publish_result.assert_not_awaited()
