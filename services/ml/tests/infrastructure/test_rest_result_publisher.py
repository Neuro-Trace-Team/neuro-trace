from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import respx

from infrastructure.rest_result_publisher import RestResultPublisher


@pytest.fixture
def mock_auth_client():
    auth_client = MagicMock()
    auth_client.get_token = AsyncMock(return_value="valid_token_xyz")
    auth_client.invalidate_token = AsyncMock()
    return auth_client

@pytest.mark.asyncio
@respx.mock
async def test_publish_result_success(mock_auth_client):
    base_url = "http://backend-api"
    examination_id = "exam_789"
    target_url = f"{base_url}/api/v1/examinations/{examination_id}/results"

    route = respx.post(target_url).respond(status_code=200)

    publisher = RestResultPublisher(base_url=base_url, auth_client=mock_auth_client)
    payload = {
        "prediction": [1]
    }

    await publisher.publish_result(examination_id, payload)

    assert route.called
    assert route.calls.last.request.headers["Authorization"] == "Bearer valid_token_xyz"

@pytest.mark.asyncio
@respx.mock
async def test_publish_result_retry_on_401(mock_auth_client):
    base_url = "http://backend-api"
    examination_id = "exam_789"
    target_url = f"{base_url}/api/v1/examinations/{examination_id}/results"

    route = respx.post(target_url)
    route.side_effect = [
        httpx.Response(401, text="Token expired"),
        httpx.Response(200)
    ]

    publisher = RestResultPublisher(base_url=base_url, auth_client=mock_auth_client)
    payload = {
        "prediction": [1]
    }

    await publisher.publish_result(examination_id, payload)

    mock_auth_client.invalidate_token.assert_awaited_once()
    assert route.call_count == 2

@pytest.mark.asyncio
@respx.mock
async def test_publish_result_fails_on_500(mock_auth_client):
    base_url = "http://backend-api"
    examination_id = "exam_789"
    target_url = f"{base_url}/api/v1/examinations/{examination_id}/results"

    respx.post(target_url).respond(status_code=500, text="Internal Server Error")

    publisher = RestResultPublisher(base_url=base_url, auth_client=mock_auth_client)
    payload = {
        "prediction": [1]
    }

    with pytest.raises(httpx.HTTPStatusError):
        await publisher.publish_result(examination_id, payload)

    mock_auth_client.invalidate_token.assert_not_awaited()