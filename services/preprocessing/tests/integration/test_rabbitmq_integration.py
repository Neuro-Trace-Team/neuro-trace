from __future__ import annotations

import csv
import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import UUID

import pytest

import pytest

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


@pytest.mark.parametrize("metadata_columns", [False, True])
def test_rabbitmq_publishes_one_json_message_per_csv_row(monkeypatch, tmp_path: Path, metadata_columns) -> None:
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

    if metadata_columns:
        csv_path.write_text(
            "event_index,examination_id,analysis_id,alpha_power,total_analyses_count\n"
            "1,untrusted-examination,untrusted-analysis,0.42,999\n"
            "2,untrusted-examination,untrusted-analysis,nan,999\n"
        )

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

    examination_id = "86b0602a-1452-440b-aeef-6c6c39fdf29b"
    original_csv = csv_path.read_bytes()
    assert publish_combined_features(settings, csv_path, examination_id=examination_id) == 2
    assert exchange.publish.await_count == 2
    messages = [json.loads(call.args[0].body) for call in exchange.publish.await_args_list]
    for message in messages:
        assert list(message)[:2] == ["examination_id", "total_analyses_count"]
        assert message["examination_id"] == examination_id
        assert "analysis_id" not in message
        assert message["total_analyses_count"] == 2
        assert type(message["total_analyses_count"]) is int
    assert messages[0]["event_index"] == 1
    assert messages[0]["alpha_power"] == 0.42
    assert messages[1]["event_index"] == 2
    assert messages[1]["alpha_power"] is None
    assert connection.closed is True

    exchange.publish.reset_mock()
    publish_combined_features(settings, csv_path, examination_id=examination_id)
    assert [json.loads(call.args[0].body) for call in exchange.publish.await_args_list] == messages
    assert csv_path.read_bytes() == original_csv

    exchange.publish.reset_mock()
    publish_combined_features(settings, csv_path, examination_id="13b5b2e5-078b-447d-a6d8-6e18330d105a")
    other_messages = [json.loads(call.args[0].body) for call in exchange.publish.await_args_list]
    assert other_messages == [
        {**message, "examination_id": "13b5b2e5-078b-447d-a6d8-6e18330d105a"}
        for message in messages
    ]
