import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from aiormq.exceptions import ChannelAccessRefused
from botocore.exceptions import ClientError

import main
from service import health
from service.config import Settings


def mock_checks(monkeypatch, failed=None):
    def sync_check(name):
        def check(settings):
            if name == failed:
                raise ConnectionError("secret password must not escape")
        return check

    monkeypatch.setattr(health, "_check_rustfs", sync_check("rustfs"))
    monkeypatch.setattr(health, "_check_rabbitmq", AsyncMock(
        side_effect=ConnectionError("secret") if failed == "rabbitmq" else None
    ))


async def get(path):
    """Exercise the ASGI app without adding an HTTP client dependency."""
    messages = []

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        messages.append(message)

    await main.app({
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "GET", "scheme": "http", "path": path,
        "raw_path": path.encode(), "query_string": b"", "root_path": "",
        "headers": [], "server": ("test", 80), "client": ("test", 1234),
    }, receive, send)
    status = next(m["status"] for m in messages if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in messages)
    return status, json.loads(body)


@pytest.mark.parametrize("failed", [None, "rustfs", "rabbitmq"])
def test_connections_http_status_and_complete_results(monkeypatch, failed):
    mock_checks(monkeypatch, failed)
    status, body = asyncio.run(get("/health/connections"))
    assert status == (503 if failed else 200)
    assert body["status"] == ("degraded" if failed else "ok")
    assert set(body) == {"status", "connections"}
    assert set(body["connections"]) == {"rustfs", "rabbitmq"}
    for name, result in body["connections"].items():
        assert result["status"] == ("error" if name == failed else "ok")
        assert result["error"] == ("connection_failed" if name == failed else None)
        assert result["latency_ms"] >= 0
    assert "secret" not in json.dumps(body)


def test_timeout_keeps_other_results(monkeypatch):
    mock_checks(monkeypatch)
    monkeypatch.setattr(health, "CHECK_TIMEOUT_SECONDS", 0.02)

    async def hanging_check(settings):
        await asyncio.sleep(10)

    monkeypatch.setattr(health, "_check_rabbitmq", hanging_check)
    status, body = asyncio.run(get("/health/connections"))
    assert status == 503
    assert body["connections"]["rabbitmq"]["error"] == "timeout"
    assert body["connections"]["rustfs"]["status"] == "ok"


@pytest.mark.parametrize("error", [None, ChannelAccessRefused("secret")])
def test_rabbitmq_passive_queue_probe_closes_resources(monkeypatch, error):
    channel = MagicMock()
    channel.__aenter__ = AsyncMock(return_value=channel)
    channel.__aexit__ = AsyncMock(return_value=False)
    channel.declare_queue = AsyncMock(side_effect=error)
    connection = MagicMock()
    connection.__aenter__ = AsyncMock(return_value=connection)
    connection.__aexit__ = AsyncMock(return_value=False)
    connection.channel = AsyncMock(return_value=channel)
    connect = AsyncMock(return_value=connection)
    monkeypatch.setattr(health.aio_pika, "connect", connect)
    settings = Settings.from_environment()
    result = asyncio.run(health._measure(health._check_rabbitmq(settings)))
    assert result.error == ("access_denied" if error else None)
    connect.assert_awaited_once_with(settings.rabbitmq_url, timeout=3.0)
    channel.declare_queue.assert_awaited_once_with(
        settings.rabbitmq_queue, passive=True, timeout=3.0
    )
    channel.__aexit__.assert_awaited_once()
    connection.__aexit__.assert_awaited_once()


@pytest.mark.parametrize("error", [None, TimeoutError(), ClientError(
    {"ResponseMetadata": {"HTTPStatusCode": 403}}, "HeadBucket"
)])
def test_rustfs_checks_configured_bucket_without_retries(monkeypatch, error):
    # S3 clients expose close(), but do not implement a context manager.
    client = Mock(spec=["head_bucket", "close"])
    client.head_bucket.side_effect = error
    factory = MagicMock(return_value=client)
    monkeypatch.setattr(health.boto3, "client", factory)
    settings = Settings.from_environment()
    if error is None:
        health._check_rustfs(settings)
    else:
        with pytest.raises(type(error)) as raised:
            health._check_rustfs(settings)
        assert raised.value is error
    client.head_bucket.assert_called_once_with(Bucket=settings.rustfs_bucket)
    config = factory.call_args.kwargs["config"]
    assert config.retries == {"total_max_attempts": 1}
    assert config.connect_timeout == config.read_timeout == 3.0
    client.close.assert_called_once_with()


@pytest.mark.parametrize("error,code", [
    (TimeoutError(), "timeout"),
    (ClientError({"ResponseMetadata": {"HTTPStatusCode": 503}}, "HeadBucket"), "http_error"),
    (ClientError({"ResponseMetadata": {"HTTPStatusCode": 403}}, "HeadBucket"), "access_denied"),
    (ClientError({"ResponseMetadata": {"HTTPStatusCode": 404}}, "HeadBucket"), "bucket_not_found"),
    (health.aio_pika.exceptions.ChannelNotFoundEntity("secret"), "queue_not_found"),
])
def test_safe_error_codes(error, code):
    assert health._error_code(error) == code


def test_existing_health_does_not_probe_dependencies(monkeypatch):
    probe = AsyncMock(side_effect=AssertionError("Unexpected dependency check"))
    monkeypatch.setattr(main, "check_connections", probe)
    assert asyncio.run(get("/health")) == (200, {"status": "ok"})
    probe.assert_not_called()
