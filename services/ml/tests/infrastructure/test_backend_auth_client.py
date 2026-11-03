import pytest

from infrastructure.backend_auth_client import BackendAuthClient


@pytest.mark.asyncio
async def test_get_token_returns_configured_service_token():
    client = BackendAuthClient("  mock_service_jwt  ")

    assert await client.get_token() == "mock_service_jwt"
    assert await client.get_token() == "mock_service_jwt"


@pytest.mark.asyncio
async def test_get_token_rejects_missing_service_token():
    client = BackendAuthClient(" ")

    with pytest.raises(RuntimeError, match="ML_SERVICE_TOKEN is not configured"):
        await client.get_token()


@pytest.mark.asyncio
async def test_invalidate_token_is_noop_for_static_token():
    client = BackendAuthClient("static_service_token")

    await client.invalidate_token()

    assert await client.get_token() == "static_service_token"
