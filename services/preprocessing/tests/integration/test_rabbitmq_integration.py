from __future__ import annotations

import asyncio
import csv
import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock

from service.config import Settings
from service.rabbitmq import publish_combined_features


class _FakeConnection:
    def __init__(self, channel):
        self.channel_instance = channel
        self.closed = False

    async def channel(self):
        return self.channel_instance

    async def close(self):
        self.closed = True


def test_rabbitmq_publishes_one_json_message_per_csv_row(monkeypatch, tmp_path: Path) -> None:
    exchange = Mock()
    exchange.publish = AsyncMock()
    queue = Mock()
    queue.name = "features"
    channel = Mock()
    channel.declare_queue = AsyncMock(return_value=queue)
    channel.default_exchange = exchange
    connection = _FakeConnection(channel)
    monkeypatch.setattr(
        "service.rabbitmq.aio_pika.connect_robust",
        AsyncMock(return_value=connection),
    )

    csv_path = tmp_path / "combined_features.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["event_index", "alpha_power"])
        writer.writeheader()
        writer.writerows([
            {"event_index": 1, "alpha_power": 0.42},
            {"event_index": 2, "alpha_power": "nan"},
        ])

    settings = Settings(
        backend_url="http://mock-backend",
        backend_token="token",
        backend_timeout_seconds=2,
        rustfs_endpoint_url="http://mock-rustfs",
        rustfs_access_key_id="access",
        rustfs_secret_access_key="secret",
        rustfs_bucket="bucket",
        work_root=tmp_path,
        rabbitmq_queue="features",
        rabbitmq_routing_key="features",
    )

    assert publish_combined_features(settings, csv_path) == 2
    assert exchange.publish.await_count == 2
    assert json.loads(exchange.publish.await_args_list[0].args[0].body) == {
        "event_index": 1,
        "alpha_power": 0.42,
    }
    assert json.loads(exchange.publish.await_args_list[1].args[0].body) == {
        "event_index": 2,
        "alpha_power": None,
    }
    assert connection.closed is True
