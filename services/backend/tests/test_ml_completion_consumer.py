import asyncio
import json
from unittest.mock import MagicMock
from uuid import uuid4

from src.messaging.ml_completion_consumer import MLCompletionConsumer


class Message:
    def __init__(self, payload: dict):
        self.body = json.dumps(payload).encode("utf-8")
        self.acked = self.rejected = self.nacked = False

    async def ack(self): self.acked = True
    async def reject(self, *, requeue): self.rejected = True
    async def nack(self, *, requeue): self.nacked = True


def test_completion_event_marks_examination_ready(monkeypatch):
    examination_id = uuid4()
    marked = []
    monkeypatch.setattr("src.messaging.ml_completion_consumer.mark_examination_ready", lambda session, value: marked.append(value) or True)
    consumer = MLCompletionConsumer(queue_url="amqp://test", queue_name="completed", session_factory=MagicMock(return_value=MagicMock()))
    message = Message({"event_type": "examination_completed", "examination_id": str(examination_id), "total_analyses_count": 3})
    asyncio.run(consumer._dispatch_message(message))
    assert marked == [examination_id]
    assert message.acked and not message.rejected and not message.nacked


def test_invalid_completion_event_is_rejected(monkeypatch):
    consumer = MLCompletionConsumer(queue_url="amqp://test", queue_name="completed", session_factory=MagicMock())
    message = Message({"event_type": "unexpected", "examination_id": str(uuid4())})
    asyncio.run(consumer._dispatch_message(message))
    assert message.rejected and not message.acked
