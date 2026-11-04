"""Shared setup for local integration tests using mocked dependencies."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

SERVICE_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = SERVICE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


try:
    import aio_pika  # noqa: F401
except ModuleNotFoundError:
    # The broker is mocked in these tests, so the runtime client library is
    # not needed merely to import the adapter modules.
    aio_pika_stub = types.ModuleType("aio_pika")

    class _DeliveryMode:
        PERSISTENT = 2

    class _ExchangeType:
        TOPIC = "topic"

    class _Message:
        def __init__(self, body, **kwargs):
            self.body = body
            self.__dict__.update(kwargs)

    async def _connect_robust(*args, **kwargs):
        raise RuntimeError("connect_robust must be mocked by the test")

    aio_pika_stub.DeliveryMode = _DeliveryMode
    aio_pika_stub.ExchangeType = _ExchangeType
    aio_pika_stub.Message = _Message
    aio_pika_stub.connect_robust = _connect_robust
    sys.modules["aio_pika"] = aio_pika_stub


@pytest.fixture
def backend_client(tmp_path):
    from service.config import Settings
    from service.jobs import NeuroTraceClient

    return NeuroTraceClient(
        Settings(
            backend_url="http://mock-backend",
            backend_token="mock-service-token",
            backend_timeout_seconds=2,
            rustfs_endpoint_url="http://mock-rustfs",
            rustfs_access_key_id="access",
            rustfs_secret_access_key="secret",
            rustfs_bucket="examinations",
            work_root=tmp_path,
        )
    )
