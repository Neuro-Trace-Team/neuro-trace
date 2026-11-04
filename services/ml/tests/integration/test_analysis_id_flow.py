import asyncio
import json
from unittest.mock import Mock
from uuid import uuid4

import httpx
import pytest
import respx

from infrastructure.event_handlers.prediction_event_handler import PredictionEventHandler
from infrastructure.clients.backend_auth_client import BackendAuthClient
from infrastructure.clients.rest_result_publisher import RestResultPublisher


def test_analysis_uuid_reaches_backend_callback():
    analysis_id = str(uuid4())
    predictor = Mock()
    predictor.predict.return_value = {"predictions": [1], "probabilities": [[0.2, 0.8]]}
    publisher = RestResultPublisher("http://backend", BackendAuthClient("test-token"))
    handler = PredictionEventHandler(predictor, publisher)
    with respx.mock as router:
        callback = router.post(
            f"http://backend/api/v1/internal/analyses/{analysis_id}/result"
        ).mock(return_value=httpx.Response(200, json={}))
        asyncio.run(handler.handle({"analysis_id": analysis_id, "alpha_power": 0.42}))
        assert callback.call_count == 1
        request = callback.calls[0].request
        assert request.headers["Authorization"] == "Bearer test-token"
        assert json.loads(request.content) == {
            "result": predictor.predict.return_value, "confidence": 0.8
        }
    predictor.predict.assert_called_once_with({"alpha_power": 0.42})


@pytest.mark.parametrize("analysis_id", [None, "bucket/path", "invalid"])
def test_invalid_analysis_uuid_is_not_predicted_or_published(analysis_id):
    predictor, publisher = Mock(), Mock()
    handler = PredictionEventHandler(predictor, publisher)
    with pytest.raises(ValueError):
        asyncio.run(handler.handle({"analysis_id": analysis_id, "alpha_power": 0.42}))
    predictor.predict.assert_not_called()
    publisher.publish_result.assert_not_called()
