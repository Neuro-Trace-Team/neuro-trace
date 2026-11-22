from typing import Any, Protocol

class IEventPublisher(Protocol):
    async def publish(self, event_type: str, payload: dict[str, Any]) -> None: ...