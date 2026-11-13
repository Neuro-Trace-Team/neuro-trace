"""Read-only dependency probes, isolated from pipeline clients and their timeouts."""

import asyncio
from time import perf_counter
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import aio_pika
import boto3
from aiormq.exceptions import ChannelAccessRefused
from botocore.config import Config
from botocore.exceptions import ClientError, ConnectTimeoutError, ReadTimeoutError
from pydantic import BaseModel

from service.config import Settings


CHECK_TIMEOUT_SECONDS = 3.0


class ConnectionResult(BaseModel):
    status: Literal["ok", "error"]
    latency_ms: float
    error: str | None = None


class ConnectionsResponse(BaseModel):
    status: Literal["ok", "degraded"]
    dependencies: dict[str, ConnectionResult]


def _check_rustfs(settings: Settings) -> None:
    client = boto3.client(
        "s3",
        endpoint_url=settings.rustfs_endpoint_url,
        aws_access_key_id=settings.rustfs_access_key_id,
        aws_secret_access_key=settings.rustfs_secret_access_key,
        config=Config(
            s3={"addressing_style": "path"},
            connect_timeout=CHECK_TIMEOUT_SECONDS,
            read_timeout=CHECK_TIMEOUT_SECONDS,
            retries={"total_max_attempts": 1},
        ),
    )
    try:
        client.head_bucket(Bucket=settings.rustfs_bucket)
    finally:
        client.close()


async def _check_rabbitmq(settings: Settings) -> None:
    connection = await aio_pika.connect(
        settings.rabbitmq_url, timeout=CHECK_TIMEOUT_SECONDS
    )
    async with connection:
        async with await connection.channel() as channel:
            await channel.declare_queue(
                settings.rabbitmq_queue, passive=True, timeout=CHECK_TIMEOUT_SECONDS
            )


def _check_backend(settings: Settings) -> None:
    with urlopen(
        f"{settings.backend_url}/health/live", timeout=CHECK_TIMEOUT_SECONDS
    ) as response:
        if response.status != 200:
            raise HTTPError(response.url, response.status, "Health check failed", {}, None)


def _error_code(error: Exception) -> str:
    if isinstance(error, (TimeoutError, ConnectTimeoutError, ReadTimeoutError)):
        return "timeout"
    if isinstance(error, URLError) and isinstance(error.reason, TimeoutError):
        return "timeout"
    if isinstance(error, HTTPError):
        return "access_denied" if error.code in (401, 403) else "http_error"
    if isinstance(error, ClientError):
        status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if status in (401, 403):
            return "access_denied"
        if status == 404:
            return "bucket_not_found"
        return "http_error"
    if isinstance(error, aio_pika.exceptions.ChannelNotFoundEntity):
        return "queue_not_found"
    if isinstance(error, (
        aio_pika.exceptions.AuthenticationError,
        aio_pika.exceptions.ProbableAuthenticationError,
        ChannelAccessRefused,
    )) or getattr(error, "reply_code", None) == 403:
        return "access_denied"
    return "connection_failed"


async def _measure(check) -> ConnectionResult:
    start = perf_counter()
    error = None
    try:
        await asyncio.wait_for(check, timeout=CHECK_TIMEOUT_SECONDS)
    except Exception as exc:
        error = _error_code(exc)
    return ConnectionResult(
        status="ok" if error is None else "error",
        latency_ms=round((perf_counter() - start) * 1000, 2),
        error=error,
    )


async def check_connections(settings: Settings) -> ConnectionsResponse:
    results = await asyncio.gather(
        _measure(asyncio.to_thread(_check_rustfs, settings)),
        _measure(_check_rabbitmq(settings)),
        _measure(asyncio.to_thread(_check_backend, settings)),
    )
    dependencies = dict(zip(("rustfs", "rabbitmq", "backend"), results))
    return ConnectionsResponse(
        status="ok" if all(result.status == "ok" for result in results) else "degraded",
        dependencies=dependencies,
    )
