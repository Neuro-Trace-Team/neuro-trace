from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import pytest
import respx

from infrastructure.clients.rest_result_publisher import RestResultPublisher


@pytest.fixture
def mock_auth_client():
    auth_client = MagicMock()
    auth_client.get_token = AsyncMock(return_value="valid_service_token")
    auth_client.invalidate_token = AsyncMock()
    return auth_client


@pytest.mark.asyncio
@respx.mock
async def test_publish_result_posts_to_analysis_callback(mock_auth_client):
    base_url = "http://backend-api"
    analysis_id = str(uuid4())
    target_url = f"{base_url}/api/v1/internal/analyses/{analysis_id}/result"
    payload = {"result": {"prediction": [1]}, "confidence": 0.9}
    route = respx.post(target_url).respond(status_code=200)

    publisher = RestResultPublisher(base_url, mock_auth_client)
    await publisher.publish_result(analysis_id, payload)

    assert route.called
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer valid_service_token"
    assert request.read() == httpx.Request("POST", target_url, json=payload).read()
    mock_auth_client.get_token.assert_awaited_once()


@pytest.mark.asyncio
@respx.mock
async def test_publish_result_propagates_401_without_token_refresh(mock_auth_client):
    analysis_id = str(uuid4())
    route = respx.post(
        f"http://backend-api/api/v1/internal/analyses/{analysis_id}/result"
    ).respond(status_code=401, text="Unauthorized")
    publisher = RestResultPublisher("http://backend-api", mock_auth_client)

    with pytest.raises(httpx.HTTPStatusError):
        await publisher.publish_result(analysis_id, {"result": {"prediction": [1]}})

    assert route.call_count == 1
    mock_auth_client.invalidate_token.assert_not_awaited()


@pytest.mark.asyncio
@respx.mock
async def test_publish_result_fails_on_500(mock_auth_client):
    analysis_id = str(uuid4())
    route = respx.post(
        f"http://backend-api/api/v1/internal/analyses/{analysis_id}/result"
    ).respond(status_code=500, text="Internal Server Error")
    publisher = RestResultPublisher("http://backend-api", mock_auth_client)

    with pytest.raises(httpx.HTTPStatusError):
        await publisher.publish_result(analysis_id, {"result": {"prediction": [1]}})

    assert route.call_count == 1
    mock_auth_client.invalidate_token.assert_not_awaited()
