import httpx
import pytest
import respx

from infrastructure.rest_result_publisher import RestResultPublisher

@pytest.mark.asyncio
@respx.mock
async def test_publish_result_success():
    target_url = "http://backend-service/api/predictions"
    route = respx.post(target_url).respond(status_code=200)

    publisher = RestResultPublisher(target_url=target_url)
    payload = {
        "experiment_id": "exp_1", 
        "prediction_result": {"prediction": [1]}
    }

    await publisher.publish_result(payload)

    assert route.called

    request_content = route.calls.last.request.read()
    assert b"exp_1" in request_content

@pytest.mark.asyncio
@respx.mock
async def test_publish_result_http_error():
    target_url = "http://backend-service/api/predictions"
    respx.post(target_url).respond(status_code=500)

    publisher = RestResultPublisher(target_url=target_url)
    payload = {"experiment_id": "exp_1"}

    with pytest.raises(httpx.HTTPStatusError):
        await publisher.publish_result(payload)