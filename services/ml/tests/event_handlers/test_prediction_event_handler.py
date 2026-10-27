from unittest.mock import MagicMock

import pytest

from event_handlers.prediction_event_handler import PredictionEventHandler


@pytest.fixture
def mock_predictor():
    predictor = MagicMock()
    predictor.predict.return_value = {
        "prediction": [1], 
        "probabilities": [[0.1, 0.9]]
    }
    return predictor

@pytest.mark.asyncio
async def test_handle_success(mock_predictor):
    handler = PredictionEventHandler(predictor=mock_predictor)

    payload = {
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
        "feature_2": 1.2
    }

    await handler.handle(payload)

    expected_feature_payload = {
        "feature_1": 0.5,
        "feature_2": 1.2
    }

    mock_predictor.predict.assert_called_once_with(expected_feature_payload)


@pytest.mark.asyncio
async def test_handle_predictor_exception(mock_predictor):
    mock_predictor.predict.side_effect = RuntimeError("Inference failed")
    handler = PredictionEventHandler(predictor=mock_predictor)

    payload = {
        "experiment_id": "exp_123",
        "subject_id": "sub_456",
        "recording_id": "rec_789",
        "window_id": "win_001",
        "feature_1": 0.5
    }

    with pytest.raises(RuntimeError, match="Inference failed"):
        await handler.handle(payload)

    mock_predictor.predict.assert_called_once()