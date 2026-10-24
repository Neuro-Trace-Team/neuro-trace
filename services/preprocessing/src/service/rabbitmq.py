from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import aio_pika
from aio_pika import DeliveryMode, Message

from service.config import Settings


def _json_safe(value: Any) -> Any:
    """Convert values from a CSV row to values accepted by strict JSON."""
    if value is None:
        return None
    if isinstance(value, float) and (
        value != value or value in (float("inf"), float("-inf"))
    ):
        return None
    if hasattr(value, "item"):
        return _json_safe(value.item())
    return value


def _read_rows(csv_path: Path) -> list[dict[str, Any]]:
    # pandas is already a runtime dependency of the preprocessing pipeline and
    # preserves the numeric types of the feature columns for consumers.
    import pandas as pd

    frame = pd.read_csv(csv_path)
    return [
        {column: _json_safe(value) for column, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


async def _publish_rows(settings: Settings, rows: list[dict[str, Any]]) -> int:
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    try:
        channel = await connection.channel()
        queue = await channel.declare_queue(settings.rabbitmq_queue, durable=True)
        for row in rows:
            body = json.dumps(row, ensure_ascii=False, allow_nan=False).encode("utf-8")
            await channel.default_exchange.publish(
                Message(
                    body=body,
                    content_type="application/json",
                    delivery_mode=DeliveryMode.PERSISTENT,
                ),
                routing_key=queue.name,
            )
        return len(rows)
    finally:
        await connection.close()


def publish_combined_features(settings: Settings, csv_path: str | Path) -> int:
    """Publish every row of combined_features.csv as one JSON message."""
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(f"Combined features file not found: {path}")
    rows = _read_rows(path)
    return asyncio.run(_publish_rows(settings, rows))
