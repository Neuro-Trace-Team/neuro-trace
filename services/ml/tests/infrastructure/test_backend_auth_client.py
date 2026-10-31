import httpx
from infrastructure.backend_auth_client import BackendAuthClient
import pytest
import respx


@pytest.mark.asyncio
@respx.mock
async def test_get_token_success_and_cache():
    base_url = "http://backend-api"
    login_url = f"{base_url}/api/v1/auth/login"

    route = respx.post(login_url).respond(
        status_code=200, 
        json={"access_token": "mock_jwt_token_123"}
    )

    client = BackendAuthClient(base_url=base_url, email="test@test.com", password="password")

    token1 = await client.get_token()
    assert token1 == "mock_jwt_token_123"
    assert route.call_count == 1

    token2 = await client.get_token()
    assert token2 == "mock_jwt_token_123"
    assert route.call_count == 1

@pytest.mark.asyncio
@respx.mock
async def test_get_token_http_error():
    base_url = "http://backend-api"
    login_url = f"{base_url}/api/v1/auth/login"

    respx.post(login_url).respond(status_code=401, text="Unauthorized")

    client = BackendAuthClient(base_url=base_url, email="test@test.com", password="wrong")

    with pytest.raises(httpx.HTTPStatusError):
        await client.get_token()

@pytest.mark.asyncio
async def test_invalidate_token():
    client = BackendAuthClient(base_url="http://backend-api", email="a@b.com", password="123")
    client._access_token = "cached_token_abc"

    await client.invalidate_token()
    assert client._access_token is None
